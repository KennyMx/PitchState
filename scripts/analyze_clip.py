"""Run and report the real pipeline; credentials load only from an ignored local file."""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv
from server.pitchstate.pipeline import analyze

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('video',type=Path)
    parser.add_argument('--output',type=Path,default=Path('.local/analysis.json'))
    parser.add_argument('--seconds',type=float,default=30)
    parser.add_argument('--fps',type=float,default=5)
    parser.add_argument('--jev',action='store_true')
    parser.add_argument('--home-attacks-left',action='store_true')
    args=parser.parse_args();load_dotenv('.env.local')
    result=analyze(args.video,output=args.output,duration_limit=args.seconds,sample_fps=args.fps,use_jev=args.jev,home_attacks_right=not args.home_attacks_left,progress=lambda p:print(json.dumps(p),flush=True))
    print(json.dumps(result['quality'],indent=2))
