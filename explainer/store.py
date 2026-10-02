import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

def now(): return datetime.now(timezone.utc).isoformat()
def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)

class Store:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.db = config.assets/'jobs.sqlite'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5(job_id UNINDEXED, evidence_id UNINDEXED, text)')

    def connect(self):
        db = sqlite3.connect(self.db, timeout=30)
        db.execute('PRAGMA journal_mode=WAL')
        return db

    def create(self, request):
        job_id = 'lesson_' + uuid.uuid4().hex[:12]
        self.folder(job_id).mkdir(parents=True)
        job = dict(id=job_id, request=request, status='queued', stage='Waiting to research', progress=0, created=now(), updated=now(), revision=1, error=None, approval=None, artifacts={}, events=[])
        self.save(job)
        self.artifact(job_id, 'request.json', request)
        return job

    def folder(self, job_id):
        if not job_id.startswith('lesson_') or not job_id[7:].isalnum(): raise ValueError('Invalid lesson ID')
        return self.config.lessons/job_id

    def get(self, job_id):
        with self.connect() as db:
            row = db.execute('SELECT data FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row: raise KeyError('Lesson not found')
        return json.loads(row[0])

    def delete(self, job_id):
        self.get(job_id)
        with self.lock, self.connect() as db:
            db.execute('DELETE FROM passages WHERE job_id=?', (job_id,))
            db.execute('DELETE FROM jobs WHERE id=?', (job_id,))

    def list(self):
        with self.connect() as db: rows = db.execute('SELECT data FROM jobs ORDER BY rowid DESC').fetchall()
        return [json.loads(row[0]) for row in rows]

    def save(self, job):
        job['updated'] = now()
        with self.lock, self.connect() as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)', (job['id'], json.dumps(job)))

    def update(self, job_id, **fields):
        with self.lock:
            job = self.get(job_id); job.update(fields); self.save(job)
            return job

    def event(self, job_id, stage, progress=None, **fields):
        with self.lock:
            job = self.get(job_id)
            job['events'] = (job['events'] + [{'time': now(), 'message': stage}])[-60:]
            job.update(stage=stage, **fields)
            if progress is not None: job['progress'] = progress
            self.save(job)

    def artifact(self, job_id, name, value):
        path = self.folder(job_id)/name
        write_json(path, value)
        return path

    def read(self, job_id, name):
        return json.loads((self.folder(job_id)/name).read_text(encoding='utf-8'))

    def index(self, job_id, passages):
        with self.connect() as db:
            db.execute('DELETE FROM passages WHERE job_id=?', (job_id,))
            db.executemany('INSERT INTO passages VALUES (?,?,?)', [(job_id,p['id'],p['text']) for p in passages])

    def search(self, job_id, query):
        with self.connect() as db:
            return db.execute('SELECT evidence_id,text FROM passages WHERE job_id=? AND passages MATCH ? ORDER BY rank LIMIT 12', (job_id,query)).fetchall()
