"""Explicit, replayable model-only resource revision using the owning Control API."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import secrets

from powerflow_lab.runner import canonical, digest
from .pi import Limits

MODEL_DIMENSIONS = ('research_walltime_ms', 'turns', 'tool_executions')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(canonical(value))
    temporary.replace(path)


def revise_model_policy(service, token, project, run, root, policy, reason, *, previous_policy_path=None):
    """Caller explicitly authorizes this revision; never called by timeout recovery."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('explicit_resource_revision_reason_required')
    Limits(**policy['session_limits'])
    identity = hashlib.sha256(canonical([project, run, policy, reason])).hexdigest()
    directory = root / 'resource-revisions' / identity
    intent_path = directory / 'intent.json'
    state = service.get_run(token, project, run)
    if (state['state'] != 'paused' or state['health'] != 'ok'
            or any(s['state'] != 'exited' or not s.get('execution_exited') for s in state['runtime_sessions'])
            or any(b['reserved'] for b in state['budget'].values())):
        raise ValueError('reconcile_before_resource_revision')
    if intent_path.exists():
        intent = json.loads(intent_path.read_text())
        if intent['policy'] != policy or intent['reason'] != reason:
            raise ValueError('resource_revision_intent_changed')
    else:
        old = json.loads((root / 'resource-policy.json').read_text())
        expected = copy.deepcopy(old)
        for dimension in MODEL_DIMENSIONS:
            amount = policy['budget'][dimension]
            if type(amount) is not int or amount < old['budget'][dimension]:
                raise ValueError('model_only_monotonic_revision_required')
            expected['budget'][dimension] = amount
        for key in old['session_limits']:
            if policy['session_limits'][key] < old['session_limits'][key]:
                raise ValueError('model_only_monotonic_revision_required')
        for key in ('session_limits', 'purpose', 'basis', 'exceedance'):
            expected[key] = policy[key]
        if expected != policy:
            raise ValueError('model_only_resource_revision_required')
        document = copy.deepcopy(state['contract']['document'])
        source = previous_policy_path or root / 'resource-policy.json'
        if (document['budget'] != old['budget'] or
                json.loads(source.read_text()) != old or
                document['provenance']['resource_policy_sha256'] != digest(source)):
            raise ValueError('resource_policy_contract_mismatch')
        document['budget'] = copy.deepcopy(policy['budget'])
        document['provenance']['resource_policy_sha256'] = hashlib.sha256(canonical(policy)).hexdigest()
        intent = dict(project=project, run=run, reason=reason, policy=policy, prior_policy=old,
                      prior_contract=state['contract'], document=document,
                      control_revision=state['control_revision'], prior_budget=state['budget'])
        save(intent_path, intent)
    # Fixed request identities replay publication/application after an interrupted write.
    prior = intent['prior_contract']
    allowed = ((prior['revision'], prior['document']), (prior['revision'] + 1, intent['document']))
    if (state['contract_id'] != prior['contract_id'] or
            (state['contract_revision'], state['contract']['document']) not in allowed):
        raise ValueError('resource_revision_contract_drift')
    receipt_path = directory / 'receipt.json'
    if receipt_path.exists():
        if (state['contract_revision'] != prior['revision'] + 1 or
                json.loads((root / 'resource-policy.json').read_text()) != policy):
            raise ValueError('resource_revision_receipt_drift')
        return json.loads(receipt_path.read_text())
    published = service.publish_contract(token, project, prior['contract_id'], intent['document'],
        expected_revision=prior['revision'], idempotency_key='model-policy-publish-' + identity)
    applied = service.command(token, project, run, 'apply_contract', expected_revision=intent['control_revision'],
        idempotency_key='model-policy-apply-' + identity,
        payload=dict(contract_id=prior['contract_id'], revision=published['revision']))
    save(root / 'resource-policy.json', policy)
    receipt = dict(reason=reason, contract_revision=published['revision'], command=applied,
                   prior_budget=intent['prior_budget'], budget=service.get_run(token, project, run)['budget'])
    save(receipt_path, receipt)
    return receipt


def main():
    from asr_service.control import ControlService
    from .organization_implementation import resources
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--limits', type=Path, required=True)
    parser.add_argument('--reason', required=True)
    parser.add_argument('--previous-limits', type=Path, help='Exact original policy source if the local saved copy was reformatted')
    args = parser.parse_args()
    identity = json.loads((args.root / 'identity.json').read_text())
    token = secrets.token_urlsafe(32)
    service = ControlService(args.root / 'control.db', credentials={token: dict(
        subject='human-resource-revision', role='human', projects=[identity['project_id']])})
    receipt = revise_model_policy(service, token, identity['project_id'], identity['research_run_id'],
                                  args.root, resources(args.limits), args.reason, previous_policy_path=args.previous_limits)
    print(json.dumps(dict(contract_revision=receipt['contract_revision'], budget=receipt['budget'])))


if __name__ == '__main__':
    main()
