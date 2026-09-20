"""Builder smoke tests with synthetic profiles/tools; never install packages or build a real ISO."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent

class BuilderTests(unittest.TestCase):
    def test_help_without_privileges(self):
        r=subprocess.run(['bash',str(ROOT/'build-iso.sh'),'--help'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0)
        self.assertIn('30 GiB',r.stdout)
    def test_too_many_arguments(self):
        r=subprocess.run(['bash',str(ROOT/'build-iso.sh'),'a','b'],capture_output=True,text=True)
        self.assertEqual(r.returncode,2)
    def test_mock_build_outputs_checksum_and_retains_previous_iso(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'project';source.mkdir();binpath=root/'bin';binpath.mkdir()
            profile=root/'releng';(profile/'airootfs/root').mkdir(parents=True)
            (profile/'airootfs/etc/systemd/system').mkdir(parents=True)
            (profile/'profiledef.sh').write_text('declare -A file_permissions=()\n')
            (profile/'packages.x86_64').write_text('base\n')
            for p in ROOT.iterdir():
                if p.is_file():shutil.copy2(p,source/p.name)
            script=(source/'build-iso.sh').read_text()
            script=script.replace('/usr/share/archiso/configs/releng',str(profile)).replace('/var/tmp',str(root))
            script=script.replace('/run/archiso',str(root/'not-live')).replace('/etc/arch-release',str(root/'arch-release'))
            script=script.replace('$EUID','0') # Run isolated test branch without elevating privileges.
            (root/'arch-release').touch();(source/'build-iso.sh').write_text(script)
            stubs={'df':"printf 'Filesystem 1024-blocks Used Available Capacity Mounted\\nfixture 999999999 0 999999999 0 /\\n'",
                   'chown':'exit 0',
                   'mkarchiso':'''while (( $# )); do
if [[ $1 == -o ]]; then dest=$2; shift; fi
shift
done
mkdir -p "$dest"
printf 'test ISO artifact' > "$dest/winux-7-test.iso"'''}
            for name,body in stubs.items():
                p=binpath/name;p.write_text('#!/bin/bash\nset -eu\n'+body+'\n');p.chmod(0o755)
            env={**os.environ,'PATH':str(binpath)+':'+os.environ['PATH']}
            output=root/'output';output.mkdir();(output/'winux-7-test.iso').write_text('previous ISO')
            r=subprocess.run(['bash',str(source/'build-iso.sh'),str(output)],env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertEqual((output/'winux-7-test.iso').read_text(),'previous ISO')
            checksums=list(output.glob('*.sha256'));self.assertEqual(len(checksums),1)
            subprocess.run(['sha256sum','-c',checksums[0].name],cwd=output,check=True,capture_output=True)
            staged=next(root.glob('winux-iso.*/profile/airootfs/opt/winux-setup'))
            self.assertTrue((staged/'wallpaper.jpg').exists())
            self.assertTrue((staged/'desktop.py').exists())

if __name__=='__main__':unittest.main(verbosity=2)
