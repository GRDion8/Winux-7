#!/usr/bin/env python3
"""One-time, non-privileged first-login welcome."""
from pathlib import Path
import subprocess
import tkinter as tk
from tkinter import ttk

marker = Path.home() / '.local/state/winux-welcome-complete'
if not marker.exists():
    app = tk.Tk()
    app.title('Winux 7')
    app.geometry('640x420')
    app.configure(bg='white')
    tk.Label(app, text='Welcome home.', bg='white', fg='#075594', font=('DejaVu Sans', 28)).pack(anchor='w', padx=35, pady=(30, 15))
    tk.Label(app, text='Your familiar desktop, powered by Arch Linux.\n\nUse the Start menu to find your apps.\nFirefox is your browser; Task Manager opens TMOG.\nConnect to Wi-Fi from the network icon near the clock.\n\nDesktop and Wine setup may take a moment to finish.\nSign out and back in if some details have not refreshed.', bg='white', fg='#334b60', justify='left', font=('DejaVu Sans', 11)).pack(anchor='w', padx=35)
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
