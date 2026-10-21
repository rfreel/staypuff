"""Runner regressions; optional real CPU/CUDA binaries are supplied via env vars."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parents[1]
spec = importlib.util.spec_from_file_location('diagnostic_runner', PROJECT / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'study.json'
        self.binary = self.root / 'diagnostic'
        self.binary.write_bytes(b'supplied executable A')

    def invoke(self, execute=None):
        if execute is None:
            execute = self.measurement
        argv = ['run.py', '--binary', str(self.binary), '--steps', '100',
                '--output', str(self.output)]
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
            with patch.object(runner.subprocess, 'check_output', side_effect=execute) as call:
                runner.main()
        return call

    @staticmethod
    def measurement(*args, **kwargs):
        return json.dumps(dict(curve=[dict(success=0.5, length=40)],
                               heldout=dict(success=0.5, length=40, left=0.25, right=0.75),
                               seconds_including_curve_eval=0))

    def test_all_existing_artifacts_block_before_execution(self):
        for suffix in ('.json', '.manifest.json', '.selected.json'):
            with self.subTest(suffix=suffix):
                path = self.output.with_suffix(suffix)
                path.write_bytes(b'frozen evidence')
                with self.assertRaisesRegex(SystemExit, 'Refusing to overwrite'):
                    self.invoke(lambda *a, **k: self.fail('must not execute'))
                self.assertEqual(path.read_bytes(), b'frozen evidence')
                path.unlink()

    def test_dangling_symlink_is_a_collision(self):
        path = self.output.with_suffix('.selected.json')
        path.symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(SystemExit, 'Refusing to overwrite'):
            self.invoke()
        self.assertTrue(path.is_symlink())

    def test_interrupted_run_freezes_manifest_and_blocks_retry(self):
        def interrupt(*args, **kwargs):
            self.assertTrue(self.output.with_suffix('.manifest.json').is_file())
            raise RuntimeError('interrupted')
        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            self.invoke(interrupt)
        manifest = self.output.with_suffix('.manifest.json').read_bytes()
        self.binary.write_bytes(b'different binary on retry')
        with self.assertRaisesRegex(SystemExit, 'Refusing to overwrite'):
            self.invoke()
        self.assertEqual(self.output.with_suffix('.manifest.json').read_bytes(), manifest)
        self.assertFalse(self.output.exists())

    def test_exclusive_writes_protect_late_collisions(self):
        for suffix in ('.manifest.json', '.selected.json', '.json'):
            with self.subTest(suffix=suffix):
                self.output = self.root / (suffix[1:] + '.json')
                target = self.output.with_suffix(suffix)
                original_open = Path.open
                def collide(path, mode='r', *args, **kwargs):
                    if path == target and mode in ('w', 'x') and not path.exists():
                        with original_open(path, 'w') as stream:
                            stream.write('concurrent evidence')
                    return original_open(path, mode, *args, **kwargs)
                with patch.object(Path, 'open', collide):
                    with self.assertRaises(FileExistsError):
                        self.invoke(self.measurement)
                self.assertEqual(target.read_text(), 'concurrent evidence')

    def test_manifest_binds_supplied_binary_and_preserves_source_hashes(self):
        records = []
        for index, data in enumerate((b'executable A', b'executable B')):
            self.binary.write_bytes(data)
            self.output = self.root / f'study{index}.json'
            self.invoke(self.measurement)
            manifest = json.loads(self.output.with_suffix('.manifest.json').read_text())
            result = json.loads(self.output.read_text())
            self.assertEqual(manifest, result['manifest'])
            self.assertEqual(manifest['binary'], dict(path=str(self.binary.resolve()),
                                                      sha256=hashlib.sha256(data).hexdigest()))
            self.assertEqual(len(result['runs']), 168)
            records.append(manifest)
        self.assertNotEqual(records[0]['binary']['sha256'], records[1]['binary']['sha256'])
        self.assertEqual(records[0]['source_sha256'], records[1]['source_sha256'])



class NativeRunnerTests(unittest.TestCase):
    def test_evaluation_metrics_survive_into_results_and_missing_metrics_fail(self):
        spec = importlib.util.spec_from_file_location('native_runner', PROJECT / 'native.py')
        native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(native)
        for complete in (True, False):
            with self.subTest(complete=complete), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ('mirror_puffer', 'mirror_view'):
                    (root / name).touch()
                output = root / 'results'
                def train(command, **kwargs):
                    options = dict(arg[2:].split('=', 1) for arg in command[2:])
                    folder = (Path(options['base.checkpoint_dir']) / 'mirror_detour'
                              / options['base.run_id'])
                    folder.mkdir(parents=True)
                    (folder / '65536.bin').touch()
                metrics = 'left=0.25 right=0.75 length=24 bonus=0' if complete else ''
                line = f'CPU_EVAL untrained=0 n=256 perf=1 score=1 {metrics}\n'
                argv = ['native.py', '--execute', '--steps', '65536', '--output', str(output)]
                with patch.object(native, 'ROOT', root), patch.object(sys, 'argv', argv), \
                        patch.object(native.subprocess, 'run', side_effect=train), \
                        patch.object(native.subprocess, 'check_output', return_value=line):
                    if not complete:
                        with self.assertRaisesRegex(AssertionError, 'Missing evaluation metric'):
                            native.main()
                        continue
                    native.main()
                results = json.loads((output / 'results.json').read_text())
                self.assertEqual(len(results), 8)
                for arm in results:
                    self.assertEqual(len(arm['scores']), 2)
                    for score in arm['scores']:
                        for key, value in dict(left='0.25', right='0.75', length='24', bonus='0').items():
                            self.assertEqual(score['metrics'][key], value)


@unittest.skipUnless(os.environ.get('MIRROR_CPU_BINARY'), 'set MIRROR_CPU_BINARY for real runtime')
class CpuMetricsTests(unittest.TestCase):
    def test_actual_runtime_exports_normalized_environment_metrics(self):
        output = subprocess.check_output([
            os.environ['MIRROR_CPU_BINARY'], '--headless', '--eval_episodes=3',
            '--base.load_model_path=None', '--env.evaluate=1',
            '--env.mode=1', '--env.strength=10', '--env.sign=1'], cwd=ROOT, text=True)
        line = next(line for line in output.splitlines() if line.startswith('CPU_EVAL '))
        fields = [field.split('=', 1) for field in line.split()[1:]]
        values = dict(fields)
        self.assertEqual(len(fields), len(values), 'duplicate metric keys')
        self.assertEqual(values['untrained'], '1')
        # No network: actions stay left, all three episodes time out at 80 steps.
        for key, expected in dict(n=3, perf=0, score=0, length=80,
                                  left=0, right=0, bonus=0, steps=240).items():
            self.assertEqual(float(values[key]), expected, key)


@unittest.skipUnless(os.environ.get('MIRROR_CUDA_BINARY'), 'set MIRROR_CUDA_BINARY; requires CUDA')
class TrainingWeightsTests(unittest.TestCase):
    def test_training_initial_selfplay_checkpoint_uses_supplied_weights(self):
        # Zero rollouts/updates: exercise real training initialization and its initial
        # self-play checkpoint, without a training campaign or optimizer effects.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def initialize(name, seed, async_mode, load='None'):
                command = [os.environ['MIRROR_CUDA_BINARY'], 'train',
                           f'--base.run_id={name}', f'--base.seed={seed}',
                           f'--base.async={async_mode}', '--base.eval_episodes=0',
                           f'--base.checkpoint_dir={root / "checkpoints"}',
                           f'--base.log_dir={root / "logs"}', f'--base.load_model_path={load}',
                           '--train.total_timesteps=0', '--train.horizon=16',
                           '--train.minibatch_size=64', '--vec.total_agents=64',
                           '--vec.num_buffers=1', '--vec.num_threads=1',
                           '--selfplay.enabled=1', '--selfplay.eval_games=0',
                           '--selfplay.eval_bot_games=0', '--vec.num_policies=2',
                           '--vec.hist_policy_percent=0.5']
                subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
                return root / 'checkpoints' / 'mirror_detour' / name / '0000000000000000.bin'
            source = initialize('source', 17, 0)
            fresh = initialize('fresh', 29, 0)
            self.assertNotEqual(source.read_bytes(), fresh.read_bytes())
            for async_mode in (0, 1):
                loaded = initialize(f'loaded{async_mode}', 29, async_mode, source)
                self.assertEqual(loaded.read_bytes(), source.read_bytes())
            with self.assertRaises(subprocess.CalledProcessError):
                initialize('missing', 29, 0, root / 'missing.bin')


if __name__ == '__main__':
    unittest.main()
