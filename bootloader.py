"""Shared boot installation/verification. Does not format or partition disks."""
import json
from pathlib import Path
import re
import os
import shutil

EFI_TYPE = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'
BIOS_TYPE = '21686148-6449-6e6f-744e-656564454649'
ROOT_TYPE = '0fc63daf-8483-4772-8e79-3d69d8477de4'

class BootError(RuntimeError):
    pass


def part(disk, number):
    return disk + ('p' if disk[-1].isdigit() else '') + str(number)


def validate_layout(data, disk, mode):
    if mode not in {'uefi', 'bios'}:
        raise BootError('Unsupported boot mode.')
    table = data['partitiontable']
    parts = table.get('partitions', [])
    if table.get('label') != 'gpt' or table.get('device') != disk or len(parts) != 2:
        raise BootError('Expected the existing Winux two-partition GPT layout; refusing to change it.')
    expected = [EFI_TYPE if mode == 'uefi' else BIOS_TYPE, ROOT_TYPE]
    for i, (p, kind) in enumerate(zip(parts, expected), 1):
        if p.get('node') != part(disk, i) or p.get('type','').lower() != kind:
            raise BootError('Partition types do not match the boot mode. Boot the ISO in the same UEFI/BIOS mode as the installation. No repartitioning attempted.')
        if p.get('start', 0) < 1 or p.get('size', 0) < 1:
            raise BootError('Invalid partition boundaries.')
    if parts[0]['start'] + parts[0]['size'] > parts[1]['start']:
        raise BootError('Partition boundaries overlap.')


def secure_boot_enabled():
    for p in Path('/sys/firmware/efi/efivars').glob('SecureBoot-*'):
        data = p.read_bytes()
        if len(data) >= 5:
            return data[4] == 1
    return False


def require_file(root, path):
    p = Path(root)/path.lstrip('/')
    if not p.is_file() or p.stat().st_size == 0:
        raise BootError(f'Missing or empty boot file: {path}. Installation is not boot-ready.')
    return p


def check_firmware(mode):
    if mode == 'uefi':
        if secure_boot_enabled():
            raise BootError('Disable Secure Boot before using this unsigned installer.')
        path = Path('/sys/firmware/efi/efivars')
        if not os.path.ismount(path) or not os.access(path, os.W_OK) or os.statvfs(path).f_flag & os.ST_RDONLY:
            raise BootError('UEFI variables are unavailable or read-only. Boot the ISO in UEFI mode with writable EFI variables.')


def prepare_initramfs(root, modules, run):
    root = Path(root)
    kernels = [p.parent.name for p in (root/'usr/lib/modules').glob('*/pkgbase') if p.read_text().strip() == 'linux']
    if len(kernels) != 1:
        raise BootError('Cannot identify the installed linux kernel; refusing to guess its module version.')
    for module in modules:
        if not re.fullmatch(r'[a-zA-Z0-9_]+', module):
            raise BootError('Invalid storage module name.')
        run('arch-chroot', str(root), 'modinfo', '-k', kernels[0], module)
    preset = root/'etc/mkinitcpio.d/linux.preset'
    preset.parent.mkdir(parents=True, exist_ok=True)
    if preset.exists() and not preset.with_suffix('.preset.winux-backup').exists():
        shutil.copy2(preset, preset.with_suffix('.preset.winux-backup'))
    preset.write_text('ALL_kver="/boot/vmlinuz-linux"\nPRESETS=(\'default\' \'fallback\')\ndefault_image="/boot/initramfs-linux.img"\nfallback_image="/boot/initramfs-linux-fallback.img"\nfallback_options="-S autodetect"\n')
    config = root/'etc/mkinitcpio.conf.d/90-winux-storage.conf'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('MODULES+=(' + ' '.join(modules) + ')\n')


