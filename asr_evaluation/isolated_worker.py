"""Offline entry point; no changes to the pinned research training worker."""
import argparse
import json
from pathlib import Path
from .isolated_confirmation import execute


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path)
    args=parser.parse_args()
    payload=json.loads(args.input.read_text())
    def emit(event):
        print('ASR_OOD_EVENT_V1:'+json.dumps(event,sort_keys=True,separators=(',',':'),allow_nan=False),flush=True)
    try:
        result=execute(payload['request'],payload['materials'],emit)
        emit(dict(type='result',result=result))
    except Exception as error:
        emit(dict(type='error',error_type=type(error).__name__,message=str(error)))
        raise SystemExit(1)


if __name__=='__main__':main()
