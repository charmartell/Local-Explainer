import base64
import html
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw
import imageio_ffmpeg
from playwright.sync_api import sync_playwright
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.lexers.special import TextLexer
from .models import FLAGS

def e(value): return html.escape(str(value))

CSS='''*{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden}body{background:#111923;color:#f4f0e8;font-family:Arial,sans-serif}main{padding:78px 100px;height:100%;position:relative;background:radial-gradient(ellipse at 85% 15%,#24373a 0,transparent 55%)}.eyebrow{font-size:22px;letter-spacing:4px;color:#83d7bf;text-transform:uppercase}.title{font-size:58px;line-height:1.13;max-width:1680px;margin:24px 0 18px;font-weight:600;letter-spacing:-1px}.goal{font-size:25px;color:#aeb9c0;max-width:1560px;line-height:1.45;margin:0}.visual{margin-top:42px;height:640px;display:flex;align-items:center;justify-content:center}.footer{position:absolute;bottom:34px;left:100px;right:100px;display:flex;justify-content:space-between;font-size:18px;color:#8b9ba5;gap:40px}.footer span:first-child{max-width:1400px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}svg{width:1720px;height:620px}.node{fill:#20313b;stroke:#426373;stroke-width:2}.active{stroke:#8ce3c8;stroke-width:4;fill:#294e4c}.node-label{fill:#f4f0e8;font-size:31px;font-weight:600}.edge{stroke:#638899;stroke-width:3;fill:none}.edge-label{fill:#bdd9d9;font-size:22px}.code-wrap{width:1680px;background:#162431;border:1px solid #38515f;border-radius:20px;padding:28px 40px;max-height:640px;overflow:hidden}.code-path{color:#83d7bf;font-size:21px;margin-bottom:24px}.code-wrap pre{margin:0;font:25px/1.55 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}.line{display:block}.number{display:inline-block;width:65px;color:#657c8c;user-select:none}.line.active{background:#294e4c}.points{display:grid;grid-template-columns:1fr 1fr;gap:24px;width:1680px}.point{border:1px solid #426373;background:#20313b;border-radius:20px;padding:35px;min-height:170px;display:flex;align-items:center;font-size:34px;line-height:1.25}.point.active{border-color:#8ce3c8}.illustration{width:1650px;height:640px;object-fit:cover;border-radius:24px}.table{border-collapse:collapse;width:1680px;font-size:28px}.table td,.table th{padding:24px;border-bottom:1px solid #426373;text-align:left}.table th{color:#83d7bf}.highlight .k,.highlight .kd{color:#b6a0e8}.highlight .s,.highlight .s1,.highlight .s2{color:#b0d99c}.highlight .c,.highlight .c1{color:#8497a8}.highlight .nf,.highlight .nx{color:#f4f0e8}'''

def wrap(label,width=26):
    words=str(label).split(); lines=[]; line=''
    for word in words:
        if len(line+' '+word)>width and line: lines.append(line); line=word
        else: line=(line+' '+word).strip()
    if line: lines.append(line)
    return lines[:3]

