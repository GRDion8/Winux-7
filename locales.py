"""Locale choices from glibc's complete supported-locale list."""
from pathlib import Path
import re


def supported(path=Path('/usr/share/i18n/SUPPORTED')):
    result = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            fields=line.split()
            if len(fields)==2 and re.fullmatch(r'[A-Za-z0-9_.@-]+',fields[0]) and re.fullmatch(r'[A-Za-z0-9_-]+',fields[1]):
                result[fields[0]]=fields[1]
    # Preview portability; Arch glibc supplies the full file on the live ISO.
    return result or {'en_US.UTF-8':'UTF-8'}


def choices():
    values=supported()
    friendly={'en_US.UTF-8':'English (United States)', 'en_GB.UTF-8':'English (United Kingdom)',
              'de_DE.UTF-8':'Deutsch', 'fr_FR.UTF-8':'Français', 'es_ES.UTF-8':'Español'}
    result={}
    for loc,charset in sorted(values.items()):
        source=Path('/usr/share/i18n/locales')/loc.split('.')[0]
        details=source.read_text(errors='replace') if source.is_file() else ''
        language=re.search(r'^language\s+"([^"]+)"',details,re.M)
        territory=re.search(r'^territory\s+"([^"]+)"',details,re.M)
        label=(language.group(1)+' — '+territory.group(1)+' · '+loc) if language and territory else loc
        result[friendly.get(loc,label+' ('+charset+')')]=loc
    return result
