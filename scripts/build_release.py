"""Build a portable release ZIP from the explicit public file allowlist."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(output):
    names = [line.strip() for line in (ROOT / 'release-files.txt').read_text(encoding='utf-8').splitlines()
             if line.strip() and not line.startswith('#')]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate release file')
    files = {}
    for name in sorted(names):
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name:
            raise ValueError('Invalid relative release path: ' + name)
        path = ROOT.joinpath(*rel.parts)
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError('Missing or nonlocal release file: ' + name)
        if path.suffix.lower() in {'.exe', '.dll', '.tsc', '.tsm', '.tdr', '.zip', '.pyc', '.pdf'}:
            raise ValueError('Excluded binary/vendor/user asset: ' + name)
        text = path.read_text(encoding='utf-8-sig')
        if re.search(r'(?i)\b[A-Z]:[\\/]', text):
            raise ValueError('Absolute workstation path in ' + name)
        files[name] = text.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')

    for required in ('LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md', 'release-files.txt',
                     '.agents/plugins/marketplace.json', 'plugins/tina-bridge/plugin.json',
                     'plugins/tina-bridge/mcp.json'):
        if required not in files:
            raise ValueError('Required release file missing: ' + required)
    for name in ('empty.xml', 'primitives.xml'):
        xml = ET.fromstring(files['plugins/tina-bridge/server/assets/' + name])
        if any(c.get('macrotype') is not None for c in xml.iter('component')) or any(
                p.get('encrypted') for p in xml.iter('parameter')):
            raise ValueError('Only primitive interoperability metadata may be bundled')

    version = json.loads(files['plugins/tina-bridge/plugin.json'])['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', version):
        raise ValueError('Invalid release version')
    index = {'version': version, 'files': [
        {'path': name, 'bytes': len(data), 'sha256': digest(data)} for name, data in files.items()]}
    files['package-index.json'] = (json.dumps(index, indent=2) + '\n').encode('utf-8')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ('tina-bridge-' + version + '.zip')
    if archive.exists():
        raise FileExistsError('Choose a new output directory: ' + str(archive))
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 9, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name], compresslevel=9)
    checksum = digest(archive.read_bytes())
    (output / (archive.name + '.sha256')).write_text(checksum + '  ' + archive.name + '\n', encoding='utf-8')
    result = {'version': version, 'archive': archive.name, 'sha256': checksum,
              'bytes': archive.stat().st_size, 'file_count': len(files),
              'python': sys.version.split()[0], 'zlib': zlib.ZLIB_VERSION}
    (output / 'release-manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    build(parser.parse_args().output)
