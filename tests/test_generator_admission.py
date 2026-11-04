"""Independent frozen-protocol checks, including the observed circular-oracle defect."""
import copy
import unittest
from research_projects.paired_acquisition.prototype import digest


def fixture():
    public={name:[dict(x=[1.4+i*.00001,1.3,1.2]) for i in range(n)] for name,n in [('train',128),('id_dev',32),('diagnostic',32)]}
    groups=[];batches=[];index=0
    for seed in range(1101,1109):
        blocks={}
        for name,n in [('T0',32),('TA',16),('TB',16),('B',16),('G',16)]:
            blocks[name]=[[round(.8+(index+i)*.0001,6),.9,1.] for i in range(n)];index+=n
        arms=[]
        for arm,names in [('TT',['T0','TA','TB']),('BT',['T0','B','TB']),('TG',['T0','TA','G']),('BG',['T0','B','G'])]:
            arms.append(dict(arm_id=arm,block_order=names,coordinates=[x for name in names for x in blocks[name]]))
        groups.append(dict(group_id=str(seed),shared_blocks=blocks,arms=arms))
        batches.append(dict(seed=seed,stream_seeds={name:seed*10+k for k,name in enumerate(['T0','TA','TB','B','G'])},blocks=blocks,block_sha256=digest(blocks)))
    c=dict(seeds=list(range(1101,1109)),inputs={name:dict(count=len(rows),coordinate_sha256=digest([r['x'] for r in rows])) for name,rows in public.items()},batches=batches,paired_sampling=dict(status='proposed-not-admitted',groups=groups))
    return c,public


class GeneratorAdmissionTests(unittest.TestCase):
    def setUp(self):self.c,self.public=fixture()

    def convert(self,c=None,expected=None):
        from research_projects.paired_acquisition.generator_admission import convert
        c=self.c if c is None else c
        return convert(c,self.public,expected_candidate_sha256=expected or digest(c))

    def test_native_protocol_preserves_all_slots_and_sharing(self):
        from asr_service.paired_sampling import validate
        old=copy.deepcopy(self.c);policy=self.convert();validate(policy,dict(attempts=32,sample_proposals=2048))
        self.assertEqual(self.c,old);self.assertEqual(len(policy['groups']),8)
        for source in self.c['paired_sampling']['groups']:
            native=policy['groups'][source['group_id']]
            for arm in source['arms']:
                self.assertEqual([x for name in native['arms'][arm['arm_id']] for x in native['blocks'][name]],arm['coordinates'])
        policy['groups']['1101']['blocks']['T0'][0][0]=1.6
        self.assertEqual(self.c,old)

    def test_wrong_order_rejected_even_when_self_hashes_are_recomputed(self):
        c=copy.deepcopy(self.c);group=c['paired_sampling']['groups'][0];arm=group['arms'][0]
        arm['block_order']=['TB','TA','T0'];arm['coordinates']=[x for n in arm['block_order'] for x in group['shared_blocks'][n]]
        with self.assertRaisesRegex(ValueError,'literal arm order'):self.convert(c)

    def test_external_pin_not_replaced_by_internal_claim(self):
        c=copy.deepcopy(self.c);c['seeds'][0]=999
        with self.assertRaisesRegex(ValueError,'candidate pin'):self.convert(c,digest(self.c))

    def test_rejects_seed_stream_count_and_reference_drift(self):
        for change in ('seed','stream','count','coordinate','group','batch'):
            with self.subTest(change=change):
                c=copy.deepcopy(self.c)
                if change=='seed':c['seeds'][0]=1100
                elif change=='stream':c['batches'][0]['stream_seeds']['T0']+=1
                elif change=='count':c['paired_sampling']['groups'][0]['shared_blocks']['T0'].pop()
                elif change=='coordinate':c['paired_sampling']['groups'][0]['arms'][0]['coordinates']=list(reversed(c['paired_sampling']['groups'][0]['arms'][0]['coordinates']))
                elif change=='group':c['paired_sampling']['groups'][1]['group_id']='1101'
                else:c['batches'][0]['block_sha256']='f'*64
                with self.assertRaises(ValueError):self.convert(c)

    def test_rejects_public_material_change_and_rounded_collision(self):
        self.public['train'][0]['x']=[.8000001,.9000001,1.0000001]
        with self.assertRaisesRegex(ValueError,'public input'):self.convert()
        self.c['inputs']['train']['coordinate_sha256']=digest([r['x'] for r in self.public['train']])
        with self.assertRaisesRegex(ValueError,'public coordinate collision'):self.convert()

    def test_rejects_cross_seed_duplicates_even_with_matching_copies(self):
        c=copy.deepcopy(self.c);point=copy.deepcopy(c['batches'][0]['blocks']['G'][0]);g=c['paired_sampling']['groups'][1]
        g['shared_blocks']['G'][0]=point;c['batches'][1]['block_sha256']=digest(g['shared_blocks'])
        for arm in g['arms']:arm['coordinates']=[x for n in arm['block_order'] for x in g['shared_blocks'][n]]
        with self.assertRaisesRegex(ValueError,'collision'):self.convert(c)


from pathlib import Path
import json
import secrets

