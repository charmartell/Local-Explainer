import argparse
import json
from pathlib import Path
from .config import settings
from .engine import Engine

def main():
    parser=argparse.ArgumentParser(description='Local source-grounded learning videos')
    parser.add_argument('command',choices=['serve','doctor','plan','status','approve','produce','resume','cancel','revise'])
    parser.add_argument('job',nargs='?'); parser.add_argument('--request'); parser.add_argument('--outline-hash'); parser.add_argument('--instruction'); parser.add_argument('--scene-id'); parser.add_argument('--port',type=int,default=8090)
    args=parser.parse_args()
    if args.command=='serve':
        import uvicorn
        from .api import make_app
        app=make_app(); server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=args.port))
        app.state.shutdown=lambda:setattr(server,'should_exit',True)
        server.run(); return
    engine=Engine(settings())
    try:
        if args.command=='doctor': result=engine.doctor()
        elif args.command=='status': result=engine.store.get(args.job) if args.job else engine.store.list()
        elif args.command=='plan':
            from .api import LessonRequest
            request=LessonRequest.model_validate_json(Path(args.request).read_text(encoding='utf-8')).model_dump()
            result=engine.store.create(request); engine.guard(result['id'],engine.plan); result=engine.store.get(result['id'])
        elif args.command=='approve': result=engine.approve(args.job,args.outline_hash)
        elif args.command in ('produce','resume'):
            action=engine.produce if args.command=='produce' or engine.store.get(args.job).get('approval') else engine.plan
            engine.guard(args.job,action); result=engine.store.get(args.job)
        elif args.command=='cancel': result=engine.cancel(args.job)
        else:
            result=engine.adjust(args.job,args.instruction,args.scene_id); engine.futures[result['id']].result(); result=engine.store.get(result['id'])
        print(json.dumps(result,indent=2,ensure_ascii=False))
        if isinstance(result,dict) and result.get('status')=='failed': raise SystemExit(1)
    finally: engine.close()

if __name__=='__main__': main()
