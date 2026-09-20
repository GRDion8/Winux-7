#!/usr/bin/env python3
"""Local, native Setup wizard. Default mode is a harmless visual preview."""
import argparse
from pathlib import Path
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageOps
import time
import engine

BLUE = '#075594'
FONT = 'Tahoma'

class Setup(tk.Tk):
    def __init__(self, install=False):
        super().__init__()
        self.real = install
        self.title('Winux 7')
        self.geometry(f'{min(1040, self.winfo_screenwidth()-30)}x{min(760, self.winfo_screenheight()-50)}')
        self.minsize(900, 680)
        self.configure(bg='#06385a')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.events = queue.Queue()
        self.busy = False
        self.page = 0
        self.finished = False
        self.disk = None
        self.disks = []
        self.locale = tk.StringVar(value='English (United States)')
        self.keyboard = tk.StringVar(value='US English')
        self.zone = tk.StringVar(value='Europe/Berlin')
        self.username = tk.StringVar()
        self.hostname = tk.StringVar(value='winux-pc')
        self.password = tk.StringVar()
        self.repeat = tk.StringVar()
        self.confirm = tk.StringVar()
        self.aero = tk.BooleanVar(value=True)
        self.erasure = tk.BooleanVar(value=False)
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('.', font=(FONT, 10))
        self.style.configure('TButton', padding=(14, 7), background='#eef4f9', foreground='#173b5d')
        self.style.map('TButton', background=[('active', '#d5ecff')])
        self.style.configure('Accent.TButton', background='#d9edfc', bordercolor='#4c99ca', font=(FONT, 11, 'bold'))
        self.style.configure('TCombobox', padding=5)
        self.style.configure('TEntry', padding=6)
        self.style.configure('Treeview', rowheight=42, font=(FONT, 10), background='white', fieldbackground='white')
        self.style.configure('Treeview.Heading', font=(FONT, 10, 'bold'))
        self.style.configure('TProgressbar', troughcolor='#e6e8e9', background='#67b648', bordercolor='#aab3bb')
        self.background_image = Image.open(Path(__file__).with_name('wallpaper.jpg'))
        self.wallpaper = tk.Canvas(self, highlightthickness=0, bg='#06385a')
        self.wallpaper.place(relwidth=1, relheight=1)
        self.wallpaper.bind('<Configure>', self.draw_background)
        self.shell = tk.Frame(self, bg='#acc6da', highlightbackground='#c6e1f1', highlightthickness=1)
        self.shell.place(relx=.5, rely=.49, anchor='center', relwidth=.87, relheight=.86)
        self.chrome = tk.Frame(self.shell, bg='#b7cede', height=42)
        self.chrome.pack(fill='x')
        tk.Label(self.chrome, text='Winux 7', font=(FONT, 11), bg='#b7cede', fg='#103655').pack(side='left', padx=15, pady=10)
        tk.Label(self.chrome, text='LIVE INSTALLER' if self.real else 'PREVIEW • NO DISK CHANGES', font=(FONT, 8, 'bold'), bg='#b7cede', fg='#365b75').pack(side='right', padx=15)
        self.content = tk.Frame(self.shell, bg='white')
        self.content.pack(fill='both', expand=True, padx=6)
        self.footer = tk.Frame(self.shell, bg='#edf1f5', height=58)
        self.footer.pack(fill='x', padx=6, pady=(0, 6))
        self.back = ttk.Button(self.footer, text='‹  Back', command=self.previous)
        self.back.pack(side='left', padx=18, pady=12)
        self.next = ttk.Button(self.footer, text='Next  ›', style='Accent.TButton', command=self.advance)
        self.next.pack(side='right', padx=18, pady=12)
        self.cancel = ttk.Button(self.footer, text='Cancel', command=self.close)
        self.cancel.pack(side='right', pady=12)
        self.status = tk.Label(self, bg='#06385a', fg='#d8eff9', text='Winux 7', font=(FONT, 10))
        self.status.place(relx=.5, rely=.955, anchor='center')
        self.bind('<Alt-Left>', lambda e: self.previous() if not self.busy else None)
        self.render()
        self.after(100, self.drain)

    def draw_background(self, event):
        c, w, h = self.wallpaper, event.width, event.height
        c.delete('all')
        self.background_photo = ImageTk.PhotoImage(ImageOps.fit(self.background_image, (max(w,1), max(h,1)), method=Image.Resampling.LANCZOS))
        c.create_image(0, 0, anchor='nw', image=self.background_photo)

    def label(self, text, *, size=11, color='#354b60', parent=None, bold=False):
        label = tk.Label(parent or self.body, text=text, bg='white', fg=color,
                         font=(FONT, size, 'bold' if bold else 'normal'), justify='left', anchor='w', wraplength=720)
        label.pack(anchor='w', pady=5)
        return label

    def heading(self, title, subtitle):
        self.label(title, size=22, color=BLUE)
        self.label(subtitle, size=10, color='#617386')

    def render(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.body = tk.Frame(self.content, bg='white')
        self.body.pack(fill='both', expand=True, padx=32, pady=20)
        self.back.configure(state='normal' if self.page and self.page < 6 else 'disabled')
        self.next.configure(text='Next  ›', state='normal')
        [self.welcome, self.region, self.connection, self.drive, self.account, self.review, self.progress][self.page]()
        self.status.configure(text=('1  Collecting information     ━━━━━     2  Installing Winux 7' if self.page < 6 else '1  Collecting information     ━━━━━     2  Installing Winux 7  ●'))

    def welcome(self):
        self.label('Welcome', size=22, color='#278dc2')
        self.label('Winux 7', size=40, color='#173f66')
        self.label('A familiar place to start.', size=19, color='#55768e')
        self.label('Set up Winux 7 on your computer. We’ll guide you through each step.', size=12)
        self.label('Keep your computer connected to power and the internet.\nYou’ll need an empty drive, or a complete backup of the drive you choose.', size=10)
        if not self.real:
            self.label('This is a preview. Drives and installation progress are simulated.\nNo operating system will be installed.', color='#916610', size=10)
        self.next.configure(text='Install now  →' if self.real else 'Try the setup  →')

    def field(self, caption, variable, values=None, secret=False):
        row = tk.Frame(self.body, bg='white')
        row.pack(fill='x', pady=8)
        tk.Label(row, text=caption, bg='white', fg='#253e57', font=(FONT, 10), anchor='w', width=22).pack(side='left')
        widget = ttk.Combobox(row, textvariable=variable, values=values, state='readonly', width=35) if values else ttk.Entry(row, textvariable=variable, width=37, show='•' if secret else '')
        widget.pack(side='left', fill='x', expand=True)
        return widget

    def region(self):
        self.heading('Choose your preferences', 'These settings will be used for your new desktop. Setup itself is in English.')
        language = self.field('Language & formats', self.locale, list(engine.LOCALES))
        language.configure(state='normal')
        def filter_locales(event):
            if event.keysym not in {'Up','Down','Return','Tab'}:
                query = self.locale.get().casefold()
                language.configure(values=[name for name in engine.LOCALES if query in name.casefold()])
        language.bind('<KeyRelease>', filter_locales)
        self.field('Keyboard layout', self.keyboard, list(engine.KEYBOARDS))
        self.field('Time zone', self.zone, engine.timezones())
        test = tk.StringVar()
        self.field('Try your keyboard', test)
        self.label('The keyboard test uses the live session layout. Select “Apply keyboard” before entering your password on the account page.', size=10)
        ttk.Button(self.body, text='Apply keyboard', command=self.apply_keyboard).pack(anchor='w', pady=8)

    def apply_keyboard(self):
        if self.real:
            try:
                subprocess.run(['setxkbmap', engine.KEYBOARDS[self.keyboard.get()][1]], check=True, capture_output=True)
            except (OSError, subprocess.CalledProcessError):
                messagebox.showerror('Keyboard', 'Could not apply the live keyboard layout. Open a live terminal and run setxkbmap for your layout before continuing.')
                return False
        return True

    def connection(self):
        self.heading('Stay connected', 'Winux 7 downloads the system and desktop components during installation.')
        self.label('An Ethernet cable is the easiest way to connect. For Wi-Fi, open Network settings and choose your network.', size=12)
        ttk.Button(self.body, text='Network settings…', command=self.network).pack(anchor='w', pady=12)
        self.label('Stock Arch ISO: if you already connected using iwctl, keep that connection. The network button is available on the Winux 7 ISO.', size=10)
        self.label('Setup checks package availability before erasing the drive. A connection can still fail later; keep the network active throughout installation.', size=10)
        ttk.Checkbutton(self.body, text='Use the classic Winux 7 appearance (recommended)', variable=self.aero).pack(anchor='w', pady=18)
        self.label('Aero builds from source and needs a compatible Plasma 6.7 package set. Uncheck this only for a standard KDE Plasma installation.', size=10)

    def network(self):
        if not self.real:
            messagebox.showinfo('Preview', 'On the custom live ISO, this opens a Wi-Fi picker with a password field and connection status.')
            return
        import shutil
        if shutil.which('nm-connection-editor') and subprocess.run(['systemctl', 'is-active', '--quiet', 'NetworkManager']).returncode == 0:
            from network import NetworkDialog
            NetworkDialog(self)
        else:
            messagebox.showinfo('Connect to Wi-Fi', 'Keep the connection you made in the Arch live terminal.\n\nIf needed, press Ctrl+Alt+F2 and use iwctl:\nstation wlan0 scan\nstation wlan0 get-networks\nstation wlan0 connect YOUR_NETWORK\n\nUse your adapter name from “device list”. Return to Setup with Ctrl+Alt+F1.')

    def drive(self):
        self.heading('Where do you want to install Winux 7?', 'Choose the entire drive to use. All partitions and files on that drive will be erased.')
        self.tree = ttk.Treeview(self.body, columns=('disk', 'size', 'state'), show='headings', height=4, selectmode='browse')
        for key, name, width in [('disk','Drive',350), ('size','Size',95), ('state','Availability',260)]:
            self.tree.heading(key, text=name)
            self.tree.column(key, width=width, minwidth=70)
        self.tree.pack(fill='x', pady=12)
        self.tree.bind('<<TreeviewSelect>>', self.select_disk)
        self.disk_note = self.label('Select a drive to see its details.', size=10)
        ttk.Button(self.body, text='↻  Refresh drives', command=self.refresh_disks).pack(anchor='w', pady=5)
        self.label('Custom installation • whole disk only\nKeeping existing partitions, dual boot, RAID and disk encryption are not supported by this release.', color='#916610', size=10)
        self.refresh_disks()

    def refresh_disks(self):
        self.disk = None
        self.confirm.set('')
        self.erasure.set(False)
        try:
            self.disks = engine.discover() if self.real else [engine.Disk('/dev/sda', 128*1024**3, 'Preview SSD', 'DEMO-001', '8:0'), engine.Disk('/dev/sdb', 16*1024**3, 'Installation USB', 'DEMO-USB', '8:16', 'Live installation media')]
        except Exception as exc:
            messagebox.showerror('Drive detection', str(exc))
            self.disks = []
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, d in enumerate(self.disks):
            self.tree.insert('', 'end', iid=str(i), values=(f'{d.path} • {d.model}', f'{d.size/1024**3:.1f} GiB', d.blocked or 'Available'))
        self.next.configure(state='disabled')

    def select_disk(self, event=None):
        rows = self.tree.selection()
        self.disk = self.disks[int(rows[0])] if rows else None
        if self.disk:
            self.disk_note.configure(text=f'Serial: {self.disk.serial or "not reported"}   •   {"UEFI / GPT" if engine.firmware()=="uefi" else "BIOS / GPT"}\n{self.disk.blocked or "System partition + Linux ext4 partition. This drive will be erased."}')
        self.next.configure(state='normal' if self.disk and not self.disk.blocked else 'disabled')

    def account(self):
        self.heading('Make this computer yours', 'Create the account you’ll use to sign in. You can change these settings later.')
        self.field('User name', self.username)
        self.field('Computer name', self.hostname)
        self.field('Password', self.password, secret=True)
        self.field('Confirm password', self.repeat, secret=True)
        self.label('Use at least 8 characters. Your account can approve administrator actions with this password. Automatic login is off.', size=10)

    def config(self):
        return engine.Config(self.disk, self.username.get().strip(), self.hostname.get().strip(), self.password.get(),
                             engine.LOCALES[self.locale.get()], self.keyboard.get(), self.zone.get(),
                             self.aero.get(), engine.firmware(), self.confirm.get())

    def review(self):
        self.heading('Ready to install', 'Please review your choices. Nothing has been erased yet.')
        c = self.config()
        self.label(f'Drive     {c.disk.label}\nAccount     {c.username} on {c.hostname}\nRegion     {c.locale}  •  {c.keyboard}  •  {c.timezone}\nDesktop     {"Winux 7" if c.aero else "Basic desktop"}', size=11)
        self.label('All data on the selected drive will be permanently erased.\nSetup cannot undo this. Disconnect drives you do not want to use.', color='#a53a27', bold=True, size=11)
        self.label('You will be asked to confirm with Yes or No before formatting begins.', size=10)
        self.label('The installation can take a long time while the Aero desktop builds. Once installation starts, keep power connected and do not close Setup.', size=10)
        self.next.configure(text='Install' if self.real else 'Simulate installation')

    def advance(self):
        if self.busy:
            return
        if self.finished:
            if self.real:
                if messagebox.askyesno('Restart computer', 'Restart now? Remove the installation USB when the computer starts restarting.'):
                    subprocess.run(['systemctl', 'reboot'], check=True)
            else:
                self.destroy()
            return
        if self.page == 1:
            if self.locale.get() not in engine.LOCALES:
                messagebox.showerror('Winux 7', 'Choose a language and format from the list.')
                return
            if not self.apply_keyboard():
                return
        if self.page == 3 and (not self.disk or self.disk.blocked):
            return
        if self.page == 4:
            if self.password.get() != self.repeat.get():
                messagebox.showerror('Check your password', 'The passwords do not match. Please enter them again.')
                return
            try:
                c = self.config()
                c.confirmation = f'ERASE {c.disk.path}'
                c.validate()
            except engine.SetupError as exc:
                messagebox.showerror('Check your details', str(exc))
                return
        if self.page == 5:
            try:
                c = self.config()
                c.confirmation = f'ERASE {c.disk.path}'
                c.validate()
                if not messagebox.askyesno('Winux 7', f'Format {c.disk.label}?\n\nAll partitions and files on this drive will be permanently deleted.\n\nContinue?', default='no', icon='warning'):
                    return
            except engine.SetupError as exc:
                messagebox.showerror('Check the drive confirmation', str(exc))
                return
            self.page = 6
            self.render()
            self.busy = True
            self.password.set('')
            self.repeat.set('')
            threading.Thread(target=self.worker, args=(c,), daemon=False).start()
            return
        self.page += 1
        self.render()

    def previous(self):
        if self.page > 0 and self.page < 6 and not self.busy:
            self.page -= 1
            self.render()

    def progress(self):
        self.heading('Installing Winux 7', 'Your computer will be ready soon. Keep it connected to power and the internet.')
        self.progress_title = self.label(engine.STAGES[0], size=14, color=BLUE)
        self.bar = ttk.Progressbar(self.body, mode='indeterminate')
        self.bar.pack(fill='x', pady=10)
        self.bar.start(20)
        self.stage_label = self.label('Step 1 of 7 • Progress follows completed steps, not download time.', size=10)
        self.log = tk.Text(self.body, height=10, bg='#f5f8fa', fg='#344c61', relief='solid', bd=1, wrap='word', font=('DejaVu Sans Mono', 9), state='disabled')
        self.log.pack(fill='both', expand=True, pady=8)
        self.next.configure(state='disabled')
        self.back.configure(state='disabled')
        self.cancel.configure(state='disabled')

    def worker(self, config):
        emit = lambda kind, data: self.events.put((kind, data))
        try:
            if self.real:
                engine.Installer(config, emit).execute()
            else:
                config.password = ''
                for i, name in enumerate(engine.STAGES):
                    emit('stage', (i, name))
                    emit('log', f'Preview: {name}. No commands are being executed.')
                    time.sleep(.65)
                emit('success', 'Preview complete. No disks were changed. Boot the live ISO to install Winux 7.')
        except Exception as exc:
            config.password = ''
            emit('error', str(exc))
        finally:
            emit('stopped', None)

    def drain(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == 'stage':
                    n, title = data
                    self.progress_title.configure(text=title)
                    self.stage_label.configure(text=f'Step {n+1} of 7 • This step can take several minutes or longer.')
                elif kind == 'log':
                    self.log.configure(state='normal')
                    self.log.insert('end', data + '\n')
                    # Bound visible log size; the full log remains on disk.
                    if int(self.log.index('end-1c').split('.')[0]) > 600:
                        self.log.delete('1.0', '101.0')
                    self.log.see('end')
                    self.log.configure(state='disabled')
                elif kind in {'success', 'error'}:
                    self.bar.stop()
                    self.progress_title.configure(text='Welcome to Winux 7' if kind == 'success' else 'Setup could not finish', fg=BLUE if kind == 'success' else '#a53a27')
                    self.stage_label.configure(text=data)
                    self.finished = kind == 'success'
                    if kind == 'error':
                        self.events.put(('log', 'ERROR: ' + data + '\nFull log: /var/log/winux-setup.log. A partially installed disk may not boot. Do not restart until you have saved the log.'))
                elif kind == 'stopped':
                    self.busy = False
                    if self.finished:
                        self.next.configure(text='Restart now' if self.real else 'Close preview', state='normal')
                    self.cancel.configure(text='Close', state='normal')
        except queue.Empty:
            pass
        self.after(100, self.drain)

    def close(self):
        if self.busy:
            messagebox.showinfo('Installation in progress', 'Please keep Setup open until installation finishes. Interrupting disk writes can leave the system incomplete.')
        elif self.finished or messagebox.askyesno('Close Setup', 'Close Setup? Before installation begins, no disk changes are made.'):
            self.destroy()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Winux 7 graphical installer. Default: safe preview.')
    parser.add_argument('--install', action='store_true', help='Allow installation, only inside the root Arch ISO session')
    parser.add_argument('--demo', action='store_true', help='Preview with simulated disks and progress (default)')
    args = parser.parse_args()
    if args.install and args.demo:
        parser.error('Choose --install or --demo, not both')
    Setup(install=args.install).mainloop()
