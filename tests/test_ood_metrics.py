"""Independent scalar metric math; no training or hidden data involved."""
import unittest
from asr_evaluation.ood_metrics import evaluate, predict, paired_interval


class IndependentMetricTests(unittest.TestCase):
    def model(self):
        weights=[[0.0]*6 for _ in range(10)]
        weights[0]=[1.,2.,3.,10.,20.,30.]
        weights[1][0]=2.;weights[7][1]=3.
        return dict(schema='regional-load-quadratic/1',weights=weights)

    def test_features_and_output_masks_are_independently_computed(self):
        model=self.model()
        self.assertEqual(predict(model,[1.5,1.2,1.]),[2.,2.3,3.,10.,20.,30.])
        case={'bus':[[1,3],[2,2],[3,1]]}
        row=dict(x=[1.,1.,1.],y=[900.,900.,4.,999.,22.,34.],status='labelled')
        result=evaluate(model,[row],case)
        self.assertEqual(result['pq_voltage_rmse_pu'],1.)
        self.assertAlmostEqual(result['nonreference_angle_rmse_degree'],10**.5)

    def test_bad_dimensions_and_nonfinite_predictions_fail(self):
        model=self.model();model['weights'][0][0]=float('nan')
        with self.assertRaises(ValueError):predict(model,[1.,1.,1.])
        model=self.model();model['weights'].pop()
        with self.assertRaises(ValueError):predict(model,[1.,1.,1.])

    def test_pairing_is_preserved_and_zero_variance_interval_exact(self):
        interval=paired_interval([1.,2.,3.],[2.,3.,4.])
        self.assertEqual(interval['lower'], -1.)
        self.assertEqual(interval['upper'], -1.)
        self.assertEqual(interval['estimand'],'candidate_minus_baseline_sample_mse')
        with self.assertRaises(ValueError):paired_interval([1.],[1.,2.])


if __name__=='__main__':unittest.main()
