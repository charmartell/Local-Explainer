import hashlib
import ipaddress
import json
import re
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from .store import digest, write_json, now

SKIP = {'.git','node_modules','dist','build','.next','.venv','venv','__pycache__','.wrangler','.vinext','outputs','test-results','target','vendor','.codex-artifacts'}
TEXT = {'.md','.txt','.rst','.py','.ts','.tsx','.js','.jsx','.json','.toml','.yaml','.yml','.sql','.dart','.rs','.go','.cs','.java','.c','.cpp','.h','.css','.html','.xml','.sh','.ps1'}
PRIMARY_DOMAINS={'python.org','developer.mozilla.org','w3.org','whatwg.org','microsoft.com','docs.rs','rust-lang.org','go.dev','docker.com','github.com','git-scm.com','sqlite.org','postgresql.org','mysql.com','cloudflare.com','kubernetes.io','react.dev','nextjs.org','vite.dev','tailwindcss.com','tiangolo.com','pytorch.org','tensorflow.org','arxiv.org','openreview.net','aclanthology.org','numpy.org','scipy.org','pandas.pydata.org','scikit-learn.org','ietf.org','rfc-editor.org','nasa.gov','nist.gov','openai.com'}

def primary_reference(url):
    host=(urlparse(url).hostname or '').lower()
    return any(host==domain or host.endswith('.'+domain) for domain in PRIMARY_DOMAINS)

def public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username: raise ValueError('Only public HTTP(S) source URLs are supported')
    for result in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80)):
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global: raise ValueError('Research URLs must use public addresses')
    return url

def fetch(url, config, offline=False):
    cache = config.assets/'References'/f'{hashlib.sha256(url.encode()).hexdigest()}.json'
    if offline:
        if not cache.exists(): raise ValueError(f'Offline source unavailable: {url}. Fetch it in research mode first or provide a local copy.')
        return json.loads(cache.read_text(encoding='utf-8'))
    original = url
    with httpx.Client(timeout=35, headers={'User-Agent':'LocalExplainer/0.1'}, trust_env=False) as client:
        for _ in range(6):
            public_url(url)
            with client.stream('GET', url) as response:
                if response.is_redirect:
                    url = str(response.url.join(response.headers['location'])); continue
                response.raise_for_status()
                body = bytearray()
                for block in response.iter_bytes():
                    body.extend(block)
                    if len(body) > 5_000_000: raise ValueError('Source exceeds 5 MB fetch limit; download it explicitly')
                html = body.decode('utf-8', errors='replace')
                break
        else: raise ValueError('Too many redirects')
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else original
    for tag in soup(['script','style','nav','header','footer']): tag.decompose()
    text = (soup.find('main') or soup.find('article') or soup).get_text('\n', strip=True)
    record = {'title':title,'origin':original,'resolved_url':url,'fetched':now(),'text':text[:150000],'hash':digest(bytes(body))}
    write_json(cache, record)
    return record

def discover(topic, config):
    if config.search_url:
        public_url(config.search_url)
        result = httpx.get(config.search_url, params={'q':topic+' official documentation','format':'json'}, timeout=25).json()
        candidates=[x['url'] for x in result.get('results',[])]
    else:
        from ddgs import DDGS
        results = list(DDGS(timeout=15).text(topic+' official documentation', max_results=10))
        candidates=[x['href'] for x in results]
    primary=list(dict.fromkeys(url for url in candidates if primary_reference(url)))[:5]
    if not primary: raise ValueError('No recognized primary sources found. Supply the author\'s documentation URLs explicitly.')
    return primary

def safe_file(path, root):
    relative = path.relative_to(root)
    lower = path.name.lower()
    return not any(p in SKIP for p in relative.parts) and not path.is_symlink() and not (lower.startswith('.env') or any(x in lower for x in ('credentials','secret','private-key')) or path.suffix.lower() in {'.pem','.key','.pfx'})

