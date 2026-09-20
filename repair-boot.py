#!/usr/bin/env python3
"""Repair an existing Winux installation. Never partitions or formats a disk."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import bootloader
import engine
import hardware


def repair(disk, apply=False):
    if os.geteuid() != 0 or not Path('/run/archiso').is_dir():
        raise engine.SetupError('Run this from the Arch/Winux live ISO as root.')
    if not re.fullmatch(r'/dev/(?:sd[a-z]+|vd[a-z]+|xvd[a-z]+|nvme\d+n\d+|mmcblk\d+)', disk):
        raise engine.SetupError('Specify a whole disk such as /dev/nvme0n1, not a partition.')
    with open('/run/winux-setup.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        runner = engine.Runner(lambda kind, text: print(text, flush=True), '/var/log/winux-boot-repair.log')
        def run(*args):
            return runner.run(args)
        mount = None
        mounted = False
        try:
            choices = {d.path:d for d in engine.discover()}
            selected = choices.get(disk)
            if not selected or selected.blocked:
                raise engine.SetupError('Disk unavailable or in use. Close setup and reboot the live ISO if needed.')
            mode = engine.firmware()
            bootloader.validate_layout(json.loads(run('sfdisk', '--json', disk)), disk, mode)
            for n, kind in [(2, 'ext4')] + ([(1, 'vfat')] if mode == 'uefi' else []):
                if run('blkid', '-p', '-s', 'TYPE', '-o', 'value', bootloader.part(disk, n)).strip() != kind:
                    raise engine.SetupError('Existing filesystem does not match Winux layout; stopping without formatting.')
            runner.write(f'Existing Winux-compatible layout: {disk}; firmware: {mode}. No partitions will be changed.')
            if not apply:
                runner.write('Inspection only. To rebuild boot files and register the firmware entry, repeat with --apply.')
                return
            bootloader.check_firmware(mode)
            if {d.path:d for d in engine.discover()}.get(disk) != selected:
                raise engine.SetupError('Disk changed or became busy. Stopping.')
            mount = Path(tempfile.mkdtemp(prefix='winux-repair-', dir='/mnt'))
            run('mount', '-t', 'ext4', bootloader.part(disk, 2), str(mount))
            mounted = True
            if 'Winux' not in bootloader.require_file(mount, '/etc/default/grub').read_text():
                raise engine.SetupError('This does not appear to be an existing Winux installation.')
            if mode == 'uefi':
                esp = mount/'boot/efi'
                if esp.is_symlink():
                    raise engine.SetupError('Unexpected EFI directory link; stopping.')
                esp.mkdir(parents=True, exist_ok=True)
                run('mount', '-t', 'vfat', bootloader.part(disk, 1), str(esp))
            bootloader.prepare_initramfs(mount, hardware.detect().plan()['storage_modules'], run)
            bootloader.install(mount, disk, mode, run, runner.write)
            run('sync')
            run('umount', '-R', str(mount))
            mounted = False
            runner.write('Boot repair completed and files verified. Shut down, disconnect the ISO, and boot the installed disk in the same firmware mode.')
        finally:
            try:
                if mounted:
                    run('umount', '-R', str(mount))
            finally:
                if mount and not os.path.ismount(mount):
                    mount.rmdir()
                runner.log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', required=True, help='Existing Winux whole disk, e.g. /dev/nvme0n1')
    parser.add_argument('--apply', action='store_true', help='Rebuild boot files; otherwise inspect only')
    args = parser.parse_args()
    try:
        repair(args.disk, args.apply)
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'Boot repair stopped: {exc}\nLog: /var/log/winux-boot-repair.log\n')
