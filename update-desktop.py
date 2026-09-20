#!/usr/bin/env python3
"""Update an installed Winux 7 desktop without touching disks or boot configuration."""
import argparse
import fcntl
import os
from pathlib import Path
import pwd
import subprocess
import desktop


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user',default=os.environ.get('SUDO_USER'),help='Desktop account; defaults to the user who invoked sudo')
    parser.add_argument('--wallpaper',type=Path,help='Optional replacement PNG/JPEG/WebP')
    args=parser.parse_args()
    if os.geteuid()!=0 or Path('/run/archiso').exists():
        parser.error('Run with sudo from the installed Winux 7 desktop, not the live ISO.')
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
        print('Downloading and verifying TMOG…',flush=True)
        tmog=desktop.fetch_tmog(Path('/var/cache/winux/TMOG.AppImage'))
        # Full system upgrade avoids unsupported partial upgrades on rolling Arch.
        run('pacman','-Syu','--needed',*desktop.PACKAGES)
        desktop.install(Path('/'),account.pw_name,account.pw_dir,run,tmog,args.wallpaper)
        # Re-arm desktop defaults on explicit updates; leave an existing Wine prefix intact.
        (Path(account.pw_dir)/'.local/state/winux-desktop-v1/desktop-complete').unlink(missing_ok=True)
        print('Winux 7 updated. Save your work and restart. X11 is selected for the next login; desktop and Wine setup finish after sign-in.')

if __name__=='__main__':
    try: main()
    except (RuntimeError,OSError,KeyError,subprocess.CalledProcessError) as exc:
        raise SystemExit(f'Update stopped: {exc}')
