"""Winux desktop assets and package-update maintenance, confined to the target root."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile

STATE = 'var/lib/winux-desktop-core'
IMAGE = 'usr/share/wallpapers/Winux7/contents/images/3840x2160.jpg'
LOOK = 'usr/local/share/plasma/look-and-feel/org.winux7.desktop'
VENDORS = {'plasma-workspace', 'plasma-workspace-wallpapers', 'breeze', 'breeze-wallpapers'}


def digest(path):
    data = b'symlink\0'+os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
    return hashlib.sha256(data).hexdigest()


class Assets:
    """Keep small manifests and on-disk originals, including removed vendor pictures."""
    def __init__(self, root):
        self.root = Path(root)
        self.directory = self.root/STATE
        self.path = self.directory/'files.json'
        self.entries = json.loads(self.path.read_text()) if self.path.exists() else {}

    def target(self, relative, allow_symlink=False):
        path = PurePosixPath(relative)
        if path.is_absolute() or '..' in path.parts:
            raise RuntimeError('Invalid desktop asset path')
        result = self.root/relative
        # Package symlinks are deliberately not followed into another tree.
        if any(p.is_symlink() for p in [result, *result.parents] if p != self.root.parent and not (allow_symlink and p==result)):
            raise RuntimeError('Desktop asset is a symlink: '+relative)
        return result

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.directory.chmod(0o700)
        pending = self.path.with_suffix('.tmp')
        pending.write_text(json.dumps(self.entries, indent=2)+'\n')
        pending.replace(self.path)

    def remember(self, relative, allow_symlink=False):
        path = self.target(relative, allow_symlink)
        record = self.entries.get(relative)
        current = digest(path) if path.is_file() or path.is_symlink() else None
        if record is None or current != record['installed']:
            # A package upgrade has supplied a new original. Undo restores that version.
            original = None
            if path.exists() or path.is_symlink():
                original = 'originals/'+hashlib.sha256(relative.encode()).hexdigest()+'/'+current
                backup = self.directory/original
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup, follow_symlinks=False)
            self.entries[relative] = {'original': original, 'installed': current}
        return path

    def write(self, relative, data):
        path = self.remember(relative)
        data = data.encode() if isinstance(data, str) else data
        expected = hashlib.sha256(data).hexdigest()
        if (path.exists() or path.is_symlink()) and digest(path) == expected: return
        self.entries[relative]['installed'] = expected
        self.save()
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
            f.write(data);pending=Path(f.name)
        pending.chmod(0o644);pending.replace(path)

    def retire(self, relative):
        path = self.remember(relative, allow_symlink=True)
        self.entries[relative]['installed'] = None
        self.save()
        path.unlink(missing_ok=True)


def set_wallpaper_default(text):
    """Keep all other KConfig entries and replace only the Wallpaper/Image key."""
    import re
    text = re.sub(r'(?ms)^\[Wallpaper\]\n(.*?)(?=^\[|\Z)',
                  lambda m:'[Wallpaper]\n'+re.sub(r'^Image(?:\[.*?\])?=.*\n?', '', m[1], flags=re.M)+'Image=Winux7\n', text)
    if not re.search(r'^\[Wallpaper\]$', text, re.M):
        text = text.rstrip()+'\n\n[Wallpaper]\nImage=Winux7\n'
    return text


def vendor_pictures(root):
    """Use pacman's installed ownership records; never sweep user wallpaper folders."""
    result = set()
    for folder in (root/'var/lib/pacman/local').glob('*'):
        desc, files = folder/'desc', folder/'files'
        if not desc.is_file() or not files.is_file(): continue
        fields = desc.read_text().splitlines()
        try: name = fields[fields.index('%NAME%')+1]
        except (ValueError, IndexError): continue
        if name not in VENDORS: continue
        for line in files.read_text().splitlines():
            path = PurePosixPath(line)
            if (line.startswith('usr/share/wallpapers/') and not line.endswith('/') and
                '..' not in path.parts and len(path.parts)>=4 and path.parts[3]!='Winux7'):
                target=root/line
                if any(parent.is_symlink() for parent in target.parents): continue
                if target.is_file() or target.is_symlink(): result.add(line)
    return sorted(result)


def refresh(root, image=None):
    root = Path(root)
    assets = Assets(root)
    supplied = image or root/'usr/share/winux-setup/wallpaper.jpg'
    if not supplied.is_file(): raise RuntimeError('The Winux wallpaper asset is missing.')
    assets.write(IMAGE, supplied.read_bytes())
    assets.write('usr/share/wallpapers/Winux7/metadata.json', json.dumps({
        'KPlugin': {'Id':'Winux7', 'Name':'Winux 7', 'Description':'Winux 7 desktop background'},
        'KPackageStructure':'Wallpaper/Images'}, indent=2)+'\n')
    source = root/'usr/share/plasma/look-and-feel/authui7'
    if not (source/'metadata.json').is_file(): raise RuntimeError('The Aero desktop assets are missing.')
    # The underlying Aero resources and license files are retained in the Winux package.
    for path in sorted(source.rglob('*')):
        if path.is_symlink(): raise RuntimeError('Unexpected symlink in Aero look-and-feel: '+str(path))
        if not path.is_file(): continue
        relative = str(path.relative_to(source))
        content = path.read_bytes()
        if relative=='metadata.json':
            metadata=json.loads(content)
            metadata.setdefault('KPlugin',{}).update({'Id':'org.winux7.desktop','Name':'Winux 7'})
            for key in list(metadata['KPlugin']):
                if key.startswith('Name['):del metadata['KPlugin'][key]
            content=json.dumps(metadata,indent=2)+'\n'
        elif relative=='contents/defaults':content=set_wallpaper_default(content.decode())
        assets.write(LOOK+'/'+relative,content)
    # Some minimal theme packages have no defaults file at all.
    if not (source/'contents/defaults').exists():
        assets.write(LOOK+'/contents/defaults','[Wallpaper]\nImage=Winux7\n')
    # First-login Aero bootstrap still uses this identity before the locked Winux theme loads.
    original=source/'contents/defaults'
    assets.write(str(original.relative_to(root)),set_wallpaper_default(original.read_text() if original.exists() else ''))
    for relative in vendor_pictures(root): assets.retire(relative)
    # Empty wallpaper directories are not useful gallery entries; preserve non-owned contents.
    gallery=root/'usr/share/wallpapers'
    for path in sorted(gallery.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if path.is_dir() and not path.is_symlink():
            try:path.rmdir()
            except OSError:pass
    assets.save()


def remove(root):
    assets=Assets(root)
    for relative,record in assets.entries.items():
        path=assets.target(relative, allow_symlink=True)
        if (path.exists() or path.is_symlink()) and digest(path)!=record['installed']:
            raise RuntimeError('Desktop asset changed after installation: '+relative)
    for relative,record in reversed(list(assets.entries.items())):
        path=assets.target(relative, allow_symlink=True)
        if record['original']:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.unlink(missing_ok=True)
            shutil.copy2(assets.directory/record['original'],path,follow_symlinks=False)
        else:path.unlink(missing_ok=True)
    if assets.path.exists():assets.path.unlink()


if __name__=='__main__':
    import fcntl
    if os.geteuid()!=0:raise SystemExit('Desktop asset maintenance requires root.')
    with open('/run/winux-desktop-assets.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        refresh(Path('/'))
