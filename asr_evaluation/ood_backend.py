"""Final evaluator uses a distinct admission profile and a fresh offline container."""
from asr_supervisor.study import StudyBackend


class OODFinalBackend(StudyBackend):
    profile='ood-independent-final/1'
    operations=('final',)


class IsolatedConfirmationBackend(StudyBackend):
    """Uses the contract's output allowance; never mounts a research workspace."""
    profile='ood-isolated-confirmation/1'
    operations=('isolated_final',)
    worker_module='asr_evaluation.isolated_worker'

    def __init__(self,image_id,*,output_bytes):
        if type(output_bytes) is not int or output_bytes<1:raise ValueError('explicit contract output allowance required')
        super().__init__(image_id)
        self.output_bytes=output_bytes

    def finalize(self,path,request,status):
        import json
        from pathlib import Path
        from asr_evaluation.isolated_confirmation import verify, SPLITS
        from powerflow_lab.runner import canonical
        result=super().finalize(path,request,status)
        if status!='succeeded' or result:return result
        try:
            payload=json.loads((Path(path)/'study-input.json').read_text())
            p=verify(payload['request'],payload['materials'])
            events=json.loads((Path(path)/'study-events.json').read_text())
            expected=[(split,i) for split in SPLITS for i in range(p['counts'][split])]
            if [(e.get('split'),e.get('index')) for e in events[:-1]]!=expected:raise ValueError('incomplete isolated sample evidence')
            summary=events[-1]['result']
            if summary.get('schema')!='asr-isolated-confirmation-result/1' or summary.get('protocol_sha256')!=payload['request']['protocol_sha256']:
                raise ValueError('isolated result identity mismatch')
        except (ValueError,KeyError,TypeError,OSError) as error:
            (Path(path)/'study-output-error.json').write_bytes(canonical(dict(error_type=type(error).__name__,message=str(error),task_retained=True)))
            return dict(status='failed')
