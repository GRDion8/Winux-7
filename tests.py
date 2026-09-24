"""Non-destructive tests: fake block devices and commands only."""
import copy
import dataclasses
import io
import tempfile
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import engine
import desktop
from boot_tests import FakeBoot, UUID


def config(**kwargs):
    base = dict(disk=engine.Disk('/dev/sda', 80*1024**3, 'Test SSD', '123', '8:0'), username='alice',
                hostname='winux-pc', password='correct horse battery', confirmation='ERASE /dev/sda')
    base.update(kwargs)
    return engine.Config(**base)


def block(**kwargs):
    base = {'path':'/dev/sda', 'size':80*1024**3, 'model':'Test SSD', 'serial':'123', 'maj:min':'8:0',
            'type':'disk', 'ro':False, 'mountpoints':[None]}
    base.update(kwargs)
    return base


class Validation(unittest.TestCase):
    def test_valid(self):
        config().validate()

    def test_bad_accounts(self):
        for name in ['root', 'sddm', 'a;touch /tmp/pwn', '../alice', 'alice\nroot', 'Alice', 'a'*32]:
            with self.subTest(name=name), self.assertRaises(engine.SetupError):
                config(username=name).validate()

    def test_bad_hostnames(self):
        for host in ['-pc', 'pc-', 'pc\nx', 'pc;reboot', '', 'a'*64]:
            with self.subTest(host=host), self.assertRaises(engine.SetupError):
                config(hostname=host).validate()

    def test_password_hidden(self):
        self.assertNotIn('correct horse battery', repr(config()))
        for password in ['short', 'secret\nroot:pw', 'secret\0data']:
            with self.assertRaises(engine.SetupError):
                config(password=password).validate()

    def test_zone_traversal(self):
        for zone in ['../../etc/passwd', '/etc/passwd', 'Not/AZone']:
            with self.assertRaises(engine.SetupError):
                config(timezone=zone).validate()

    def test_exact_confirmation(self):
        for text in ['', 'yes', 'ERASE /dev/sdb', 'ERASE /dev/sda ']:
            with self.assertRaises(engine.SetupError):
                config(confirmation=text).validate()

    def test_partition_and_mapper_rejected(self):
        for path in ['/dev/sda1', '/dev/mapper/root', '/dev/loop0', '/tmp/disk', '/dev/nvme0n1p1']:
            d = dataclasses.replace(config().disk, path=path)
            with self.assertRaises(engine.SetupError):
                config(disk=d, confirmation='ERASE '+path).validate()

    def test_small_or_blocked_disk(self):
        for disk in [dataclasses.replace(config().disk, size=20*1024**3), dataclasses.replace(config().disk, blocked='Mounted')]:
            with self.assertRaises(engine.SetupError):
                config(disk=disk).validate()

    def test_partition_paths(self):
        for disk, part in [('/dev/sda','/dev/sda2'), ('/dev/vda','/dev/vda2'), ('/dev/nvme0n1','/dev/nvme0n1p2'), ('/dev/mmcblk0','/dev/mmcblk0p2')]:
            self.assertEqual(engine.partition_path(disk, 2), part)

    def test_bios_and_uefi_tables(self):
        self.assertIn('type=U', engine.partition_table('uefi'))
        self.assertIn('21686148', engine.partition_table('bios'))
        self.assertIn('type=L', engine.partition_table('bios'))


class Discovery(unittest.TestCase):
    def parse(self, node):
        return engine.parse_disks({'blockdevices':[node]})[0]

    def test_free(self):
        self.assertEqual(self.parse(block()).blocked, '')

    def test_live_usb_excluded(self):
        self.assertTrue(self.parse(block(children=[block(type='part', mountpoints=['/run/archiso/bootmnt'])])).blocked)

    def test_swap_excluded(self):
        self.assertTrue(self.parse(block(children=[block(type='part', mountpoints=['[SWAP]'])])).blocked)

    def test_nested_lvm_excluded(self):
        self.assertTrue(self.parse(block(children=[block(type='part', children=[block(type='lvm')])])).blocked)

    def test_readonly_excluded(self):
        self.assertTrue(self.parse(block(ro=True)).blocked)

    def test_changed_device_refused(self):
        installer = engine.Installer(config(), lambda *x:None)
        with patch.object(engine, 'discover', return_value=[dataclasses.replace(config().disk, serial='different')]):
            with self.assertRaisesRegex(engine.SetupError, 'changed'):
                installer.check_disk()

    def test_nonlive_refused(self):
        with patch.object(engine.os, 'geteuid', return_value=1000):
            with self.assertRaisesRegex(engine.SetupError, 'Arch live ISO'):
                engine.Installer(config(), lambda *x:None).check_live()


