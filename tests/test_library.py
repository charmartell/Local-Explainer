import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from explainer.api import make_app
from explainer.config import Settings
from explainer.engine import Engine
from explainer.library import Library

@pytest.fixture
def engine(tmp_path):
    config=Settings(assets=tmp_path/'assets',scratch=tmp_path/'scratch',builds=tmp_path/'builds')
    config.prepare(); value=Engine(config)
    yield value
    value.close()

def completed(engine, name='A lesson'):
    job=engine.store.create({'topic':name,'inputs':[]})
    package=engine.config.builds/f'Example-{job["id"]}-r1'; package.mkdir()
    (package/'lesson.mp4').write_bytes(b'video contents')
    working=engine.config.scratch/job['id']; working.mkdir(); (working/'clip.mp4').write_bytes(b'working contents')
    return engine.store.update(job['id'],status='complete',artifacts={'lesson.mp4':str(package/'lesson.mp4')})

def test_revision_groups_and_demos_are_separate(engine):
    root=engine.store.create({'topic':'Tavern update','kind':'lesson'})
    newer=engine.store.create({'topic':'Tavern update','kind':'lesson'})
    engine.store.update(newer['id'],parent=root['id'],revision=2,status='awaiting_approval')
    demo=completed(engine,'Test fixture');engine.store.update(demo['id'],approval={'actor':'implementation_test'})
    rows=Library(engine).summary()['lessons']
    assert len(rows)==2
    assert next(r for r in rows if r['root_id']==root['id'])['revision_count']==2
    assert next(r for r in rows if r['id']==demo['id'])['category']=='demo'

def test_bulk_delete_requires_confirmation_and_keeps_other_lessons(engine,tmp_path):
    first=completed(engine); second=completed(engine,'Keep this')
    source=tmp_path/'repository';source.mkdir();(source/'main.py').write_text('keep')
    engine.store.update(first['id'],request={'topic':'A lesson','inputs':[str(source)]})
    library=Library(engine)
    preview=library.preview([first['id']],'delete')
    with pytest.raises(ValueError,match='confirmed'):library.execute(preview['token'],'NO')
    assert Path(first['artifacts']['lesson.mp4']).is_file()
    preview=library.preview([first['id']],'delete');assert library.execute(preview['token'],'DELETE')['results'][0]['ok']
    with pytest.raises(KeyError):engine.store.get(first['id'])
    assert Path(second['artifacts']['lesson.mp4']).is_file()
    assert (source/'main.py').read_text()=='keep'

def test_active_or_changed_jobs_cannot_be_deleted(engine):
    job=completed(engine);library=Library(engine)
    preview=library.preview([job['id']],'delete')
    engine.store.update(job['id'],status='producing')
    with pytest.raises(ValueError,match='Pause active'):library.execute(preview['token'],'DELETE')
    assert Path(job['artifacts']['lesson.mp4']).is_file()
    engine.store.update(job['id'],status='complete')
    preview=library.preview([job['id']],'delete')
    Path(job['artifacts']['lesson.mp4']).write_bytes(b'new video')
    with pytest.raises(ValueError,match='changed'):library.execute(preview['token'],'DELETE')

def test_active_scene_revision_protects_parent_storage(engine):
    parent=completed(engine);child=engine.store.create({'topic':'Scene revision'})
    engine.store.update(child['id'],parent=parent['id'],status='producing',revision=2)
    with pytest.raises(ValueError,match='Pause active'):Library(engine).preview([parent['id']],'delete')
    assert Path(parent['artifacts']['lesson.mp4']).is_file()

def test_offload_verify_playback_and_restore(engine,tmp_path):
    job=completed(engine);library=Library(engine);destination=tmp_path/'external';destination.mkdir()
    preview=library.preview([job['id']],'offload',str(destination))
    assert library.execute(preview['token'],'OFFLOAD')['results'][0]['ok']
    cold=engine.store.get(job['id']);assert cold['storage_state']=='offloaded'
    assert not Path(job['artifacts']['lesson.mp4']).exists()
    assert library.artifact_path(cold,'lesson.mp4').read_bytes()==b'video contents'
    with pytest.raises(ValueError,match='Restore'):engine.submit(job['id'],engine.plan)
    restored=library.restore(job['id']);assert restored['storage_state']=='local'
    assert Path(job['artifacts']['lesson.mp4']).read_bytes()==b'video contents'
    assert not Path(cold['offload']['root']).exists()

