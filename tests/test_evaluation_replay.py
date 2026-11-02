"""Frozen-material evaluator tests; Docker execution is an explicit opt-in."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from powerflow_lab.reference import make_request
from powerflow_lab.runner import canonical
from asr_evaluation.replay import (
    Replay, ReplayError, UnresolvedReplay, freeze_source, verify_container,
    IMAGE_ID, INPUT_SHA256, VALIDATOR_SHA256,
)

FIXTURE = Path(__file__).resolve().parents[1] / 'environments/scientific/fixtures/matpower-case118'
IDENTITY = dict(trial_id='trial_source', execution_attempt_id='attempt_source', research_run_id='run_source')


def create_source(path):
    path.mkdir()
    for name in ('input.json', 'solution.json'):
        (path/name).write_bytes((FIXTURE/name).read_bytes())
    (path/'request.json').write_bytes(canonical(make_request()))
    return seal_source(path)


def seal_source(path):
    artifacts = {p.name: dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in path.iterdir() if p.name != 'manifest.json'}
    record = dict(schema='asr-managed-attempt/1', **IDENTITY, status='succeeded', execution_exited=True,
                  request_sha256=artifacts['request.json']['sha256'], artifacts=artifacts)
    body = canonical(record)
    (path/'manifest.json').write_bytes(body)
    return hashlib.sha256(body).hexdigest()


class FrozenSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root/'source'
        self.manifest_hash = create_source(self.source)

    def freeze(self, **identity):
        return freeze_source(self.source, self.manifest_hash, **(identity or IDENTITY))

    def test_binds_full_source_to_original_profile_and_exact_bytes(self):
        frozen = self.freeze()
        self.assertEqual(frozen['input_sha256'], INPUT_SHA256)
        self.assertEqual(frozen['manifest_sha256'], self.manifest_hash)
        self.assertEqual(frozen['identity'], IDENTITY)
        self.assertEqual(frozen['files']['solution.json'], (self.source/'solution.json').read_bytes())

    def test_rejects_hash_membership_and_identity_tampering(self):
        (self.source/'solution.json').write_bytes(b'{}')
        with self.assertRaises(ReplayError): self.freeze()
        self.manifest_hash = seal_source(self.source)
        with self.assertRaises(ReplayError): self.freeze(trial_id='other', execution_attempt_id='attempt_source', research_run_id='run_source')
        (self.source/'extra.txt').write_text('unpublished')
        with self.assertRaises(ReplayError): self.freeze()

    def test_candidate_input_never_defines_original_problem(self):
        value = json.loads((self.source/'input.json').read_text()); value['bus'][0][2] += 1
        (self.source/'input.json').write_bytes(canonical(value)); self.manifest_hash = seal_source(self.source)
        with self.assertRaisesRegex(ReplayError, 'original input'): self.freeze()

    def test_rejects_symlinks_and_unsupported_profile(self):
        target = self.source/'solution.json'; target.unlink(); target.symlink_to(FIXTURE/'solution.json')
        with self.assertRaises(ReplayError): self.freeze()
        target.unlink(); target.write_bytes((FIXTURE/'solution.json').read_bytes())
        request = json.loads((self.source/'request.json').read_text()); request['policy'] = 'arbitrary-candidate'
        (self.source/'request.json').write_bytes(canonical(request)); self.manifest_hash = seal_source(self.source)
        with self.assertRaises(ReplayError): self.freeze()

    def test_rejects_different_or_missing_frozen_evaluation_rules(self):
        original = json.loads((self.source/'request.json').read_text())
        for mutate in (lambda v:v.update(validation_tolerance_pu=.1),
                       lambda v:v.pop('validation_tolerance_pu'),
                       lambda v:v['source_hashes'].update({'validation.py':'0'*64}),
                       lambda v:v.pop('source_hashes')):
            request = copy.deepcopy(original); mutate(request)
            (self.source/'request.json').write_bytes(canonical(request)); self.manifest_hash = seal_source(self.source)
            with self.assertRaises(ReplayError): self.freeze()

    def test_final_manifest_cannot_relabel_hashed_negative_result_or_execution_facts(self):
        replay = Replay(self.root/'evaluations')
        with patch.object(replay,'_docker',side_effect=ReplayError('fixture backend')):
            with self.assertRaises(UnresolvedReplay): replay.run('derived',self.source,self.manifest_hash,**IDENTITY)
        pending = next(replay.root.glob('*.pending'))
        job = json.loads((pending/'job.json').read_text())
        identity = dict(job['identity'],container_id='fixture-container')
        (pending/'identity.json').write_bytes(canonical(identity))
        (pending/'output/result.json').write_bytes(canonical(dict(equation_valid=False)))
        value = dict(Id='fixture-container',Name='/'+identity['name'],Image=IMAGE_ID,
                     Config={'Labels':identity['labels']},State=dict(Running=False,Status='exited',ExitCode=0))
        # A fake backend exercises metadata consistency only; it proves no OS
        # isolation. The real Docker tests below exercise that separate boundary.
        honest = replay._publish(pending,replay.root/pending.name.removesuffix('.pending'),job,'succeeded',value)
        final = replay.root/pending.name.removesuffix('.pending')
        for mutate in (lambda v:v['result'].update(equation_valid=True),
                       lambda v:v.update(exit_code=123),
                       lambda v:v.update(execution_status='failed'),
                       lambda v:v['source'].update(input_sha256='0'*64),
                       lambda v:v['evaluator'].update(policy='forged')):
            corrupted = copy.deepcopy(honest); mutate(corrupted)
            (final/'manifest.json').write_bytes(canonical(corrupted))
            with self.assertRaises(ReplayError): replay._verified_final(final)
        (final/'manifest.json').write_bytes(canonical(honest))
        self.assertEqual(replay._verified_final(final),honest)

    def test_unknown_create_retains_pending_and_blocks_retry_even_after_reopen(self):
        replay = Replay(self.root/'evaluations')
        with patch.object(replay, '_docker', side_effect=ReplayError('daemon unavailable')):
            with self.assertRaises(UnresolvedReplay):
                replay.run('key', self.source, self.manifest_hash, **IDENTITY)
        reopened = Replay(self.root/'evaluations')
        with self.assertRaises(UnresolvedReplay): reopened.run('key', self.source, self.manifest_hash, **IDENTITY)
        with patch.object(reopened, '_docker', side_effect=ReplayError('daemon unavailable')):
            with self.assertRaises(UnresolvedReplay): reopened.reconcile('key')
        self.assertEqual(len(list((self.root/'evaluations').glob('*.pending'))), 1)

    def test_finite_limits_are_required_before_execution(self):
        replay = Replay(self.root/'evaluations')
        for value in (0, -1, 61, float('inf'), True):
            with self.assertRaises(ValueError): replay.run('key', self.source, self.manifest_hash, timeout_seconds=value, **IDENTITY)

    def test_rejects_oversized_source_before_docker(self):
        (self.source/'large.bin').write_bytes(b'x'*(4*1024*1024+1))
        self.manifest_hash = seal_source(self.source)
        with self.assertRaisesRegex(ReplayError, 'size limit'): self.freeze()


class ContainerInspectionTests(unittest.TestCase):
    def test_rejects_unexpected_mount_env_privilege_and_image(self):
        with tempfile.TemporaryDirectory() as root:
            pending = Path(root)
            identity = dict(name='asr-eval-example', labels={'asr.evaluation':'example'}, container_id='container-id')
            expected = dict(Id='container-id', Image=IMAGE_ID,
                Config=dict(Image=IMAGE_ID, User='65532:65532', Entrypoint=['python3'],
                            Cmd=['-I','-S','/evaluator/entrypoint.py'], Env=['HOME=/tmp','PYTHONDONTWRITEBYTECODE=1'], Labels=identity['labels']),
                HostConfig=dict(NetworkMode='none', ReadonlyRootfs=True, Privileged=False, CapAdd=None, CapDrop=['ALL'],
                                SecurityOpt=['no-new-privileges'], PidsLimit=32, Memory=268435456, MemorySwap=268435456, NanoCpus=1000000000,
                                LogConfig={'Type':'none'},RestartPolicy={'Name':'no','MaximumRetryCount':0},
                                Tmpfs={'/tmp':'rw,nosuid,nodev,noexec,size=16m'}, Binds=None, Devices=[]),
                Mounts=[dict(Type='bind', Source=str((pending/name).resolve()), Destination=dest, RW=rw)
                        for name,dest,rw in [('inputs','/inputs',False),('code','/evaluator',False),('output','/output',True)]])
            verify_container(expected, identity, pending)
            for mutate in (
                lambda v:v['Mounts'][0].update(RW=True),
                lambda v:v['Mounts'].append(dict(Type='bind',Source='/var/run/docker.sock',Destination='/socket',RW=True)),
                lambda v:v['Config']['Env'].append('OPENAI_API_KEY=fixture'),
                lambda v:v['HostConfig'].update(Privileged=True),
                lambda v:v['HostConfig'].update(NetworkMode='host'),
                lambda v:v['HostConfig'].update(MemorySwap=-1),
                lambda v:v['HostConfig'].update(RestartPolicy={'Name':'always'}),
                lambda v:v['HostConfig'].update(LogConfig={'Type':'json-file'}),
                lambda v:v.update(Image='other'),
            ):
                value = copy.deepcopy(expected); mutate(value)
                with self.assertRaises(ReplayError): verify_container(value, identity, pending)


@unittest.skipUnless(os.environ.get('ASR_REAL_DOCKER') == '1', 'explicit local Docker acceptance only')
class RealDockerReplayTests(unittest.TestCase):
    def test_interrupted_publication_recovers_same_container(self):
        import asr_evaluation.replay as implementation
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); source = root/'source'; digest = create_source(source)
            runner = Replay(root/'evaluation')
            write = implementation._write
            def interrupt(path, body):
                if path.name == 'manifest.json': raise KeyboardInterrupt
                return write(path, body)
            with patch.object(implementation, '_write', side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt): runner.run('interrupted', source, digest, **IDENTITY)
            pending = next((root/'evaluation').glob('*.pending'))
            original_id = json.loads((pending/'identity.json').read_text())['container_id']
            recovered = Replay(root/'evaluation').reconcile('interrupted')
            self.assertEqual(recovered['execution_status'], 'succeeded')
            final = next(path for path in (root/'evaluation').iterdir() if path.is_dir())
            self.assertEqual(json.loads((final/'exit-inspection.json').read_text())['Id'], original_id)

    def test_baseline_invalid_solution_and_isolation_probe(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); source = root/'source'; digest = create_source(source)
            runner = Replay(root/'evaluation')
            baseline = runner.run('baseline', source, digest, **IDENTITY)
            self.assertTrue(baseline['result']['equation_valid'])
            self.assertEqual(baseline['result']['operational_status'], 'violated')
            self.assertEqual(baseline['result']['thermal_limits_unassessed'], 186)
            self.assertTrue(baseline['execution_exited'])
            self.assertEqual(runner.run('baseline', source, digest, **IDENTITY), baseline)
            probe = runner.run('probe', source, digest, mode='probe', **IDENTITY)
            self.assertTrue(all(probe['result']['checks'].values()), probe['result'])
            value = json.loads((source/'solution.json').read_text()); value['bus'][0][7] += .01
            (source/'solution.json').write_bytes(canonical(value)); digest = seal_source(source)
            invalid = runner.run('invalid-voltage', source, digest, **IDENTITY)
            self.assertFalse(invalid['result']['equation_valid'])
            self.assertTrue(invalid['result']['input_preserved'])
            value['bus'][0][2] += 1; (source/'solution.json').write_bytes(canonical(value)); digest = seal_source(source)
            changed = runner.run('changed-fixed-input', source, digest, **IDENTITY)
            self.assertFalse(changed['result']['input_preserved'])
            self.assertFalse(changed['result']['equation_valid'])
            timed = runner.run('bounded-timeout', source, digest, mode='probe', timeout_seconds=.01, **IDENTITY)
            self.assertEqual(timed['execution_status'], 'timed_out')
            self.assertTrue(timed['execution_exited'])
            self.assertIsNone(timed['result'])
