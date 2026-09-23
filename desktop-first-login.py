#!/usr/bin/env python3
"""Finish the first session, then restore the saved wallpaper at every login."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
import queue
import threading


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=kwargs.pop('timeout',60), **kwargs).stdout.strip()


def configure(home, state, progress=lambda message: None):
    progress("Preparing your Aero desktop…")
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
    desktop_pending = not (state/'desktop-complete').exists()
    if desktop_pending:
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
        progress('Setting up Windows application support…')
        env = {**os.environ, 'WINEPREFIX':str(home/'.wine'), 'WINEDEBUG':'-all'}
        run('wineboot','--init',env=env,timeout=180)
        run('wineserver','--wait',env=env,timeout=180)
        (state/'wine-complete').touch()
    progress('Saving your desktop background…')
    restore_wallpaper(initial=not (state/'wallpaper-complete').exists())
    (state/'wallpaper-complete').touch()



def restore_wallpaper(initial=False):
    helper = Path('/usr/local/bin/winux-control-panel')
    for attempt in range(30):
        try:
            if helper.is_file():
                # Dedicated API remains available under the desktop layout lock.
                run(str(helper), '--restore-wallpaper', timeout=90)
            else:
                # Standard Plasma fallback keeps its own wallpaper controls.
                if not initial: return
                path = Path('/usr/share/winux-setup/wallpaper-path')
                if not path.exists(): return
                image = Path(path.read_text().strip())
                if not image.is_file(): raise RuntimeError('Configured wallpaper is missing.')
                script = 'var ds=desktops(); if (!ds.length) throw new Error("No desktop");'
                script += 'for(var i=0;i<ds.length;i++){var d=ds[i];d.wallpaperPlugin="org.kde.image";d.currentConfigGroup=["Wallpaper","org.kde.image","General"];d.writeConfig("Image",'+json.dumps(image.as_uri())+');} print("winux-wallpaper-applied");'
                if 'winux-wallpaper-applied' not in run('qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.evaluateScript',script):
                    raise RuntimeError('Desktop background was not confirmed.')
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError):
            if attempt == 29: raise
            time.sleep(2)


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def needs_setup(home, state):
    config = Path(os.environ.get('XDG_CONFIG_HOME', home/'.config'))
    aero_state = Path(os.environ.get('XDG_STATE_HOME', home/'.local/state'))/'win7-aero-postinstall/first-login-complete'
    return ((state/'setup-started').exists() and not (state/'ready.json').exists()) or (not (state/'desktop-complete').exists() or not (state/'wine-complete').exists() or
            ((config/'autostart/aerothemeplasma-first-login.desktop').exists() and not aero_state.exists()))


def finish(home, state, progress):
    (state/'setup-started').touch()
    configure(home, state, progress)
    # Written only after every stage succeeds. A later login never schedules another restart.
    pending = state/'ready.tmp'
    pending.write_text(json.dumps({'boot_id':boot_id()})+'\n')
    pending.replace(state/'ready.json')


def ready_screen(home, state, log, demo=False):
    import tkinter as tk
    from tkinter import ttk
    app=tk.Tk();app.title('Winux 7');app.configure(bg='#063b70')
    app.geometry(f'{app.winfo_screenwidth()}x{app.winfo_screenheight()}+0+0')
    app.attributes('-fullscreen', True)
    app.protocol('WM_DELETE_WINDOW', lambda: None)
    def close():
        for callback in app.tk.call('after', 'info'):
            app.after_cancel(callback)
        app.destroy()
    frame=tk.Frame(app,bg='#063b70');frame.place(relx=.5,rely=.5,anchor='center')
    tk.Label(frame,text='Winux 7',bg='#063b70',fg='white',font=('DejaVu Sans',34)).pack(pady=25)
    tk.Label(frame,text='Getting things ready',bg='#063b70',fg='white',font=('DejaVu Sans',24)).pack(pady=15)
    status=tk.StringVar(value='Preparing your desktop…')
    tk.Label(frame,textvariable=status,bg='#063b70',fg='white',wraplength=650,font=('DejaVu Sans',13)).pack(pady=20)
    bar=ttk.Progressbar(frame,mode='indeterminate',length=400);bar.pack(pady=15);bar.start(20)
    tk.Label(frame,text='Your computer will restart when setup is complete.',bg='#063b70',fg='#d4e8ff',font=('DejaVu Sans',11)).pack(pady=15)
    actions=tk.Frame(frame,bg='#063b70');actions.pack(pady=15)
    events=queue.Queue()
    def work():
        try:
            if demo:
                events.put(('progress','Setting up Windows application support…'))
                return
            finish(home,state,lambda message:events.put(('progress',message)))
            log.write('Desktop, Wine and wallpaper setup completed.\n');log.flush()
            events.put(('complete',None))
        except Exception as exc:
            log.write(f'Setup will retry next login: {exc}\n')
            if isinstance(exc,subprocess.CalledProcessError):log.write(exc.stderr or '')
            log.flush();events.put(('error',str(exc)))
    def restart():
        try:
            # Normal logind authorization and inhibitors apply; never use force or sudo.
            run('systemctl','reboot',timeout=30)
            status.set('Restarting…')
        except Exception as exc:
            status.set('Setup is complete. Please restart from the Start menu.')
            log.write(f'Automatic restart was not available: {exc}\n');log.flush()
            ttk.Button(actions,text='Continue to desktop',command=close).pack()
    def countdown(seconds):
        status.set(f'Everything is ready. Restarting in {seconds} seconds…')
        if seconds:app.after(1000,lambda:countdown(seconds-1))
        else:restart()
    def poll():
        try:
            while True:
                kind,message=events.get_nowait()
                if kind=='progress':status.set(message)
                elif kind=='complete':
                    bar.stop();bar.configure(mode='determinate',value=100)
                    ttk.Button(actions,text='Restart later',command=close).pack()
                    countdown(15)
                else:
                    bar.stop();status.set('Setup could not finish. '+message+'\nIt will retry when you sign in again.')
                    ttk.Button(actions,text='View setup log',command=lambda:subprocess.Popen(['xdg-open',str(state/'setup.log')])).pack(side='left',padx=8)
                    ttk.Button(actions,text='Continue to desktop',command=close).pack(side='left',padx=8)
        except queue.Empty:pass
        app.after(150,poll)
    threading.Thread(target=work,daemon=True).start();poll()
    if demo:app.bind('<Escape>',lambda event:close())
    app.mainloop()


def main():
    import sys
    if '--demo' in sys.argv:
        # Preview performs no setup, file writes or reboot.
        ready_screen(None,None,None,demo=True);return
    if os.geteuid()==0:
        raise RuntimeError('Desktop setup must run as the logged-in user, never root.')
    home=Path.home()
    state=Path(os.environ.get('XDG_STATE_HOME',home/'.local/state'))/'winux-desktop-v1'
    state.mkdir(parents=True,exist_ok=True)
    with (state/'lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        with (state/'setup.log').open('a',buffering=1) as log:
            if needs_setup(home,state):
                ready_screen(home,state,log)
            else:
                try:
                    configure(home,state)
                    log.write('Saved desktop background restored.\n')
                except Exception as exc:
                    log.write(f'Background restore will retry next login: {exc}\n')

if __name__=='__main__': main()
