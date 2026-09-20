"""Desktop defaults shared by new installs and the existing-system updater."""
import configparser
import hashlib
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parent
PACKAGES = ['firefox', 'wine', 'wine-mono', 'wine-gecko', 'winetricks', 'fuse2',
            'xdg-utils', 'xdg-user-dirs', 'qt6-tools', 'plasma-x11-session', 'kwin-x11']
TMOG_URL = 'https://tmog.org/downloads/TaskManagerOG-0.1.4-x86_64.AppImage'
TMOG_SHA256 = 'a9873347ee2b1a4895cf2c8f39660d8cf4b86ab89b24c08d541f237e365b4346'


def fetch_tmog(destination):
    """Pinned official Linux build, checked against the publisher's release manifest."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        with destination.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() == TMOG_SHA256:
                return destination
    temporary = destination.with_suffix('.download')
    try:
        with urllib.request.urlopen(TMOG_URL, timeout=60) as response, temporary.open('wb') as out:
            shutil.copyfileobj(response, out)
        with temporary.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != TMOG_SHA256:
            raise RuntimeError('TMOG checksum mismatch. No unverified application will be installed.')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def write(root, relative, text, mode=0o644):
    path = Path(root)/relative.lstrip('/')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)
    return path


def edit_ini(path, changes):
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.optionxform = str
    if path.exists():
        config.read(path)
        backup = path.with_name(path.name + '.winux-backup')
        if not backup.exists():
            shutil.copy2(path, backup)
    for section, values in changes.items():
        if not config.has_section(section):
            config.add_section(section)
        for key, value in values.items():
            config.set(section, key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as stream:
        config.write(stream, space_around_delimiters=False)


def configure_x11(root, username, run):
    root = Path(root)
    sessions = root/'usr/share/xsessions'
    candidates = sorted(p for p in sessions.glob('*.desktop') if p.name != 'winux-x11.desktop')
    aero = [p for p in candidates if 'aero' in p.name.lower()]
    source = next(iter(aero), sessions/'plasmax11.desktop')
    if not source.is_file() or 'Exec=' not in source.read_text():
        raise RuntimeError('No installed Plasma/Aero X11 session found. Stopping rather than selecting Wayland.')
    # A unique basename prevents ambiguity with an Aero Wayland session of the same name.
    shutil.copy2(source, sessions/'winux-x11.desktop')
    names={'Name':'Winux 7', 'Hidden':'false', 'NoDisplay':'false'}
    for line in source.read_text().splitlines():
        if line.startswith('Name[') and '=' in line:
            names[line.split('=',1)[0]]='Winux 7'
    edit_ini(sessions/'winux-x11.desktop', {'Desktop Entry':names})
    # /etc/sddm.conf takes precedence over all vendor and local drop-ins.
    edit_ini(root/'etc/sddm.conf', {'General':{'DisplayServer':'x11'},
        'Users':{'RememberLastSession':'false'}, 'Autologin':{'Session':'winux-x11.desktop'}})
    state = root/'var/lib/sddm/state.conf'
    edit_ini(state, {'Last':{'User':username, 'Session':'winux-x11.desktop'}})
    state.chmod(0o600)
    run('chown','sddm:sddm','/var/lib/sddm')
    run('chown','sddm:sddm','/var/lib/sddm/state.conf')


def install(root, username, home, run, tmog, wallpaper=None):
    """run executes commands INSIDE root; home is the account's absolute target path."""
    root = Path(root)
    configure_x11(root, username, run)
    app = root/'opt/winux/tmog/TaskManagerOG.AppImage'
    app.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tmog, app)
    app.chmod(0o755)
    write(root, 'usr/local/bin/winux-taskmanager', '#!/bin/sh\nexec /opt/winux/tmog/TaskManagerOG.AppImage "$@"\n', 0o755)
    launcher = '[Desktop Entry]\nType=Application\nName=Task Manager\nComment=TMOG system and process monitor\nExec=/usr/local/bin/winux-taskmanager\nIcon=utilities-system-monitor\nTerminal=false\nCategories=System;Monitor;\nStartupNotify=true\n'
    write(root, 'usr/share/applications/winux-taskmanager.desktop', launcher)
    write(root, 'usr/share/applications/winux-wine.desktop', '[Desktop Entry]\nType=Application\nName=Windows Application\nExec=wine start /unix %f\nIcon=wine\nNoDisplay=true\nMimeType=application/x-ms-dos-executable;application/x-msdownload;application/vnd.microsoft.portable-executable;application/x-msi;\n')
    write(root, 'usr/share/applications/winux-wine-settings.desktop', '[Desktop Entry]\nType=Application\nName=Windows Application Settings\nExec=winecfg\nIcon=wine\nCategories=Settings;\n')
    data = root/'usr/share/winux-setup'
    data.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'desktop-first-login.py', data/'desktop-first-login.py')
    image = Path(wallpaper) if wallpaper else ROOT/'wallpaper.jpg'
    if image.is_file():
        if image.suffix.lower() not in {'.png','.jpg','.jpeg','.webp'}:
            raise RuntimeError('Wallpaper must be a PNG, JPEG or WebP image.')
        target = root/'usr/share/backgrounds/winux'/('wallpaper' + image.suffix.lower())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, target)
        write(root, 'usr/share/winux-setup/wallpaper-path', '/' + str(target.relative_to(root)) + '\n')
    userhome = root/home.lstrip('/')
    autostart = write(userhome, '.config/autostart/winux-desktop.desktop', '[Desktop Entry]\nType=Application\nName=Finish Winux desktop setup\nExec=python /usr/share/winux-setup/desktop-first-login.py\nOnlyShowIn=KDE;\nX-KDE-autostart-after=panel\n')
    # Preserve KDE's familiar system-monitor launcher identity so existing menu/shortcut links open TMOG.
    override = write(userhome, '.local/share/applications/org.kde.plasma-systemmonitor.desktop', launcher + 'X-KDE-Shortcuts=Ctrl+Esc\n')
    run('chown',username, '/' + str(autostart.relative_to(root)))
    run('chown',username, '/' + str(override.relative_to(root)))
    # These directories may have just been created as root on an existing installation.
    for folder in ['.config', '.config/autostart', '.local', '.local/share', '.local/share/applications']:
        run('chown',username,home+'/'+folder)
