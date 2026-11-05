import threading
import unittest


class AsyncObservationTests(unittest.TestCase):
    def test_slow_registration_does_not_block_producer_and_barrier_keeps_order(self):
        from integrations.runtimes.async_observations import OrderedObservations
        entered=threading.Event();release=threading.Event();seen=[]
        def consume(value):entered.set();release.wait(3);seen.append(value['id'])
        worker=OrderedObservations(consume)
        try:
            worker.submit({'id':1});self.assertTrue(entered.wait(1))
            worker.submit({'id':2})
            self.assertFalse(worker.barrier(timeout=.01)['drained'])
            release.set()
            self.assertTrue(worker.barrier(timeout=1)['drained'])
            self.assertEqual(seen,[1,2])
        finally:release.set();worker.close(timeout=1)

    def test_failure_and_unfinished_worker_are_explicit_and_do_not_kill_research(self):
        from integrations.runtimes.async_observations import OrderedObservations
        release=threading.Event()
        def consume(value):release.wait(3);raise OSError('private credentials')
        worker=OrderedObservations(consume);worker.submit({'id':1})
        result=worker.close(timeout=.01)
        self.assertFalse(result['drained']);self.assertFalse(result['research_terminated'])
        release.set();result=worker.close(timeout=1)
        self.assertEqual(result['failures'],[{'sequence':1,'reason':'observation_record_failed'}])
        self.assertNotIn('private credentials',str(result))

    def test_observation_snapshot_is_immutable_and_shutdown_rejects_new_work(self):
        from integrations.runtimes.async_observations import OrderedObservations
        release=threading.Event();seen=[]
        worker=OrderedObservations(lambda value:(release.wait(3),seen.append(value)))
        value={'body':'original'}
        worker.submit(value);value['body']='mutated';release.set()
        self.assertTrue(worker.close(timeout=1)['drained'])
        self.assertEqual(seen,[{'body':'original'}])
        with self.assertRaises(ValueError):worker.submit({'id':2})
