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
    int writes=0;
    QVariantMap image{{"Image","file:///plasma-default.jpg"},{"wallpaperPlugin","org.kde.image"}};
public:
    Shell() {
        if(qEnvironmentVariableIsSet("LATE_RESET")) QTimer::singleShot(1500,this,[this]{
            image["Image"]="file:///late-plasma-default.jpg";
        });
    }
public slots:
    bool immutable() {return true;}
    QVariantMap wallpaper(uint screen) {return screen==0 ? image : QVariantMap{};}
    void setWallpaper(const QString &plugin, const QVariantMap &value, uint screen) {
        if(screen!=0 || qEnvironmentVariableIsSet("IGNORE_WALLPAPER"))return;
        image=value;image["wallpaperPlugin"]=plugin;
        QFile count(qEnvironmentVariable("WRITE_COUNT"));
        if(count.open(QIODevice::WriteOnly))count.write(QByteArray::number(++writes));
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
    def start(ignore=False,late=False):
        server_env=env.copy()
        if ignore:server_env['IGNORE_WALLPAPER']='1'
        if late:server_env['LATE_RESET']='1'
        server_env['WRITE_COUNT']=str(root/'writes')
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

    # The resident service must repair a late reset and a completely restarted shell.
    import time
    state=root/'state/winux-desktop-v1';state.mkdir(parents=True)
    for name in ['desktop-complete','wine-complete']:(state/name).touch()
    env['XDG_STATE_HOME']=str(root/'state')
    server=start(late=True)
    guardian=subprocess.Popen([binary,'--wallpaper-service'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    def wait_count(expected):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if (root/'writes').exists() and (root/'writes').read_text()==str(expected):return
            time.sleep(.1)
        raise AssertionError('Wallpaper service did not repair the reset')
    try:
        wait_count(2)
        time.sleep(.5)
        assert (root/'writes').read_text()=='2', 'unchanged wallpaper must not be rewritten'
        server.terminate();server.wait(timeout=5);(root/'writes').unlink()
        server=start();wait_count(1)
    finally:
        guardian.terminate();guardian.wait(timeout=5)
        server.terminate();server.wait(timeout=5)

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
            r=subprocess.run(['dbus-run-session','--',sys.executable,str(Path(__file__).resolve()),'--worker',str(root/'panel'),str(root/'service'),folder],capture_output=True,text=True,timeout=55,env={**os.environ,'XDG_RUNTIME_DIR':str(runtime)})
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':worker(*sys.argv[2:])
    else:unittest.main()
