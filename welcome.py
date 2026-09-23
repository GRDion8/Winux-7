#!/usr/bin/env python3
"""One-time, non-privileged first-login welcome."""
from pathlib import Path
import subprocess
import os
import json
import tkinter as tk
from tkinter import ttk

marker = Path.home() / '.local/state/winux-welcome-complete'
state = Path(os.environ.get('XDG_STATE_HOME', Path.home()/'.local/state'))/'winux-desktop-v1'
# Keep the first session dedicated to setup; show the welcome after its restart.
try:
    ready = json.loads((state/'ready.json').read_text())
    ready_after_restart = ready['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip()
except (OSError, ValueError, KeyError):
    ready_after_restart = False
if not marker.exists() and ready_after_restart:
    app = tk.Tk()
    app.title('Winux 7')
    app.geometry('640x420')
    app.configure(bg='white')
    tk.Label(app, text='Welcome home.', bg='white', fg='#075594', font=('DejaVu Sans', 28)).pack(anchor='w', padx=35, pady=(30, 15))
    tk.Label(app, text='Your familiar desktop, powered by Arch Linux.\n\nUse the Start menu to find your apps.\nFirefox is your browser; Task Manager opens TMOG.\nConnect to Wi-Fi from the network icon near the clock.\n\nYour desktop and Windows application support are ready.', bg='white', fg='#334b60', justify='left', font=('DejaVu Sans', 11)).pack(anchor='w', padx=35)
    def guide():
        subprocess.Popen(['xdg-open', '/usr/share/winux-setup/TUTORIAL.md'])
    def done():
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        (Path.home() / '.config/autostart/winux-welcome.desktop').unlink(missing_ok=True)
        app.destroy()
    ttk.Button(app, text='Read the user guide', command=guide).pack(side='left', padx=35, pady=25)
    ttk.Button(app, text='Start using Winux', command=done).pack(side='right', padx=35, pady=25)
    app.mainloop()
