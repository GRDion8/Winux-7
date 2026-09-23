"""Run under an isolated Xvfb display; all setup and reboot operations are mocked."""
import io
import tempfile
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
import first_login_tests
first=first_login_tests.first
original_tk=tk.Tk

for outcome in ['success','failure','restart-blocked','restart-later']:
    roots=[];calls=[];errors=[]
    def make_root():
        app=original_tk();roots.append(app)
        destroy=app.destroy
        def clean_destroy():
            for callback in app.tk.call('after','info'):app.after_cancel(callback)
            destroy()
        app.destroy=clean_destroy
        after=app.after
        def fast(ms,fn=None,*args):
            return after(5 if ms==1000 else ms,fn,*args)
        if outcome!='restart-later':app.after=fast
        def inspect():
            def widgets(parent):
                for child in parent.winfo_children():
                    yield child
                    yield from widgets(child)
            texts=[str(w.cget('text')) for w in widgets(app) if 'text' in w.keys()]
            if outcome=='failure' and 'Continue to desktop' in texts:app.destroy();return
            if outcome=='restart-blocked' and 'Continue to desktop' in texts:app.destroy();return
            if outcome=='restart-later':
                for w in widgets(app):
                    if 'text' in w.keys() and w.cget('text')=='Restart later':w.invoke();return
            after(50,inspect)
        after(50,inspect)
        def timeout():errors.append('UI did not complete');app.destroy()
        after(4000,timeout)
        return app
    def finish(*args):
        if outcome=='failure':raise RuntimeError('simulated setup failure')
    def run(*args,**kwargs):
        calls.append(args)
        assert args==('systemctl','reboot'),args
        if outcome=='restart-blocked':raise RuntimeError('inhibited')
        roots[-1].after(10,roots[-1].destroy)
    with tempfile.TemporaryDirectory() as folder,patch.object(tk,'Tk',side_effect=make_root),patch.object(first,'finish',side_effect=finish),patch.object(first,'run',side_effect=run):
        log=io.StringIO();first.ready_screen(Path(folder),Path(folder),log)
    assert not errors,(outcome,errors)
    assert len(calls)==(1 if outcome in ['success','restart-blocked'] else 0),(outcome,calls)
print('PASS: preparation UI success, setup failure, inhibited reboot and Restart later; no actual setup or reboot')
