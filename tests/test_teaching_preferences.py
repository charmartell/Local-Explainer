import json
import jsonschema
import pytest
from pydantic import ValidationError
from explainer.api import LessonRequest
from explainer.authoring import outline, chapter_scenes
from explainer.config import REPO


def test_preferences_validate_and_survive_request_serialization():
    request=LessonRequest(topic='Queue processing',explanation_styles=['analogy'],visual_preferences=['comparison'],visual_direction='Show before and after')
    assert request.model_dump()['visual_direction']=='Show before and after'
    with pytest.raises(ValidationError):
        LessonRequest(topic='Queue processing',visual_preferences=['interactive'])


def test_preferences_reach_outline_and_scenes_and_comparison_schema():
    evidence={'sources':[{'id':'src','kind':'document'}],'gaps':[],'passages':[{'id':'ev1','source_id':'src','title':'Queues','kind':'document','start_line':1,'text':'Before processing a message waits in a queue. After processing it is complete.'}]}
    request=LessonRequest(topic='My video title',visual_preferences=['comparison'],explanation_styles=['step_by_step'],visual_direction='Show before and after').model_dump()
    request['_beat_count']=2
    prompts=[]
    class Models:
        def json(self,system,prompt,checkpoint,max_tokens,schema=None):
            prompts.append(prompt)
            if 'Check these draft scenes' in prompt:
                return {'supported':True,'issues':[]}
            if schema:
                return {'scenes':[{'title':'Waiting' if i==0 else 'Completion','teaching_goal':'Follow processing','narration':'A message waits before processing.','evidence_ids':['ev1'],'kind':'documented_behavior','qualification':'','visual_type':'comparison','labels':['Before: waiting','After: complete'],'links':[],'image_prompt':'','code_evidence_id':'','code_line_offset':0} for i in range(2)]}
            return {'title':'Model renamed this','beats':[{'title':'Queue','focus':'Before processing','evidence_ids':['ev1']},{'title':'Done','focus':'After processing','evidence_ids':['ev1']}],'outcome':'Follow processing','visuals':'Before and after tables','gaps':[]}
    plan=outline(request,evidence,Models(),lambda:None)
    assert plan['title']=='My video title'
    scenes,claims,_=chapter_scenes(plan['beats'][0],0,request,evidence,Models(),lambda:None)
    for prompt in prompts[:3]:
        assert 'Show before and after' in prompt
        assert 'step_by_step' in prompt
    schema=json.loads((REPO/'explainer/schemas/lesson.schema.json').read_text())
    visual_schema={'$defs':schema['$defs'],'$ref':'#/$defs/visual'}
    for scene in scenes:
        assert scene['visual']['type']=='comparison'
        assert scene['visual']['rows'][0]['cells']==['Before','waiting']
        jsonschema.validate(scene['visual'],visual_schema)
