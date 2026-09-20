"""Run with DISPLAY (or xvfb-run). Never invokes the installation engine."""
import time
from unittest.mock import patch
import setup

app = setup.Setup(install=False)
app.withdraw()
with patch.object(setup.engine.Installer, 'execute', side_effect=AssertionError('Real install attempted')):
    app.advance() # preferences
    assert app.page == 1
    app.advance() # connection
    app.advance() # drives
    assert app.page == 3
    app.tree.selection_set('0')
    app.select_disk()
    assert app.disk.path == '/dev/sda'
    app.advance() # account
    app.username.set('demo')
    app.password.set('not-a-real-password')
    app.repeat.set('not-a-real-password')
    app.advance() # review
    assert app.page == 5
    with patch.object(setup.messagebox, 'askyesno', return_value=False):
        app.advance()
        assert app.page == 5 and not app.busy, 'No must not start formatting'
    with patch.object(setup.messagebox, 'askyesno', return_value=True):
        app.advance() # simulated progress
    deadline = time.monotonic() + 12
    while app.busy and time.monotonic() < deadline:
        app.update()
        time.sleep(.02)
    assert app.finished and not app.busy, 'Preview did not finish'
    assert not app.password.get() and not app.repeat.get(), 'Password fields not cleared'
# Wi-Fi dialog receives mocked nmcli results; no real network changes.
import network
from unittest.mock import Mock
with patch.object(network.NetworkDialog, 'scan'):
    dialog = network.NetworkDialog(app)
    dialog.queue.put(('scan', 0, 'Home Wi-Fi\nGuest\n'))
    dialog.poll()
    assert dialog.choices.cget('values') == ('Guest', 'Home Wi-Fi')
    dialog.queue.put(('connect', 0, ''))
    dialog.poll()
    assert 'Connected' in dialog.status.cget('text')
    dialog.destroy()
app.destroy()
print('PASS: complete GUI preview flow; real installer never invoked')
