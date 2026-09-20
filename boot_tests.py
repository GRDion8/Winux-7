"""Boot regression tests use temporary directories and fake commands, never disks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import bootloader as boot
import hardware

UUID = '12345678-1234-1234-1234-123456789abc'
ESP = 'abcdef01-1234-1234-1234-123456789abc'


def layout(disk='/dev/sda', mode='uefi'):
    return {'partitiontable': {'label':'gpt', 'device':disk, 'partitions':[
        {'node':boot.part(disk,1), 'type':boot.EFI_TYPE if mode=='uefi' else boot.BIOS_TYPE, 'start':2048, 'size':4096},
        {'node':boot.part(disk,2), 'type':boot.ROOT_TYPE, 'start':6144, 'size':99999}]}}


class FakeBoot:
    def __init__(self, root, mode='uefi', disk='/dev/sda'):
        self.root, self.mode, self.disk = Path(root), mode, disk
        self.calls = []
        self.registered = False
        self.missing = ''
        self.wrong_mount = False
    def write(self, file, data):
        if file == self.missing:
            return
        path = self.root/file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data,str) else data)
    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == 'sfdisk':
            return json.dumps(layout(self.disk,self.mode))
        if args[0] == 'findmnt':
            esp = args[3].endswith('/boot/efi')
            return json.dumps({'filesystems':[{'source':'/dev/wrong' if self.wrong_mount else boot.part(self.disk,1 if esp else 2), 'fstype':'vfat' if esp else 'ext4'}]})
        if args[0] == 'blkid':
            return ESP if 'PARTUUID' in args else UUID
        if 'mkinitcpio' in args:
            for file in ['boot/initramfs-linux.img','boot/initramfs-linux-fallback.img']:
                self.write(file,'image')
        if 'grub-install' in args:
            file = ('boot/efi/EFI/BOOT/BOOTX64.EFI' if '--removable' in args else 'boot/efi/EFI/Winux/grubx64.efi') if self.mode=='uefi' else 'boot/grub/i386-pc/core.img'
            self.write(file,b'MZtest')
        if 'efibootmgr' in args:
            if '--create' in args:
                self.registered=True
            return f'BootOrder: 0001,0002\nBoot0001* Winux 7 HD(1,GPT,{ESP},0x800,0x1000)/File(\\EFI\\Winux\\grubx64.efi)\n' if self.registered else 'BootOrder: 0002\n'
        if 'grub-mkconfig' in args:
            self.write('boot/grub/grub.cfg', f'menuentry "Winux" {{\nlinux /vmlinuz-linux root=UUID={UUID}\ninitrd /initramfs-linux.img\n}}\n')
        return ''


class BootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.fake=FakeBoot(self.root)
        self.fake.write('boot/vmlinuz-linux','kernel')
        self.fake.write('etc/fstab',f'UUID={UUID} / ext4 defaults 0 1\n')
        self.fake.write('usr/lib/modules/6.7-test/pkgbase','linux\n')
        self.guard=patch.object(boot,'secure_boot_enabled',return_value=False)
        self.guard.start(); self.addCleanup(self.guard.stop)
    def install(self):
        boot.install(self.root,self.fake.disk,self.fake.mode,self.fake,lambda x:None)
    def test_uefi_nvme_named_fallback_and_registration(self):
        self.fake.disk='/dev/nvme0n1'
        self.install()
        create=next(c for c in self.fake.calls if '--create' in c)
        self.assertIn('/dev/nvme0n1',create)
        self.assertIn('--part',create)
        self.assertTrue((self.root/'boot/efi/EFI/BOOT/BOOTX64.EFI').exists())
        commands=[c[2] for c in self.fake.calls if c[0]=='arch-chroot']
        self.assertLess(commands.index('mkinitcpio'),commands.index('grub-mkconfig'))
    def test_repair_reuses_existing_correct_entry(self):
        self.fake.registered=True
        self.install()
        self.assertFalse(any('--create' in c for c in self.fake.calls))
    def test_bios_whole_disk(self):
        self.fake.mode='bios'
        self.install()
        self.assertIn(('arch-chroot',str(self.root),'grub-install','--target=i386-pc','--recheck','/dev/sda'),self.fake.calls)
    def test_missing_image_stops_before_grub(self):
        self.fake.missing='boot/initramfs-linux-fallback.img'
        with self.assertRaisesRegex(boot.BootError,'Missing'):
            self.install()
        self.assertFalse(any('grub-install' in c for c in self.fake.calls))
    def test_wrong_mount_never_writes(self):
        self.fake.wrong_mount=True
        with self.assertRaises(boot.BootError): self.install()
        self.assertFalse(any(c[0]=='arch-chroot' for c in self.fake.calls))
    def test_missing_efi_file_fails(self):
        self.fake.missing='boot/efi/EFI/BOOT/BOOTX64.EFI'
        with self.assertRaises(boot.BootError): self.install()
    def test_wrong_fstab_fails(self):
        self.fake.write('etc/fstab','UUID=wrong / ext4 defaults 0 1\n')
        with self.assertRaisesRegex(boot.BootError,'fstab'): self.install()
    def test_missing_nvram_registration_fails(self):
        def run(*args):
            answer=self.fake(*args)
            return 'BootOrder: 0002\n' if 'efibootmgr' in args else answer
        with self.assertRaisesRegex(boot.BootError,'BootOrder'):
            boot.install(self.root,'/dev/sda','uefi',run,lambda x:None)
    def test_layout_mismatch_and_overlap_rejected(self):
        for change in ['mode','overlap','extra','disk']:
            data=layout()
            if change=='mode': data['partitiontable']['partitions'][0]['type']=boot.BIOS_TYPE
            if change=='overlap': data['partitiontable']['partitions'][1]['start']=3000
            if change=='extra': data['partitiontable']['partitions'].append({})
            if change=='disk': data['partitiontable']['device']='/dev/sdb'
            with self.subTest(change=change), self.assertRaises(boot.BootError): boot.validate_layout(data,'/dev/sda','uefi')
    def test_presets_and_storage_modules_use_target_kernel(self):
        boot.prepare_initramfs(self.root,['nvme'],self.fake)
        self.assertIn(('arch-chroot',str(self.root),'modinfo','-k','6.7-test','nvme'),self.fake.calls)
        self.assertIn('-S autodetect',(self.root/'etc/mkinitcpio.d/linux.preset').read_text())
    def test_secure_boot_stops(self):
        with patch.object(boot,'secure_boot_enabled',return_value=True), self.assertRaises(boot.BootError): self.install()


class HardwareTests(unittest.TestCase):
    def test_vmware_intel_nvme(self):
        p=hardware.Hardware('GenuineIntel','vmware',[{'class':'010802','vendor':'15ad','module':'nvme'}]).plan()
        self.assertTrue({'intel-ucode','open-vm-tools'} <= set(p['packages']))
        self.assertNotIn('amd-ucode',p['packages'])
        self.assertEqual(p['storage_modules'],['nvme'])
        self.assertIn('vmtoolsd.service',p['services'])
    def test_hybrid_and_amd_cpu(self):
        p=hardware.Hardware('AuthenticAMD','none',[{'class':'030000','vendor':v,'module':''} for v in ['8086','1002','10de']]).plan()
        self.assertTrue({'amd-ucode','vulkan-intel','vulkan-radeon','vulkan-nouveau'} <= set(p['packages']))
        self.assertNotIn('intel-ucode',p['packages'])
    def test_other_vms(self):
        for virt,pkg in [('oracle','virtualbox-guest-utils'),('kvm','qemu-guest-agent'),('qemu','spice-vdagent')]:
            self.assertIn(pkg,hardware.Hardware('unknown',virt,[]).plan()['packages'])

if __name__=='__main__': unittest.main(verbosity=2)