def scene_html(scene,chapter,active='',image=None):
    v=scene['visual']; source='Evidence-backed learning'; body=''
    if v['type'] in ('diagram','sequence','state'):
        nodes=v['nodes']; n=len(nodes); positions={}
        for i,node in enumerate(nodes):
            cols=min(3,n); row=i//cols; row_count=min(cols,n-row*cols)
            positions[node['id']]=(860+(i%cols-(row_count-1)/2)*550,200+row*270 if n>3 else 300)
        arrows=[]
        for edge in v['edges']:
            x1,y1=positions[edge['from']]; x2,y2=positions[edge['to']]
            label_y=(y1+y2)/2-120 if y1==y2 else (y1+y2)/2-20
            if y1==y2:
                sign=1 if x2>x1 else -1; x1+=sign*220; x2-=sign*230
            else: y1+=80; y2-=85
            color='#8ce3c8' if edge['id']==active else '#638899'
            arrows.append(f'<path class="edge" style="stroke:{color}" d="M{x1},{y1} C{x1},{(y1+y2)/2} {x2},{(y1+y2)/2} {x2},{y2}" marker-end="url(#arrow)"/><text class="edge-label" text-anchor="middle" x="{(x1+x2)/2}" y="{label_y}">{e(edge["label"][:40])}</text>')
        boxes=[]
        for node in nodes:
            x,y=positions[node['id']]; lines=wrap(node['label']); yy=y-(len(lines)-1)*19
            boxes.append(f'<rect class="node {"active" if node["id"]==active else ""}" x="{x-225}" y="{y-85}" width="450" height="170" rx="22"/><text class="node-label" text-anchor="middle">'+''.join(f'<tspan x="{x}" y="{yy+k*38}">{e(line)}</tspan>' for k,line in enumerate(lines))+'</text>')
        body='<svg viewBox="0 0 1720 620"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#83d7bf"/></marker></defs>'+''.join(arrows+boxes)+'</svg>'
    elif v['type']=='code':
        try: lexer=get_lexer_by_name({'tsx':'typescript','ts':'typescript','py':'python'}.get(v['language'],v['language']))
        except Exception: lexer=TextLexer()
        lines=v['code'].splitlines(); font=25 if max(map(len,lines),default=0)<90 else 21
        body='<div class="code-wrap"><div class="code-path">'+e(v['display_path'])+'</div><pre style="font-size:'+str(font)+'px" class="highlight">'+''.join(f'<span class="line"><span class="number">{v["start_line"]+i}</span>{highlight(line,lexer,HtmlFormatter(nowrap=True)).rstrip()}</span>' for i,line in enumerate(lines))+'</pre></div>'
        source=v['display_path']+f' · lines {v["start_line"]}–{v["start_line"]+len(lines)-1}'
    elif v['type']=='recap':
        body='<div class="points">'+''.join('<div class="point '+('active' if item['id']==active else '')+'">'+e(item['label'])+'</div>' for item in v['entries'])+'</div>'
    elif v['type'] in ('table','comparison'):
        body='<table class="table"><thead><tr>'+''.join('<th>'+e(x)+'</th>' for x in v['columns'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+e(x)+'</td>' for x in row['cells'])+'</tr>' for row in v['rows'])+'</tbody></table>'
    elif v['type']=='illustration':
        if not image or not Path(image).exists(): raise ValueError('Illustration asset unavailable')
        encoded=base64.b64encode(Path(image).read_bytes()).decode()
        body=f'<img class="illustration" src="data:image/png;base64,{encoded}" alt="Illustrative scene"/>'
        source='Generated illustration · technical claims are backed by sources'
    else: raise ValueError('Unsupported visual template')
    data={'title':scene['title'],'chapter':chapter,'goal':scene['teaching_goal']}
    return '<!doctype html><html><head><meta charset="utf-8"><style>'+CSS+'</style></head><body><main><div class="eyebrow">'+e(chapter)+'</div><h1 class="title">'+e(scene['title'])+'</h1><p class="goal">'+e(scene['teaching_goal'])+'</p><div class="visual">'+body+'</div><div class="footer"><span>'+e(source)+'</span><span>LOCAL EXPLAINER</span></div></main><script>window.seek=(seconds)=>{document.body.dataset.time=seconds;return true};</script></body></html>'

def run_ffmpeg(args,log,checkpoint=lambda:None):
    with Path(log).open('wb') as output:
        process=subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-hide_banner',*args],stdout=output,stderr=output,creationflags=FLAGS)
        try:
            while process.poll() is None: checkpoint(); time.sleep(.2)
            if process.returncode: raise RuntimeError(f'Video encoder failed. See {log}')
        finally:
            if process.poll() is None: process.terminate(); process.wait(timeout=10)

def concat_file(path,files,durations=None):
    # Paths originate in application-owned scratch; quote for the concat parser, not a shell.
    lines=[]
    for i,file in enumerate(files):
        safe=str(Path(file).resolve()).replace('\\','/').replace("'","'\\''")
        lines.append("file '"+safe+"'")
        if durations: lines.append(f'duration {durations[i]:.6f}')
    if durations and files: lines.append(lines[-2])
    Path(path).write_text('\n'.join(lines)+'\n',encoding='utf-8')

def active_target(scene,segment,index):
    for cue in scene['cues']:
        if cue['segment_id']==segment['id']: return cue['target_id']
    items=scene['visual'].get('nodes',scene['visual'].get('entries',[]))
    for item in items:
        if item['label'].lower() in segment['text'].lower(): return item['id']
    return items[min(index,len(items)-1)]['id'] if items else ''

