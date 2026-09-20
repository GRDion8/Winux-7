"""Winux Setup engine. No disk writes happen on import or during discovery."""
from __future__ import annotations
import dataclasses
import fcntl
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import subprocess
import time
import bootloader
import hardware
import desktop
import locales

ROOT = Path(__file__).resolve().parent
TARGET = Path('/mnt/winux-target')
MIN_DISK = 48 * 1024**3
LOCALES = locales.choices()
KEYBOARDS = {'US English': ('us', 'us'), 'UK English': ('uk', 'gb'), 'German': ('de-latin1', 'de'),
             'French': ('fr', 'fr'), 'Spanish': ('es', 'es')}
STAGES = ['Checking your computer', 'Preparing the drive', 'Installing Winux 7',
          'Setting up your account', 'Setting up your desktop', 'Making your computer bootable', 'Finishing up']

class SetupError(RuntimeError):
    pass

@dataclasses.dataclass(frozen=True)
class Disk:
    path: str
    size: int
    model: str
    serial: str
    identity: str
    blocked: str = ''

    @property
    def label(self):
        return f'{self.model or "Disk"} • {self.size / 1024**3:.1f} GiB • {self.path}'

@dataclasses.dataclass
class Config:
    disk: Disk
    username: str
    hostname: str
    password: str = dataclasses.field(repr=False)
    locale: str = 'en_US.UTF-8'
    keyboard: str = 'US English'
    timezone: str = 'Europe/Berlin'
    aero: bool = True
    firmware: str = 'uefi'
    confirmation: str = ''

    def validate(self):
        if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,30}', self.username) or self.username in {'root', 'nobody', 'sddm', 'arch', 'daemon'}:
            raise SetupError('Choose a user name starting with a lowercase letter; use letters, numbers, _ or - (up to 31 characters).')
        if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', self.hostname):
            raise SetupError('The computer name must be 1–63 letters, numbers or hyphens, with no leading/trailing hyphen.')
        if len(self.password) < 8 or len(self.password) > 256 or any(c in self.password for c in '\n\r\0'):
            raise SetupError('Use a password of 8–256 characters without line breaks.')
        if self.locale not in LOCALES.values() or self.keyboard not in KEYBOARDS:
            raise SetupError('Select a supported regional format and keyboard.')
        zone = Path('/usr/share/zoneinfo') / self.timezone
        if self.timezone.startswith('/') or '..' in Path(self.timezone).parts or not zone.is_file() or self.timezone not in timezones():
            raise SetupError('Select a time zone from the list.')
        if self.firmware not in {'uefi', 'bios'}:
            raise SetupError('Unsupported firmware mode.')
        if not re.fullmatch(r'/dev/(?:sd[a-z]+|vd[a-z]+|xvd[a-z]+|nvme\d+n\d+|mmcblk\d+)', self.disk.path):
            raise SetupError('Select a supported whole disk, not a partition or virtual mapping.')
        if self.disk.blocked or self.disk.size < MIN_DISK:
            raise SetupError(self.disk.blocked or 'Use a disk with at least 48 GiB.')
        if self.confirmation != f'ERASE {self.disk.path}':
            raise SetupError(f'Type ERASE {self.disk.path} to confirm the selected disk.')


def timezones():
    result = {'UTC'}
    for file in ['zone1970.tab', 'zone.tab']:
        p = Path('/usr/share/zoneinfo') / file
        if p.exists():
            for line in p.read_text().splitlines():
                if line and not line.startswith('#'):
                    result.add(line.split('\t')[2])
    return sorted(result)


def firmware():
    return 'uefi' if Path('/sys/firmware/efi').exists() else 'bios'