class Execution(unittest.TestCase):
    def test_preflight_mismatch_never_wipes(self):
        installer = engine.Installer(config(), lambda *x:None)
        commands = []
        def run(*args, **kw):
            commands.append(args)
            return 'Version : 6.8.0-1\n'
        with patch.object(installer, 'check_live'), patch.object(installer, 'check_disk'), patch.object(installer, 'run', side_effect=run):
            with self.assertRaisesRegex(engine.SetupError, 'Plasma 6.7'):
                installer.preflight()
        self.assertFalse(any('wipefs' in cmd or 'sfdisk' in cmd for cmd in commands))

    def test_preflight_compatible(self):
        installer = engine.Installer(config(), lambda *x:None)
        with patch.object(installer, 'check_live'), patch.object(installer, 'check_disk') as check, patch.object(installer, 'run', return_value='Version : 6.7.4-1\n'):
            installer.preflight()
        check.assert_called_once()

    def test_password_stdin_only(self):
        with tempfile.TemporaryDirectory() as d:
            events = []
            runner = engine.Runner(lambda *x:events.append(x), Path(d)/'log')
            with patch.object(engine.subprocess, 'run', return_value=Mock(returncode=0, stdout='secret echoed')) as run:
                runner.run(['chpasswd'], input='alice:secret\n', secret=True)
            runner.log.close()
            self.assertEqual(run.call_args.kwargs['input'], 'alice:secret\n')
            self.assertNotIn('secret', (Path(d)/'log').read_text())
            self.assertNotIn('secret', str(events))
            self.assertEqual((Path(d)/'log').stat().st_mode & 0o777, 0o600)

    def test_command_failure_raises(self):
        with tempfile.TemporaryDirectory() as d:
            runner = engine.Runner(lambda *x:None, Path(d)/'log')
            with patch.object(engine.subprocess, 'run', return_value=Mock(returncode=1, stdout='failure')):
                with self.assertRaises(engine.SetupError):
                    runner.run(['sfdisk', '/dev/fake'], input='table')
            runner.log.close()

    def simulate(self, mode='uefi', failure=None, aero=True):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        target = root/'target'
        events, commands = [], []
        boot = FakeBoot(target, mode)
        class FakeRunner:
            log_path = root/'log'
            log = io.StringIO()
            def write(self, text):
                self.log.write(text + "\n")
            def run(self, args, **kwargs):
                commands.append((tuple(map(str,args)), kwargs))
                if failure and failure in args:
                    raise engine.SetupError('Injected failure')
                if (args[0] in {'sfdisk', 'findmnt'} and ('--json' in args)) or (args[0] == 'blkid' and ('UUID' in args or 'PARTUUID' in args)):
                    return boot(*args)
                if args[0] == 'arch-chroot':
                    return boot(*args)
                if args[0] == 'blkid':
                    return 'vfat\n' if str(args[-1]).endswith('1') else 'ext4\n'
                if args[0] == 'pacstrap':
                    boot.write('usr/share/xsessions/plasmax11.desktop', '[Desktop Entry]\nType=Application\nName=Plasma (X11)\nExec=startplasma-x11\n')
                    boot.write('boot/vmlinuz-linux', 'kernel')
                    boot.write('usr/lib/modules/6.7-test/pkgbase', 'linux\n')
                    for folder in ['root', 'var/log', 'etc']:
                        (target/folder).mkdir(parents=True, exist_ok=True)
                return f'UUID={UUID} / ext4 defaults 0 1\n' if args[0]=='genfstab' else ''
        FakeRunner.log_path.write_text('test log')
        cfg = config(firmware=mode, aero=aero)
        installer = engine.Installer(cfg, lambda *x:events.append(x), FakeRunner())
        with patch.object(engine, 'TARGET', target), patch.object(installer, 'check_live'), patch.object(installer, 'check_disk'), patch.object(installer, 'preflight'), patch('engine.open', return_value=io.StringIO(), create=True), patch.object(engine.fcntl, 'flock'), patch.object(engine.winux_profile, 'install') as installed_profile:
            if failure:
                with self.assertRaises(engine.SetupError):
                    installer.execute()
            else:
                installer.execute()
        if not failure: installed_profile.assert_called_once()
        self.assertEqual(cfg.password, '')
        return commands, events, target

    def test_uefi_pipeline(self):
        commands, events, target = self.simulate()
        flat = [c for c,k in commands]
        grub = [c for c in flat if 'grub-install' in c][0]
        self.assertIn('--target=x86_64-efi', grub)
        self.assertIn('--no-nvram', grub)
        mounts = [c for c in flat if c[0] == 'mount']
        self.assertEqual(mounts, [('mount', '-t', 'ext4', '/dev/sda2', str(target)), ('mount', '-t', 'vfat', '/dev/sda1', str(target/'boot/efi'))])
        self.assertIn('--wipe-partitions', next(c for c in flat if c[0] == 'sfdisk'))
        self.assertTrue((target/'etc/fstab').exists())
        self.assertTrue((target/'etc/sudoers.d/10-winux-wheel').exists())
        secret = [(c,k) for c,k in commands if 'chpasswd' in c][0]
        self.assertTrue(secret[1]['secret'])
        self.assertNotIn('correct horse battery', str(secret[0]))
        self.assertTrue(any(kind=='success' for kind,data in events))
        self.assertEqual(flat[-1][0], 'umount')

    def test_bios_pipeline(self):
        commands, events, target = self.simulate('bios')
        grub = [c for c,k in commands if 'grub-install' in c][0]
        self.assertIn('--target=i386-pc', grub)
        self.assertEqual(grub[-1], '/dev/sda')
        self.assertFalse(any('mkfs.fat' in c for c,k in commands))

    def test_generic_desktop_rejected_before_installation(self):
        with self.assertRaisesRegex(engine.SetupError,'requires its desktop'):
            config(aero=False).validate()

    def test_failure_cleans_mounts_and_never_reports_success(self):
        commands, events, target = self.simulate(failure='pacstrap')
        self.assertEqual(commands[-1][0][0], 'umount')
        self.assertFalse(any(kind=='success' for kind,data in events))

    def test_unmount_failure_not_success(self):
        commands, events, target = self.simulate(failure='umount')
        self.assertFalse(any(kind=='success' for kind,data in events))

