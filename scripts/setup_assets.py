"""Download selected public assets, with resumable transfers and a provenance manifest."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import time
import sys
import urllib.request
import zipfile
from pathlib import Path

from explainer.config import storage_path

ROOT = storage_path('assets')
SCRATCH = storage_path('scratch') / 'setup'

def download(url, destination, expected=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and (not expected or destination.stat().st_size == expected):
        return destination
    SCRATCH.mkdir(parents=True, exist_ok=True)
    partial = SCRATCH / (hashlib.sha256(url.encode()).hexdigest()[:12] + '.part')
    for attempt in range(4):
        start = partial.stat().st_size if partial.exists() else 0
        request = urllib.request.Request(url, headers={'User-Agent': 'LocalExplainer/0.1', **({'Range': f'bytes={start}-'} if start else {})})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                append = response.status == 206
                total = int(response.headers.get('Content-Length', 0)) + (start if append else 0)
                with partial.open('ab' if append else 'wb') as target:
                    shutil.copyfileobj(response, target, 1024 * 1024)
            if total and partial.stat().st_size != total:
                raise IOError('Incomplete transfer')
            if expected and partial.stat().st_size != expected:
                raise IOError('Asset size mismatch')
            shutil.move(str(partial), str(destination))
            print('Downloaded', destination.name, destination.stat().st_size, flush=True)
            return destination
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))

def main():
    manifest=Path(__file__).resolve().parent.parent/'dependencies.json'
    jobs=json.loads(manifest.read_text(encoding='utf-8'))
    if '--vision-only' in sys.argv: jobs=[r for r in jobs if r['path'].startswith('Models/vision/')]
    records = []
    def run(job):
        path=(ROOT/job['path']).resolve()
        if not path.is_relative_to(ROOT.resolve()): raise ValueError('Asset path escapes the configured model directory')
        path = download(job['url'], path, job['size'])
        sha = hashlib.sha256()
        with path.open('rb') as source:
            for block in iter(lambda: source.read(8*1024*1024), b''):
                sha.update(block)
        if sha.hexdigest()!=job['sha256']: raise ValueError(f'Asset checksum mismatch: {path}. Preserve this file and repair the installation before using it.')
        return {**job,'path':str(path),'verified':True}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for record in pool.map(run, jobs):
            records.append(record)
    existing=json.loads((ROOT/'dependencies.json').read_text(encoding='utf-8')) if (ROOT/'dependencies.json').exists() else []
    merged={r['path']:r for r in existing+records}
    (ROOT/'dependencies.json').write_text(json.dumps(list(merged.values()),indent=2),encoding='utf-8')
    if '--vision-only' not in sys.argv and not (ROOT/'Runtime'/'llama'/'llama-server.exe').is_file():
        destination=(ROOT/'Runtime'/'llama').resolve()
        with zipfile.ZipFile(ROOT/'Runtime'/'llama.zip') as archive:
            for name in archive.namelist():
                if not (destination/name).resolve().is_relative_to(destination): raise ValueError('Unsafe runtime archive path')
            archive.extractall(destination)
    print('Assets ready', flush=True)

if __name__ == '__main__':
    main()
