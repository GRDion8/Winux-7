import configparser
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import desktop
import locales

spec=importlib.util.spec_from_file_location('first_login',Path(__file__).with_name('desktop-first-login.py'))
first=importlib.util.module_from_spec(spec);spec.loader.exec_module(first)

class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        desktop.write(self.root,'usr/share/xsessions/plasmax11.desktop','[Desktop Entry]\nType=Application\nName=Plasma\nExec=startplasma-x11\n')
    def test_x11_session_unique_preserves_autologin_and_theme(self):
        desktop.write(self.root,'etc/sddm.conf','[Autologin]\nUser=alice\nSession=plasmawayland.desktop\n[Theme]\nCurrent=custom\n')
        calls=[]
        desktop.configure_x11(self.root,'alice',lambda *c:calls.append(c))
        c=configparser.ConfigParser();c.read(self.root/'etc/sddm.conf')
        self.assertEqual(c['Autologin']['User'],'alice')
        self.assertEqual(c['Autologin']['Session'],'winux-x11.desktop')
        self.assertEqual(c['Theme']['Current'],'custom')
        self.assertEqual(c['Users']['RememberLastSession'],'false')
        self.assertIn('startplasma-x11',(self.root/'usr/share/xsessions/winux-x11.desktop').read_text())
        self.assertTrue((self.root/'etc/sddm.conf.winux-backup').exists())
    def test_does_not_enable_autologin(self):
        desktop.configure_x11(self.root,'alice',lambda *c:None)
        c=configparser.ConfigParser();c.read(self.root/'etc/sddm.conf')
        self.assertNotIn('user',c['Autologin'])
    def test_aero_x11_preferred(self):
        desktop.write(self.root,'usr/share/xsessions/aero.desktop','[Desktop Entry]\nExec=start-aero-x11\n')
        desktop.configure_x11(self.root,'alice',lambda *c:None)
        self.assertIn('start-aero-x11',(self.root/'usr/share/xsessions/winux-x11.desktop').read_text())
    def test_missing_x11_refused(self):
        (self.root/'usr/share/xsessions/plasmax11.desktop').unlink()
        with self.assertRaises(RuntimeError):desktop.configure_x11(self.root,'alice',lambda *c:None)
        self.assertFalse((self.root/'etc/sddm.conf').exists())
    def test_yay_and_tmog_build_as_user_and_cleanup_sudo(self):
        calls=[]
        desktop.install_tmog(self.root,'alice','/home/alice',lambda *c:calls.append(c))
        builds=[c for c in calls if c[0]=='runuser']
        self.assertEqual(len(builds),3)
        self.assertTrue(all(c[2]=='alice' for c in builds))
        self.assertIn('https://aur.archlinux.org/yay-bin.git', builds[0])
        self.assertIn('tmog-bin', builds[-1])
        self.assertIn(('test','-x','/usr/bin/tmog-task-manager'),calls)
        self.assertEqual(list((self.root/'etc/sudoers.d').iterdir()),[])
        self.assertEqual(list((self.root/'var/tmp').iterdir()),[])
    def test_existing_yay_reused(self):
        desktop.write(self.root,'usr/bin/yay','fixture')
        calls=[]
        desktop.install_tmog(self.root,'alice','/home/alice',lambda *c:calls.append(c))
        self.assertFalse(any('clone' in c for c in calls))
        self.assertTrue(any('tmog-bin' in c for c in calls))
    def test_yay_build_directory_exists_and_is_owned_before_use(self):
        for existing_yay in (False, True):
            with self.subTest(existing_yay=existing_yay):
                if existing_yay:
                    desktop.write(self.root,'usr/bin/yay','fixture')
                owned=set()
                checked=[]
                def run(*args):
                    if args[:2] == ('chown','alice'):
                        for path in args[2:]:
                            self.assertTrue((self.root/path.lstrip('/')).is_dir())
                            owned.add(path)
                    if '--builddir' in args:
                        path=args[args.index('--builddir')+1]
                        directory=self.root/path.lstrip('/')
                        self.assertTrue(directory.is_dir(), 'yay needs an existing build directory')
                        self.assertIn(path,owned, 'build directory must belong to the package builder')
                        self.assertEqual(directory.stat().st_mode & 0o777,0o700)
                        import subprocess
                        subprocess.run(['git','-C',str(directory),'init','--quiet'],check=True)
                        checked.append(path)
                desktop.install_tmog(self.root,'alice','/home/alice',run)
                self.assertEqual(len(checked),1)
                self.assertEqual(list((self.root/'var/tmp').iterdir()),[])
    def test_aur_failure_cleans_temporary_privileges(self):
        def run(*args):
            if 'tmog-bin' in args: raise RuntimeError('AUR failure')
        with self.assertRaisesRegex(RuntimeError,'AUR failure'):
            desktop.install_tmog(self.root,'alice','/home/alice',run)
        self.assertEqual(list((self.root/'etc/sudoers.d').iterdir()),[])
        self.assertEqual(list((self.root/'var/tmp').iterdir()),[])
    def test_install_arms_unprivileged_setup_and_copies_exact_wallpaper(self):
        desktop.install(self.root,'alice','/home/alice',lambda *c:None)
        copied=self.root/'usr/share/backgrounds/winux/wallpaper.jpg'
        self.assertEqual(copied.read_bytes(),(desktop.ROOT/'wallpaper.jpg').read_bytes())
        self.assertIn('desktop-first-login.py',(self.root/'home/alice/.config/autostart/winux-desktop.desktop').read_text())
        self.assertIn('winux-taskmanager',(self.root/'home/alice/.local/share/applications/org.kde.plasma-systemmonitor.desktop').read_text())
    def test_first_login_localized_desktop_and_wine_once(self):
        home=self.root/'home';home.mkdir();state=home/'state';state.mkdir()
        calls=[]
        def run(*args,**kwargs):
            calls.append((args,kwargs))
            if args[0]=='xdg-user-dir':return str(home/'Schreibtisch')
            if args[0]=='qdbus6':return 'winux-desktop-applied'
            return ''
        with patch.dict(first.os.environ,{'XDG_CONFIG_HOME':str(home/'.config'),'XDG_STATE_HOME':str(home/'.local/state')}),patch.object(first,'run',side_effect=run):
            first.configure(home,state);first.configure(home,state)
        self.assertIn('URL=trash:/',(home/'Schreibtisch/Trash.desktop').read_text())
        wines=[x for x in calls if x[0][0]=='wineboot']
        self.assertEqual(len(wines),1)
        self.assertEqual(wines[0][1]['env']['WINEPREFIX'],str(home/'.wine'))
        self.assertNotIn('WINEARCH',wines[0][1]['env'])
    def test_failed_wine_keeps_retry_marker_unset(self):
        state=self.root/'state';state.mkdir();(state/'desktop-complete').touch()
        with patch.object(first,'run',side_effect=RuntimeError('wine failed')):
            with self.assertRaises(RuntimeError):first.configure(self.root,state)
        self.assertFalse((state/'wine-complete').exists())
    def test_locale_catalog_and_charset(self):
        p=self.root/'SUPPORTED';p.write_text('ja_JP.UTF-8 UTF-8\nja_JP.EUC-JP EUC-JP\ninvalid;name UTF-8\n')
        self.assertEqual(locales.supported(p),{'ja_JP.UTF-8':'UTF-8','ja_JP.EUC-JP':'EUC-JP'})
        self.assertGreater(len(locales.choices()),100)

if __name__=='__main__':unittest.main(verbosity=2)
