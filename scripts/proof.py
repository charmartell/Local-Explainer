"""Render a real local proof with exact visuals, local speech, and a generated image."""
import json
import shutil
import time
from pathlib import Path
from explainer.config import settings
from explainer.models import LocalModels
from explainer.render import render_scene,export
from explainer.store import write_json

def main():
    config=settings(); work=config.scratch/'proof'; work.mkdir(parents=True,exist_ok=True)
    models=LocalModels(config); started=time.monotonic()
    code='''def approve(outline_hash, current_hash):
    if outline_hash != current_hash:
        raise ValueError("Review the current outline")
    return {"approved": True}'''
    scripts=[
      ('A local lesson production pipeline','diagram','The source, outline, and lesson are separate artifacts.','A local explainer begins with source material, such as a repository or design document. It captures that material before writing the lesson, so the explanation remains attached to the version you actually reviewed. The next artifact is a short outline. Once you approve that outline, production creates narration and visuals. These separate stages can save their results, which lets the application resume after an interruption.'),
      ('Approval belongs to one outline revision','code','An exact hash check prevents approval of an outdated plan.','This small example checks whether the outline you approved is still the current outline. If the two hashes differ, it raises an error and asks for a new review. Only a matching hash reaches the approved result. The actual application keeps that approval in its local job database. This is useful when an outline changes between opening the review screen and pressing Generate. A completed video should follow the plan you saw.'),
      ('A local visual production workshop','illustration','Images illustrate ideas; the technical labels come from structured data.','The illustration was generated on this computer. It gives the lesson a concrete visual setting: reference books, a microphone, and a drawing table. Exact technical relationships still belong in diagrams and source excerpts, where labels and connections can be checked. Local speech provides the narration, and the encoder combines that audio with rendered scenes. The result is an ordinary video file with captions and chapters, ready to watch without a hosted video service.')
    ]
    scenes=[]
    for i,(title,kind,goal,text) in enumerate(scripts):
        sid=f'proof_{i+1}'
        if kind=='diagram':
            visual={'type':'diagram','nodes':[{'id':'source','label':'Source snapshot','role':'input'},{'id':'outline','label':'Approved outline','role':'review'},{'id':'video','label':'Local lesson video','role':'output'}],'edges':[{'id':'e1','from':'source','to':'outline','label':'Organize and review','claim_ids':['c1']},{'id':'e2','from':'outline','to':'video','label':'Produce locally','claim_ids':['c1']}]}
        elif kind=='code': visual={'type':'code','source_id':'proof','evidence_id':'approval','display_path':'Illustrative approval example','start_line':1,'language':'python','code':code,'regions':[]}
        else: visual={'type':'illustration','prompt':'','reference_asset_ids':[],'overlay_labels':[]}
        from explainer.authoring import split_speech
        voice=[{'id':sid+'_voice_'+str(k),'text':sentence,'speech_text':sentence,'claim_ids':['c1']} for k,sentence in enumerate(split_speech(text))]
        scenes.append({'id':sid,'chapter_id':'proof','title':title,'teaching_goal':goal,'narration':voice,'visual':visual,'cues':[]})
    lesson={'title':'Local Explainer Production Proof','chapters':[{'id':'proof','title':'Local production proof'}],'scenes':scenes}
    try:
        if not (work/'illustration.png').is_file():
            models.illustrate('A quiet editorial illustration of a local learning workshop, reference books, a desktop computer with microphone, drawing table, warm amber and emerald palette, wide composition, no text or labels',work/'illustration.png',42)
            models.stop()
        records=models.speech([s for scene in scenes for s in scene['narration']],work/'speech')
        audio={r['id']:r for r in records}
        clips=[render_scene(s,'Local production proof',audio,work/'scenes'/s['id'],work/'illustration.png' if s['visual']['type']=='illustration' else None) for s in scenes]
        report=export(lesson,clips,audio,work/'export')
        report.update(elapsed=time.monotonic()-started,local_speech=True,local_image=True,source='Implementation test fixture; not a user-approved subject lesson')
        write_json(work/'export'/'quality-report.json',report)
        target=config.builds/'Local-Explainer-Production-Proof'; target.mkdir(parents=True,exist_ok=True)
        for file in (work/'export').iterdir():
            if file.name!='clips.txt' and file.suffix in ('.mp4','.html','.json','.srt','.vtt','.jpg','.txt'): shutil.copy2(file,target/file.name)
        print(json.dumps({'path':str(target/'lesson.mp4'),'report':report},indent=2))
    finally: models.stop()

if __name__=='__main__':main()
