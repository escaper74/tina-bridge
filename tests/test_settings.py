"""Configuration precedence and relocation behavior; no desktop interaction."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.exe=self.root/'tina.exe';self.exe.write_bytes(b'fixture only')
        self.config=self.root/'settings.json'
        self.config.write_text(json.dumps({'tina_exe':'tina.exe','workspace':'runs','monitor':'unchanged'}),encoding='utf-8')

    def test_relative_settings_follow_config_location(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(str(self.exe),settings.executable(path=self.config))
            self.assertEqual(self.root/'runs',settings.workspace(self.config))
            self.assertEqual('unchanged',settings.monitor(self.config))

    def test_environment_wins(self):
        other=self.root/'other.exe';other.write_bytes(b'fixture')
        with patch.dict(os.environ,{'TINA_EXE':str(other),'TINA_WORKSPACE':str(self.root/'elsewhere'),'TINA_MONITOR':'secondary'},clear=True):
            self.assertEqual(str(other),settings.executable(path=self.config))
            self.assertEqual(self.root/'elsewhere',settings.workspace(self.config))
            self.assertEqual('secondary',settings.monitor(self.config))

    def test_missing_explicit_path_does_not_select_another_installation(self):
        with patch.dict(os.environ,{'TINA_EXE':str(self.root/'missing.exe')},clear=True),patch.object(settings,'discover_executables',return_value=[self.exe]):
            with self.assertRaises(FileNotFoundError):settings.executable(path=self.config)

    def test_ambiguous_discovery_is_explicit(self):
        with patch.dict(os.environ,{},clear=True),patch.object(settings,'read_config',return_value={}),patch.object(settings,'discover_executables',return_value=[self.exe,self.root/'second/tina.exe']):
            with self.assertRaises(ValueError):settings.executable()


if __name__=='__main__':unittest.main()
