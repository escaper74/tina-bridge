"""Run self-contained offline tests without accessing a real TINA installation."""
from pathlib import Path
import os
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    if os.name != 'nt':
        raise SystemExit('These offline tests import Windows adapters; run them on Windows.')
    sys.path.insert(0, str(ROOT / 'plugins/tina-bridge/server'))
    with tempfile.TemporaryDirectory(prefix='tina-bridge-tests-') as folder:
        # Satisfy import-time path discovery only. These tests never launch TINA.
        os.environ['TINA_EXE'] = sys.executable
        os.environ['TINA_CONFIG'] = str(Path(folder) / 'settings.json')
        os.environ['TINA_WORKSPACE'] = str(Path(folder) / 'runs')
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
