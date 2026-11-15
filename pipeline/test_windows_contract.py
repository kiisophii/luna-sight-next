"""Regression: full contract checker must reject two formerly unchecked hashes.

python -m unittest discover -s pipeline -p test_windows_contract.py -v
All mutations occur in a disposable copy, never in project data.
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProvenanceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {}
        cls.temporary = tempfile.TemporaryDirectory(prefix='llsn-window-contract-')
        cls.fixture = Path(cls.temporary.name) / 'repo'
        cls.data = cls.fixture / 'web/data'
        shutil.copytree(ROOT / 'web/data', cls.data)
        (cls.fixture / 'web/js').mkdir(parents=True)
        shutil.copy2(ROOT / 'web/js/core.js', cls.fixture / 'web/js/core.js')
        cls.target = cls.data / 'windows/SHACKLETON_RIM.json'
        cls.original = cls.target.read_bytes()

    @classmethod
    def tearDownClass(cls):
        expected = {'normal_outputs', 'site_sha256', 'producer_sha256', 'missing_terrain_tile'}
        report = {'generated_utc': datetime.now(timezone.utc).isoformat(),
                  'passed': set(cls.results) == expected,
                  'checker_sha256': hashlib.sha256((ROOT / 'pipeline/check_windows.py').read_bytes()).hexdigest(),
                  'producer_sha256': hashlib.sha256((ROOT / 'pipeline/build_windows.mjs').read_bytes()).hexdigest(),
                  'scope': 'Full contract checker against a disposable copy, including real hterrain index and tiles; production data never mutated',
                  'checks': cls.results}
        (ROOT / 'docs/windows_hash_check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        # The resolved deletion target is the tempfile-owned tree only.
        target = Path(cls.temporary.name).resolve()
        assert target.parent == Path(tempfile.gettempdir()).resolve()
        assert target.name.startswith('llsn-window-contract-')
        cls.temporary.cleanup()

    def tearDown(self):
        self.target.write_bytes(self.original)

    def contract(self):
        return subprocess.run([sys.executable, str(ROOT / 'pipeline/check_contract.py'),
                               '--data', str(self.data)], capture_output=True,
                              text=True, encoding='utf-8', timeout=90)

    def assert_hash_rejected(self, key):
        document = json.loads(self.original)
        document['source'][key] = '0' * 64
        self.target.write_text(json.dumps(document) + '\n', encoding='utf-8')
        result = self.contract()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ERROR windows/SHACKLETON_RIM.json: input changed: ' + key, result.stdout)
        # Derived detail products may also correctly flag the changed window
        # input. Assert this specific rejection, not an obsolete global count.
        self.assertIn('FAIL:', result.stdout)
        self.results[key] = {'tampered_value': '0' * 64, 'exit_code': result.returncode,
                             'rejected': True, 'error': next(line for line in result.stdout.splitlines()
                                                            if line.startswith('ERROR windows/SHACKLETON_RIM.json'))}

    def test_unchanged_real_outputs_pass(self):
        result = self.contract()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS: 0 errors', result.stdout)
        self.results['normal_outputs'] = {'exit_code': result.returncode, 'passed': True}

    def test_missing_large_terrain_tile_is_error(self):
        tile = next((self.data / 'hterrain/tiles/near').glob('*.i16.gz'))
        content = tile.read_bytes()
        try:
            tile.unlink()
            result = self.contract()
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('ERROR hterrain.near: 1 tiles missing', result.stdout)
            self.assertIn('FAIL:', result.stdout)
            self.results['missing_terrain_tile'] = {'exit_code': result.returncode,
                                                   'rejected_as_error': True,
                                                   'error': next(line for line in result.stdout.splitlines()
                                                                 if line.startswith('ERROR hterrain.near:'))}
        finally:
            tile.write_bytes(content)

    def test_zero_site_hash_is_rejected_by_full_checker(self):
        self.assert_hash_rejected('site_sha256')

    def test_zero_producer_hash_is_rejected_by_full_checker(self):
        self.assert_hash_rejected('producer_sha256')


if __name__ == '__main__':
    unittest.main()
