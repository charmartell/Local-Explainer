"""Kokoro worker using only explicit local weights, voices and language resources."""
import json
import os
import sys
import time
import socket
from pathlib import Path
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
# Speech uses explicit local resources. Fail any attempted dependency download.
def no_network(*args,**kwargs): raise RuntimeError('Speech worker is offline; install its language resources first')
socket.socket.connect=no_network
socket.create_connection=no_network
import numpy as np
import soundfile as sf
import torch
from kokoro import KModel, KPipeline

def main():
    request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    model_dir=Path(request['model']); out=Path(request['output']); out.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(6)
    model=KModel(config=str(model_dir/'config.json'),model=str(model_dir/'kokoro-v1_0.pth')).eval().to('cpu')
    pipeline=KPipeline(lang_code='a',model=model,device='cpu')
    voice=torch.load(model_dir/(request['voice']+'.pt'),weights_only=True,map_location='cpu')
    records=[]
    for segment in request['segments']:
        path=out/(segment['id']+'.wav'); start=time.monotonic()
        if path.exists():
            info=sf.info(path)
            records.append({'id':segment['id'],'path':str(path),'duration':info.duration,'cached':True}); continue
        chunks=[result.audio.numpy() for result in pipeline(segment['speech_text'],voice=voice,speed=0.98)]
        if not chunks: raise ValueError('No narration generated')
        audio=np.concatenate(chunks+[np.zeros(6000,dtype=np.float32)])
        temporary=path.with_suffix('.tmp.wav'); sf.write(temporary,audio,24000); temporary.replace(path)
        records.append({'id':segment['id'],'path':str(path),'duration':len(audio)/24000,'seconds':time.monotonic()-start,'peak':float(np.max(np.abs(audio)))})
    (out/'speech-result.json').write_text(json.dumps(records,indent=2),encoding='utf-8')

if __name__=='__main__': main()