def collect(request, config, checkpoint=lambda:None,describe_image=None):
    sources, evidence, gaps = [], [], []
    def add(title, origin, text, kind='document', meta=None):
        source_id = 'source_' + digest(origin.encode())[:12]
        sources.append({'id':source_id,'title':title,'origin':origin,'kind':kind,'hash':digest(text.encode()),**(meta or {})})
        lines = text.splitlines()
        for start in range(0,len(lines),48):
            part = '\n'.join(lines[start:start+48])
            if not part.strip(): continue
            evidence.append({'id': 'ev_'+digest((source_id+str(start)).encode())[:12], 'source_id':source_id,'title':title,'kind':kind,'start_line':start+1,'end_line':min(start+48,len(lines)),'text':part})
    for raw in request.get('inputs',[]):
        checkpoint()
        if raw.startswith(('http://','https://')):
            record = fetch(raw,config,request['mode']=='offline')
            add(record['title'], raw, record['text'],meta={'fetched':record['fetched']})
            continue
        path = Path(raw).expanduser().resolve()
        if not path.exists(): raise ValueError(f'Input does not exist: {raw}')
        if path.is_dir():
            try:
                commit = subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'], stderr=subprocess.DEVNULL,text=True).strip()
                names = subprocess.check_output(['git','-C',str(path),'ls-files','-z'],stderr=subprocess.DEVNULL).decode().split('\0')
                files = [path/name for name in names if name]
            except subprocess.CalledProcessError:
                commit = None; files = list(path.rglob('*'))
            # Prioritize documentation, entrypoints, schemas, and routes; retain file inventory for later retrieval.
            def rank(file):
                name = file.name.lower()
                return (0 if name.startswith(('readme','architecture')) else 1 if name in ('package.json','schema.ts','main.py','index.ts','page.tsx','route.ts') else 2 if file.suffix=='.md' else 3, len(str(file)))
            files = [f for f in files if f.is_file() and safe_file(f,path) and f.suffix.lower() in TEXT and f.stat().st_size < 400000]
            inventory = [{'path':str(f.relative_to(path)),'hash':hashlib.sha256(f.read_bytes()).hexdigest()} for f in files[:1000]]
            total = 0
            for file in sorted(files,key=rank):
                checkpoint()
                text = file.read_text(encoding='utf-8',errors='replace')
                if total > 500000: break
                add(str(file.relative_to(path)),str(file),text,'code' if file.suffix.lower() not in {'.md','.txt','.rst'} else 'document',{'commit':commit,'repository':str(path)})
                total += len(text)
            sources.append({'id':'inventory_'+digest(str(path).encode())[:12],'title':'Repository inventory','origin':str(path),'kind':'inventory','commit':commit,'files':inventory})
        elif path.suffix.lower()=='.pdf':
            for i,page in enumerate(PdfReader(path).pages):
                text=page.extract_text() or ''
                if text.strip(): add(f'{path.name}, page {i+1}',f'{path}#page={i+1}',text,meta={'page':i+1})
            if not any(s['origin'].startswith(str(path)) for s in sources): gaps.append(f'{path.name} contains no extractable text; provide text or an OCR export.')
        elif path.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:
            if describe_image:
                description=describe_image(path,checkpoint)
                add(path.name,str(path),'Local visual-model observation of the supplied image. Interpretations are inferences, not implemented behavior.\n'+description,'image',{'image_hash':digest(path.read_bytes())})
            else:
                add(path.name,str(path),f'User-supplied design image: {path.name}. Its pixels require a vision model or a written design description.','image')
                gaps.append(f'{path.name} needs visual analysis or a written description for factual design analysis.')
        else:
            if not safe_file(path,path.parent): raise ValueError('Secret or unsupported source file')
            if path.suffix.lower() not in TEXT and path.suffix.lower()!='.svg': raise ValueError('Unsupported format; provide a text, PDF, or image export')
            if path.stat().st_size>10_000_000: raise ValueError('Input text exceeds 10 MB; select a smaller source')
            add(path.name,str(path),path.read_text(encoding='utf-8',errors='replace')[:300000],'document' if path.suffix.lower() in {'.md','.txt','.rst'} else 'code')
    if not evidence:
        words=set(re.findall(r'[a-z]{4,}',request['topic'].lower()))-{'official','documentation','explain','understand','learn','concept','works','overview','technical'}
        cached=[]
        for file in (config.assets/'References').glob('*.json'):
            record=json.loads(file.read_text(encoding='utf-8'))
            score=sum(min(record['text'].lower().count(w),10) for w in words)
            matches=sum(w in record['text'].lower() for w in words)
            if score and matches>=min(2,len(words)): cached.append((score,record))
        for _,record in sorted(cached,key=lambda x:x[0],reverse=True)[:5]:
            add(record['title'],record['origin'],record['text'],meta={'fetched':record['fetched'],'cached':True})
    if not evidence and request['mode']=='research':
        try:
            urls = discover(request['topic'],config)
            for url in urls:
                checkpoint()
                try:
                    record=fetch(url,config); add(record['title'],url,record['text'],meta={'fetched':record['fetched']})
                except Exception as exc: gaps.append(f'Could not read {url}: {type(exc).__name__}')
        except Exception as exc:
            gaps.append(f'Automatic search failed: {exc}. Supply reference URLs or local documents.')
    if not evidence:
        raise ValueError('No readable evidence. Add local files or reference URLs; a concept-only request needs research mode.')
    # Always capture the user's topic/goal as instructions, never treat it as independent evidence.
    return {'sources':list({s['id']:s for s in sources}.values()),'passages':list({p['id']:p for p in evidence}.values()),'gaps':gaps,'captured':now()}