def render_scene(scene,chapter,audio,folder,image,checkpoint=lambda:None):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    frames=[]; durations=[]; checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--disable-background-networking','--disable-component-update','--disable-sync'])
        page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
        page.route('**/*',lambda route:route.abort() if not route.request.url.startswith('data:') else route.continue_())
        for i,segment in enumerate(scene['narration']):
            checkpoint()
            html_text=scene_html(scene,chapter,active_target(scene,segment,i),image)
            page.set_content(html_text,wait_until='load'); page.evaluate('document.fonts.ready')
            layout=page.evaluate('''() => [...document.querySelectorAll('.title,.goal,.visual,.footer,.code-wrap,.point,.points,.table')].map(e=>({name:e.className,x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,overflow:e.scrollHeight>e.clientHeight+2||e.scrollWidth>e.clientWidth+2}))''')
            if any(x['overflow'] or x['y']+x['height']>1080 for x in layout): raise ValueError('Scene layout overflows: '+scene['id'])
            checks.append(layout)
            file=folder/f'frame-{i:03}.png'; page.screenshot(path=str(file)); frames.append(file); durations.append(audio[segment['id']]['duration'])
        browser.close()
    concat_file(folder/'frames.txt',frames,durations)
    concat_file(folder/'audio.txt',[audio[s['id']]['path'] for s in scene['narration']])
    run_ffmpeg(['-f','concat','-safe','0','-i',str(folder/'audio.txt'),'-c:a','pcm_s16le',str(folder/'narration.wav')],folder/'audio-encode.log',checkpoint)
    duration=sum(durations)
    run_ffmpeg(['-f','concat','-safe','0','-i',str(folder/'frames.txt'),'-i',str(folder/'narration.wav'),'-vf',f"fps=30,zoompan=z='min(1.02,1+on*0.00001)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1920x1080:fps=30,format=yuv420p,fade=t=in:st=0:d=0.35,fade=t=out:st={max(0,duration-.3):.3f}:d=0.3",'-t',str(duration),'-c:v','libx264','-preset','veryfast','-crf','20','-threads','8','-c:a','aac','-b:a','192k','-movflags','+faststart',str(folder/'scene.mp4')],folder/'video-encode.log',checkpoint)
    return {'id':scene['id'],'path':str(folder/'scene.mp4'),'duration':duration,'preview':str(frames[0]),'checks':checks}

def srt_time(seconds):
    ms=int(round(seconds*1000)); hours,ms=divmod(ms,3600000); minutes,ms=divmod(ms,60000); sec,ms=divmod(ms,1000)
    return f'{hours:02}:{minutes:02}:{sec:02},{ms:03}'

def export(lesson,clips,audio,folder,checkpoint=lambda:None):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    concat_file(folder/'clips.txt',[clip['path'] for clip in clips])
    run_ffmpeg(['-f','concat','-safe','0','-i',str(folder/'clips.txt'),'-c','copy','-movflags','+faststart',str(folder/'lesson.mp4')],folder/'assembly.log',checkpoint)
    # Full decode verifies the assembled media, not just the presence of a file.
    run_ffmpeg(['-v','error','-i',str(folder/'lesson.mp4'),'-f','null','-'],folder/'decode-check.log',checkpoint)
    captions=[]; transcript=[]; chapters=[]; total=0; number=1; previous=None
    chapter_map={c['id']:c['title'] for c in lesson['chapters']}
    for scene in lesson['scenes']:
        if scene['chapter_id']!=previous:
            chapters.append({'title':chapter_map[scene['chapter_id']],'start':total}); previous=scene['chapter_id']
        transcript.append('<section><h2>'+e(scene['title'])+'</h2><img src="'+scene['id']+'.jpg" alt="Lesson scene">')
        for segment in scene['narration']:
            duration=audio[segment['id']]['duration']
            # Keep caption lines short and allocate time proportionally inside the sentence.
            words=segment['text'].split(); chunks=[' '.join(words[i:i+10]) for i in range(0,len(words),10)]
            position=total
            for chunk in chunks:
                end=position+duration*len(chunk.split())/max(1,len(words))
                captions.append(f'{number}\n{srt_time(position)} --> {srt_time(end)}\n{chunk}\n'); number+=1; position=end
            transcript.append('<p>'+e(segment['text'])+'</p>'); total+=duration
        transcript.append('</section>')
    (folder/'captions.srt').write_text('\n'.join(captions),encoding='utf-8')
    (folder/'captions.vtt').write_text('WEBVTT\n\n'+re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})',r'\1.\2','\n'.join(captions)),encoding='utf-8')
    (folder/'chapters.json').write_text(json.dumps(chapters,indent=2),encoding='utf-8')
    (folder/'chapters.txt').write_text('\n'.join(f'{int(c["start"])//60:02}:{int(c["start"])%60:02} {c["title"]}' for c in chapters),encoding='utf-8')
    (folder/'transcript.html').write_text('<!doctype html><meta charset="utf-8"><title>'+e(lesson['title'])+'</title><style>body{max-width:900px;margin:60px auto;background:#111923;color:#eee;font:20px/1.65 Arial}img{width:100%;border-radius:14px}h2{margin-top:60px}</style><h1>'+e(lesson['title'])+'</h1>'+''.join(transcript),encoding='utf-8')
    sheet=Image.new('RGB',(1280,math.ceil(len(clips)/3)*250),'#111923'); draw=ImageDraw.Draw(sheet)
    for i,clip in enumerate(clips):
        img=Image.open(clip['preview']).convert('RGB'); img.thumbnail((410,230)); sheet.paste(img,((i%3)*425,(i//3)*250)); draw.text(((i%3)*425+8,(i//3)*250+232),clip['id'],fill='white')
        img.save(folder/(clip['id']+'.jpg'))
    sheet.save(folder/'contact-sheet.jpg')
    return {'duration':total,'captions':number-1,'dimensions':[1920,1080],'fps':30,'decoded':True,'chapters':chapters}
