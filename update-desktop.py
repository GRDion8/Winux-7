#!/usr/bin/env python3
"""Update an installed Winux 7 desktop without touching disks or boot configuration."""
import argparse
import fcntl
import os
from pathlib import Path
import pwd
import subprocess
import desktop
import winux_profile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user',default=os.environ.get('SUDO_USER'),help='Desktop account; defaults to the user who invoked sudo')
    parser.add_argument('--wallpaper',type=Path,help='Optional replacement PNG/JPEG/WebP')
    parser.add_argument('--defaults-only',action='store_true',help='Fix profile picture, X11 login and TMOG menu only; no package upgrade')
    parser.add_argument('--desktop-profile',action='store_true',help='Install the fixed Winux appearance and Control Panel on a working Aero desktop')
    parser.add_argument('--remove-desktop-profile',action='store_true',help='Restore the login and menu files saved before the Winux desktop profile')
    args=parser.parse_args()
    if sum([args.defaults_only,args.desktop_profile,args.remove_desktop_profile]) > 1:
        parser.error('Choose only one update mode.')
    if os.geteuid()!=0 or Path('/run/archiso').exists():
        parser.error('Run with sudo from the installed Winux 7 desktop, not the live ISO.')
    if args.defaults_only and args.wallpaper:
        parser.error('--wallpaper cannot be combined with --defaults-only.')
    if (args.desktop_profile or args.remove_desktop_profile) and args.wallpaper:
        parser.error('Profile operations cannot be combined with --wallpaper.')
    account=pwd.getpwnam(args.user or '')
    if account.pw_uid<1000 or not Path(account.pw_dir).is_dir():
        parser.error('Choose a regular desktop user with an existing home directory.')
    osrelease=Path('/etc/os-release').read_text()
    if not any(line in {'ID=arch','ID="arch"'} for line in osrelease.splitlines()) or not Path('/usr/share/winux-setup').is_dir():
        parser.error('This updater expects an installed Winux 7 system.')
    if args.wallpaper and not args.wallpaper.is_file():
        parser.error('Wallpaper file does not exist.')
    def run(*cmd):
        subprocess.run(cmd,check=True)
    with open('/run/winux-setup.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.remove_desktop_profile:
            winux_profile.remove(Path('/'))
            print('Previous login and menu files restored. Save your work and restart.')
            return
        if args.desktop_profile:
            winux_profile.install(Path('/'),run)
            print('Winux Control Panel and appearance profile installed. Save your work and restart. Initial Aero/desktop setup must finish before layout locking activates.')
            return
        if (Path('/')/winux_profile.STATE).exists():
            parser.error('Remove the desktop profile before reapplying older desktop defaults; then install the profile again.')
        if args.defaults_only:
            desktop.configure_defaults(Path('/'),account.pw_name,account.pw_dir,run)
            print('Profile picture, Winux 7 X11 login and TMOG menu updated. Save your work and restart.')
            return
        # Full system upgrade avoids unsupported partial upgrades on rolling Arch.
        run('pacman','-Syu','--needed',*desktop.PACKAGES)
        desktop.install(Path('/'),account.pw_name,account.pw_dir,run,args.wallpaper)
        # Re-arm desktop defaults on explicit updates; leave an existing Wine prefix intact.
        (Path(account.pw_dir)/'.local/state/winux-desktop-v1/desktop-complete').unlink(missing_ok=True)
        print('Winux 7 updated. Save your work and restart. X11 is selected for the next login; desktop and Wine setup finish after sign-in.')

if __name__=='__main__':
    try: main()
    except (RuntimeError,OSError,KeyError,subprocess.CalledProcessError) as exc:
        raise SystemExit(f'Update stopped: {exc}')
