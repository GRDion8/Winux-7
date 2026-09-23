"""Install the reversible Winux 7 desktop profile; never touch disks or firmware."""
import base64
import configparser
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
STATE = 'var/lib/winux-desktop-profile/manifest.json'
# Explicit desktop runtime, rather than the entire plasma-meta bundle.
PACKAGES = ['plasma-desktop', 'plasma-workspace', 'plasma-x11-session', 'kwin-x11',
            'sddm', 'systemsettings', 'kde-cli-tools', 'plasma-nm', 'plasma-pa',
            'powerdevil', 'kscreen', 'polkit-kde-agent', 'plasma-integration',
            'kde-gtk-config', 'xdg-desktop-portal-kde', 'kio-extras']
THEME = {
    'kdeglobals': '[KDE]\nLookAndFeelPackage[$i]=authui7\nwidgetStyle[$i]=kvantum\nSingleClick=false\n\n[General]\nColorScheme[$i]=Aero\n\n[Icons]\nTheme[$i]=Windows 7 Aero\n',
    'plasmarc': '[Theme]\nname[$i]=Seven-Black\n',
    'kcminputrc': '[Mouse]\ncursorTheme[$i]=aero-drop\n',
    'kwinrc': '[org.kde.kdecoration2]\nlibrary[$i]=org.smod.smod\ntheme[$i]=SMOD\n\n[TabBox]\nLayoutName[$i]=thumbnail_seven\n\n[TabBoxAlternative]\nLayoutName[$i]=flip3d\n',
    'ksplashrc': '[KSplash]\nTheme[$i]=authui7\n',
    'kvantum.kvconfig': '[General]\ntheme=Windows7Aero\n',
}
LOCKED = '''[KDE Action Restrictions]
plasma/plasmashell/unlockedDesktop[$i]=false
plasma/allow_configure_when_locked[$i]=false
ghns[$i]=false
'''
APPEARANCE = {'kcm_lookandfeel', 'kcm_desktoptheme', 'kcm_colors', 'kcm_icons', 'kcm_style',
              'kcm_cursortheme', 'kcm_kwindecoration', 'kcm_splashscreen', 'kcm_kwin_effects',
              'kcm_kwin_scripts', 'kcm_sddm', 'kcm_plasmastyle', 'kcm_wallpaper'}
PANEL_DESKTOP = '''[Desktop Entry]
Type=Application
Name=Control Panel
Comment=Change your computer's settings
Exec=/usr/local/bin/winux-control-panel
Icon=preferences-system
Categories=Settings;
Terminal=false
StartupNotify=true
'''