def test_failed_offload_preserves_originals(engine,tmp_path,monkeypatch):
    import explainer.library as module
    job=completed(engine);library=Library(engine);destination=tmp_path/'external';destination.mkdir()
    def fail(*args):raise ValueError('Copy verification failed')
    monkeypatch.setattr(module,'copy_verified',fail)
    preview=library.preview([job['id']],'offload',str(destination))
    result=library.execute(preview['token'],'OFFLOAD')
    assert not result['results'][0]['ok']
    assert Path(job['artifacts']['lesson.mp4']).read_bytes()==b'video contents'
    assert engine.store.get(job['id']).get('storage_state')!='offloaded'

def test_corrupt_archive_refuses_restore(engine,tmp_path):
    job=completed(engine);library=Library(engine);destination=tmp_path/'external';destination.mkdir()
    p=library.preview([job['id']],'offload',str(destination));library.execute(p['token'],'OFFLOAD')
    cold=engine.store.get(job['id']);Path(cold['artifacts']['lesson.mp4']).write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='verification'):library.restore(job['id'])
    assert engine.store.get(job['id'])['storage_state']=='offloaded'

def test_artifact_outside_owned_storage_is_not_deleted(engine,tmp_path):
    job=completed(engine);foreign=tmp_path/'foreign';foreign.mkdir();(foreign/'lesson.mp4').write_bytes(b'keep')
    engine.store.update(job['id'],artifacts={'lesson.mp4':str(foreign/'lesson.mp4')})
    with pytest.raises(ValueError,match='outside'):Library(engine).preview([job['id']],'delete')
    assert (foreign/'lesson.mp4').is_file()

def test_upload_bounds_traversal_and_composer_settings(engine,monkeypatch):
    config=engine.config;(config.assets/'Models'/'kokoro').mkdir(parents=True);(config.assets/'Models'/'kokoro'/'af_bella.pt').write_bytes(b'fixture')
    app=make_app(config);captured=[]
    monkeypatch.setattr(app.state.engine,'create',lambda request:(captured.append(request) or {'id':'lesson_test'}))
    with TestClient(app) as client:
        batch=client.post('/api/sources',json={}).json()['batch']
        assert client.put(f'/api/sources/{batch}',params={'path':'../outside.md'},content=b'bad').status_code==409
        assert client.put(f'/api/sources/{batch}',params={'path':'.env'},content=b'bad').status_code==409
        assert client.put(f'/api/sources/{batch}',params={'path':'design.png'},content=b'png').status_code==200
        source=client.post(f'/api/sources/{batch}/finish',json={}).json()['paths'][0]
        assert Path(source).name=='design.png'
        assert client.put(f'/api/sources/{batch}',params={'path':'late.txt'},content=b'late').status_code==409
        request={'topic':'A detailed explanation','voice':'af_bella','minutes':18,'detail_level':'longform','kind':'demo','inputs':[source]}
        assert client.post('/api/jobs',json=request).status_code==200
        assert captured[-1]['voice']=='af_bella' and captured[-1]['detail_level']=='longform'
        assert client.post('/api/jobs',json={**request,'voice':'../../private'}).status_code==409
        assert client.post('/api/jobs',json={**request,'detail_level':'unbounded'}).status_code==422

def test_missing_archive_does_not_break_library(engine,tmp_path):
    job=completed(engine);library=Library(engine);destination=tmp_path/'external';destination.mkdir()
    p=library.preview([job['id']],'offload',str(destination));library.execute(p['token'],'OFFLOAD')
    root=Path(engine.store.get(job['id'])['offload']['root']);root.rename(root.with_name('disconnected'))
    assert library.summary()['lessons'][0]['archive_unavailable']

def test_storage_api_serves_offloaded_video_and_keeps_confirmation_gate(engine,tmp_path):
    job=completed(engine);app=make_app(engine.config);destination=tmp_path/'external';destination.mkdir()
    with TestClient(app) as client:
        assert client.post('/api/storage/preview',json={'ids':[job['id']],'action':'delete'},
                           headers={'Origin':'https://foreign.example'}).status_code==403
        preview=client.post('/api/storage/preview',json={'ids':[job['id']],'action':'offload','destination':str(destination)})
        assert preview.status_code==200
        done=client.post('/api/storage/execute',json={'token':preview.json()['token'],'confirmation':'OFFLOAD'})
        assert done.json()['results'][0]['ok']
        video=client.get(f'/api/jobs/{job["id"]}/artifacts/lesson.mp4')
        assert video.status_code==200 and video.content==b'video contents'
        assert client.get(f'/api/jobs/{job["id"]}/artifacts/../../config.json').status_code==404
        assert client.post(f'/api/jobs/{job["id"]}/restore',json={}).status_code==200
