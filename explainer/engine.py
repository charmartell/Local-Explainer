import json
import os
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .store import Store,digest,write_json,now
from .inputs import collect
from .models import LocalModels
from .authoring import outline,chapter_scenes,validate_lesson
from .render import render_scene,export

class Cancelled(Exception): pass

class Engine:
    def __init__(self,config,recover=False):
        self.config=config; self.store=Store(config); self.models=LocalModels(config)
        self.pool=ThreadPoolExecutor(max_workers=1); self.cancelled={}; self.futures={}; self.lock=threading.RLock()
        # A restart cannot preserve live inference, but checkpoint artifacts remain resumable.
        if recover:
            for job in self.store.list():
                if job['status'] in ('planning','producing','queued'):
                    self.store.update(job['id'],status='interrupted',stage='Interrupted; resume from saved work')

    def checkpoint(self,job_id):
        if self.cancelled.get(job_id,threading.Event()).is_set(): raise Cancelled()

    def submit(self,job_id,action):
        with self.lock:
            if self.store.get(job_id).get('storage_state') == 'offloaded': raise ValueError('Restore this lesson before editing or generating it')
            if job_id in self.futures and not self.futures[job_id].done(): raise ValueError('This lesson is already running')
            self.cancelled[job_id]=threading.Event()
            self.futures[job_id]=self.pool.submit(self.guard,job_id,action)
        return self.store.get(job_id)

    def guard(self,job_id,action):
        try: action(job_id)
        except Cancelled:
            self.store.event(job_id,'Paused; completed work is saved',status='cancelled')
        except Exception as exc:
            self.store.event(job_id,'Needs attention',status='failed',error=str(exc))
            log=self.config.scratch/job_id/'failure.log'; log.parent.mkdir(parents=True,exist_ok=True)
            import traceback; log.write_text(traceback.format_exc(),encoding='utf-8')
        finally: self.models.stop()

    def create(self,request):
        job=self.store.create(request)
        return self.submit(job['id'],self.plan)

    def plan(self,job_id):
        self.checkpoint(job_id)
        self.store.event(job_id,'Reading sources',5,status='planning',error=None)
        job=self.store.get(job_id); cp=lambda:self.checkpoint(job_id)
        evidence_path=self.store.folder(job_id)/'evidence.json'
        evidence=self.store.read(job_id,'evidence.json') if evidence_path.exists() else collect(job['request'],self.config,cp,self.models.describe_image)
        self.store.artifact(job_id,'evidence.json',evidence); self.store.artifact(job_id,'sources.json',evidence['sources']); self.store.index(job_id,evidence['passages'])
        self.store.event(job_id,'Preparing your lesson outline',20)
        result=outline(job['request'],evidence,self.models,cp)
        self.store.artifact(job_id,'outline.json',result)
        self.store.update(job_id,status='awaiting_approval',stage='Review your outline',progress=25,outline=result,approval=None)

    def approve(self,job_id,outline_hash):
        with self.lock:
            job=self.store.get(job_id)
            if job['status']!='awaiting_approval': raise ValueError('Lesson is not awaiting outline approval')
            plan=self.store.read(job_id,'outline.json')
            if outline_hash!=plan['hash']: raise ValueError('Outline changed; review the current plan before generating')
            return self.store.update(job_id,status='approved',stage='Approved and ready',approval={'outline_hash':outline_hash,'time':now(),'actor':'user'})

    def produce(self,job_id):
        self.checkpoint(job_id)
        job=self.store.get(job_id); plan=self.store.read(job_id,'outline.json')
        if not job.get('approval') or job['approval']['outline_hash']!=plan['hash']:
            raise ValueError('Approve the current outline before production')
        self.store.event(job_id,'Writing the lesson',28,status='producing',error=None)
        evidence=self.store.read(job_id,'evidence.json'); cp=lambda:self.checkpoint(job_id)
        folder=self.store.folder(job_id); scratch=self.config.scratch/job_id; scratch.mkdir(parents=True,exist_ok=True)
        request={**job['request'],'_beat_count':len(plan['beats'])}
        chapters=[]; scenes=[]; claims=[]; reviews=[]
        for index,beat in enumerate(plan['beats']):
            request['_other_chapter_focus']=[b['focus'] for b in plan['beats'] if b['id']!=beat['id']]
            request['_existing_scene_titles']=[s['title'] for s in scenes]
            cp(); chapter_file=folder/f'chapter-{index+1}.json'
            if chapter_file.exists(): result=json.loads(chapter_file.read_text(encoding='utf-8'))
            else:
                self.store.event(job_id,f'Writing and checking: {beat["title"]}',28+int(22*index/len(plan['beats'])))
                last_error=None
                for attempt in range(2):
                    try:
                        chapter_scene,chapter_claim,review=chapter_scenes(beat,index,request,evidence,self.models,cp)
                        result={'scenes':chapter_scene,'claims':chapter_claim,'review':review}; break
                    except ValueError as exc: last_error=exc
                else: raise last_error
                write_json(chapter_file,result)
            target=job.get('revision_scene')
            revision_checkpoint=folder/'revision-applied.json'
            if target and any(s['id']==target for s in result['scenes']) and not revision_checkpoint.exists():
                current=next(s for s in result['scenes'] if s['id']==target)
                if job.get('parent'): current=next(s for s in self.store.read(job['parent'],'lesson.json')['scenes'] if s['id']==target)
                self.store.event(job_id,f'Revising scene: {current["title"]}',40)
                for attempt in range(2):
                    try:
                        replacements,new_claims,review=chapter_scenes(beat,index,request,evidence,self.models,cp,current); break
                    except ValueError:
                        if attempt==1: raise
                old_claims={c for s in result['scenes'] if s['id']==target for v in s['narration'] for c in v['claim_ids']}
                result['scenes']=[replacements[0] if s['id']==target else s for s in result['scenes']]
                result['claims']=[c for c in result['claims'] if c['id'] not in old_claims]+new_claims
                result['review']=review
                write_json(chapter_file,result); write_json(revision_checkpoint,{'scene_id':target})
            chapters.append({'id':f'chapter_{index+1}','title':beat['title'],'outline_beat_id':beat['id']})
            scenes.extend(result['scenes']); claims.extend(result['claims']); reviews.append(result['review'])
        lesson={'schema_version':'1.0','lesson_id':job_id,'approved_outline_hash':plan['hash'],'title':plan['title'],'learning_outcomes':[plan['outcome']],'audience':plan['assumptions'],'style':{'theme_id':'editorial','illustration_direction':'Sophisticated editorial illustration, emerald, warm amber and charcoal palette, concrete objects, wide composition. No text, no words, no labels.','language':'en-US'},'chapters':chapters,'claims':claims,'scenes':scenes,'glossary':[]}
        validate_lesson(lesson,evidence,plan)
        self.store.artifact(job_id,'lesson.json',lesson)
        self.models.stop_llama()
        self.store.event(job_id,'Creating visual assets',52)
        assets={}
        for i,scene in enumerate(scenes):
            cp()
            if scene['visual']['type']=='illustration':
                path=folder/(scene['id']+'.png'); key=digest({'visual':scene['visual'],'style':lesson['style']})
                manifest=folder/(scene['id']+'.asset.json')
                cached=manifest.exists() and json.loads(manifest.read_text(encoding='utf-8')).get('input_hash')==key and path.exists()
                if not cached:
                    self.store.event(job_id,f'Illustrating: {scene["title"]}',52+int(8*i/len(scenes)))
                    self.models.illustrate(scene['visual']['prompt']+' '+lesson['style']['illustration_direction'],path,int(digest(scene['id'].encode())[:8],16),cp)
                    write_json(manifest,{'input_hash':key,'path':str(path),'model':'FLUX.2 klein 4B','sha256':digest(path.read_bytes())})
                assets[scene['id']]=str(path)
        self.models.stop()
        self.store.artifact(job_id,'assets.json',assets)
        self.store.event(job_id,'Recording local narration',62)
        speech_dir=scratch/'speech'; speech_dir.mkdir(parents=True,exist_ok=True)
        segments=[v for scene in scenes for v in scene['narration']]
        # Each audio file is addressed by both text and voice so edits cannot reuse stale speech.
        mapped=[]
        voice=job['request'].get('voice') or self.config.voice
        from .voices import validate as validate_voice
        validate_voice(self.config,voice)
        for segment in segments:
            mapped.append({**segment,'original_id':segment['id'],'id':segment['id']+'_'+digest({'text':segment['speech_text'],'voice':voice})[:10]})
        speech=self.models.speech(mapped,speech_dir,cp,voice=voice)
        audio={original['original_id']:result for original,result in zip(mapped,speech)}
        self.store.artifact(job_id,'timeline.json',{'audio':audio})
        clips=[]; chapter_titles={c['id']:c['title'] for c in chapters}
        for i,scene in enumerate(scenes):
            cp(); self.store.event(job_id,f'Rendering: {scene["title"]}',68+int(23*i/len(scenes)))
            scene_dir=scratch/'scenes'/scene['id']; key=digest({'renderer_version':2,'scene':scene,'audio':{v['id']:{'duration':audio[v['id']]['duration'],'sha256':digest(Path(audio[v['id']]['path']).read_bytes())} for v in scene['narration']},'asset':digest(Path(assets[scene['id']]).read_bytes()) if scene['id'] in assets else None})
            checkpoint_file=scene_dir/'checkpoint.json'
            if checkpoint_file.exists(): cached=json.loads(checkpoint_file.read_text(encoding='utf-8'))
            else: cached={}
            if cached.get('input_hash')==key and Path(cached.get('clip',{}).get('path','missing')).is_file(): clip=cached['clip']
            else:
                clip=render_scene(scene,chapter_titles[scene['chapter_id']],audio,scene_dir,assets.get(scene['id']),cp)
                write_json(checkpoint_file,{'input_hash':key,'clip':clip})
            clips.append(clip)
        self.store.event(job_id,'Assembling and checking your video',94)
        package=scratch/'export'; report=export(lesson,clips,audio,package,cp)
        write_json(package/'quality-report.json',{**report,'evidence_reviews':reviews,'claim_count':len(claims),'schema_valid':True,'source_consistency':True,'limitations':['Evidence support includes a local model review; it is not a proof of semantic correctness.','Caption timing is estimated within each sentence from its measured audio duration.']})
        write_json(package/'lesson.json',lesson)
        write_json(package/'sources.json',evidence['sources'])
        # Useful, compact evidence for the viewer; source code stays in the durable lesson snapshot.
        source_titles={s['id']:s for s in evidence['sources']}
        passage_map={p['id']:p for p in evidence['passages']}
        source_html=['<!doctype html><meta charset="utf-8"><title>Lesson sources</title><h1>Lesson sources</h1>']
        from .render import e
        for claim in claims:
            source_html.append('<h2>'+e(claim['id'])+'</h2><p>'+e(claim['statement'])+'</p><ul>')
            for ref in claim['evidence']:
                s=source_titles[ref['source_id']]; origin=s['origin']
                label=e(s['title'])
                if origin.startswith(('https://','http://')): label='<a href="'+e(origin)+'">'+label+'</a>'
                passage=passage_map[ref['evidence_id']]
                source_html.append('<li>'+label+' · lines '+str(passage['start_line'])+'–'+str(passage['end_line'])+' · '+e(ref['evidence_id'])+'<details><summary>Captured evidence</summary><pre style="white-space:pre-wrap">'+e(passage['text'])+'</pre></details></li>')
            source_html.append('</ul>')
        (package/'sources.html').write_text(''.join(source_html),encoding='utf-8')
        title=re.sub('[^a-zA-Z0-9-]+','-',lesson['title']).strip('-')[:60] or job_id
        final=self.config.builds/(title+'-'+job_id+f'-r{job["revision"]}')
        final.mkdir(parents=True,exist_ok=True)
        for file in package.iterdir():
            if file.suffix in ('.mp4','.srt','.vtt','.json','.html','.jpg','.txt') and file.name!='clips.txt': shutil.copy2(file,final/file.name)
        artifacts={file.name:str(file) for file in final.iterdir() if file.is_file()}
        self.store.update(job_id,status='complete',stage='Your video is ready',progress=100,artifacts=artifacts,error=None,duration=report['duration'],scenes=[{'id':s['id'],'title':s['title']} for s in scenes],chapters=report['chapters'])

    def cancel(self,job_id):
        if job_id in self.cancelled: self.cancelled[job_id].set()
        job=self.store.get(job_id)
        if job['status'] in ('awaiting_approval','approved','queued'): self.store.update(job_id,status='cancelled',stage='Cancelled')
        return self.store.get(job_id)

    def resume(self,job_id):
        job=self.store.get(job_id)
        if job['status'] not in ('failed','cancelled','interrupted','approved'): raise ValueError('This lesson does not need resuming')
        return self.submit(job_id,self.produce if job.get('approval') else self.plan)

    def adjust(self,job_id,instruction,scene_id=None):
        with self.lock:
            old=self.store.get(job_id)
            if old.get('storage_state') == 'offloaded': raise ValueError('Restore this lesson before making an adjustment')
            if old['status'] in ('queued','planning','producing'): raise ValueError('Pause the active job before adjusting it')
            if scene_id:
                if old['status']!='complete' or not old.get('approval'): raise ValueError('Scene revisions require a completed, approved lesson')
                lesson=self.store.read(job_id,'lesson.json')
                if scene_id not in {s['id'] for s in lesson['scenes']}: raise ValueError('Unknown scene')
            request={**old['request'],'goal':old['request'].get('goal','')+'\nRequested adjustment: '+instruction}
            new=self.store.create(request)
            self.store.update(new['id'],revision=old['revision']+1,parent=job_id)
            self.store.artifact(new['id'],'evidence.json',self.store.read(job_id,'evidence.json'))
            if scene_id:
                source=self.store.folder(job_id); destination=self.store.folder(new['id'])
                for file in source.iterdir():
                    if file.name in ('outline.json','sources.json') or file.name.startswith('chapter-') or file.suffix=='.png' or file.name.endswith('.asset.json'):
                        shutil.copy2(file,destination/file.name)
                for part in ('speech','scenes'):
                    cached=self.config.scratch/job_id/part
                    if cached.is_dir(): shutil.copytree(cached,self.config.scratch/new['id']/part,dirs_exist_ok=True)
                plan=self.store.read(job_id,'outline.json')
                self.store.update(new['id'],status='approved',outline=plan,approval={**old['approval'],'revision_instruction':instruction},revision_scene=scene_id)
                return self.submit(new['id'],self.produce)
            return self.submit(new['id'],self.plan)

    def doctor(self):
        import imageio_ffmpeg
        models=self.config.assets/'Models'
        return {'version':'0.1.0','local_only_inference':True,'llm':self.config.model.is_file() and self.config.llama.is_file(),'vision':all((models/'vision'/p).is_file() for p in ('Qwen3VL-4B-Instruct-Q4_K_M.gguf','mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf')),'speech':(models/'kokoro'/'kokoro-v1_0.pth').is_file() and self.config.python.is_file(),'images':all((models/'comfy'/p).is_file() for p in ('diffusion_models/flux-2-klein-4b.safetensors','text_encoders/qwen_3_4b_fp4_flux2.safetensors','vae/flux2-vae.safetensors')),'renderer':(self.config.assets/'Runtime'/'browsers').is_dir(),'ffmpeg':Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file(),'paths':{'assets':str(self.config.assets),'scratch':str(self.config.scratch),'builds':str(self.config.builds)}}

    def close(self):
        for event in self.cancelled.values(): event.set()
        self.pool.shutdown(wait=True,cancel_futures=True); self.models.stop()
