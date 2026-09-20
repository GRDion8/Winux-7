#!/usr/bin/env python3
"""Apply user defaults once, after Aero's layout setup; never run Wine as root."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=kwargs.pop('timeout',60), **kwargs).stdout.strip()


def configure(home, state):
    config = Path(os.environ.get('XDG_CONFIG_HOME', home/'.config'))
    # Aero resets layout/wallpaper on first login. Wait for its completion, not a fixed race-prone delay.
    aero = config/'autostart/aerothemeplasma-first-login.desktop'
    aero_state = Path(os.environ.get('XDG_STATE_HOME', home/'.local/state'))/'win7-aero-postinstall/first-login-complete'
    for _ in range(180):
        if not aero.exists() or aero_state.exists():
            break
        time.sleep(2)
    else:
        raise RuntimeError('Aero setup has not finished. Winux defaults will retry on the next login.')
    if not (state/'desktop-complete').exists():
        run('xdg-user-dirs-update')
        desktop = Path(run('xdg-user-dir','DESKTOP'))
        if not desktop.is_absolute() or desktop == home:
            desktop = home/'Desktop'
            run('xdg-user-dirs-update','--set','DESKTOP',str(desktop))
        desktop.mkdir(parents=True, exist_ok=True)
        (desktop/'Trash.desktop').write_text('[Desktop Entry]\nType=Link\nName=Recycle Bin\nName[de]=Papierkorb\nIcon=user-trash\nEmptyIcon=user-trash\nURL=trash:/\n')
        # Keep Aero's desktop containment; configure its desktop-folder location.
        script = 'var ds=desktops(); if (!ds.length) { throw new Error("No desktops ready"); }\n'
        script += 'for (var i=0;i<ds.length;i++) { var d=ds[i]; d.currentConfigGroup=["General"]; d.writeConfig("url", "desktop:/"); }\n'
        wallpaper = Path('/usr/share/winux-setup/wallpaper-path')
        if wallpaper.exists():
            image = Path(wallpaper.read_text().strip())
            if not image.is_file():
                raise RuntimeError('Configured wallpaper file is missing.')
            script += 'for (var i=0;i<ds.length;i++) { var d=ds[i]; d.wallpaperPlugin="org.kde.image"; d.currentConfigGroup=["Wallpaper","org.kde.image","General"]; d.writeConfig("Image",'+json.dumps(image.as_uri())+'); }'
        script += '\nprint("winux-desktop-applied");'
        for attempt in range(30):
            try:
                result=run('qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.evaluateScript',script)
                if 'winux-desktop-applied' not in result:
                    raise RuntimeError('Plasma has not applied the desktop defaults yet: '+result)
                break
            except (subprocess.CalledProcessError, RuntimeError):
                if attempt==29: raise
                time.sleep(2)
        run('xdg-settings','set','default-web-browser','firefox.desktop')
        run('xdg-mime','default','firefox.desktop','x-scheme-handler/http','x-scheme-handler/https','text/html')
        run('xdg-mime','default','winux-wine.desktop','application/x-ms-dos-executable','application/x-msdownload','application/vnd.microsoft.portable-executable','application/x-msi')
        run('kbuildsycoca6','--noincremental')
        (state/'desktop-complete').touch()
    if not (state/'wine-complete').exists():
        # Arch's WoW64 package supports 32/64-bit apps in one prefix. Do not force WINEARCH=win32.
        env = {**os.environ, 'WINEPREFIX':str(home/'.wine'), 'WINEDEBUG':'-all'}
        run('wineboot','--init',env=env,timeout=180)
        run('wineserver','--wait',env=env,timeout=180)
        (state/'wine-complete').touch()
    (config/'autostart/winux-desktop.desktop').unlink(missing_ok=True)


def main():
    if os.geteuid()==0:
        raise RuntimeError('Desktop setup must run as the logged-in user, never root.')
    home=Path.home()
    state=Path(os.environ.get('XDG_STATE_HOME',home/'.local/state'))/'winux-desktop-v1'
    state.mkdir(parents=True,exist_ok=True)
    with (state/'lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        with (state/'setup.log').open('a') as log:
            try:
                configure(home,state)
                log.write('Desktop and Wine setup completed.\n')
            except Exception as exc:
                log.write(f'Setup will retry next login: {exc}\n')
                if isinstance(exc,subprocess.CalledProcessError): log.write(exc.stderr or '')
                raise

if __name__=='__main__': main()
