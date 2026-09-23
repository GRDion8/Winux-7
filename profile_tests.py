"""Temporary-root, isolated-process tests; never modify a running desktop."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import winux_profile as profile

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name in ['usr/bin/startatp','usr/share/plasma/look-and-feel/authui7/metadata.json',
                     'usr/share/xsessions/winux-x11.desktop','usr/share/winux-setup/xsessions/winux-x11.desktop',
                     'usr/share/applications/systemsettings.desktop','usr/share/applications/kcm_lookandfeel.desktop']:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text('[Desktop Entry]\nExec=startatp\nTryExec=startatp\n')
    def run_target(self,*args):
        # Only replace the compiler; real policy/file installation runs against this temporary root.
        if args[0]=='sh':
            (self.root/args[-1].lstrip('/')/'control-panel').write_bytes(b'fixture executable')
    def test_install_restore_and_idempotence(self):
        session=self.root/'usr/share/xsessions/winux-x11.desktop';original=session.read_bytes()
        profile.install(self.root,self.run_target)
        profile.install(self.root,self.run_target)
        self.assertIn('Exec=/usr/local/bin/winux-session',session.read_text())
        panel=self.root/'usr/local/share/applications/systemsettings.desktop'
        self.assertIn('winux-control-panel',panel.read_text())
        self.assertIn('Hidden=true',(self.root/'usr/local/share/applications/kcm_lookandfeel.desktop').read_text())
        self.assertEqual((self.root/'usr/local/bin/winux-session').stat().st_mode&0o777,0o755)
        profile.remove(self.root)
        self.assertEqual(session.read_bytes(),original)
        self.assertFalse(panel.exists())
        self.assertFalse((self.root/profile.STATE).exists())
    def test_compile_failure_changes_no_login_files(self):
        def fail(*args):raise RuntimeError('compiler unavailable')
        original=(self.root/'usr/share/xsessions/winux-x11.desktop').read_bytes()
        with self.assertRaises(RuntimeError):profile.install(self.root,fail)
        self.assertEqual((self.root/'usr/share/xsessions/winux-x11.desktop').read_bytes(),original)
        self.assertFalse((self.root/profile.STATE).exists())
    def test_standard_plasma_refused_without_changes(self):
        (self.root/'usr/bin/startatp').unlink()
        with self.assertRaisesRegex(RuntimeError,'Aero'):profile.install(self.root,self.run_target)
        self.assertFalse((self.root/profile.STATE).exists())
    def test_remove_preserves_later_manual_changes(self):
        profile.install(self.root,self.run_target)
        p=self.root/'etc/winux-7/theme/kdeglobals';p.write_text('administrator edit')
        with self.assertRaisesRegex(RuntimeError,'edited separately'):profile.remove(self.root)
        self.assertEqual(p.read_text(),'administrator edit')
        self.assertTrue((self.root/'usr/local/bin/winux-session').exists())
    def test_session_policy_waits_for_both_finishers(self):
        script=(profile.ROOT/'winux-session.sh').read_text().replace('exec /usr/bin/startatp', 'printf "%s" "$XDG_CONFIG_DIRS"')
        sh=self.root/'session.sh';sh.write_text(script)
        state=self.root/'state';config=self.root/'config'
        env={**os.environ,'HOME':str(self.root),'XDG_STATE_HOME':str(state),'XDG_CONFIG_HOME':str(config),'XDG_CONFIG_DIRS':'/etc/xdg'}
        def start():return subprocess.check_output(['sh',str(sh)],env=env,text=True)
        self.assertNotIn('/etc/winux-7/',start())
        marker=state/'winux-desktop-v1/desktop-complete';marker.parent.mkdir(parents=True);marker.touch()
        aero=config/'autostart/aerothemeplasma-first-login.desktop';aero.parent.mkdir(parents=True);aero.touch()
        self.assertNotIn('/etc/winux-7/',start())
        done=state/'win7-aero-postinstall/first-login-complete';done.parent.mkdir(parents=True);done.touch()
        self.assertTrue(start().startswith('/etc/winux-7/locked:/etc/winux-7/theme:'))
        # Re-arming the desktop updater must reopen bootstrap access on the next login.
        marker.unlink();self.assertNotIn('/etc/winux-7/',start())
    @unittest.skipUnless(shutil.which('kreadconfig6') and shutil.which('kwriteconfig6'),'KConfig tools unavailable')
    def test_real_kconfig_immutable_theme_overrides_user_choice(self):
        user=self.root/'user';system=self.root/'system';user.mkdir();system.mkdir()
        (system/'kdeglobals').write_text(profile.THEME['kdeglobals'])
        (user/'kdeglobals').write_text('[KDE]\nwidgetStyle=Breeze\n')
        env={**os.environ,'HOME':str(self.root),'XDG_CONFIG_HOME':str(user),'XDG_CONFIG_DIRS':str(system)}
        read=['kreadconfig6','--file','kdeglobals','--group','KDE','--key','widgetStyle']
        self.assertEqual(subprocess.check_output(read,env=env,text=True).strip(),'kvantum')
        subprocess.run(['kwriteconfig6','--file','kdeglobals','--group','KDE','--key','widgetStyle','Breeze'],env=env,capture_output=True)
        self.assertEqual(subprocess.check_output(read,env=env,text=True).strip(),'kvantum')
    def test_minimal_package_paths_do_not_request_meta(self):
        import engine
        self.assertNotIn('plasma-meta',profile.PACKAGES)
        for name in ['plasma-desktop','powerdevil','kscreen','plasma-nm','plasma-pa','polkit-kde-agent','xdg-desktop-portal-kde']:
            self.assertIn(name,profile.PACKAGES)
        self.assertNotIn("'plasma-meta'",(profile.ROOT/'engine.py').read_text())
        self.assertNotIn('  plasma-meta ',(profile.ROOT/'arch-win7-aero-postinstall.sh').read_text())

class NativePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('c++') or not shutil.which('pkg-config'):raise unittest.SkipTest('Qt compiler unavailable')
        flags=subprocess.run(['pkg-config','--cflags','--libs','Qt6Widgets'],capture_output=True,text=True)
        if flags.returncode:raise unittest.SkipTest('Qt Widgets development files unavailable')
        cls.tmp=tempfile.TemporaryDirectory();cls.binary=Path(cls.tmp.name)/'control-panel'
        import shlex
        subprocess.run(['c++','-std=c++17','-fPIC',str(profile.ROOT/'control-panel.cpp'),'-o',str(cls.binary),*shlex.split(flags.stdout)],check=True,capture_output=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def invoke(self,*args):
        return subprocess.run([str(self.binary),*args],env={**os.environ,'QT_QPA_PLATFORM':'offscreen','HOME':self.tmp.name,'XDG_CONFIG_HOME':self.tmp.name},capture_output=True,text=True,timeout=15)
    def test_no_appearance_actions_and_no_shell_execution(self):
        r=self.invoke('--list-actions');self.assertEqual(r.returncode,0,r.stderr)
        actions=json.loads(r.stdout)
        for command in actions.values():
            self.assertFalse(any('systemsettings' in p or 'sh'==p for p in command))
            self.assertFalse(any(p in profile.APPEARANCE for p in command))
        self.assertEqual(actions['display'],['/usr/bin/kcmshell6','kcm_kscreen'])
        for value in ['kcm_lookandfeel','kcm_style','; touch /tmp/test','--config']:
            self.assertEqual(self.invoke('--dry-run',value).returncode,2)
        r=self.invoke('kcm_lookandfeel','--smoke-test')
        self.assertEqual(r.returncode,0,r.stderr)
    def test_gui_search_and_known_deep_link(self):
        r=self.invoke('--smoke-test');self.assertEqual(r.returncode,0,r.stderr)
        r=self.invoke('--dry-run','kcm_componentchooser');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout),['/usr/bin/kcmshell6','kcm_componentchooser'])

if __name__=='__main__':unittest.main()
