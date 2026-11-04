"""Independent structural admission of the team's frozen coordinate proposal.

Literal expectations come from PREVIOUS-PROTOCOL, never the generator's ARMS or
its accepted flag. This converts existing coordinates; it does not generate,
repair, resample, grant execution budget, or establish scientific utility.
"""
import copy
import hashlib

from .prototype import digest, require
from asr_service.paired_sampling import validate, fingerprint
from asr_service.study import coordinate

SEEDS = tuple(range(1101, 1109))
BLOCK_COUNTS = {'T0': 32, 'TA': 16, 'TB': 16, 'B': 16, 'G': 16}
ARM_ORDER = {'TT': ['T0', 'TA', 'TB'], 'BT': ['T0', 'B', 'TB'],
             'TG': ['T0', 'TA', 'G'], 'BG': ['T0', 'B', 'G']}


def convert(candidate, materials, *, expected_candidate_sha256):
    require(digest(candidate) == expected_candidate_sha256, 'external candidate pin mismatch')
    require(candidate['seeds'] == list(SEEDS), 'literal seed set mismatch')
    public = set()
    for name, count in (('train', 128), ('id_dev', 32), ('diagnostic', 32)):
        points = [list(coordinate(row['x'])) for row in materials[name]]
        require(len(points) == count and candidate['inputs'][name] == dict(
            count=count, coordinate_sha256=digest(points)), 'public input pin mismatch')
        public.update(tuple(round(v, 6) for v in x) for x in points)
    proposed = candidate['paired_sampling']
    require(proposed['status'] == 'proposed-not-admitted', 'proposal status mismatch')
    groups = proposed['groups']
    require([g['group_id'] for g in groups] == [str(s) for s in SEEDS], 'literal group sequence mismatch')
    require([b['seed'] for b in candidate['batches']] == list(SEEDS), 'literal batch sequence mismatch')
    native = {}
    for seed, group, batch in zip(SEEDS, groups, candidate['batches']):
        blocks = group['shared_blocks']
        require(set(blocks) == set(BLOCK_COUNTS), 'literal block names mismatch')
        for name, count in BLOCK_COUNTS.items():
            require(len(blocks[name]) == count, 'literal block count mismatch')
            for x in blocks[name]:
                point = coordinate(x)
                require(all(v == round(v, 6) for v in point), 'coordinate precision mismatch')
                require(point not in public, 'public coordinate collision')
        require(batch['blocks'] == blocks and batch['block_sha256'] == digest(blocks), 'batch block correspondence mismatch')
        require(batch['stream_seeds'] == {name: 10 * seed + k for k, name in enumerate(BLOCK_COUNTS)},
                'literal stream seeds mismatch')
        require([a['arm_id'] for a in group['arms']] == list(ARM_ORDER), 'literal arm sequence mismatch')
        for arm in group['arms']:
            names = ARM_ORDER[arm['arm_id']]
            require(arm['block_order'] == names, 'literal arm order mismatch')
            require(arm['coordinates'] == [x for name in names for x in blocks[name]],
                    'arm coordinate correspondence mismatch')
        native[str(seed)] = dict(blocks=copy.deepcopy(blocks), arms=copy.deepcopy(ARM_ORDER))
    policy = dict(schema='asr-paired-sampling/1', proposal_sha256=expected_candidate_sha256,
                  purpose='augmentation', charging='each_slot_no_retries', groups=native)
    # Structural check only. These counts are not a budget grant or reservation.
    validate(policy, dict(attempts=32, sample_proposals=2048))
    return policy


def from_trial(service, token, project, run, trial_id, *, expected_manifest_sha256,
               expected_source_sha256, expected_candidate_sha256):
    """Bind conversion to actual authenticated, immutable analysis evidence."""
    from .training_adapter import read_trial
    record = read_trial(service, token, project, run, trial_id)
    require(record['reference']['manifest_hash'] == expected_manifest_sha256, 'analysis manifest pin mismatch')
    require(record['trial']['variables']['operation'] == 'analysis', 'analysis operation required')
    request = record['payload']['request']
    require(request['operation'] == 'analysis' and
            hashlib.sha256(request['source'].encode()).hexdigest() == expected_source_sha256,
            'generator source pin mismatch')
    candidate = record['result']['author_output']['result']['candidate']
    policy = convert(candidate, record['payload']['materials'], expected_candidate_sha256=expected_candidate_sha256)
    return dict(schema='asr-generator-protocol-binding/1', source_evidence=record['reference'],
                source_sha256=expected_source_sha256, candidate_sha256=expected_candidate_sha256,
                policy=policy, protocol_sha256=fingerprint(policy), group_seeds={str(s): s for s in SEEDS},
                unique_coordinates=768, proposed_label_slots=2048, label_batches=32,
                authority='proposal-only; requires new Control contract and explicit execution budget',
                scope='independent structure and immutable evidence checks; no RNG regeneration or utility validation')
