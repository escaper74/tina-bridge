"""Per-user TINA Bridge settings; no workstation-specific paths or UI access."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import shutil

SUPPORTED_VERSION = '9.3.150.328SF-TI'


def data_directory():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData/Local')))/'TinaBridge'


def config_path():
    return Path(os.environ.get('TINA_CONFIG',str(data_directory()/'settings.json'))).expanduser().resolve()


def read_config(path=None):
    path=Path(path) if path else config_path()
    if not path.exists():return {}
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value,dict):raise ValueError(f'Expected a settings object in {path}')
    return value


def _expanded(value,relative_to=None):
    path=Path(os.path.expandvars(str(value))).expanduser()
    if not path.is_absolute() and relative_to is not None:path=relative_to/path
    return path.resolve()


def _registry_candidates():
    if os.name!='nt':return
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
            access=winreg.KEY_READ|view
            try:
                with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\App Paths\tina.exe',0,access) as key:
                    yield winreg.QueryValueEx(key,'')[0].strip('"')
            except OSError:pass
            try:
                root=winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\Uninstall',0,access)
            except OSError:continue
            with root:
                for i in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        with winreg.OpenKey(root,winreg.EnumKey(root,i),0,access) as key:
                            name=winreg.QueryValueEx(key,'DisplayName')[0]
                            if 'tina' not in name.casefold():continue
                            try:yield str(Path(winreg.QueryValueEx(key,'InstallLocation')[0])/'tina.exe')
                            except OSError:pass
                            try:
                                icon=winreg.QueryValueEx(key,'DisplayIcon')[0]
                                yield icon.rsplit(',',1)[0].strip('"')
                            except OSError:pass
                    except OSError:continue


def discover_executables():
    """Use installer registration, PATH, then a few normal installation roots."""
    candidates=list(_registry_candidates())
    on_path=shutil.which('tina.exe')
    if on_path:candidates.append(on_path)
    for env in ('ProgramFiles','ProgramFiles(x86)'):
        root=os.environ.get(env)
        if root:
            for folder in ('DesignSoft/Tina9-TI','DesignSoft/TINA9-TI','TINA9-TI','TINA-TI'):
                candidates.append(str(Path(root)/folder/'tina.exe'))
    found={}
    for value in candidates:
        path=_expanded(value)
        if path.name.casefold()=='tina.exe' and path.is_file():found[str(path).casefold()]=path
    return sorted(found.values(),key=lambda p:str(p).casefold())


def executable(required=True,path=None):
    config=read_config(path)
    value=os.environ.get('TINA_EXE') or config.get('tina_exe')
    if value:
        result=_expanded(value,(Path(path) if path else config_path()).parent)
        if not result.is_file():raise FileNotFoundError(f'TINA executable does not exist: {result}')
        return str(result)
    found=discover_executables()
    if len(found)==1:return str(found[0])
    if len(found)>1:raise ValueError('Multiple TINA installations found; set TINA_EXE or tina_exe in settings.json: '+str(found))
    if required:
        raise FileNotFoundError('TINA installation not found. Run setup.py --tina-exe <full path to tina.exe>, or set TINA_EXE. See '+str(config_path()))
    return None


def workspace(path=None):
    config=read_config(path)
    value=os.environ.get('TINA_WORKSPACE') or config.get('workspace') or str(data_directory()/'runs')
    return _expanded(value,(Path(path) if path else config_path()).parent)


def monitor(path=None):
    return os.environ.get('TINA_MONITOR') or read_config(path).get('monitor','secondary')


def python_executable(path=None):
    value=os.environ.get('TINA_PYTHON') or read_config(path).get('python') or str(data_directory()/'venv/Scripts/python.exe')
    return _expanded(value,(Path(path) if path else config_path()).parent)


def file_version(path):
    """Read the executable's published FileVersion; do not start the application."""
    if os.name!='nt':raise OSError('TINA Bridge requires Windows')
    version=C.WinDLL('version',use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes=[W.LPCWSTR,C.POINTER(W.DWORD)]
    version.GetFileVersionInfoSizeW.restype=W.DWORD
    version.GetFileVersionInfoW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p]
    version.VerQueryValueW.argtypes=[C.c_void_p,W.LPCWSTR,C.POINTER(C.c_void_p),C.POINTER(W.UINT)]
    size=version.GetFileVersionInfoSizeW(str(path),None)
    if not size:raise OSError(C.get_last_error(),'Cannot read TINA file version')
    data=C.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path),0,size,data):raise OSError(C.get_last_error(),'Cannot read file version resource')
    ptr=C.c_void_p();length=W.UINT()
    if version.VerQueryValueW(data,r'\VarFileInfo\Translation',C.byref(ptr),C.byref(length)):
        words=C.cast(ptr,C.POINTER(W.WORD))
        for i in range(length.value//4):
            query=f'\\StringFileInfo\\{words[i*2]:04x}{words[i*2+1]:04x}\\FileVersion'
            value=C.c_void_p();count=W.UINT()
            if version.VerQueryValueW(data,query,C.byref(value),C.byref(count)):
                return C.wstring_at(value).strip()
    raise ValueError('FileVersion string is absent')
