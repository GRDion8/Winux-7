"""Compile native wallpaper code and exercise real, private D-Bus traffic.
The service is a test double; never connects to the user's desktop bus.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent
SERVICE=r'''
#include <QtCore>
#include <QtDBus>
#include <cstdio>
class Shell : public QObject {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.kde.PlasmaShell")
    QVariantMap image{{"Image","file:///plasma-default.jpg"},{"wallpaperPlugin","org.kde.image"}};
public slots:
    bool immutable() {return true;}
    QVariantMap wallpaper(uint screen) {return screen==0 ? image : QVariantMap{};}
    void setWallpaper(const QString &plugin, const QVariantMap &value, uint screen) {
        if(screen!=0 || qEnvironmentVariableIsSet("IGNORE_WALLPAPER"))return;
        image=value;image["wallpaperPlugin"]=plugin;
    }
};
int main(int argc,char **argv) {
    QCoreApplication app(argc,argv);Shell shell;
    auto bus=QDBusConnection::sessionBus();
    if(!bus.registerService("org.kde.plasmashell") || !bus.registerObject("/PlasmaShell",&shell,QDBusConnection::ExportAllSlots))return 2;
    std::puts("ready");std::fflush(stdout);return app.exec();
}
#include "service.moc"
'''

def worker(binary, service, folder):
    root=Path(folder)
    env={**os.environ,'QT_QPA_PLATFORM':'offscreen','HOME':folder,'XDG_CONFIG_HOME':str(root/'config'),'XDG_DATA_HOME':str(root/'data')}
    source=root/'a picture " with spaces.jpg';shutil.copyfile(ROOT/'wallpaper.jpg',source)
    def invoke(*args):return subprocess.run([binary,*args],env=env,text=True,capture_output=True,timeout=15)
    def start(ignore=False):
        server_env=env.copy()
        if ignore:server_env['IGNORE_WALLPAPER']='1'
        proc=subprocess.Popen([service],env=server_env,stdout=subprocess.PIPE,text=True)
        assert proc.stdout.readline().strip()=='ready'
        return proc
    server=start()
    try:
        r=invoke('--set-wallpaper',str(source));assert r.returncode==0,r.stderr
        prefs=root/'config/winux-7/wallpaper.json';saved=json.loads(prefs.read_text())['image']
        assert Path(saved).read_bytes()==source.read_bytes()
        source.unlink()  # selected picture must survive removal of the original
        bad=root/'bad.jpg';bad.write_text('not a picture')
        r=invoke('--set-wallpaper',str(bad));assert r.returncode!=0
        assert json.loads(prefs.read_text())['image']==saved
    finally:server.terminate();server.wait(timeout=5)
    # A new desktop starts with the Plasma default; login restoration must change it.
    server=start()
    try:
        r=invoke('--restore-wallpaper');assert r.returncode==0,r.stderr
        assert json.loads(prefs.read_text())['image']==saved
    finally:server.terminate();server.wait(timeout=5)
    server=start(ignore=True)
    try:
        r=invoke('--restore-wallpaper');assert r.returncode!=0,'silent desktop rejection must fail'
        assert 'confirmed' in r.stderr,r.stderr
        assert json.loads(prefs.read_text())['image']==saved
    finally:server.terminate();server.wait(timeout=5)

class WallpaperTests(unittest.TestCase):
    def test_native_picker_persistence_and_locked_desktop_api(self):
        if not all(shutil.which(x) for x in ['c++','pkg-config','dbus-run-session']):self.skipTest('Qt/DBus tools unavailable')
        flags=subprocess.run(['pkg-config','--cflags','--libs','Qt6Widgets','Qt6DBus'],text=True,capture_output=True)
        if flags.returncode:self.skipTest('Qt headers unavailable')
        libexec=subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip()
        moc=Path(libexec)/'moc'
        if not moc.exists():self.skipTest('Qt moc unavailable')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'service.cpp';source.write_text(SERVICE)
            subprocess.run([str(moc),str(source),'-o',str(root/'service.moc')],check=True,capture_output=True)
            for src,output in [(source,root/'service'),(ROOT/'control-panel.cpp',root/'panel')]:
                subprocess.run(['c++','-std=c++17','-fPIC',str(src),'-o',str(output),*shlex.split(flags.stdout)],check=True,capture_output=True)
            runtime=root/'runtime';runtime.mkdir(mode=0o700)
            r=subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),'--worker',str(root/'panel'),str(root/'service'),folder],capture_output=True,text=True,timeout=35,env={**os.environ,'XDG_RUNTIME_DIR':str(runtime)})
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':worker(*sys.argv[2:])
    else:unittest.main()
