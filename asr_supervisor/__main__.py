"""Trusted local operator entry point for a single admitted attempt."""
import argparse
import json
from .store import ExecutionStore
from .supervisor import Supervisor


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True)
    parser.add_argument('--evidence-root',required=True)
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--owner',required=True)
    parser.add_argument('--reconcile',action='store_true')
    args=parser.parse_args()
    supervisor=Supervisor(ExecutionStore(args.db),args.evidence_root)
    action=supervisor.reconcile if args.reconcile else supervisor.execute
    print(json.dumps(action(args.attempt,args.owner),indent=2,allow_nan=False))


if __name__=='__main__':
    main()
