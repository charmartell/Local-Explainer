"""Bounded drag/drop transfers from the browser to this computer only."""
import time
import uuid
from pathlib import Path, PurePosixPath
from .inputs import TEXT, SKIP, safe_file

ALLOWED = TEXT | {'.pdf', '.png', '.jpg', '.jpeg', '.webp', '.svg'}

class Sources:
    def __init__(self, config): self.config = config; self.batches = {}

    def create(self):
        key = uuid.uuid4().hex
        root = self.config.assets / 'Inputs' / key
        root.mkdir(parents=True, exist_ok=False)
        self.batches[key] = {'root': root, 'bytes': 0, 'count': 0, 'expires': time.monotonic()+3600, 'busy': False}
        return {'batch': key}

    def batch(self, key):
        batch = self.batches.get(key)
        if not batch or batch['expires'] < time.monotonic(): raise ValueError('Drop session expired; drop the files again')
        return batch

    async def upload(self, key, name, request):
        batch = self.batch(key)
        if batch['busy']: raise ValueError('Upload files sequentially')
        parts = PurePosixPath(name.replace('\\', '/'))
        if parts.is_absolute() or not parts.parts or any(p in ('.', '..') or ':' in p or p in SKIP for p in parts.parts):
            raise ValueError('Unsupported source path')
        target = batch['root'].joinpath(*parts.parts)
        if target.suffix.lower() not in ALLOWED or not safe_file(target, batch['root']): raise ValueError('Unsupported or secret source file')
        if target.exists(): raise ValueError('A source with that name already exists')
        if batch['count'] >= 400: raise ValueError('Drop up to 400 files; use the repository picker for larger projects')
        target.parent.mkdir(parents=True, exist_ok=True)
        batch['busy'] = True; length = 0; written = False
        try:
            with target.open('xb') as stream:
                written = True
                async for block in request.stream():
                    length += len(block)
                    if length > 10_000_000 or batch['bytes']+length > 100_000_000:
                        raise ValueError('Drop limit is 10 MB per file and 100 MB per batch; choose a local path instead')
                    stream.write(block)
            batch['bytes'] += length; batch['count'] += 1
        except Exception:
            if written: target.unlink(missing_ok=True)
            raise
        finally: batch['busy'] = False
        return {'name': name, 'bytes': length}

    def finish(self, key):
        batch = self.batch(key)
        if batch['busy'] or not batch['count']: raise ValueError('Wait for the source transfer to finish')
        del self.batches[key]
        top = sorted(batch['root'].iterdir())
        return {'paths': [str(p) for p in top] if len(top)<=20 else [str(batch['root'])],
                'files': batch['count'], 'bytes': batch['bytes']}
