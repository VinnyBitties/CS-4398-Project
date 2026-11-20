"""Prospective software identity grouping; preserve installer framework strata.

Six observed PortableApps installer import hashes span 3-14 different AppIDs
each. These identify shared installer code, not the installed application.
Only this explicit publisher category + resource combination gets the exception;
ordinary/malware imphash relationships remain conservative. Never predictors.
"""
import re
from grouping import relationships as original, normalize, connected

VERSION = 'cfd-release-software-groups-v3'
INSTALLER_STUBS = frozenset(('61259b55b8912888e90f516ca08dc514',
    '9dda1a1d1f8a1d13ae0297b47046b26e', '46ce5c12b293febbeb513b196aa7f843',
    '32f3282581436269b3a75b6675fe3e08', 'c05041e01f84e1ccca9c4451f3b6a383',
    '1f23f452093b5c1ff091a2f9fb4fa3e9'))


def relationships(entry, source):
    tokens, removed, identity = original(entry, source)
    pe = source.get('target',{}).get('file',{}).get('pe') or {}
    vi = {x.get('name'):x.get('value') for x in pe.get('versioninfo',[]) if isinstance(x,dict)}
    app = vi.get('PortableApps.comAppID'); version = vi.get('PortableApps.comInstallerVersion')
    if (entry.get('label_source') == 'PortableApps Installers' and
        identity['company'] == 'portableapps.com' and isinstance(app,str) and
        re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',app) and isinstance(version,str) and
        re.fullmatch(r'[0-9.]{1,30}',version) and pe.get('imphash') in INSTALLER_STUBS):
        token = 'imphash:'+pe['imphash']; tokens = [t for t in tokens if t != token]
        tokens.append('portableapps_appid:'+normalize(app))
        removed.append({'token':token,'reason':'shared_publisher_installer_framework_not_application_identity'})
        identity['installer_framework'] = token
        identity['installer_version'] = version
        identity['portableapps_appid'] = normalize(app)
    return sorted(set(tokens)), removed, identity
