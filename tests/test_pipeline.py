import json
import threading
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from explainer.config import Settings
from explainer.store import Store,digest,write_json
from explainer.inputs import collect,fetch,select_passages,primary_reference
from explainer.engine import Engine,Cancelled
from explainer.authoring import validate_lesson
from explainer.api import make_app
from explainer.render import scene_html,srt_time

@pytest.fixture
def config(tmp_path):
    result=Settings(assets=tmp_path/'assets',scratch=tmp_path/'scratch',builds=tmp_path/'builds');result.prepare();return result

def outline_fixture():
    result={'title':'Example','outcome':'Understand flow','assumptions':'Beginner','minutes':2,'beats':[{'id':'beat1','title':'Flow','focus':'Understand','evidence_ids':['ev1']}],'visuals':'diagram','gaps':[]};result['hash']=digest(result);return result

def lesson_fixture(plan):
    return {'schema_version':'1.0','lesson_id':'lesson_fixture','approved_outline_hash':plan['hash'],'title':'Example','learning_outcomes':['Understand'],'audience':'Beginner','style':{'theme_id':'editorial','illustration_direction':'Clear','language':'en-US'},'chapters':[{'id':'chapter1','title':'Flow','outline_beat_id':'beat1'}],'claims':[{'id':'claim1','statement':'Input reaches output','kind':'documented_behavior','qualification':'','evidence':[{'source_id':'source1','evidence_id':'ev1'}]}],'scenes':[{'id':'scene1','chapter_id':'chapter1','title':'Flow','teaching_goal':'Understand','narration':[{'id':'voice1','text':'Input reaches output.','speech_text':'Input reaches output.','claim_ids':['claim1']}],'visual':{'type':'diagram','nodes':[{'id':'input','label':'Input','role':'input'},{'id':'output','label':'Output','role':'output'}],'edges':[{'id':'edge','from':'input','to':'output','label':'flows','claim_ids':['claim1']}]},'cues':[]}],'glossary':[]}

def test_stale_approval_rejected(config):
    engine=Engine(config);job=engine.store.create({'topic':'test','inputs':[]});plan=outline_fixture();engine.store.artifact(job['id'],'outline.json',plan);engine.store.update(job['id'],status='awaiting_approval')
    with pytest.raises(ValueError,match='Outline changed'):engine.approve(job['id'],'stale')
    engine.approve(job['id'],plan['hash']);plan['hash']='new';engine.store.artifact(job['id'],'outline.json',plan)
    with pytest.raises(ValueError,match='Approve'):engine.produce(job['id'])
    engine.close()

def test_source_repository_is_readonly_and_secrets_ignored(config,tmp_path):
    root=tmp_path/'source';root.mkdir();(root/'entry.py').write_text('print("hello")');(root/'.env').write_text('PRIVATE=secret');(root/'node_modules').mkdir();(root/'node_modules'/'a.py').write_text('ignored')
    before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result=collect({'inputs':[str(root)],'mode':'offline','topic':'entry'},config)
    assert len(result['passages'])==1
    assert 'PRIVATE' not in json.dumps(result)
    assert before=={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}

def test_offline_uncached_url_never_connects(config,monkeypatch):
    import httpx
    def forbidden(*a,**k):raise AssertionError('Network used')
    monkeypatch.setattr(httpx,'Client',forbidden)
    with pytest.raises(ValueError,match='Offline source unavailable'):fetch('https://example.com/docs',config,True)

def test_offline_cache_and_concept_library(config,monkeypatch):
    import hashlib
    url='https://example.com/queues';record={'origin':url,'title':'Queues','fetched':'2026-10-01','text':'A message queue holds messages until a worker processes them.','hash':'x'}
    write_json(config.assets/'References'/f'{hashlib.sha256(url.encode()).hexdigest()}.json',record)
    assert fetch(url,config,True)['text']==record['text']
    result=collect({'inputs':[],'mode':'offline','topic':'message queue'},config)
    assert result['passages'] and result['sources'][0]['cached']

def test_missing_input_stops(config):
    with pytest.raises(ValueError,match='does not exist'):collect({'inputs':[str(config.assets/'missing.md')],'mode':'offline','topic':'test'},config)

def test_semantic_references_and_code_are_checked():
    plan=outline_fixture();lesson=lesson_fixture(plan);evidence={'passages':[{'id':'ev1','source_id':'source1','start_line':10,'text':'first\nsecond','kind':'code'}]}
    assert validate_lesson(lesson,evidence,plan)
    lesson['scenes'][0]['visual']['edges'][0]['to']='missing'
    with pytest.raises(ValueError,match='Unresolved diagram'):validate_lesson(lesson,evidence,plan)
    lesson=lesson_fixture(plan);lesson['scenes'][0]['visual']={'type':'code','source_id':'source1','evidence_id':'ev1','language':'text','display_path':'source.py','start_line':10,'code':'edited','regions':[]}
    with pytest.raises(ValueError,match='differs'):validate_lesson(lesson,evidence,plan)

def test_cancelled_job_keeps_artifacts(config):
    engine=Engine(config);job=engine.store.create({'topic':'test'});engine.store.artifact(job['id'],'saved.json',{'done':True});engine.cancelled[job['id']]=threading.Event();engine.cancelled[job['id']].set()
    engine.guard(job['id'],lambda jid:engine.checkpoint(jid))
    assert engine.store.get(job['id'])['status']=='cancelled';assert engine.store.read(job['id'],'saved.json')['done'];engine.close()