def read_state(root):
    path = root/STATE
    return json.loads(path.read_text()) if path.exists() else {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Transaction:
    def __init__(self, root):
        self.root = Path(root)
        self.entries = read_state(self.root)

    def save(self):
        path = self.root/STATE
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_suffix('.tmp')
        pending.write_text(json.dumps(self.entries, indent=2)+'\n')
        pending.chmod(0o600)
        pending.replace(path)

    def write(self, relative, content, mode=0o644):
        relative = relative.lstrip('/')
        path = self.root/relative
        if relative not in self.entries:
            if path.is_symlink():
                raise RuntimeError(f'Refusing to overwrite symlink: {path}')
            self.entries[relative] = {'original': base64.b64encode(path.read_bytes()).decode() if path.exists() else None,
                                      'mode': path.stat().st_mode & 0o777 if path.exists() else None}
        else:
            recorded = self.entries[relative].get('installed')
            if recorded and (not path.is_file() or path.is_symlink() or digest(path) != recorded):
                raise RuntimeError(f'Profile file was edited separately: {path}. Restore or review it before updating.')
        data = content.encode() if isinstance(content, str) else content
        # Record the expected result before writing so interrupted installs remain recoverable.
        self.entries[relative]['installed'] = hashlib.sha256(data).hexdigest()
        self.save()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(mode)


def remove(root):
    root = Path(root)
    entries = read_state(root)
    # Check every file before restoring anything. Do not discard later manual edits.
    for relative, record in entries.items():
        path = root/relative
        if path.exists() and (path.is_symlink() or digest(path) != record['installed']):
            raise RuntimeError(f'Profile file was edited separately: {path}. Back up and review that edit first.')
    for relative, record in reversed(list(entries.items())):
        path = root/relative
        if record['original'] is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(base64.b64decode(record['original']))
            path.chmod(record['mode'])
    (root/STATE).unlink(missing_ok=True)


def install(root, run):
    """run executes inside root. Compile our Qt front end before changing login files."""
    root = Path(root)
    for required in ['usr/bin/startatp', 'usr/share/plasma/look-and-feel/authui7/metadata.json',
                     'usr/share/winux-setup', 'usr/share/xsessions/winux-x11.desktop']:
        if not (root/required).exists():
            raise RuntimeError('The Winux desktop profile requires a completed Aero installation: '+required)
    parent = root/'var/tmp'
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='winux-control-panel-', dir=parent) as folder:
        build = Path(folder)
        for name in ['control-panel.cpp', 'wallpaper.hpp']:
            shutil.copyfile(ROOT/name, build/name)
        inside = '/'+str(build.relative_to(root))
        # Fixed command, positional directory argument, no user text interpolated into a shell.
        run('sh', '-c', 'cd -- "$1" && c++ -std=c++17 -fPIC control-panel.cpp -o control-panel $(pkg-config --cflags --libs Qt6Widgets Qt6DBus)', 'winux-build', inside)
        binary = (build/'control-panel').read_bytes()
    tx = Transaction(root)
    tx.write('usr/local/bin/winux-control-panel', binary, 0o755)
    tx.write('usr/local/bin/systemsettings', '#!/bin/sh\nexec /usr/local/bin/winux-control-panel "$@"\n', 0o755)
    tx.write('usr/local/bin/winux-session', (ROOT/'winux-session.sh').read_bytes(), 0o755)
    tx.write('usr/share/winux-setup/desktop-first-login.py', (ROOT/'desktop-first-login.py').read_bytes())
    tx.write('usr/share/winux-setup/welcome.py', (ROOT/'welcome.py').read_bytes())
    tx.write('etc/xdg/autostart/winux-desktop.desktop', '[Desktop Entry]\nType=Application\nName=Winux 7\nExec=python /usr/share/winux-setup/desktop-first-login.py\nOnlyShowIn=KDE;\nX-KDE-autostart-after=panel\n')
    for name, content in THEME.items():
        tx.write('etc/winux-7/theme/'+name, content)
    tx.write('etc/winux-7/locked/kdeglobals', LOCKED)
    # Duplicate vendor settings IDs so pinned shortcuts also open the curated panel.
    ids = {'systemsettings.desktop', 'org.kde.systemsettings.desktop'}
    for path in (root/'usr/share/applications').glob('*.desktop'):
        content = path.read_text(errors='replace')
        if path.stem in APPEARANCE or any(re.search(r'\b'+re.escape(k)+r'\b', content) for k in APPEARANCE):
            tx.write('usr/local/share/applications/'+path.name, '[Desktop Entry]\nType=Application\nName=Appearance\nHidden=true\n')
        if path.name in ids:
            tx.write('usr/local/share/applications/'+path.name, PANEL_DESKTOP)
            ids.discard(path.name)
    if len(ids) == 2:
        tx.write('usr/local/share/applications/winux-control-panel.desktop', PANEL_DESKTOP)
    for name in ['usr/share/xsessions/winux-x11.desktop', 'usr/share/winux-setup/xsessions/winux-x11.desktop']:
        text = (root/name).read_text()
        text = re.sub(r'^Exec=.*$', 'Exec=/usr/local/bin/winux-session', text, flags=re.M)
        text = re.sub(r'^TryExec=.*$', 'TryExec=/usr/local/bin/winux-session', text, flags=re.M)
        tx.write(name, text)
