"""First-session completion and failure checks; no real Wine, desktop or reboot."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('finisher',Path(__file__).with_name('desktop-first-login.py'))
first=importlib.util.module_from_spec(spec);spec.loader.exec_module(first)

class FirstLoginTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name);self.state=self.home/'state';self.state.mkdir()
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':str(self.home/'config'),'XDG_STATE_HOME':str(self.home/'state-root')})
        env.start();self.addCleanup(env.stop)
    def test_completed_existing_install_does_not_schedule_restart(self):
        for name in ['desktop-complete','wine-complete']:(self.state/name).touch()
        self.assertFalse(first.needs_setup(self.home,self.state))
    def test_incomplete_aero_requires_setup_even_with_other_markers(self):
        for name in ['desktop-complete','wine-complete']:(self.state/name).touch()
        auto=self.home/'config/autostart/aerothemeplasma-first-login.desktop';auto.parent.mkdir(parents=True);auto.touch()
        self.assertTrue(first.needs_setup(self.home,self.state))
    def test_failed_final_stage_remains_pending_without_success_marker(self):
        def incomplete(*args):
            for name in ['desktop-complete','wine-complete']:(self.state/name).touch()
            raise RuntimeError('wallpaper not ready')
        with patch.object(first,'configure',side_effect=incomplete):
            with self.assertRaises(RuntimeError):first.finish(self.home,self.state,lambda x:None)
        self.assertFalse((self.state/'ready.json').exists())
        self.assertTrue(first.needs_setup(self.home,self.state))
    def test_success_marker_written_only_after_configuration(self):
        def complete(*args):
            self.assertFalse((self.state/'ready.json').exists())
            for name in ['desktop-complete','wine-complete']:(self.state/name).touch()
        with patch.object(first,'configure',side_effect=complete),patch.object(first,'boot_id',return_value='boot-one'):
            first.finish(self.home,self.state,lambda x:None)
        self.assertIn('boot-one',(self.state/'ready.json').read_text())
        self.assertFalse(first.needs_setup(self.home,self.state))
    def test_aero_timeout_never_initializes_wine_or_finishes(self):
        auto=self.home/'config/autostart/aerothemeplasma-first-login.desktop';auto.parent.mkdir(parents=True);auto.touch()
        with patch.object(first.time,'sleep'),patch.object(first,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'Aero'):first.finish(self.home,self.state,lambda x:None)
        run.assert_not_called();self.assertFalse((self.state/'ready.json').exists())
    def test_every_completed_login_restores_wallpaper_without_resetting_wine(self):
        for name in ['desktop-complete','wine-complete']:(self.state/name).touch()
        with patch.object(first,'restore_wallpaper') as wallpaper,patch.object(first,'run') as run:
            first.configure(self.home,self.state);first.configure(self.home,self.state)
        self.assertEqual(wallpaper.call_count,2);run.assert_not_called()

if __name__=='__main__':unittest.main()