def test_restart_recovery_not_triggered_by_doctor(config):
    engine=Engine(config);job=engine.store.create({'topic':'test'});engine.store.update(job['id'],status='producing');engine.close()
    reader=Engine(config);assert reader.store.get(job['id'])['status']=='producing';reader.close()
    restart=Engine(config,recover=True);assert restart.store.get(job['id'])['status']=='interrupted';restart.close()

def test_api_blocks_cross_origin_and_arbitrary_artifacts(config):
    app=make_app(config)
    with TestClient(app) as client:
        assert client.get('/api/jobs',headers={'Origin':'https://malicious.example'}).status_code==403
        assert client.get('/api/jobs',headers={'Host':'malicious.example'}).status_code==403
        job=app.state.engine.store.create({'topic':'fixture'})
        assert client.get(f'/api/jobs/{job["id"]}/artifacts/secrets.json').status_code==404
        assert client.post(f'/api/jobs/{job["id"]}/production',json={}).status_code==409

def test_renderer_escapes_source_markup():
    scene=lesson_fixture(outline_fixture())['scenes'][0];scene['title']='<script>alert(1)</script>'
    text=scene_html(scene,'Chapter');assert '&lt;script&gt;' in text;assert '<script>alert(1)</script>' not in text
    assert srt_time(3661.123)=='01:01:01,123'

def test_repository_overview_includes_foundations():
    passages=[{'id':str(i),'source_id':str(i),'title':title,'text':text,'kind':kind,'start_line':1} for i,(title,text,kind) in enumerate([
        ('package.json','React and vinext dependencies','code'),('db/schema.ts','Database tables','code'),('worker/index.ts','Request entry point','code'),
        ('docs/alpha.md','alpha enrollment request '*100,'document'),('app/api/alpha/route.ts','alpha enrollment request validation','code')])]
    chosen=select_passages({'sources':[{'kind':'inventory'}],'passages':passages},'Repository architecture and alpha enrollment',4)
    assert {'package.json','db/schema.ts','worker/index.ts'}<={p['title'] for p in chosen}

def test_explicit_multirepo_plan_keeps_client_and_updater_evidence():
    passages=[]
    for i in range(18):
        for part in range(3):
            passages.append({'id':f'admin{i}_{part}','source_id':f'admin{i}',
                'title':f'admin-update-publishing-{i}.ts','text':'admin update publish '*30,
                'kind':'code','start_line':part*48+1})
    for title,text in [('application_update_card.dart','User confirms restart.'),
                       ('Program.cs','Journal restores the previous program on failed health check.')]:
        passages.append({'id':title,'source_id':title,'title':title,'text':text,'kind':'code','start_line':1})
    evidence={'sources':[{'kind':'code'}],'passages':passages}
    chosen=select_passages(evidence,'admin update publishing',24,cover_sources=True)
    assert {'application_update_card.dart','Program.cs'}<={p['title'] for p in chosen}
    assert len({p['source_id'] for p in chosen})==20

def test_scene_revision_preserves_approval_and_other_work(config,monkeypatch):
    engine=Engine(config);job=engine.store.create({'topic':'fixture','goal':'Understand flow'});plan=outline_fixture();lesson=lesson_fixture(plan)
    for name,value in [('outline.json',plan),('lesson.json',lesson),('evidence.json',{'sources':[],'passages':[]}),('chapter-1.json',{'scenes':lesson['scenes'],'claims':lesson['claims'],'review':{'supported':True}})]: engine.store.artifact(job['id'],name,value)
    engine.store.update(job['id'],status='complete',approval={'outline_hash':plan['hash'],'actor':'implementation_test','time':'test'})
    speech=config.scratch/job['id']/'speech';speech.mkdir(parents=True);(speech/'cached.wav').write_bytes(b'cached audio')
    calls=[]
    monkeypatch.setattr(engine,'submit',lambda jid,action:(calls.append(action.__name__) or engine.store.get(jid)))
    revised=engine.adjust(job['id'],'Use a simpler example','scene1')
    assert revised['revision_scene']=='scene1' and revised['approval']['outline_hash']==plan['hash']
    assert revised['parent']==job['id'] and calls==['produce']
    assert engine.store.read(revised['id'],'chapter-1.json')==engine.store.read(job['id'],'chapter-1.json')
    assert (config.scratch/revised['id']/'speech'/'cached.wav').read_bytes()==b'cached audio'
    with pytest.raises(ValueError,match='Unknown scene'): engine.adjust(job['id'],'change','missing')
    engine.close()

def test_automatic_research_prefers_primary_sources():
    assert primary_reference('https://docs.python.org/3/library/collections.html')
    assert not primary_reference('https://docs.python.org.evil.example/tutorial')
    assert not primary_reference('https://www.geeksforgeeks.org/python/deque/')

@pytest.mark.parametrize('name,text',[('concept','A queue holds messages before a worker processes them.'),('process','A migration changes a database schema in recorded steps.'),('design','This proposal separates the input from the rendering worker.'),('repository','The entrypoint calls the worker and stores its result.')])
def test_four_source_kinds_are_captured(config,tmp_path,name,text):
    path=tmp_path/(name+'.md');path.write_text(text)
    result=collect({'topic':name,'inputs':[str(path)],'mode':'offline'},config)
    assert result['passages'][0]['text']==text
