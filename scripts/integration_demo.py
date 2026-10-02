"""Exercise real source -> outline -> reviewed script -> local video with a tiny owned fixture."""
import json
from pathlib import Path
from explainer.config import settings
from explainer.engine import Engine

def main():
    config=settings(); source=config.scratch/'fixtures'/'queue-worker'; source.mkdir(parents=True,exist_ok=True)
    (source/'README.md').write_text('''# Queue worker implementation demo
This tiny teaching example holds tasks in a Python deque. enqueue adds a task at the right. work_one removes the oldest task from the left and passes it to a supplied handler. It returns None when the queue is empty. The caller provides the handler, so the queue does not decide what processing means. This is an in-memory, single-threaded teaching example. It does not persist tasks, provide retries, or guarantee delivery after process failure. The handler exception propagates, and the task has already been removed when that happens.
''',encoding='utf-8')
    (source/'worker.py').write_text('''from collections import deque

tasks = deque()

def enqueue(task):
    tasks.append(task)

def work_one(handler):
    if not tasks:
        return None
    task = tasks.popleft()
    return handler(task)
''',encoding='utf-8')
    engine=Engine(config)
    try:
        job=engine.store.create({'topic':'Queue worker implementation demo','inputs':[str(source)],'goal':'Explain this tiny example. Two chapters only: FIFO queue flow, then handler behavior and limitations. Include one exact code excerpt. This is an implementation test fixture.','audience':'Beginner Python builder','minutes':1,'mode':'offline'})
        engine.guard(job['id'],engine.plan)
        planned=engine.store.get(job['id'])
        if planned['status']=='failed': raise RuntimeError(planned['error'])
        engine.approve(job['id'],planned['outline']['hash'])
        engine.store.update(job['id'],approval={'outline_hash':planned['outline']['hash'],'actor':'implementation_test','purpose':'Owned fixture verifying the pipeline; not approval of any user lesson'})
        engine.guard(job['id'],engine.produce)
        completed=engine.store.get(job['id'])
        print(json.dumps(completed,indent=2))
        if completed['status']!='complete': raise RuntimeError(completed.get('error','Pipeline did not complete'))
    finally: engine.close()

if __name__=='__main__': main()
