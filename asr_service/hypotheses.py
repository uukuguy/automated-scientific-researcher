"""Strict author hypothesis documents; validation makes no scientific judgement."""
import copy
from jsonschema import Draft202012Validator

HYPOTHESIS_SCHEMA = {
    '$schema':'https://json-schema.org/draft/2020-12/schema',
    '$id':'asr-hypothesis-document/1',
    'type':'object',
    'additionalProperties':False,
    'required':['statement','prediction','scope','refutation_criteria','study_type','change_reason','analysis_timing'],
    'properties':{
        **{key:{'type':'string','minLength':1,'maxLength':16384} for key in
           ('statement','prediction','scope','refutation_criteria','change_reason')},
        'study_type':{'enum':['exploratory','confirmatory']},
        'analysis_timing':{'enum':['prospective','post_hoc']},
    },
}
_VALIDATOR=Draft202012Validator(HYPOTHESIS_SCHEMA)


def validate_document(document):
    if next(_VALIDATOR.iter_errors(document),None) is not None:
        raise ValueError('invalid_hypothesis')
    if any(not document[key].strip() for key in ('statement','prediction','scope','refutation_criteria','change_reason')):
        raise ValueError('invalid_hypothesis')
    return copy.deepcopy(document)
