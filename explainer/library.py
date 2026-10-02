"""Local library summaries and confirmed, owned-file storage operations."""
import hashlib
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from .store import digest, now, write_json

ACTIVE = {'queued', 'planning', 'producing'}

def checked(path, root, allow_root=False):
    path, root = Path(path).absolute(), Path(root).resolve()
    if path.is_symlink() or path.is_junction():
        raise ValueError('Storage operations cannot follow links or junctions')
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or (resolved == root and not allow_root):
        raise ValueError('Storage path is outside its managed directory')
    current = path
    while current != root:
        if current.is_symlink() or current.is_junction():
            raise ValueError('Storage operations cannot follow links or junctions')
        current = current.parent
    return resolved

def files(path):
    path = Path(path)
    if not path.exists(): return []
    if path.is_file(): return [path]
    result = []
    for base, dirs, names in os.walk(path, followlinks=False):
        for name in dirs + names:
            entry = Path(base) / name
            if entry.is_symlink() or entry.is_junction():
                raise ValueError('A managed folder contains a link or junction')
        result.extend(Path(base) / name for name in names)
    return result

def size(path):
    return sum(p.stat().st_size for p in files(path))

def hashes(path):
    result = {}
    for file in files(path):
        value = hashlib.sha256()
        with file.open('rb') as stream:
            for block in iter(lambda: stream.read(2**20), b''): value.update(block)
        result[str(file.relative_to(path))] = value.hexdigest()
    return result

def copy_verified(source, target):
    if target.exists(): raise ValueError('Destination already contains this lesson')
    expected = hashes(source)
    shutil.copytree(source, target)
    if hashes(target) != expected or hashes(source) != expected:
        raise ValueError('Copy verification failed; original files were preserved')
    return expected

def families(jobs):
    lookup = {j['id']: j for j in jobs}
    groups = {}
    for job in jobs:
        root = job; seen = set()
        while root.get('parent') in lookup and root['id'] not in seen:
            seen.add(root['id']); root = lookup[root['parent']]
        groups.setdefault(root['id'], []).append(job)
    return groups

def category(job):
    if job.get('label') == 'lesson': return 'video' if job['status'] == 'complete' else 'draft'
    if job.get('label') == 'demo' or job['request'].get('kind') == 'demo': return 'demo'
    if (job.get('approval') or {}).get('actor') == 'implementation_test': return 'demo'
    return 'video' if job['status'] == 'complete' else 'draft'

