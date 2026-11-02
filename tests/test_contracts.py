import copy
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from asr_service.contracts import resolve_policy, check_change, PolicyError, PolicyStore


def example():
    return json.loads(Path('contracts/examples/research-variables.json').read_text())


class PolicyTests(unittest.TestCase):
    def test_defaults_and_unknown_override(self):
        template=example(); value=resolve_policy(template)
        self.assertEqual(value['variables']['solver']['value'], 'newton_raphson')
        self.assertNotIn('value', template['variables']['solver'])
        with self.assertRaises(PolicyError): resolve_policy(template, {'typo': {'value': 1}})

    def test_strict_fields_and_types(self):
        for field,value in [('value', True),('value',float('nan')),('type','number'),('unit','MW')]:
            with self.subTest(field=field,value=value), self.assertRaises(PolicyError):
                resolve_policy(example(), {'iterations':{field:value}})
        doc=example();doc['unknown']=1
        with self.assertRaises(PolicyError): resolve_policy(doc)

    def test_bounds_and_open_interface(self):
        with self.assertRaises(PolicyError): resolve_policy(example(), {'iterations':{'value':101}})
        doc=example();del doc['variables']['solver']['implementation']
        with self.assertRaises(PolicyError): resolve_policy(doc)
        doc=example();doc['variables']['iterations']['allowed']={'minimum':20,'maximum':1}
        with self.assertRaises(PolicyError): resolve_policy(doc)

    def test_candidate_permission_and_fixed_semantics(self):
        policy=resolve_policy(example())
        self.assertEqual(check_change(policy,'iterations',30,'researcher'),30)
        with self.assertRaises(PolicyError): check_change(policy,'network','case14','researcher')
        with self.assertRaises(PolicyError): check_change(policy,'iterations',200,'researcher')
        with self.assertRaises(PolicyError): check_change(policy,'iterations',20,'viewer')
        self.assertEqual(check_change(policy,'solver','novel_algorithm','researcher'),'novel_algorithm')
        self.assertEqual(policy['variables']['iterations']['value'],20)

    def test_trial_cannot_change_project_scoped_variable(self):
        policy=resolve_policy(example())
        policy["variables"]["iterations"]["scope"]="project"
        with self.assertRaises(PolicyError): check_change(policy,"iterations",30,"researcher")

    def test_user_can_change_mode_without_changing_type(self):
        result=resolve_policy(example(),{'network':{'mode':'bounded','allowed':{'choices':['case118','case14']},'value':'case14'}})
        self.assertEqual(result['variables']['network']['value'],'case14')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'state.sqlite'
        self.store=PolicyStore(self.path)
        self.policy=resolve_policy(example())

    def publish(self, key='one', base=0, policy=None, project='p'):
        return self.store.publish(project,'policy',self.policy if policy is None else policy,
                                  expected_revision=base,idempotency_key=key,actor='human')

    def test_immutable_revision_and_idempotency(self):
        a=self.publish();self.assertEqual(a,self.publish())
        other=copy.deepcopy(self.policy);other['variables']['iterations']['value']=30
        with self.assertRaises(PolicyError): self.publish(policy=other)
        with self.assertRaises(PolicyError): self.publish(key='stale')
        b=self.publish(key='two',base=1,policy=other)
        self.assertEqual(b['revision'],2)
        self.assertEqual(self.store.get('p','policy',1)['policy'],self.policy)
        self.assertEqual(PolicyStore(self.path).get('p','policy',2),b)

    def test_activation_is_explicit_and_versioned(self):
        self.publish()
        with self.assertRaises(PolicyError): self.store.binding('p','run')
        a=self.store.apply('p','run','policy',1,expected_revision=0,actor='human')
        self.assertEqual(a['control_revision'],1)
        self.publish(key='two',base=1)
        self.assertEqual(self.store.binding('p','run')['policy_revision'],1)
        with self.assertRaises(PolicyError): self.store.apply('p','run','policy',2,expected_revision=0,actor='human')
        b=self.store.apply('p','run','policy',2,expected_revision=1,actor='human')
        self.assertEqual(b['policy_revision'],2)
        self.assertEqual(len(self.store.events('p')),4)

    def test_cross_project_and_role_rejected(self):
        self.publish()
        with self.assertRaises(PolicyError): self.store.apply('q','run','policy',1,expected_revision=0,actor='human')
        with self.assertRaises(PolicyError): self.store.publish('p','other',self.policy,expected_revision=0,idempotency_key='x',actor='researcher')

    def test_concurrent_publication_has_one_winner(self):
        def write(key):
            try: return self.publish(key=key)['revision']
            except PolicyError: return 'conflict'
        with ThreadPoolExecutor(2) as pool: results=list(pool.map(write,['a','b']))
        self.assertCountEqual(results,[1,'conflict'])
        self.assertEqual(len(self.store.events('p')),1)