def parse_disks(data):
    disks = []
    def descendants(node):
        yield node
        for child in node.get('children', []):
            yield from descendants(child)
    for node in data.get('blockdevices', []):
        if node.get('type') != 'disk':
            continue
        nodes = list(descendants(node))
        reason = ''
        if any(n.get('ro') for n in nodes):
            reason = 'Read-only drive'
        elif any(any(m for m in (n.get('mountpoints') or [])) for n in nodes):
            reason = 'In use (mounted filesystem, swap, or live installation media)'
        elif any(n.get('type') not in {'disk', 'part'} for n in nodes):
            reason = 'In use by a storage mapping (LVM, RAID, or encryption)'
        elif int(node.get('size', 0)) < MIN_DISK:
            reason = 'At least 48 GiB is required'
        disks.append(Disk(node['path'], int(node['size']), (node.get('model') or '').strip(),
                          node.get('serial') or '', node.get('maj:min') or '', reason))
    return disks


def discover():
    p = subprocess.run(['lsblk', '--json', '--bytes', '--paths', '--output',
                        'PATH,SIZE,MODEL,SERIAL,MAJ:MIN,TYPE,RO,MOUNTPOINTS'], capture_output=True, text=True, check=True)
    return parse_disks(json.loads(p.stdout))


def partition_path(disk, number):
    return disk + ('p' if disk[-1].isdigit() else '') + str(number)


def partition_table(mode):
    if mode == 'uefi':
        return 'label: gpt\nsize=1GiB, type=U, name="System"\ntype=L, name="Winux"\n'
    if mode == 'bios':
        return 'label: gpt\nsize=2MiB, type=21686148-6449-6E6F-744E-656564454649, name="BIOS boot"\ntype=L, name="Winux"\n'
    raise SetupError('Invalid firmware mode')


class Runner:
    def __init__(self, emit, log_path):
        self.emit = emit
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.log_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        self.log = os.fdopen(fd, 'w', buffering=1)

    def write(self, text):
        self.log.write(text + '\n')
        self.emit('log', text)

    def run(self, args, *, input=None, secret=False, timeout=None):
        self.write('$ ' + ' '.join(str(a) for a in args))
        # No shell expansion. Password input is never placed in argv or logs.
        if input is not None or timeout:
            try:
                p = subprocess.run(list(map(str, args)), input=input, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                                   env={**os.environ, 'LC_ALL': 'C', 'TERM': 'dumb'})
            except subprocess.TimeoutExpired as exc:
                raise SetupError(f'{args[0]} timed out. Check the network and try again.') from exc
            output = '' if secret else p.stdout
            if output:
                self.write(output)
            if p.returncode:
                raise SetupError(f'{args[0]} failed (exit {p.returncode}). See the installation log.')
            return output
        p = subprocess.Popen(list(map(str, args)), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, start_new_session=True,
                             env={**os.environ, 'LC_ALL': 'C', 'TERM': 'dumb'})
        chunks = []
        try:
            for line in p.stdout:
                if not secret:
                    self.write(line.rstrip())
                    chunks.append(line)
            result = p.wait()
        except BaseException:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait()
            raise
        if result:
            raise SetupError(f'{args[0]} failed (exit {p.returncode}). See the installation log.')
        return ''.join(chunks)


