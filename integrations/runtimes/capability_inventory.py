"""Explicit supported role inventories shared by runtime and bridge gates."""

SMOKE_TOOLS = frozenset({'asr.state','asr.publish_hypothesis','asr.submit_trial','asr.publish_finding',
                         'asr.snapshot','asr.ack_guidance','asr.resolve_library','asr.query_docs','asr.search_literature'})
PROFILE_TOOLS = {
    'research-organization/1': frozenset({'asr.state','asr.organization_records','asr.organization_change','asr.research_note','asr.snapshot'}),
    'research-organization-study/1': frozenset({'asr.state','asr.organization_records','asr.organization_change','asr.research_note',
        'asr.snapshot','asr.publish_hypothesis','asr.publish_finding','asr.ack_guidance','asr.submit_study'}),
    'powerflow-calibration-smoke/3': SMOKE_TOOLS,
    'powerflow-candidate-research/1': SMOKE_TOOLS | {'asr.freeze_candidate','asr.submit_candidate','asr.request_evaluation','asr.request_replication'},
    'ood-project-intake/1': frozenset({'asr.state','asr.publish_hypothesis','asr.snapshot','asr.ack_guidance'}),
    'ood-study-development/1': frozenset({'asr.state','asr.publish_hypothesis','asr.publish_finding',
                                        'asr.snapshot','asr.ack_guidance','asr.submit_study'}),
    'ood-study-synthesis/1': frozenset({'asr.state','asr.publish_hypothesis','asr.publish_finding',
                                      'asr.snapshot','asr.ack_guidance'}),
    'powerflow-readonly-finalization/1': frozenset({'asr.state'}),
}
PROFILE_CODING_TOOLS={profile:['pi.read','pi.edit','pi.write','pi.grep','pi.find','pi.ls'] for profile in PROFILE_TOOLS}
PROFILE_CODING_TOOLS['powerflow-readonly-finalization/1']=['pi.read','pi.grep','pi.find','pi.ls']
