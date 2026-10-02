from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .config import settings
from .engine import Engine
from .library import Library
from .sources import Sources
from .desktop import pick
from .voices import available, validate as validate_voice, VoicePreviews

class LessonRequest(BaseModel):
    topic:str=Field(min_length=3,max_length=500)
    inputs:list[str]=Field(default_factory=list,max_length=20)
    goal:str=Field(default='Understand the mechanism and its tradeoffs',max_length=2000)
    audience:str=Field(default='Curious builder; explain unfamiliar terms',max_length=500)
    minutes:int=Field(default=8,ge=1,le=20)
    mode:Literal['offline','research']='offline'
    voice:str|None=Field(default=None,max_length=60)
    detail_level:Literal['shortform','standard','longform']='standard'
    kind:Literal['lesson','demo']='lesson'
    explanation_styles:list[Literal['step_by_step','analogy','worked_example','why_it_works','tradeoffs','recap']]=Field(default_factory=list,max_length=6)
    visual_preferences:list[Literal['diagram','sequence','state','code','illustration','comparison','recap']]=Field(default_factory=list,max_length=7)
    visual_direction:str=Field(default='',max_length=2000)

def make_app(config=None):
    config=config or settings(); config.prepare(); engine=Engine(config,recover=True)
    library=Library(engine); sources=Sources(config); previews=VoicePreviews(config)
    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.close()
    app=FastAPI(title='Local Explainer',lifespan=lifespan)
    app.state.engine=engine
    @app.middleware('http')
    async def local_boundary(request:Request,call_next):
        host=request.headers.get('host','').split(':')[0]
        if host not in ('127.0.0.1','localhost','testserver'): return JSONResponse({'detail':'Local requests only'},status_code=403)
        origin=request.headers.get('origin')
        if origin and origin not in (f'http://{request.headers.get("host")}',f'https://{request.headers.get("host")}'):
            return JSONResponse({'detail':'Cross-origin requests are not allowed'},status_code=403)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-store'
        return response
    @app.exception_handler(ValueError)
    async def bad_request(request,exc): return JSONResponse({'detail':str(exc)},status_code=409)
    @app.exception_handler(KeyError)
    async def missing(request,exc): return JSONResponse({'detail':str(exc)},status_code=404)
    @app.get('/api/health')
    def health(): return {'application':'local-explainer',**engine.doctor()}
    @app.post('/api/shutdown')
    def shutdown():
        stop=getattr(app.state,'shutdown',None)
        if not stop: raise ValueError('This server is not managed by the application launcher')
        stop()
        return {'status':'stopping'}
    @app.get('/api/jobs')
    def jobs(): return engine.store.list()
    @app.post('/api/jobs')
    def create(body:LessonRequest):
        if body.voice: validate_voice(config,body.voice)
        return engine.create(body.model_dump())
    @app.get('/api/voices')
    def voices(): return {'voices':available(config),'default':config.voice}
    @app.get('/api/voices/{voice}/preview')
    @app.post('/api/voices/{voice}/preview')
    def voice_preview(voice:str): return FileResponse(previews.sample(voice),media_type='audio/wav')
    class Picker(BaseModel): kind:Literal['folder','files']='folder'
    @app.post('/api/picker')
    def picker(body:Picker): return pick(body.kind)
    @app.post('/api/sources')
    def source_batch(): return sources.create()
    @app.put('/api/sources/{key}')
    async def source_upload(key:str,request:Request,path:str): return await sources.upload(key,path,request)
    @app.post('/api/sources/{key}/finish')
    def source_finish(key:str): return sources.finish(key)
    @app.get('/api/library')
    def library_summary(): return library.summary()
    class StoragePreview(BaseModel):
        ids:list[str]=Field(min_length=1,max_length=200)
        action:Literal['delete','offload']
        destination:str|None=None
    @app.post('/api/storage/preview')
    def storage_preview(body:StoragePreview): return library.preview(body.ids,body.action,body.destination)
    class StorageExecute(BaseModel): token:str; confirmation:str
    @app.post('/api/storage/execute')
    def storage_execute(body:StorageExecute): return library.execute(body.token,body.confirmation)
    @app.post('/api/jobs/{job_id}/restore')
    def restore(job_id:str): return library.restore(job_id)
    class Label(BaseModel): kind:Literal['lesson','demo']
    @app.post('/api/jobs/{job_id}/label')
    def label(job_id:str,body:Label): return engine.store.update(job_id,label=body.kind)
    @app.get('/api/jobs/{job_id}')
    def status(job_id:str): return engine.store.get(job_id)
    class Approval(BaseModel): outline_hash:str
    @app.post('/api/jobs/{job_id}/approval')
    def approve(job_id:str,body:Approval): return engine.approve(job_id,body.outline_hash)
    @app.post('/api/jobs/{job_id}/production')
    def produce(job_id:str):
        job=engine.store.get(job_id)
        if job['status']!='approved': raise ValueError('Approve the current outline before generating')
        return engine.submit(job_id,engine.produce)
    @app.post('/api/jobs/{job_id}/cancel')
    def cancel(job_id:str): return engine.cancel(job_id)
    @app.post('/api/jobs/{job_id}/resume')
    def resume(job_id:str): return engine.resume(job_id)
    class Revision(BaseModel):
        instruction:str=Field(min_length=3,max_length=2000)
        scene_id:str|None=None
        request:LessonRequest|None=None
    @app.post('/api/jobs/{job_id}/revisions')
    def revise(job_id:str,body:Revision): return engine.adjust(job_id,body.instruction,body.scene_id,body.request.model_dump() if body.request else None)
    @app.get('/api/jobs/{job_id}/evidence')
    def evidence(job_id:str): return engine.store.read(job_id,'evidence.json')
    @app.get('/api/jobs/{job_id}/artifacts/{artifact}')
    def artifact(job_id:str,artifact:str):
        job=engine.store.get(job_id)
        try: file=library.artifact_path(job,artifact)
        except (ValueError,OSError): raise HTTPException(404,'Artifact unavailable')
        if not file.is_file(): raise HTTPException(404,'Artifact unavailable')
        return FileResponse(file,filename=file.name if artifact.endswith(('.srt','.json')) else None)
    app.mount('/',StaticFiles(directory=Path(__file__).parent/'static',html=True),name='ui')
    return app