class Installer:
    def __init__(self, config, emit, runner=None):
        self.c = config
        self.emit = emit
        self.runner = runner
        self.mounted = False
        self.tmog = None
        self.erased = False
        self.hardware_plan = hardware.Hardware("unknown", "none", []).plan()

    def stage(self, n):
        self.emit('stage', (n, STAGES[n]))

    def run(self, *args, **kw):
        return self.runner.run(args, **kw)

    def chroot(self, *args, **kw):
        return self.run('arch-chroot', str(TARGET), *args, **kw)

    def write(self, path, text, mode=0o644):
        p = TARGET / path.lstrip('/')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        p.chmod(mode)

    def check_live(self):
        if os.geteuid() != 0 or platform.machine() != 'x86_64' or not Path('/run/archiso').is_dir():
            raise SetupError('Real installation is allowed only as root inside an x86_64 Arch live ISO. Use Preview on your everyday computer.')
        for name in ['lsblk', 'sfdisk', 'wipefs', 'blkid', 'udevadm', 'mkfs.ext4', 'mkfs.fat', 'mount',
                     'findmnt', 'systemd-detect-virt', 'umount', 'pacstrap', 'arch-chroot', 'genfstab', 'pacman', 'timedatectl']:
            if not shutil.which(name):
                raise SetupError(f'The live environment is missing {name}. Start with launch.sh on a current Arch ISO.')
        if firmware() != self.c.firmware:
            raise SetupError('Firmware mode changed. Restart Setup.')
        if TARGET.is_symlink() or os.path.ismount(TARGET) or (TARGET.exists() and any(TARGET.iterdir())):
            raise SetupError(f'{TARGET} is occupied. Reboot the live ISO before starting another installation.')
        bootloader.check_firmware(self.c.firmware)
        self.check_disk()

    def check_disk(self):
        choices = {d.path: d for d in discover()}
        current = choices.get(self.c.disk.path)
        if current != self.c.disk:
            raise SetupError('The selected disk changed or became busy. Return to drive selection and review it again.')
        if current.blocked or not stat.S_ISBLK(os.stat(current.path).st_mode):
            raise SetupError('This disk is not available for installation.')
        # Refuse active holders, including mappings not surfaced as lsblk children.
        for node in Path('/sys/class/block').iterdir():
            real = node.resolve()
            parent = Path('/sys/class/block') / Path(current.path).name
            if real == parent.resolve() or parent.resolve() in real.parents:
                if (node / 'holders').exists() and any((node / 'holders').iterdir()):
                    raise SetupError('The disk has active storage holders. Reboot the ISO and select an unused disk.')

    def preflight(self):
        self.c.validate()
        self.check_live()
        info = hardware.detect()
        self.hardware_plan = info.plan()
        self.emit('log', 'Hardware selection: ' + json.dumps(self.hardware_plan))
        self.run('timedatectl', 'set-ntp', 'true')
        # Refresh only the disposable live ISO's package database, before disk writes.
        self.run('pacman', '-Sy', '--noconfirm')
        self.run('pacman', '-Si', 'base', 'linux', 'linux-firmware', 'grub', 'plasma-meta', 'plasma-x11-session', 'kwin-x11', 'mkinitcpio', *self.hardware_plan['packages'], *desktop.PACKAGES)
        if self.c.aero:
            details = self.run('pacman', '-Si', 'plasma-workspace')
            match = re.search(r'^Version\s*:\s*(?:\d+:)?(\d+\.\d+)\.', details, re.M)
            if not match or match.group(1) != '6.7':
                raise SetupError('Aero currently targets Plasma 6.7. The available package version differs or cannot be verified. No disk has been erased. Choose the standard Plasma option or use compatible repositories.')
            self.run('git', 'ls-remote', '--exit-code', 'https://github.com/aeroshell-desktop/aerothemeplasma.git', 'refs/heads/Plasma/6.7', timeout=60)
        self.emit('log', 'Downloading and verifying TMOG from its official publisher.')
        self.tmog = desktop.fetch_tmog(Path('/var/cache/winux/TMOG.AppImage'))
        self.check_disk()

    def execute(self):
        self.stage(0)
        self.c.validate()
        self.check_live()
        self.lock = open('/run/winux-setup.lock', 'w')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.lock.close()
            raise SetupError('Another installation is already running.') from exc
        self.runner = self.runner or Runner(self.emit, '/var/log/winux-setup.log')
        completed = False
        cleanup_ok = True
        try:
            self.preflight()
            self.stage(1)
            disk = self.c.disk.path
            self.check_disk()  # Last possible check before the first destructive command.
            self.erased = True
            self.run('wipefs', '--all', disk)
            self.run('sfdisk', '--lock', '--wipe', 'always', '--wipe-partitions', 'always', disk,
                     input=partition_table(self.c.firmware))
            self.run('udevadm', 'settle')
            bootloader.validate_layout(json.loads(self.run('sfdisk', '--json', disk)), disk, self.c.firmware)
            root_part = partition_path(disk, 2)
            boot_part = partition_path(disk, 1)
            self.prepare_filesystem(root_part, 'ext4')
            TARGET.mkdir(parents=True, exist_ok=True)
            self.run('mount', '-t', 'ext4', root_part, str(TARGET))
            self.mounted = True
            if self.c.firmware == 'uefi':
                self.prepare_filesystem(boot_part, 'vfat')
                (TARGET / 'boot/efi').mkdir(parents=True)
                self.run('mount', '-t', 'vfat', boot_part, str(TARGET / 'boot/efi'))
            self.stage(2)
            packages = ['base', 'linux', 'mkinitcpio', 'grub', 'efibootmgr',
                        'networkmanager', 'sudo', 'git', 'base-devel', 'pciutils', 'python', 'tk',
                        'plasma-meta', 'plasma-x11-session', 'kwin-x11', 'sddm', 'dolphin', 'konsole',
                        'kate', 'ark', 'gwenview', 'pipewire', 'pipewire-audio', 'pipewire-pulse', 'wireplumber',
                        'noto-fonts', 'ttf-dejavu', 'xdg-user-dirs', *self.hardware_plan['packages'], *desktop.PACKAGES]
            self.run('pacstrap', '-K', str(TARGET), *packages)
            fstab = self.run('genfstab', '-U', str(TARGET))
            self.write('etc/fstab', fstab)
            self.stage(3)
            self.configure()
            self.stage(4)
            if self.c.aero:
                shutil.copy2(ROOT / 'arch-win7-aero-postinstall.sh', TARGET / 'root/winux-postinstall.sh')
                # Existing wrapper builds as the regular user via runuser inside the target.
                # Skip live-kernel GPU detection; the target has its own graphics baseline.
                self.chroot('env', 'QT_QPA_PLATFORM=offscreen', 'bash', '/root/winux-postinstall.sh', '--user', self.c.username, '--yes', '--gpu', 'none')
                (TARGET / 'root/winux-postinstall.sh').unlink()
            else:
                self.chroot('systemctl', 'enable', 'sddm.service')
                self.chroot('systemctl', 'set-default', 'graphical.target')
            desktop.install(TARGET, self.c.username, '/home/'+self.c.username, self.chroot, self.tmog)
            self.stage(5)
            bootloader.prepare_initramfs(TARGET, self.hardware_plan['storage_modules'], self.run)
            bootloader.install(TARGET, disk, self.c.firmware, self.run, self.runner.write)
            self.stage(6)
            self.install_welcome()
            self.run('sync')
            completed = True
        finally:
            self.c.password = ''
            if self.mounted:
                logdest = TARGET / 'var/log/winux-setup.log'
                try:
                    shutil.copy2(self.runner.log_path, logdest)
                except OSError as exc:
                    self.emit('log', f'Could not copy installation log: {exc}')
                try:
                    self.run('umount', '-R', str(TARGET))
                    self.mounted = False
                except Exception as exc:
                    cleanup_ok = False
                    self.emit('log', f'Cleanup needs attention: {exc}. Shut down before disconnecting the drive.')
            if self.runner:
                self.runner.log.close()
            self.lock.close()
        if completed and cleanup_ok:
            self.emit('success', 'Installation complete. Restart, remove the USB drive, and sign in with your new account.')
        elif completed:
            raise SetupError('System installed, but the drive could not be safely unmounted. Shut down before removing any drives; see the log.')

    def prepare_filesystem(self, partition, fstype):
        # Called only for newly created partitions of the confirmed erase target.
        # Wiping the whole disk's partition table does not clear signatures inside
        # partitions, and udev may still remember the previous filesystem type.
        if fstype not in {'ext4', 'vfat'}:
            raise SetupError('Unsupported installation filesystem.')
        self.run('wipefs', '--all', partition)
        if fstype == 'ext4':
            self.run('mkfs.ext4', '-F', '-L', 'Winux', partition)
        else:
            self.run('mkfs.fat', '-F', '32', '-n', 'SYSTEM', partition)
        # Low-level probing reads the new superblock instead of cached metadata.
        detected = self.run('blkid', '-p', '-s', 'TYPE', '-o', 'value', partition).strip()
        if detected != fstype:
            raise SetupError(f'{partition}: expected {fstype} after formatting, detected {detected or "no filesystem"}. Stopping before mounting.')
        self.run('udevadm', 'trigger', '--action=change', '--sysname-match=' + Path(partition).name)
        self.run('udevadm', 'settle')

    def configure(self):
        c = self.c
        self.write('etc/hostname', c.hostname + '\n')
        self.write('etc/hosts', f'127.0.0.1 localhost\n::1 localhost\n127.0.1.1 {c.hostname}.localdomain {c.hostname}\n')
        charset = locales.supported()[c.locale]
        self.write('etc/locale.gen', c.locale + ' ' + charset + '\n' + ('en_US.UTF-8 UTF-8\n' if c.locale != 'en_US.UTF-8' else ''))
        self.write('etc/locale.conf', f'LANG={c.locale}\n')
        console, xkb = KEYBOARDS[c.keyboard]
        self.write('etc/vconsole.conf', f'KEYMAP={console}\n')
        self.write('etc/X11/xorg.conf.d/00-keyboard.conf', f'Section "InputClass"\n Identifier "keyboard"\n MatchIsKeyboard "on"\n Option "XkbLayout" "{xkb}"\nEndSection\n')
        self.chroot('ln', '-sf', '/usr/share/zoneinfo/' + c.timezone, '/etc/localtime')
        self.chroot('locale-gen')
        self.chroot('hwclock', '--systohc', '--utc')
        self.chroot('useradd', '-m', '-G', 'wheel', '-s', '/bin/bash', c.username)
        self.chroot('chpasswd', input=f'{c.username}:{c.password}\n', secret=True)
        c.password = ''
        self.chroot('passwd', '-l', 'root')
        self.write('etc/sudoers.d/10-winux-wheel', '%wheel ALL=(ALL:ALL) ALL\n', 0o440)
        self.chroot('visudo', '-cf', '/etc/sudoers')
        self.chroot('systemctl', 'enable', 'NetworkManager.service', 'systemd-timesyncd.service')
        self.write('var/log/winux-hardware.json', json.dumps(self.hardware_plan, indent=2) + '\n')
        if self.hardware_plan['services']:
            self.chroot('systemctl', 'enable', *self.hardware_plan['services'])
        self.write('etc/default/grub', 'GRUB_DEFAULT=0\nGRUB_TIMEOUT=3\nGRUB_DISTRIBUTOR="Winux 7"\nGRUB_CMDLINE_LINUX_DEFAULT="quiet"\n')
        # RAM-backed swap avoids another partition and works without a fixed swapfile.
        self.write('etc/systemd/system/winux-zram.service', '[Unit]\nDescription=Winux compressed swap\nAfter=systemd-modules-load.service\n[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=/usr/bin/modprobe zram\nExecStart=/usr/bin/zramctl /dev/zram0 --algorithm zstd --size 2G\nExecStart=/usr/bin/mkswap /dev/zram0\nExecStart=/usr/bin/swapon --priority 100 /dev/zram0\n[Install]\nWantedBy=multi-user.target\n')
        self.chroot('systemctl', 'enable', 'winux-zram.service')

    def install_welcome(self):
        target = TARGET / 'usr/share/winux-setup'
        target.mkdir(parents=True, exist_ok=True)
        for name in ['welcome.py', 'TUTORIAL.md', 'POSTINSTALL.md', 'DESKTOP.md']:
            shutil.copy2(ROOT / name, target / name)
        autostart = TARGET / f'home/{self.c.username}/.config/autostart'
        autostart.mkdir(parents=True, exist_ok=True)
        (autostart / 'winux-welcome.desktop').write_text('[Desktop Entry]\nType=Application\nName=Welcome to Winux 7\nExec=python /usr/share/winux-setup/welcome.py\nOnlyShowIn=KDE;\n')
        self.chroot('chown', '-R', f'{self.c.username}:{self.c.username}', f'/home/{self.c.username}/.config')
