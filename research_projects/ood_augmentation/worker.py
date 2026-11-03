"""Frozen experiment primitives, invoked only with controller-bound materials.

This module is not admission/authentication. The owning service must freeze and
authenticate material identities before launching it in an isolated container.
It selects no coordinates, hypotheses, seeds, experimental arms or models.
"""
import argparse
import json
import math
from pathlib import Path

from research_projects.ood_augmentation import project

PREFIX = 'ASR_OOD_EVENT_V1:'
MAX_BATCH = 64


def coordinate(value):
    if (type(value) is not list or len(value) != 3 or
        any(type(x) not in (int, float) or not math.isfinite(x) or not .7 <= x <= 1.6 for x in value)):
        raise ValueError('three finite regional multipliers in [0.7,1.6] required')
    return tuple(float(x) for x in value)


def verify_label(case, row):
    """Rebuild the problem and check equations instead of trusting row metrics."""
    from powerflow_lab.validation import validate
    original = project.make_scenario(case, list(coordinate(row['x'])))
    if row['input_sha256'] != project.digest(original) or row['input'] != original:
        raise ValueError('label original-input mismatch')
    if row['status'] != 'labelled':
        if row.get('y') is not None:
            raise ValueError('unsuccessful label has a target')
        return False
    solution = row['solution']
    if row['solution_sha256'] != project.digest(solution):
        raise ValueError('label solution mismatch')
    if not validate(original, solution, 1e-7)['equation_valid']:
        raise ValueError('label equations invalid')
    expected = [b[7] for b in solution['bus']] + [b[8] for b in solution['bus']]
    if row['y'] != expected:
        raise ValueError('label target differs from independently checked solution')
    return True


def execute(request, materials, emit):
    operation = request.get('operation')
    case = materials['case']
    if operation == 'analysis':
        if set(request) != {'operation', 'source'} or type(request['source']) is not str or not 0 < len(request['source'].encode()) <= 65536:
            raise ValueError('analysis requires at most 65536 UTF-8 source bytes')
        # This branch is untrusted author computation. It is ONLY launched in
        # the offline disposable container, never by the host Control service.
        # Its result cannot be used as a label or model training dependency.
        namespace = {'__name__': '__asr_analysis__'}
        exec(compile(request['source'], 'analysis.py', 'exec'), namespace)
        output = namespace['main'](materials)
        project.canonical(output)
        return dict(operation='analysis', author_output=output, independently_validated=False)
    if operation == 'label':
        if set(request) != {'operation', 'purpose', 'coordinates'} or request['purpose'] not in ('augmentation', 'probe'):
            raise ValueError('label purpose must be augmentation or probe')
        values = request['coordinates']
        if type(values) is not list or not 1 <= len(values) <= MAX_BATCH:
            raise ValueError('label batch must contain 1..64 proposals; split larger batches without dropping rows')
        coordinates = [coordinate(x) for x in values]
        if len(set(coordinates)) != len(coordinates):
            raise ValueError('duplicate coordinates within batch')
        labelled = 0
        for index, x in enumerate(coordinates):
            row = project.solve_sample(case, list(x), f'proposal-{index:04d}')
            emit(dict(type='sample', index=index, row=row))
            labelled += row['status'] == 'labelled'
        return dict(operation=operation, purpose=request['purpose'], proposed=len(values), labelled=labelled)
    if operation == 'fit':
        if set(request) != {'operation'}:
            raise ValueError('fixed trainer accepts no hyperparameter overrides')
        batches = materials['augmentation']
        if any(batch['purpose'] != 'augmentation' for batch in batches):
            raise ValueError('only augmentation batches may train the model')
        original = materials['train']
        seen = {coordinate(row['x']) for name in ('train', 'id_dev', 'diagnostic') for row in materials[name]}
        added = []
        proposed = 0
        for batch in batches:
            for row in batch['rows']:
                key = coordinate(row['x'])
                if key in seen:
                    raise ValueError('duplicate training/development coordinate')
                seen.add(key)
                proposed += 1
                if verify_label(case, row):
                    added.append(row)
        # Original client rows are authenticated by the service against its
        # frozen package; additional rows are rechecked from full raw evidence.
        training = [r for r in original if r['status'] == 'labelled'] + added
        if any(len(r['y']) != 2 * len(case['bus']) for r in training):
            raise ValueError('target dimension mismatch')
        model = project.fit([r['x'] for r in training], [r['y'] for r in training])
        return dict(operation=operation, model=model, augmentation_proposed=proposed,
                    augmentation_labelled=len(added), development={
                        name: project.metrics(model, materials[name], case)
                        for name in ('id_dev', 'diagnostic')})
    raise ValueError('unsupported study operation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    def emit(event):
        print(PREFIX + project.canonical(event).decode(), flush=True)
    try:
        result = execute(payload['request'], payload['materials'], emit)
        emit(dict(type='result', result=result))
    except Exception as error:
        # Already-emitted rows survive a later failure or external interruption.
        emit(dict(type='error', error_type=type(error).__name__, message=str(error)))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
