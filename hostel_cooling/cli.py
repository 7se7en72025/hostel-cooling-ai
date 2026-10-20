import argparse
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description="Combined CE F417 / CE F423 hostel cooling prototype")
    sub=parser.add_subparsers(dest="command",required=True)
    serve=sub.add_parser("serve",help="Open local advisory dashboard")
    serve.add_argument("--port",type=int,default=8765);serve.add_argument("--llm",action="store_true")
    exp=sub.add_parser("experiment",help="Run reproducible synthetic policy comparison")
    exp.add_argument("--days",type=int,default=7);exp.add_argument("--seeds",type=int,nargs="+",default=[11,23,47])
    exp.add_argument("--output",default="outputs/demo");exp.add_argument("--llm",action="store_true",help="Use actual Ollama extraction and B4; many local model requests")
    gen=sub.add_parser("sample-data");gen.add_argument("--output",default="data/synthetic_pilot.csv");gen.add_argument("--days",type=int,default=7)
    validate=sub.add_parser("validate");validate.add_argument("csv")
    cal=sub.add_parser("calibrate");cal.add_argument("csv");cal.add_argument("--output",default="outputs/calibration.json")
    args=parser.parse_args()
    try:
        if args.command=="serve":
            from .server import serve
            from .llm import Ollama,Offline
            serve(args.port,Ollama() if args.llm else Offline())
        elif args.command=="experiment":
            from .experiment import run_experiment
            from .llm import Ollama
            result=run_experiment(args.output,args.days,tuple(args.seeds),Ollama() if args.llm else None)
            print(json.dumps({"output":str(Path(args.output).resolve()),"methods":len(result["rows"]),"provenance":result["provenance"],"skipped":result["skipped"]},indent=2))
        elif args.command=="sample-data":
            if not 1 <= args.days <= 60:
                raise ValueError("days must be 1..60")
            from .pilot import generate_pilot
            print(f"Wrote {generate_pilot(args.output,args.days)} synthetic rows to {args.output}")
        elif args.command=="validate":
            from .pilot import load_pilot
            rows=load_pilot(args.csv)
            print(json.dumps({"valid":True,"rows":len(rows),"provenance":rows[0][3]}))
        elif args.command=="calibrate":
            from .pilot import calibrate
            print(json.dumps(calibrate(args.csv,args.output),indent=2))
    except (ValueError,RuntimeError,FileNotFoundError,PermissionError) as error:
        parser.exit(2,f"Error: {error}\n")
