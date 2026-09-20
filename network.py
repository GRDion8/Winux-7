"""Small NetworkManager Wi-Fi dialog for the custom live ISO."""
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk


class NetworkDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Connect to a network')
        self.geometry('530x350')
        self.resizable(False, False)
        self.configure(bg='white')
        self.transient(parent)
        self.queue = queue.Queue()
        self.network = tk.StringVar()
        self.password = tk.StringVar()
        self.busy = False
        self.protocol('WM_DELETE_WINDOW', self.close)
        tk.Label(self, text='Connect to Wi-Fi', bg='white', fg='#075594', font=('DejaVu Sans',20)).pack(anchor='w', padx=24, pady=(22,12))
        self.choices = ttk.Combobox(self, textvariable=self.network, state='readonly', width=47)
        self.choices.pack(padx=24, pady=8, fill='x')
        tk.Label(self, text='Network password (leave blank for an open network)', bg='white', fg='#354b60').pack(anchor='w', padx=24)
        ttk.Entry(self, textvariable=self.password, show='•').pack(padx=24, pady=8, fill='x')
        self.status = tk.Label(self, text='Finding nearby networks…', bg='white', fg='#526a80', wraplength=475, justify='left')
        self.status.pack(anchor='w', padx=24, pady=12)
        row = tk.Frame(self, bg='white')
        row.pack(fill='x', padx=24, pady=8)
        self.scan_button = ttk.Button(row, text='Refresh', command=self.scan)
        self.scan_button.pack(side='left')
        self.connect_button = ttk.Button(row, text='Connect', command=self.connect)
        self.connect_button.pack(side='right')
        ttk.Button(row, text='Advanced…', command=lambda: subprocess.Popen(['nm-connection-editor'])).pack(side='right', padx=8)
        self.after(100, self.poll)
        self.scan()

    def operation(self, kind, args, secret=None):
        try:
            result = subprocess.run(args, input=secret, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=75)
            # Never display nmcli output from a connection/password transaction.
            self.queue.put((kind, result.returncode, result.stdout if kind == 'scan' else ''))
        except (OSError, subprocess.TimeoutExpired):
            self.queue.put((kind, 1, ''))

    def scan(self):
        if self.busy:
            return
        self.busy = True
        self.status.configure(text='Finding nearby networks…')
        threading.Thread(target=self.operation, args=('scan', ['nmcli','-t','-e','no','-f','SSID','device','wifi','list','--rescan','yes']), daemon=True).start()

    def connect(self):
        if self.busy or not self.network.get():
            return
        if '\n' in self.password.get() or '\r' in self.password.get():
            self.status.configure(text='The network password cannot contain line breaks.')
            return
        self.busy = True
        self.status.configure(text='Connecting…')
        secret = self.password.get() + '\n'
        self.password.set('')
        # --ask reads the password through stdin; it is never an argv value.
        threading.Thread(target=self.operation, args=('connect', ['nmcli','--ask','--wait','60','device','wifi','connect',self.network.get()], secret), daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, code, output = self.queue.get_nowait()
                self.busy = False
                if kind == 'scan':
                    names = sorted(set(x for x in output.splitlines() if x))
                    self.choices.configure(values=names)
                    if names:
                        self.network.set(names[0])
                    self.status.configure(text='Choose your Wi-Fi network.' if names else 'No Wi-Fi networks found. Connect Ethernet, check your adapter, or use Advanced for a hidden/enterprise network.')
                else:
                    self.status.configure(text='Connected. Close this window to continue Setup.' if code == 0 else 'Could not connect. Check the password and signal, or use Advanced for enterprise Wi-Fi.')
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        if self.busy:
            self.status.configure(text='Please wait for the network operation to finish.')
        else:
            self.password.set('')
            self.destroy()
