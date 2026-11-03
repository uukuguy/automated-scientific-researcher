"""Explicit supported role inventories shared by runtime and bridge gates."""

SMOKE_TOOLS = frozenset({'asr.state','asr.publish_hypothesis','asr.submit_trial','asr.publish_finding',
                         'asr.snapshot','asr.ack_guidance','asr.resolve_library','asr.query_docs','asr.search_literature'})
PROFILE_TOOLS = {
    'powerflow-calibration-smoke/3': SMOKE_TOOLS,
    'powerflow-candidate-research/1': SMOKE_TOOLS | {'asr.freeze_candidate','asr.submit_candidate','asr.request_evaluation','asr.request_replication'},
}
