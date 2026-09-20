"""Simulated repair workflow; no real mounts, firmware edits, or block devices."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import engine
import hardware
from boot_tests import FakeBoot, layout, UUID

spec=importlib.util.spec_from_file_location('repair_boot',Path(__file__).with_name('repair-boot.py'))
repair=importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)

class RepairTests(unittest.TestCase):
    def simulate(self, apply=False, failure=False, mode='uefi'):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'target'; root.mkdir()
            fake=FakeBoot(root)
            calls=[]
            class Runner:
                log=io.StringIO()
                def __init__(self,*args): pass
                def write(self,text): pass
                def run(self,args):
                    calls.append(args)
                    if args[0]=='blkid' and 'TYPE' in args:
                        return 'vfat' if args[-1].endswith('1') else 'ext4'
                    if args[0]=='mount' and args[-1]==str(root):
                        fake.write('etc/default/grub','GRUB_DISTRIBUTOR="Winux 7"\n')
                        fake.write('etc/fstab',f'UUID={UUID} / ext4 defaults 0 1\n')
                        fake.write('boot/vmlinuz-linux','kernel')
                        fake.write('usr/lib/modules/6.7-test/pkgbase','linux\n')
                    if failure and 'mkinitcpio' in args:
                        raise engine.SetupError('Injected mkinitcpio failure')
                    return fake(*args)
            disk=engine.Disk('/dev/sda',80*1024**3,'Test','123','8:0')
            with patch.object(repair.os,'geteuid',return_value=0), patch.object(Path,'is_dir',return_value=True), patch.object(Path,'rmdir'), patch.object(repair,'open',return_value=io.StringIO(),create=True), patch.object(repair.fcntl,'flock'), patch.object(engine,'Runner',Runner), patch.object(engine,'discover',return_value=[disk]), patch.object(engine,'firmware',return_value=mode), patch.object(repair.tempfile,'mkdtemp',return_value=str(root)), patch.object(repair.bootloader,'check_firmware'), patch.object(repair.bootloader,'secure_boot_enabled',return_value=False), patch.object(hardware,'detect',return_value=hardware.Hardware('unknown','none',[])):
                if failure or mode=='bios':
                    with self.assertRaises(RuntimeError): repair.repair('/dev/sda',apply)
                else: repair.repair('/dev/sda',apply)
            self.assertFalse(any(c[0].startswith('mkfs') or c[0]=='wipefs' or (c[0]=='sfdisk' and '--json' not in c) for c in calls))
            return calls
    def test_inspection_never_mounts_or_chroots(self):
        calls=self.simulate()
        self.assertFalse(any(c[0] in {'mount','arch-chroot'} for c in calls))
    def test_apply_preserves_partitions(self):
        calls=self.simulate(apply=True)
        self.assertTrue(any('grub-install' in c for c in calls))
        self.assertEqual(calls[-1][0],'umount')
    def test_failure_unmounts(self):
        self.assertEqual(self.simulate(apply=True,failure=True)[-1][0],'umount')
    def test_wrong_firmware_never_mounts(self):
        self.assertFalse(any(c[0]=='mount' for c in self.simulate(apply=True,mode='bios')))

if __name__=='__main__': unittest.main(verbosity=2)
