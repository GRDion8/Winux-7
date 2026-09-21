"""Desktop defaults shared by new installs and the existing-system updater."""
import configparser
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
PACKAGES = ['firefox', 'wine', 'wine-mono', 'wine-gecko', 'winetricks', 'git', 'base-devel', 'sudo',
            'xdg-utils', 'xdg-user-dirs', 'qt6-tools', 'plasma-x11-session', 'kwin-x11']
TMOG_PACKAGE = 'tmog-bin'


def install_tmog(root, username, home, run):
    """Build AUR packages as the desktop user, with temporary pacman-only sudo."""
    root = Path(root)
    parent = root/'var/tmp'
    parent.mkdir(parents=True, exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix='winux-aur-', dir=parent))
    inside = '/' + str(build.relative_to(root))
    sudoers = root/'etc/sudoers.d'
    sudoers.mkdir(parents=True, exist_ok=True)
    rule = None
    try:
        import os
        fd, name = tempfile.mkstemp(prefix='90-winux-aur-', dir=sudoers)
        rule = Path(name)
        with os.fdopen(fd, 'w') as stream:
            stream.write(f'{username} ALL=(root) NOPASSWD: /usr/bin/pacman\n')
        rule.chmod(0o440)
        run('visudo', '-cf', '/' + str(rule.relative_to(root)))
        # yay invokes git in this directory; create it before dropping privileges.
        (build/'packages').mkdir(mode=0o700)
        run('chown', username, inside, inside+'/packages')
        def user(*args):
            return run('runuser', '-u', username, '--', 'env', 'HOME='+home,
                       'XDG_CACHE_HOME='+inside+'/cache', *args)
        if not (root/'usr/bin/yay').is_file():
            user('git', 'clone', '--depth', '1', 'https://aur.archlinux.org/yay-bin.git', inside+'/yay-bin')
            user('bash', '-c', 'cd -- "$1" && makepkg -si --needed --noconfirm',
                 'winux-build-yay', inside+'/yay-bin')
        run('test', '-x', '/usr/bin/yay')
        user('/usr/bin/yay', '-S', '--needed', '--noconfirm', '--builddir', inside+'/packages', TMOG_PACKAGE)
        run('pacman', '-Q', TMOG_PACKAGE)
        run('test', '-x', '/usr/bin/tmog-task-manager')
    finally:
        if rule is not None:
            rule.unlink(missing_ok=True)
        shutil.rmtree(build)


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
    # Use a dedicated session list so a missing/stale SDDM state cannot select
    # the first vendor Wayland entry. Keep vendor session files intact.
    login_sessions = root/'usr/share/winux-setup/xsessions'
    login_sessions.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sessions/'winux-x11.desktop', login_sessions/'winux-x11.desktop')
    (root/'usr/share/winux-setup/wayland-sessions').mkdir(parents=True, exist_ok=True)
    # /etc/sddm.conf takes precedence over all vendor and local drop-ins.
    edit_ini(root/'etc/sddm.conf', {'General':{'DisplayServer':'x11'},
        'Users':{'RememberLastSession':'true'}, 'Autologin':{'Session':'winux-x11.desktop'},
        'X11':{'SessionDir':'/usr/share/winux-setup/xsessions'},
        'Wayland':{'SessionDir':'/usr/share/winux-setup/wayland-sessions'}})
    state = root/'var/lib/sddm/state.conf'
    edit_ini(state, {'Last':{'User':username, 'Session':'winux-x11.desktop'}})
    state.chmod(0o600)
    run('chown','sddm:sddm','/var/lib/sddm')
    run('chown','sddm:sddm','/var/lib/sddm/state.conf')


def configure_avatar(root, username, home, run):
    """Seed both KDE's home avatar and SDDM's readable system copy."""
    root = Path(root)
    image = ROOT/'user.bmp'
    # Copy the supplied BMP unchanged; Qt identifies the image by its contents.
    for relative in [home.lstrip('/')+'/.face.icon', home.lstrip('/')+'/.face',
                     'usr/share/winux-setup/user.bmp',
                     'usr/share/sddm/faces/'+username+'.face.icon',
                     'var/lib/AccountsService/icons/'+username]:
        path = root/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        # Replace the entry itself, rather than following a previous avatar symlink.
        if path.is_symlink():
            path.unlink()
        shutil.copyfile(image, path)
        path.chmod(0o644)
    run('chown', username, home+'/.face.icon', home+'/.face')
    edit_ini(root/'etc/sddm.conf', {'Theme':{'FacesDir':'/usr/share/sddm/faces', 'EnableAvatars':'true'}})
    account = root/'var/lib/AccountsService/users'/username
    edit_ini(account, {'User':{'Icon':'/var/lib/AccountsService/icons/'+username}})
    account.chmod(0o600)


def configure_defaults(root, username, home, run):
    """Apply the avatar, login and menu fixes without reinstalling packages."""
    root = Path(root)
    run('test', '-x', '/usr/bin/tmog-task-manager')
    configure_x11(root, username, run)
    configure_avatar(root, username, home, run)
    write(root, 'usr/local/bin/winux-taskmanager', '#!/bin/sh\nexec /usr/bin/tmog-task-manager "$@"\n', 0o755)
    # Aero's taskbar/Start context menus invoke the legacy executable directly.
    write(root, 'usr/local/bin/ksysguard', '#!/bin/sh\nexec /usr/bin/tmog-task-manager "$@"\n', 0o755)
    launcher = '[Desktop Entry]\nType=Application\nName=Task Manager\nComment=TMOG system and process monitor\nExec=/usr/local/bin/winux-taskmanager\nIcon=utilities-system-monitor\nTerminal=false\nCategories=System;Monitor;\nStartupNotify=true\n'
    write(root, 'usr/share/applications/winux-taskmanager.desktop', launcher)
    userhome = root/home.lstrip('/')
    for name in ['org.kde.plasma-systemmonitor.desktop', 'org.kde.ksysguard.desktop', 'ksysguard.desktop']:
        shortcut = 'X-KDE-Shortcuts=Ctrl+Esc\n' if name == 'org.kde.plasma-systemmonitor.desktop' else ''
        override = write(userhome, '.local/share/applications/'+name, launcher + shortcut)
        run('chown', username, '/'+str(override.relative_to(root)))
    for folder in ['.local', '.local/share', '.local/share/applications']:
        run('chown', username, home+'/'+folder)
    return launcher


def install(root, username, home, run, wallpaper=None):
    """run executes commands INSIDE root; home is the account's absolute target path."""
    root = Path(root)
    install_tmog(root, username, home, run)
    launcher = configure_defaults(root, username, home, run)
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