def install(root, disk, mode, run, log, register=True):
    root = Path(root)
    def chroot(*args):
        return run('arch-chroot', str(root), *args)
    validate_layout(json.loads(run('sfdisk','--json',disk)), disk, mode)
    # Check exact mounted sources before writing a bootloader.
    for mount, device, kind in [(root,part(disk,2),'ext4')] + ([(root/'boot/efi',part(disk,1),'vfat')] if mode=='uefi' else []):
        data = json.loads(run('findmnt','--json','--mountpoint',str(mount),'--output','SOURCE,FSTYPE'))['filesystems']
        if len(data)!=1 or data[0]['source'] != device or data[0]['fstype'] != kind:
            raise BootError(f'{mount} is not the expected {kind} filesystem on {device}.')
    uuid = run('blkid','-p','-s','UUID','-o','value',part(disk,2)).strip()
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', uuid):
        raise BootError('Could not verify the root filesystem UUID.')
    if mode == 'uefi' and secure_boot_enabled():
        raise BootError('Secure Boot is enabled. This installer does not provide a signed boot chain; configure firmware before continuing.')
    # Generate images BEFORE generating the menu that references them.
    chroot('mkinitcpio','-P')
    require_file(root, '/boot/vmlinuz-linux')
    require_file(root, '/boot/initramfs-linux.img')
    require_file(root, '/boot/initramfs-linux-fallback.img')
    chroot('lsinitcpio','/boot/initramfs-linux.img')
    chroot('lsinitcpio','/boot/initramfs-linux-fallback.img')
    if mode == 'uefi':
        chroot('grub-install','--target=x86_64-efi','--efi-directory=/boot/efi','--bootloader-id=Winux','--no-nvram','--recheck')
        chroot('grub-install','--target=x86_64-efi','--efi-directory=/boot/efi','--removable','--no-nvram','--recheck')
        for p in ['/boot/efi/EFI/Winux/grubx64.efi','/boot/efi/EFI/BOOT/BOOTX64.EFI']:
            if require_file(root, p).read_bytes()[:2] != b'MZ':
                raise BootError(f'{p} is not an EFI executable.')
        if register:
            esp_uuid = run('blkid', '-s', 'PARTUUID', '-o', 'value', part(disk,1)).strip()
            if not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', esp_uuid):
                raise BootError('Cannot identify the EFI partition UUID.')
            pattern = r'^Boot([0-9A-Fa-f]{4})\*\s+Winux\s+.*HD\(1,GPT,' + re.escape(esp_uuid) + r',.*[\\/]EFI[\\/]Winux[\\/]grubx64\.efi'
            entries = chroot('efibootmgr', '--verbose')
            entry = re.search(pattern, entries, re.M|re.I)
            if not entry:
                # Explicit parent disk/partition; never let efibootmgr guess /dev/sda.
                chroot('efibootmgr','--create','--disk',disk,'--part','1','--label','Winux','--loader',r'\EFI\Winux\grubx64.efi')
                entries = chroot('efibootmgr','--verbose')
                entry = re.search(pattern, entries, re.M|re.I)
            order = re.search(r'^BootOrder:\s*(.+)', entries, re.M)
            if not entry or not order or entry.group(1).upper() not in order.group(1).upper().split(','):
                raise BootError('The Winux firmware boot entry was not verified in BootOrder. Do not assume the disk will boot automatically.')
    else:
        chroot('grub-install','--target=i386-pc','--recheck',disk)
        require_file(root, '/boot/grub/i386-pc/core.img')
    chroot('grub-mkconfig','-o','/boot/grub/grub.cfg')
    cfg = require_file(root, '/boot/grub/grub.cfg').read_text()
    chroot('grub-script-check','/boot/grub/grub.cfg')
    if 'menuentry ' not in cfg or '/vmlinuz-linux' not in cfg or '/initramfs-linux.img' not in cfg or f'root=UUID={uuid}' not in cfg:
        raise BootError('GRUB menu is missing the kernel, initramfs, or verified root UUID.')
    fstab = require_file(root, '/etc/fstab').read_text()
    if not re.search(r'^UUID='+re.escape(uuid)+r'\s+/\s+ext4\s', fstab, re.M):
        raise BootError('fstab does not identify the verified root filesystem.')
    log('Verified kernel, initramfs, GRUB menu, root UUID and bootloader files.' + (' UEFI boot entry registered.' if mode=='uefi' and register else ''))