def select_passages(evidence,topic,limit=18,cover_sources=False):
    words=set(re.findall(r'[a-z][a-z0-9_]{2,}',topic.lower()))
    def score(p):
        title=p['title'].lower().replace('\\','/'); text=p['text'].lower()
        # Path matches help a small relevant module compete with long repetitive documentation.
        return sum(12*(w in title)+min(text.count(w),3) for w in words) + (3 if 'readme' in title else 0) + (7 if p['kind']=='code' else 0)
    ranked=sorted(evidence['passages'],key=score,reverse=True)
    selected=[]; counts={}
    def include(p):
        if p['id'] not in {x['id'] for x in selected}:
            selected.append(p); counts[p['source_id']]=counts.get(p['source_id'],0)+1
    # Explicit files describe the scope the user selected. Give each one a voice
    # in the plan before taking a second passage from a popular source. Large
    # folder inventories still use ranking and the foundation rules below.
    if cover_sources and not any(s.get('kind')=='inventory' for s in evidence['sources']):
        for passage in ranked:
            if counts.get(passage['source_id'],0): continue
            include(passage)
            if len(selected)>=limit: return selected[:limit]
    # Broad repository lessons need foundations as well as the query's representative feature.
    if any(s.get('kind')=='inventory' for s in evidence['sources']) and any(w in words for w in ('repo','repository','architecture','overview','works','components')):
        candidates={}
        for p in evidence['passages']:
            name=p['title'].lower().replace('\\','/'); category=None
            if name=='package.json': category='runtime'
            elif name.startswith(('architecture','docs/architecture')): category='architecture'
            elif name in ('db/schema.ts','src/db/schema.ts','schema.sql','prisma/schema.prisma'): category='data'
            elif name in ('worker/index.ts','src/main.py','main.py','src/main.ts','src/index.ts','app/layout.tsx'): category='entry'
            if name in ('app/layout.tsx','src/app/layout.tsx'): category='ui'
            if category and category not in candidates: candidates[category]=p
        for p in candidates.values(): include(p)
    for passage in ranked:
        if counts.get(passage['source_id'],0)>=2: continue
        include(passage)
        if len(selected)>=limit: break
    return selected[:limit]
