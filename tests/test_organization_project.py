import copy
import json
from pathlib import Path
import tempfile
import unittest


class ProjectEntryTests(unittest.TestCase):
    def spec(self):
        return dict(schema='asr-research-project/1',title='Example',objective=dict(question='Investigate robustness',success_criteria='Reproducible supported conclusion',scope='Declared data and model'),requirements=['Retain failed experiments'],deliverables=['Evidence-backed report'],materials={})

    def test_project_objective_and_requirements_drive_brief_without_history_recipe(self):
        from integrations.runtimes.organization_project import load_spec,brief
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'project.json';path.write_text(json.dumps(self.spec()))
            spec,materials=load_spec(path)
            text=brief(spec)
            self.assertIn('Investigate robustness',text);self.assertIn('Retain failed experiments',text)
            self.assertNotIn('33 models',text);self.assertNotIn('20 minutes',text)
            self.assertEqual(materials,{})
            changed=copy.deepcopy(spec);changed['objective']['question']='Investigate a different target'
            self.assertIn('Investigate a different target',brief(changed))

    def test_reference_materials_require_external_hash_and_safe_workspace_name(self):
        from integrations.runtimes.organization_project import load_spec
        from powerflow_lab.runner import digest
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.md';source.write_text('Historical suggestion, not required')
            spec=self.spec();spec['materials']={'HISTORY.md':dict(path=str(source),sha256=digest(source))}
            path=root/'project.json';path.write_text(json.dumps(spec))
            self.assertEqual(load_spec(path)[1]['HISTORY.md'],source)
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError,'material_pin'):load_spec(path)
            spec['materials']={'../escape.md':dict(path=str(source),sha256=digest(source))};path.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError,'workspace_material'):load_spec(path)

    def test_explicit_resource_policy_allows_science_without_fixed_paired_adapter(self):
        from integrations.runtimes.organization_project import resources,contract_fields
        path=Path('integrations/runtimes/organization-project-limits.json');policy=resources(path)
        fields=contract_fields(self.spec(),policy,{'image_id':'fixture'})
        self.assertEqual(fields['objective'],self.spec()['objective'])
        self.assertEqual(fields['provenance']['study_operations'],['analysis','label','fit'])
        self.assertNotIn('paired_adapter',fields['provenance']);self.assertNotIn('paired_sampling',fields['provenance'])
        self.assertGreater(policy['session_limits']['walltime_seconds'],240)

    def test_old_or_invalid_policy_cannot_silently_enable_project_operations(self):
        from integrations.runtimes.organization_project import resources
        value=json.loads(Path('integrations/runtimes/organization-project-limits.json').read_text())
        for field,bad in [('study_operations',['final']),('paid_api_fallback',True),('schema','asr-organization-implementation-resources/1')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as directory:
                altered=copy.deepcopy(value);altered[field]=bad;path=Path(directory)/'p.json';path.write_text(json.dumps(altered))
                with self.assertRaises(ValueError):resources(path)