class Library:
    def __init__(self, engine):
        self.engine = engine; self.store = engine.store; self.config = engine.config
        self.previews = {}; self.lock = threading.RLock()

    def local_paths(self, job):
        result = [('lesson', checked(self.store.folder(job['id']), self.config.lessons)),
                  ('working', checked(self.config.scratch / job['id'], self.config.scratch))]
        seen = set()
        for entry in (job.get('offload') or {}).get('entries', []):
            if entry['kind'] == 'video':
                folder = Path(entry['original']); self.validate_original(job, folder, 'video')
                if folder not in seen: result.append(('video', folder)); seen.add(folder)
        for value in job.get('artifacts', {}).values():
            path = Path(value)
            if job.get('storage_state') == 'offloaded': continue
            folder = checked(path.parent, self.config.builds)
            if job['id'] not in folder.name: raise ValueError('Release folder ownership could not be verified')
            if folder not in seen:
                result.append(('video', folder)); seen.add(folder)
        return [(kind, path) for kind, path in result if path.exists()]

    def archive_paths(self, job):
        receipt = job.get('offload')
        if not receipt: return []
        root = Path(receipt['root'])
        if root.name != job['id'] or root.parent.name != receipt['batch']:
            raise ValueError('Archive ownership could not be verified')
        root = checked(root, root.parent)
        marker = root / 'offload.json'
        if not marker.is_file(): raise ValueError('Archive receipt is missing')
        import json
        if json.loads(marker.read_text(encoding='utf-8')).get('job_id') != job['id']:
            raise ValueError('Archive receipt does not match the lesson')
        files(root)
        return [('archive', root)]

    def summary(self):
        jobs = self.store.list(); rows = []
        for root, members in families(jobs).items():
            members.sort(key=lambda j: (j.get('revision', 1), j['created']), reverse=True)
            latest = members[0]; total = 0; external = 0; unavailable = False
            for job in members:
                total += sum(size(path) for _, path in self.local_paths(job))
                if job.get('offload'):
                    try: external += sum(size(path) for _, path in self.archive_paths(job))
                    except (OSError, ValueError): unavailable = True
            rows.append({'id': latest['id'], 'root_id': root, 'ids': [j['id'] for j in members],
                         'title': latest.get('outline', {}).get('title') if latest.get('outline') else latest['request']['topic'],
                         'category': 'demo' if any(category(j) == 'demo' for j in members) else category(latest),
                         'status': latest['status'], 'created': min(j['created'] for j in members),
                         'updated': max(j['updated'] for j in members), 'bytes': total, 'archive_bytes': external,
                         'offloaded': latest.get('storage_state') == 'offloaded',
                         'archive_unavailable': unavailable,
                         'active': any(j['status'] in ACTIVE or (self.engine.futures.get(j['id']) and not self.engine.futures[j['id']].done()) for j in members),
                         'revision_count': len(members)})
        return {'lessons': rows, 'local_bytes': sum(r['bytes'] for r in rows),
                'free_bytes': shutil.disk_usage(self.config.scratch).free,
                'source_bytes': size(self.config.assets / 'Inputs'),
                'roots': {'lessons': str(self.config.lessons), 'working': str(self.config.scratch), 'videos': str(self.config.builds)}}

    def idle(self, job):
        # A scene revision can still read its parent's snapshots during production.
        # Protect the whole family even when an API caller selected only the parent.
        related = next((members for members in families(self.store.list()).values()
                        if any(j['id']==job['id'] for j in members)), [job])
        for member in related:
            future = self.engine.futures.get(member['id'])
            if member['status'] in ACTIVE or (future and not future.done()):
                raise ValueError('Pause active lessons before managing their storage')

    def fingerprint(self, jobs):
        rows = []
        for job in jobs:
            self.idle(job)
            entries = self.local_paths(job) + self.archive_paths(job)
            rows.append({'id': job['id'], 'updated': job['updated'],
                         'files': [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for _, root in entries for p in files(root)]})
        return digest(rows)

    def preview(self, ids, action, destination=None):
        ids = list(dict.fromkeys(ids))
        if not ids or len(ids) > 200: raise ValueError('Select between 1 and 200 lesson versions')
        with self.lock, self.engine.lock:
            jobs = [self.store.get(i) for i in ids]
            fingerprint = self.fingerprint(jobs)
            if action == 'offload':
                if any(j.get('storage_state') == 'offloaded' for j in jobs):
                    raise ValueError('Already offloaded lessons cannot be offloaded again')
                target = Path(destination or '').expanduser()
                if not destination or not target.is_absolute() or not target.is_dir():
                    raise ValueError('Choose an existing destination folder')
                target = target.resolve()
                for root in (self.config.assets, self.config.scratch, self.config.builds):
                    if target.is_relative_to(root.resolve()): raise ValueError('Choose a folder outside application storage')
                destination = str(target)
            token = uuid.uuid4().hex
            self.previews = {t:p for t,p in self.previews.items() if p['expires'] > time.monotonic()}
            self.previews[token] = {'ids': ids, 'action': action, 'destination': destination,
                                    'fingerprint': fingerprint, 'expires': time.monotonic()+600}
            return {'token': token, 'action': action, 'destination': destination,
                    'bytes': sum(size(p) for j in jobs for _, p in self.local_paths(j)),
                    'archive_bytes': sum(size(p) for j in jobs for _, p in self.archive_paths(j)),
                    'versions': len(jobs), 'titles': list(dict.fromkeys((j.get('outline') or {}).get('title', j['request']['topic']) for j in jobs))}

    def execute(self, token, confirmation):
        with self.lock, self.engine.lock:
            plan = self.previews.pop(token, None)
            if not plan or plan['expires'] < time.monotonic(): raise ValueError('Storage preview expired; review it again')
            if confirmation != ('DELETE' if plan['action'] == 'delete' else 'OFFLOAD'):
                raise ValueError('Storage action was not confirmed')
            jobs = [self.store.get(i) for i in plan['ids']]
            if self.fingerprint(jobs) != plan['fingerprint']:
                raise ValueError('Selected lessons changed; review storage again')
            results = []
            batch = uuid.uuid4().hex
            for job in jobs:
                try:
                    if plan['action'] == 'offload': self.offload(job, Path(plan['destination']), batch)
                    else: self.delete(job)
                    results.append({'id': job['id'], 'ok': True})
                except Exception as exc:
                    results.append({'id': job['id'], 'ok': False, 'error': str(exc)})
            return {'results': results}

    def offload(self, job, destination, batch):
        root = destination / 'Local-Explainer-Archive' / batch / job['id']
        root.mkdir(parents=True, exist_ok=False)
        entries = []
        try:
            for index, (kind, original) in enumerate(self.local_paths(job)):
                copied = root / f'{index}-{kind}'
                expected = copy_verified(original, copied)
                entries.append({'kind': kind, 'original': str(original), 'copy': str(copied), 'hashes': expected})
        except Exception:
            # Only this freshly-created staging folder is discarded. Original
            # lesson/media folders are untouched until every copy is verified.
            checked(root, destination); files(root); shutil.rmtree(root)
            raise
        artifacts = job.get('artifacts', {})
        mapped = dict(artifacts)
        for name, value in artifacts.items():
            for entry in entries:
                if Path(value).is_relative_to(entry['original']):
                    mapped[name] = str(Path(entry['copy']) / Path(value).relative_to(entry['original']))
        receipt = {'job_id': job['id'], 'batch': batch, 'root': str(root), 'entries': entries,
                   'original_artifacts': artifacts, 'offloaded_at': now()}
        write_json(root / 'offload.json', receipt)
        # Persist the verified destination before removing any original. An interruption
        # can leave extra local copies, but the retained receipt still finds the archive.
        self.store.update(job['id'], storage_state='offloaded', offload=receipt, artifacts=mapped)
        for entry in entries:
            original = Path(entry['original'])
            self.validate_original(job, original, entry['kind'])
            if hashes(original) != entry['hashes']: raise ValueError('Original changed after copying; it was preserved')
            shutil.rmtree(original)

    def validate_original(self, job, path, kind):
        if kind == 'lesson':
            if checked(path, self.config.lessons) != self.store.folder(job['id']).resolve(): raise ValueError('Wrong lesson folder')
        elif kind == 'working':
            if checked(path, self.config.scratch) != (self.config.scratch / job['id']).resolve(): raise ValueError('Wrong working folder')
        elif kind == 'video':
            checked(path, self.config.builds)
            if job['id'] not in path.name: raise ValueError('Wrong video folder')
        else: raise ValueError('Unknown storage kind')

    def delete(self, job):
        paths = self.local_paths(job) + self.archive_paths(job)
        for kind, path in paths:
            if kind != 'archive': self.validate_original(job, path, kind)
            files(path)
        for _, path in paths: shutil.rmtree(path)
        self.store.delete(job['id'])

    def restore(self, job_id):
        with self.lock, self.engine.lock:
            job = self.store.get(job_id); self.idle(job)
            if job.get('storage_state') != 'offloaded': raise ValueError('This lesson is already local')
            self.archive_paths(job)
            for entry in job['offload']['entries']:
                original, copied = Path(entry['original']), Path(entry['copy'])
                self.validate_original(job, original, entry['kind'])
                checked(copied, job['offload']['root'])
                if hashes(copied) != entry['hashes']: raise ValueError('Archive verification failed')
                if original.exists():
                    if hashes(original) != entry['hashes']: raise ValueError('Local files differ; restore will not overwrite them')
                else: copy_verified(copied, original)
            receipt = job['offload']
            self.store.update(job_id, storage_state='local', artifacts=receipt['original_artifacts'])
            # Keep the archive until all copies and local registration have succeeded.
            root = self.archive_paths(job)[0][1]
            shutil.rmtree(root)
            return self.store.update(job_id, offload=None)

    def artifact_path(self, job, name):
        raw = job.get('artifacts', {}).get(name)
        if not raw: raise ValueError('Artifact is unavailable')
        root = job['offload']['root'] if job.get('storage_state') == 'offloaded' else self.config.builds
        return checked(Path(raw), root)
