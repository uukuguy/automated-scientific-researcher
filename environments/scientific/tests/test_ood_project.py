import copy
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

class ProjectTests(unittest.TestCase):
    def module(self):
        spec = importlib.util.find_spec('research_projects.ood_augmentation.project')
        self.assertIsNotNone(spec, 'simulated project implementation is required')
        from research_projects.ood_augmentation import project
        return project

    def test_scenarios_preserve_original_and_scale_pq_together(self):
        p = self.module()
        original = p.load_case()
        before = copy.deepcopy(original)
        scenario = p.make_scenario(original, [1.2, .95, 1.05])
        self.assertEqual(original, before)
        self.assertEqual(scenario['branch'], original['branch'])
        for i,(a,b) in enumerate(zip(original['bus'], scenario['bus'])):
            k = [1.2,.95,1.05][p.group(i,len(original['bus']))]
            self.assertAlmostEqual(b[2], a[2]*k)
            self.assertAlmostEqual(b[3], a[3]*k)
            self.assertEqual(a[1],b[1])
        for bad in ([1,1], [1,float('nan'),1], [1,100,1]):
            with self.assertRaises(ValueError): p.make_scenario(original,bad)

    def test_model_roundtrip_and_invalid_training(self):
        p=self.module(); rng=np.random.default_rng(13)
        x=rng.uniform(.9,1.1,(40,3)); y=np.column_stack((x[:,0]+2*x[:,1],x[:,2]**2))
        model=p.fit(x.tolist(),y.tolist())
        prediction=p.predict(model,x.tolist())
        self.assertLess(np.max(np.abs(prediction-y)),1e-5)
        self.assertEqual(model['training_count'],40)
        with self.assertRaises(ValueError): p.fit([[1,1,1]],[[float('nan')]])

    def test_split_generation_reproducible_and_distinct(self):
        p=self.module()
        self.assertEqual(p.coordinates('train',7,5),p.coordinates('train',7,5))
        self.assertNotEqual(p.coordinates('train',7,5),p.coordinates('train',8,5))
        train=np.asarray(p.coordinates('train',7,5)); ood=np.asarray(p.coordinates('diagnostic',7,5))
        self.assertTrue(np.all(train <= 1.1)); self.assertTrue(np.all(ood[:,0] >= 1.2))
        with self.assertRaises(ValueError): p.coordinates('unknown',7,5)

    def test_public_manifest_excludes_private_material(self):
        p=self.module()
        self.assertNotIn('private',str(p.PUBLIC_SPLITS))
        self.assertEqual(set(p.PUBLIC_SPLITS),{'train','id_dev','diagnostic'})

if __name__=='__main__': unittest.main()
