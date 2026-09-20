"""Read-only hardware discovery and conservative official-package selection."""
import dataclasses
import json
from pathlib import Path
import re
import subprocess

@dataclasses.dataclass
class Hardware:
    cpu_vendor: str
    virtualization: str
    pci: list

    def plan(self):
        packages = {'linux-firmware', 'mesa'}
        services, notes = [], []
        if self.cpu_vendor == 'GenuineIntel':
            packages.add('intel-ucode')
        elif self.cpu_vendor == 'AuthenticAMD':
            packages.add('amd-ucode')
        graphics = {p['vendor'] for p in self.pci if p['class'].startswith('03')}
        if '8086' in graphics:
            packages.add('vulkan-intel')
        if '1002' in graphics:
            packages.add('vulkan-radeon')
        if '10de' in graphics:
            packages.add('vulkan-nouveau')
            notes.append('NVIDIA detected: use kernel Nouveau/Mesa initially. Proprietary or open NVIDIA modules require a GPU-generation compatibility decision; not selected blindly.')
        if any(p['class'].startswith('04') and p['vendor'] in {'8086','1022','1002'} for p in self.pci):
            packages.add('sof-firmware')
        if self.virtualization == 'vmware':
            packages.add('open-vm-tools')
            services.append('vmtoolsd.service')
        elif self.virtualization == 'oracle':
            packages.add('virtualbox-guest-utils')
            services.append('vboxservice.service')
        elif self.virtualization in {'kvm','qemu'}:
            packages.update(['qemu-guest-agent','spice-vdagent'])
            services.append('qemu-guest-agent.service')
        modules = sorted({p['module'] for p in self.pci if p['class'].startswith('01') and re.fullmatch(r'[a-zA-Z0-9_]+', p['module'])})
        return {'packages':sorted(packages), 'services':services, 'storage_modules':modules, 'notes':notes}


def detect():
    cpu = Path('/proc/cpuinfo').read_text()
    match = re.search(r'^vendor_id\s*:\s*(\S+)', cpu, re.M)
    result = subprocess.run(['systemd-detect-virt','--vm'], capture_output=True, text=True)
    virt = result.stdout.strip() if result.returncode == 0 else 'none'
    pci = []
    for device in sorted(Path('/sys/bus/pci/devices').glob('*')):
        def read(name):
            return (device/name).read_text().strip().removeprefix('0x')
        module = device/'driver/module'
        pci.append({'address':device.name, 'vendor':read('vendor'), 'device':read('device'),
                    'class':read('class'), 'module':module.resolve().name if module.exists() else ''})
    return Hardware(match.group(1) if match else 'unknown', virt, pci)

if __name__ == '__main__':
    info = detect()
    print(json.dumps({'hardware':dataclasses.asdict(info), 'plan':info.plan()}, indent=2))
