"""Core desktop policy tests use only disposable target roots."""
import json
from pathlib import Path
import tempfile
import unittest
import winux_core as core

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.put('usr/share/winux-setup/wallpaper.jpg',b'fixture wallpaper')
        self.put('usr/share/plasma/look-and-feel/authui7/metadata.json',json.dumps({'KPlugin':{'Name':'Aero','Id':'authui7','License':'AGPLv3','Authors':[{'Name':'Original author'}]}}))
        self.original='[kdeglobals][General]\nColorScheme=Aero\n'
        self.put('usr/share/plasma/look-and-feel/authui7/contents/defaults',self.original)
        self.put('usr/share/plasma/look-and-feel/authui7/contents/splash/main.qml','original splash')
        self.vendor='usr/share/wallpapers/Next/contents/images/1920x1080.png'
        self.put(self.vendor,b'vendor picture')
        self.put('usr/share/wallpapers/Next/metadata.json','vendor metadata')
        self.put('var/lib/pacman/local/plasma-workspace-1/desc','%NAME%\nplasma-workspace\n')
        self.put('var/lib/pacman/local/plasma-workspace-1/files','%FILES%\n'+self.vendor+'\nusr/share/wallpapers/Next/metadata.json\n')
    def put(self,name,data):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data,str) else data);return path
    def test_default_is_in_theme_package_and_vendor_images_are_retired(self):
        custom=self.put('usr/share/wallpapers/MyPicture/photo.jpg',b'personal asset')
        core.refresh(self.root)
        self.assertEqual((self.root/core.IMAGE).read_bytes(),b'fixture wallpaper')
        self.assertFalse((self.root/self.vendor).exists())
        self.assertFalse((self.root/'usr/share/wallpapers/Next/metadata.json').exists())
        self.assertEqual(custom.read_bytes(),b'personal asset')
        for path in ['usr/share/plasma/look-and-feel/authui7/contents/defaults',core.LOOK+'/contents/defaults']:
            self.assertIn('[Wallpaper]\nImage=Winux7',(self.root/path).read_text())
        metadata=json.loads((self.root/core.LOOK/'metadata.json').read_text())['KPlugin']
        self.assertEqual(metadata['Name'],'Winux 7');self.assertEqual(metadata['License'],'AGPLv3')
        self.assertEqual(metadata['Authors'],[{'Name':'Original author'}])
    def test_repeat_refresh_and_undo_restore_original_assets(self):
        core.refresh(self.root);core.refresh(self.root);core.remove(self.root)
        self.assertEqual((self.root/self.vendor).read_bytes(),b'vendor picture')
        self.assertEqual((self.root/'usr/share/plasma/look-and-feel/authui7/contents/defaults').read_text(),self.original)
        self.assertFalse((self.root/core.IMAGE).exists())
    def test_package_upgrade_cannot_restore_vendor_gallery(self):
        core.refresh(self.root)
        self.put(self.vendor,b'updated vendor picture')
        self.put('usr/share/plasma/look-and-feel/authui7/contents/defaults','[Wallpaper]\nImage=Next\n[Other]\nKeep=1\n')
        core.refresh(self.root)
        self.assertFalse((self.root/self.vendor).exists())
        defaults=(self.root/'usr/share/plasma/look-and-feel/authui7/contents/defaults').read_text()
        self.assertIn('Image=Winux7',defaults);self.assertIn('Keep=1',defaults)
        core.remove(self.root)
        self.assertEqual((self.root/self.vendor).read_bytes(),b'updated vendor picture')
    def test_symlink_cannot_escape_target_root(self):
        outside=self.root/'outside';outside.mkdir()
        (self.root/'usr/share/wallpapers/Winux7').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError,'symlink'):core.refresh(self.root)
        self.assertEqual(list(outside.iterdir()),[])
    def test_undo_preserves_manual_changes(self):
        core.refresh(self.root)
        self.put(core.IMAGE,b'manually changed')
        with self.assertRaises(RuntimeError):core.remove(self.root)
        self.assertEqual((self.root/core.IMAGE).read_bytes(),b'manually changed')
    def test_owned_symlink_is_retired_without_following_it(self):
        outside=self.put('private/user-photo.jpg',b'personal')
        alias=self.root/'usr/share/wallpapers/VendorLink'
        alias.symlink_to(outside)
        listing=self.root/'var/lib/pacman/local/plasma-workspace-1/files'
        listing.write_text(listing.read_text()+'usr/share/wallpapers/VendorLink\n')
        core.refresh(self.root)
        self.assertFalse(alias.is_symlink());self.assertEqual(outside.read_bytes(),b'personal')
        core.remove(self.root)
        self.assertTrue(alias.is_symlink());self.assertEqual(alias.read_bytes(),b'personal')
    def test_default_replacement_does_not_duplicate_groups(self):
        source='[Wallpaper]\nImage=Next\nOther=keep\n[Group]\nValue=1\n'
        changed=core.set_wallpaper_default(source)
        self.assertEqual(changed,core.set_wallpaper_default(changed))
        self.assertEqual(changed.count('Image='),1);self.assertIn('Other=keep',changed)

if __name__=='__main__':unittest.main()