@unittest.skipUnless(Path('artifacts/p5-implementation-001/control.db').is_file(), 'requires actual team analysis evidence')
class DeliveredGeneratorTests(unittest.TestCase):
    def setUp(self):
        from asr_service.control import ControlService
        self.receipt=json.loads(Path('docs/validation/P5-IMPLEMENTATION-RECEIPT.json').read_text())
        self.project=self.receipt['project_id'];self.run=self.receipt['research_run_id'];self.token=secrets.token_urlsafe(32)
        self.service=ControlService(Path('artifacts/p5-implementation-001/control.db'),credentials={self.token:dict(subject='admission-reader',role='viewer',projects=[self.project])})
        self.pins=dict(expected_manifest_sha256='304a2cd22107ccf69b971332ba5f0fce2f1a26240a734e06eb21ef39ad22b7d3',expected_source_sha256='ad498577d9d919bb6cc17c71a5ab970adf5370f8555ed6216a55683a682086ca',expected_candidate_sha256='f28262870d046f46d3c22c61e06df639b789966ee459c9d4723348bd3bad0176')

    def binding(self,**overrides):
        from research_projects.paired_acquisition.generator_admission import from_trial
        return from_trial(self.service,self.token,self.project,self.run,'trial_ec62b369aab54cb5932462a0e2b037fa',**dict(self.pins,**overrides))

    def test_actual_source_and_trials_preserved_without_new_spending(self):
        before=self.service.get_run(self.token,self.project,self.run)
        binding=self.binding()
        self.assertEqual(binding['unique_coordinates'],768);self.assertEqual(binding['label_batches'],32)
        for key in self.pins:
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError,'pin'):self.binding(**{key:'0'*64})
        after=self.service.get_run(self.token,self.project,self.run)
        self.assertEqual(before['budget'],after['budget']);self.assertEqual(before['trials'],after['trials'])

    def test_actual_reviewer_wrong_order_candidate_is_rejected(self):
        from research_projects.paired_acquisition.training_adapter import read_trial
        from research_projects.paired_acquisition.generator_admission import convert
        r=read_trial(self.service,self.token,self.project,self.run,'trial_7e01fb758353401cb051b8b59690d68d')
        self.assertEqual(r['reference']['manifest_hash'],'fae0a4de615a411940aabc917bef578d45a0b46da5ea65c68df0b8088abe06f1')
        wrong=r['result']['author_output']['results']['wrong_order_negative_control']
        self.assertTrue(wrong['accepted'])
        original=read_trial(self.service,self.token,self.project,self.run,'trial_ec62b369aab54cb5932462a0e2b037fa')
        candidate=copy.deepcopy(original['result']['author_output']['result']['candidate'])
        # Reviewer retained the negative candidate hash/order, not its full body.
        # Reconstruct only that permutation and prove it matches the actual hash.
        for group in candidate['paired_sampling']['groups']:
            arm=next(a for a in group['arms'] if a['arm_id']=='TT')
            arm['block_order']=wrong['first_order']
            arm['coordinates']=[x for name in wrong['first_order'] for x in group['shared_blocks'][name]]
        self.assertEqual(digest(candidate),wrong['candidate_sha256'])
        with self.assertRaisesRegex(ValueError,'literal arm order'):
            convert(candidate,r['payload']['materials'],expected_candidate_sha256=wrong['candidate_sha256'])

    def test_native_control_prepares_actual_coordinates_and_retains_budget_denial(self):
        import test_study_adapter_flow as fixtures
        f=fixtures.AdapterFlowTests('test_preparation_is_atomic_durable_and_idempotent');f.setUp();self.addCleanup(f.doCleanups)
        binding=self.binding();doc=copy.deepcopy(f.f.contract)
        doc['provenance']['paired_sampling']=binding['policy'];doc['provenance']['paired_adapter']['group_seeds']=binding['group_seeds']
        with self.assertRaisesRegex(ValueError,'paired_budget_insufficient'):
            f.s.publish_contract('human-secret','p','c',doc,expected_revision=1,idempotency_key='insufficient')
        doc['budget'].update(attempts=65,sample_proposals=2048)
        f.s.publish_contract('human-secret','p','c',doc,expected_revision=1,idempotency_key='actual-policy')
        state=f.s.get_run('human-secret','p','r');f.s.command('human-secret','p','r','apply_contract',expected_revision=state['control_revision'],idempotency_key='actual-apply',payload=dict(contract_id='c',revision=2))
        group=binding['policy']['groups']['1101'];points=[x for name in group['arms']['TT'] for x in group['blocks'][name]]
        f.kwargs['request'].update(coordinates=points,paired_batch=dict(group_id='1101',arm_id='TT'))
        trial=f.submit()
        from asr_service.study_adapters import load
        with f.s._connect() as db:prepared=load(db,'p','r',trial['paired_adapter']['preparation'])
        self.assertEqual([row['x'] for row in prepared['plan']['rows']],points)
        self.assertEqual(len(prepared['expected_inputs']),64)
        self.assertEqual(f.s.budgets.balance('p','sample_proposals')['reserved'],64)
        state=f.s.get_run('human-secret','p','r');f.s.command('human-secret','p','r','cancel_trial',expected_revision=state['control_revision'],idempotency_key='cancel-unexecuted',payload=dict(trial_id=trial['trial_id']))
        self.assertEqual(f.s.budgets.balance('p','sample_proposals')['spent'],0)
        self.assertEqual(f.s.budgets.balance('p','sample_proposals')['reserved'],0)
