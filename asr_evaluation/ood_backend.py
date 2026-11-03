"""Final evaluator uses a distinct admission profile and a fresh offline container."""
from asr_supervisor.study import StudyBackend


class OODFinalBackend(StudyBackend):
    profile='ood-independent-final/1'
    operations=('final',)