class FilesystemRegression(unittest.TestCase):
    def test_old_signature_cleared_before_format_and_probe(self):
        installer = engine.Installer(config(), lambda *x:None)
        with patch.object(installer, 'run', return_value='vfat\n') as run:
            installer.prepare_filesystem('/dev/nvme0n1p1', 'vfat')
        self.assertEqual([c.args for c in run.call_args_list], [
            ('wipefs', '--all', '/dev/nvme0n1p1'),
            ('mkfs.fat', '-F', '32', '-n', 'SYSTEM', '/dev/nvme0n1p1'),
            ('blkid', '-p', '-s', 'TYPE', '-o', 'value', '/dev/nvme0n1p1'),
            ('udevadm', 'trigger', '--action=change', '--sysname-match=nvme0n1p1'),
            ('udevadm', 'settle')])

    def test_wrong_type_refused(self):
        installer = engine.Installer(config(), lambda *x:None)
        with patch.object(installer, 'run', return_value='squashfs\n') as run:
            with self.assertRaisesRegex(engine.SetupError, 'expected vfat.*squashfs'):
                installer.prepare_filesystem('/dev/nvme0n1p1', 'vfat')
        self.assertFalse(any(c.args[0] in {'mount', 'pacstrap'} for c in run.call_args_list))

    def test_unsupported_type_never_writes(self):
        installer = engine.Installer(config(), lambda *x:None)
        with patch.object(installer, 'run') as run:
            with self.assertRaises(engine.SetupError):
                installer.prepare_filesystem('/dev/nvme0n1p1', 'squashfs')
        run.assert_not_called()

    @unittest.skipUnless(all(shutil.which(x) for x in ['mksquashfs','wipefs','mkfs.fat','blkid']), 'filesystem tools unavailable')
    def test_real_squashfs_image_reformatted_as_fat32(self):
        # Regular files only: no block devices, mounts, sudo, or root needed.
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            source = folder/'contents'
            source.mkdir()
            (source/'old.txt').write_text('old filesystem')
            image = folder/'partition.img'
            subprocess.run(['mksquashfs', str(source), str(image), '-noappend', '-processors', '1', '-quiet'], check=True, capture_output=True)
            with image.open('r+b') as stream:
                stream.truncate(64*1024**2)
            detected = subprocess.check_output(['blkid','-p','-s','TYPE','-o','value',str(image)], text=True).strip()
            self.assertEqual(detected, 'squashfs')
            installer = engine.Installer(config(), lambda *x:None)
            commands = []
            def run(*args, **kwargs):
                commands.append(args)
                if args[0] == 'udevadm':
                    return ''  # Regular files have no udev events.
                self.assertEqual(args[-1], str(image))
                self.assertTrue(image.is_file())
                return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)
            with patch.object(installer, 'run', side_effect=run):
                installer.prepare_filesystem(str(image), 'vfat')
            self.assertEqual(subprocess.check_output(['blkid','-p','-s','TYPE','-o','value',str(image)], text=True).strip(), 'vfat')

if __name__ == '__main__':
    unittest.main(verbosity=2)
