"""Process-bound TINA operations. Initial native adapter under active development.

All UI operations use window/control messages, not the mouse or keyboard. The
running application remains the authority for the circuit and exported files.
"""
import argparse
import base64
import ctypes as C
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import tina_native as native
from win32_probe import U, CB, window, windows, children, menu_items
from display import place_windows
import settings

DEFAULT_EXE = settings.executable()


class BridgeError(RuntimeError):
    pass


def list_sessions(exe=DEFAULT_EXE):
    found=[]
    @CB
    def callback(hwnd,_):
        name=C.create_unicode_buffer(256)
        U.GetClassNameW(hwnd,name,len(name))
        if name.value=='TSchematicEditor':
            w=window(hwnd)
            try:
                native.validate(w['pid'],exe)
            except OSError:
                return True
            except RuntimeError:
                return True
            found.append({'pid':w['pid'],'exe':str(native.process_path(w['pid'])),'editor':w})
        return True
    U.EnumWindows(callback,0)
    return found


def create_session(exe=DEFAULT_EXE):
    if not Path(exe).is_file():
        raise FileNotFoundError(exe)
    before={s['pid'] for s in list_sessions(exe)}
    # An MCP client's Windows job may kill its entire process tree on disconnect.
    # Launch this user-owned GUI through local WMI so it outlives the stdio server.
    # No remote host, credentials, scheduled task, service, or system setting.
    exe=str(Path(exe).resolve())
    literal=lambda s: "'"+s.replace("'","''")+"'"
    script=("$ErrorActionPreference='Stop'; "
            "$tinaStartup=New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly "
            "-Property @{ShowWindow=[uint16]4; CreateFlags=[uint32]16777216}; "
            "$tinaCreated=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{"
            f"CommandLine={literal(chr(34)+exe+chr(34))}; CurrentDirectory={literal(str(Path(exe).parent))}; "
            "ProcessStartupInformation=$tinaStartup}; "
            "$tinaCreated | Select-Object ReturnValue,ProcessId | ConvertTo-Json -Compress")
    encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
    launch=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                          capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
    if launch.returncode:
        raise BridgeError(f'Local TINA launch failed: {launch.stderr.decode("utf-8",errors="replace").strip()}')
    launched=json.loads(launch.stdout)
    if launched['ReturnValue']!=0:
        raise BridgeError(f'Local TINA launch returned {launched}')
    pid=int(launched['ProcessId'])
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        candidates=[s for s in list_sessions(exe) if s['pid']==pid and s['pid'] not in before
                    and s['editor']['visible'] and s['editor']['enabled']
                    and re.search(r'未命名|Untitled|Noname',s['editor']['title'],re.I)]
        if len(candidates)==1:
            placement=place_windows(pid)
            candidate=next(s for s in list_sessions(exe) if s['pid']==pid)
            return {**candidate,'independent_process':True,'headless':False,'launch':'local_wmi',
                    'placement':placement}
        time.sleep(0.1)
    raise TimeoutError(f'TINA editor not ready; started PID {pid}. Inspect it before launching again.')


class Tina:
    def __init__(self, pid, exe=DEFAULT_EXE):
        native.validate(pid, exe)
        self.pid, self.exe = pid, exe

    def visible(self):
        native.validate(self.pid, self.exe)
        return [w for w in windows(self.pid) if w['visible'] and w['cls'] != 'TApplication']

    def unique(self, cls):
        items = [w for w in self.visible() if w['cls'] == cls]
        if len(items) != 1:
            raise BridgeError(f'Expected one {cls}; found {len(items)}')
        return items[0]

    def wait(self, predicate, description, timeout=10):
        deadline = time.monotonic() + timeout
        while True:
            place_windows(self.pid)
            result = predicate()
            if result:
                return result
            if time.monotonic() >= deadline:
                raise TimeoutError(f'{description}; windows={self.visible()}')
            time.sleep(0.1)

    def menu(self, cls, patterns):
        if self.analysis_state()['running']:
            raise BridgeError('Native analysis is running; poll or cancel it before another menu operation')
        place_windows(self.pid,restore=True)
        if cls=='TSchematicEditor':
            self.close_operating_point_table()
        w = self.unique(cls)
        if not w['enabled']:
            raise BridgeError(f'{cls} is blocked by an active dialog; inspect status before another operation')
        entries = native.flatten_menu(menu_items(U.GetMenu(w['hwnd'])))
        matches = [m for m in entries if len(m['path']) == len(patterns)
                   and all(re.search(p, t, re.I) for p, t in zip(patterns, m['path']))]
        if len(matches) != 1:
            raise BridgeError(f'Menu match ambiguous or absent: {patterns}')
        native.command(w['hwnd'], matches[0]['command'])
        return matches[0]

    def file_dialog(self, path, save=True):
        path = str(Path(path).resolve())
        if save and Path(path).exists():
            raise FileExistsError(f'Refusing implicit overwrite: {path}')
        if not save and not Path(path).is_file():
            raise FileNotFoundError(path)
        def candidate():
            ds = [w for w in self.visible() if w['cls']=='#32770']
            for d in ds:
                cs = [c for c in children(d['hwnd']) if c['visible']]
                # Common legacy file dialog filename Edit is inside ComboBoxEx32.
                es = [c for c in cs if c['cls']=='Edit' and c['enabled'] and c['control_id']==1148]
                bs = [c for c in cs if (c['cls']=='Button' and c['control_id']==1)
                      or (c['cls']=='TApBitBtn' and re.match(r'打开|保存|Open|Save', c['title'], re.I))]
                if len(es)==1 and len(bs)==1:
                    return d, es[0], bs[0]
            return None
        d, edit, button = self.wait(candidate, 'Waiting for native file dialog')
        b = C.create_unicode_buffer(path)
        native.send(edit['hwnd'], 0x000c, 0, C.addressof(b))
        if native.read_text(edit['hwnd']) != path:
            raise BridgeError('Filename readback did not match')
        U.PostMessageW(button['hwnd'], 0x00f5, 0, 0)
        self.wait(lambda: not any(w['hwnd']==d['hwnd'] for w in self.visible()),
                  'Waiting for file dialog completion')
        if save:
            self.wait(lambda: Path(path).is_file() and Path(path).stat().st_size > 0,
                      'Waiting for saved file')
            # Netlist export can create the header before appending macro models.
            # Wait for the UI thread to finish and for the file to stop changing.
            native.send(self.unique('TSchematicEditor')['hwnd'], 0)
            previous, stable_since = None, time.monotonic()
            def settled():
                nonlocal previous, stable_since
                stat = Path(path).stat()
                value = (stat.st_size, stat.st_mtime_ns)
                now = time.monotonic()
                if value != previous:
                    previous, stable_since = value, now
                    return False
                return now-stable_since >= 0.4
            self.wait(settled, 'Waiting for completed file export')
        return {'path': path, 'bytes': Path(path).stat().st_size}

    def open(self, path):
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        self.menu('TSchematicEditor', [r'^文件|^File', r'^打开\(|^Open\('])
        result = self.file_dialog(path, save=False)
        self.wait(lambda: Path(path).stem.casefold() in self.unique('TSchematicEditor')['title'].casefold(),
                  'Waiting for opened document title')
        return {**result, 'editor': self.unique('TSchematicEditor')}

    def export_xml(self, path):
        if Path(path).exists():
            raise FileExistsError(path)
        self.menu('TSchematicEditor', [r'^文件|^File', r'^导出|^Export', r'^XML'])
        result=self.file_dialog(path)
        # This build advances native sine generators by 90 degrees on XML
        # export, after writing their original phase. Restore native controls
        # without another export so reading a circuit preserves its source.
        from waveforms import restore_after_xml_export
        restored=restore_after_xml_export(self,path)
        if restored:result['restored_sine_phases']=restored
        return result

    def new(self):
        self.menu('TSchematicEditor', [r'^文件|^File', r'^新建|^New'])
        self.wait(lambda: bool(re.search(r'未命名|Untitled|Noname', self.unique('TSchematicEditor')['title'],re.I)),
                  'Waiting for a new schematic')
        return self.unique('TSchematicEditor')

    def import_xml(self, path):
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        root=ET.parse(path).getroot()
        encrypted=[c for c in root.iter('component')
                   if any(p.get('encrypted')=='1' for p in c.findall('parameter'))]
        if encrypted:
            labels=[c.find('image/label').get('textroot') if c.find('image/label') is not None else c.get('id')
                    for c in encrypted]
            raise BridgeError('TINA-TI 9.3 XML import silently loses encrypted macros: '+str(labels)+
                              '. Import rejected before touching the application; preserve the original TSC and use native parameter editing.')
        # Native XML import already opens a new schematic tab. Calling New here
        # would leave extra empty documents which trigger save prompts on exit.
        self.menu('TSchematicEditor', [r'^文件|^File', r'^导入|^Import', r'^XML'])
        result = self.file_dialog(path, save=False)
        self.wait(lambda: self.unique('TSchematicEditor')['enabled'], 'Waiting for imported schematic')
        return {**result, 'editor': self.unique('TSchematicEditor')}

    def export_netlist(self, path):
        if Path(path).exists():
            raise FileExistsError(path)
        self.menu('TSchematicEditor', [r'^文件|^File', r'^导出|^Export', r'^网表|^Netlist', r'Tina'])
        return self.file_dialog(path)

    def save_as(self, path):
        if Path(path).exists():
            raise FileExistsError(path)
        self.menu('TSchematicEditor', [r'^文件|^File', r'^另存为|^Save as'])
        return self.file_dialog(path)

    def close(self):
        before = self.unique('TSchematicEditor')['title']
        self.menu('TSchematicEditor', [r'^文件|^File', r'^关闭\(|^Close\('])
        self.wait(lambda: self.unique('TSchematicEditor')['title'] != before,
                  'Waiting for document close; unsaved prompts are not auto-dismissed')
        return self.unique('TSchematicEditor')

    def exit_session(self):
        # Hold the process handle so a reused PID cannot be mistaken for completion.
        handle=native.K.OpenProcess(0x100000,False,self.pid)
        if not handle:
            raise OSError(C.get_last_error(),'Cannot wait on TINA process')
        native.K.WaitForSingleObject.argtypes=[C.c_void_p,C.c_uint32]
        native.K.WaitForSingleObject.restype=C.c_uint32
        try:
            self.menu('TSchematicEditor',[r'^文件|^File',r'^退出|^Exit'])
            self.wait(lambda: native.K.WaitForSingleObject(handle,0)==0,
                      'Waiting for TINA exit; unsaved prompts are not auto-dismissed')
        finally:
            native.K.CloseHandle(handle)
        return {'pid':self.pid,'exited':True}

    def documents(self):
        from accessibility import tab_names
        editor=self.unique('TSchematicEditor')
        candidates=[]
        for c in children(editor['hwnd']):
            if c['cls']!='TTabControl' or not c['visible']:
                continue
            names=tab_names(c['hwnd'])
            count=native.send(c['hwnd'],0x1304)
            selected=native.send(c['hwnd'],0x130b)
            if names and len(names)==count and 0<=selected<count and editor['title'].startswith(names[selected]):
                candidates.append({'hwnd':c['hwnd'],'count':count,'selected':selected,
                                   'documents':[{'index':i,'name':n} for i,n in enumerate(names)]})
        if len(candidates)!=1:
            raise BridgeError('Could not identify the schematic document tabs')
        return candidates[0]

    def select_document(self,index):
        if not self.unique('TSchematicEditor')['enabled']:
            raise BridgeError('Editor is blocked by a dialog')
        tabs=self.documents()
        if not 0<=index<tabs['count']:
            raise ValueError('Document index outside current list')
        native.send(tabs['hwnd'],0x1330,index)
        self.wait(lambda: self.documents()['selected']==index,'Waiting for active schematic tab')
        return {'editor':self.unique('TSchematicEditor'),**self.documents()}

    def start_transient(self, start=None, end=None, initial=None):
        previous = self.result_state()
        self.menu('TSchematicEditor',[r'^分析|^Analysis',r'^瞬时现象|^Transient'])
        dialog = self.wait(lambda: next((w for w in self.visible() if w['cls']=='TTranAnalDlg'),None),
                           'Waiting for transient settings')
        cs = [c for c in children(dialog['hwnd']) if c['visible']]
        edits = sorted([c for c in cs if c['cls']=='TFloatEdit'],key=lambda c:c['rect'][1])
        if len(edits)!=2:
            raise BridgeError('Unexpected transient time controls')
        for edit, value in zip(edits,(start,end)):
            if value is not None:
                text = C.create_unicode_buffer(str(value))
                native.send(edit['hwnd'],0x000c,0,C.addressof(text))
                if native.read_text(edit['hwnd'])!=str(value):
                    raise BridgeError('Time setting readback failed')
        radios = [c for c in cs if c['cls']=='TGroupButton']
        if initial is not None:
            pattern = {'zero':r'零初始|Zero initial','use':r'使用初始|Use initial',
                       'operating_point':r'计算操作点|Calculate operating'}[initial]
            match = [c for c in radios if re.search(pattern,c['title'],re.I)]
            if len(match)!=1:
                raise BridgeError('Initial-condition radio not found')
            U.PostMessageW(match[0]['hwnd'],0x00f5,0,0)
            self.wait(lambda: native.send(match[0]['hwnd'],0x00f0)==1,'Waiting for initial-condition selection')
        settings = {'start':native.read_text(edits[0]['hwnd']),'end':native.read_text(edits[1]['hwnd']),
                    'initial':next((c['title'] for c in radios if native.send(c['hwnd'],0x00f0)==1),None)}
        oks = [c for c in cs if c['cls'] in ('TBitBtn','Button') and re.match(r'^确定$|^OK$',c['title'],re.I)]
        if len(oks)!=1:
            raise BridgeError('Transient OK button not found')
        job = {'pid':self.pid,'exe':self.exe,'analysis':'transient','settings':settings,
               'editor':self.unique('TSchematicEditor')['title'],'previous_results':previous,
               'started_utc':datetime.now(timezone.utc).isoformat()}
        U.PostMessageW(oks[0]['hwnd'],0x00f5,0,0)
        return job

    def result_state(self):
        results=[{'hwnd':w['hwnd'],'title':w['title']} for w in self.visible() if w['cls']=='TDFWindow']
        if len(results)==1:
            pages=self.result_pages()
            results[0].update(count=pages['count'],selected=pages['selected'])
        return results

    def set_text(self, hwnd, value):
        text=C.create_unicode_buffer(str(value))
        native.send(hwnd,0x000c,0,C.addressof(text))
        if native.read_text(hwnd)!=str(value):
            raise BridgeError('Control text readback failed')

    def click_control(self, controls, pattern, checked=None):
        matches=[c for c in controls if c['cls'] in ('TBitBtn','TButton','Button','TCheckBox','TGroupButton')
                 and re.search(pattern,c['title'],re.I)]
        if len(matches)!=1:
            raise BridgeError(f'Control match ambiguous or absent: {pattern}')
        c=matches[0]
        if checked is None or native.send(c['hwnd'],0x00f0)!=int(checked):
            U.PostMessageW(c['hwnd'],0x00f5,0,0)
        if checked is not None:
            self.wait(lambda: native.send(c['hwnd'],0x00f0)==int(checked),'Waiting for control selection')

    def start_ac(self, start=None, end=None, points=None, sweep=None):
        previous=self.result_state()
        self.menu('TSchematicEditor',[r'^分析|^Analysis',r'^交流分析|^AC Analysis',r'^交流传输|^AC Transfer'])
        dialog=self.wait(lambda: next((w for w in self.visible() if w['cls']=='TACTransferDlg'),None),
                         'Waiting for AC settings')
        cs=[c for c in children(dialog['hwnd']) if c['visible']]
        fs=sorted([c for c in cs if c['cls']=='TFloatEdit'],key=lambda c:c['rect'][1])
        ns=[c for c in cs if c['cls']=='TIntEdit']
        if len(fs)!=2 or len(ns)!=1:
            raise BridgeError('Unexpected AC settings controls')
        for c,v in zip(fs+ns,(start,end,points)):
            if v is not None:
                self.set_text(c['hwnd'],v)
        if sweep is not None:
            self.click_control(cs,{'log':r'^对数|^Log','linear':r'^线性|^Linear'}[sweep],True)
        # One native page contains both gain and phase, with explicit signal names.
        for c in [c for c in cs if c['cls']=='TCheckBox']:
            want=bool(re.search(r'振幅和相位|Amplitude.*Phase',c['title'],re.I))
            self.click_control([c],r'.*',want)
        settings={'start':native.read_text(fs[0]['hwnd']),'end':native.read_text(fs[1]['hwnd']),
                  'points':native.read_text(ns[0]['hwnd']),
                  'sweep':next(c['title'] for c in cs if c['cls']=='TGroupButton' and native.send(c['hwnd'],0x00f0)==1),
                  'plots':[c['title'] for c in cs if c['cls']=='TCheckBox' and native.send(c['hwnd'],0x00f0)==1]}
        job={'pid':self.pid,'exe':self.exe,'analysis':'ac','settings':settings,
             'editor':self.unique('TSchematicEditor')['title'],'previous_results':previous,
             'started_utc':datetime.now(timezone.utc).isoformat()}
        self.click_control(cs,r'^确定$|^OK$')
        return job

    def start_dc(self, source, start=None, end=None, points=None):
        previous=self.result_state()
        self.menu('TSchematicEditor',[r'^分析|^Analysis',r'^直流分析|^DC Analysis',r'^直流传输|^DC Transfer'])
        dialog=self.wait(lambda: next((w for w in self.visible() if w['cls']=='TDCTransferDlg'),None),
                         'Waiting for DC sweep settings')
        cs=[c for c in children(dialog['hwnd']) if c['visible']]
        fs=sorted([c for c in cs if c['cls']=='TFloatEdit'],key=lambda c:c['rect'][1])
        ns=[c for c in cs if c['cls']=='TIntEdit']
        combos=[c for c in cs if c['cls']=='TComboBox']
        if len(fs)!=2 or len(ns)!=1 or len(combos)!=1:
            raise BridgeError('Unexpected DC settings controls')
        combo=combos[0]
        items=[]
        for i in range(native.send(combo['hwnd'],0x146)):
            length=native.send(combo['hwnd'],0x149,i)
            if not 0<=length<65536:
                raise BridgeError('Unexpected DC source label length')
            buf=C.create_unicode_buffer(length+1)
            native.send(combo['hwnd'],0x148,i,C.addressof(buf))
            items.append(buf.value)
        if source not in items:
            self.click_control(cs,r'^取消$|^Cancel$')
            raise ValueError(f'DC sweep source {source!r} not present; available={items}')
        index=items.index(source)
        native.send(combo['hwnd'],0x14e,index)
        native.send(combo['parent'],0x0111,combo['control_id'] | (1<<16),combo['hwnd'])
        if native.send(combo['hwnd'],0x147)!=index:
            raise BridgeError('DC source selection readback failed')
        for c,v in zip(fs+ns,(start,end,points)):
            if v is not None:
                self.set_text(c['hwnd'],v)
        self.click_control(cs,r'滞后|Hysteresis',False)
        settings={'source':source,'start':native.read_text(fs[0]['hwnd']),
                  'end':native.read_text(fs[1]['hwnd']),'points':native.read_text(ns[0]['hwnd']),
                  'hysteresis':False}
        job={'pid':self.pid,'exe':self.exe,'analysis':'dc','settings':settings,
             'editor':self.unique('TSchematicEditor')['title'],'previous_results':previous,
             'started_utc':datetime.now(timezone.utc).isoformat()}
        self.click_control(cs,r'^确定$|^OK$')
        return job

    def poll_run(self, job):
        if job['pid'] != self.pid:
            raise BridgeError('Job belongs to another process')
        place_windows(self.pid)
        ws = self.visible()
        calculation=self.analysis_state()
        editor=next((w for w in ws if w['cls']=='TSchematicEditor'),None)
        if editor and editor['title']!=job['editor']:
            return {'status':'attention','reason':'Active document changed during this job',
                    'expected_document':job['editor'],'actual_document':editor['title']}
        if calculation['running']:
            return {'status':'running','calculation':calculation}
        busy = [w for w in ws if w['cls']=='TPercentageDlg' or re.search(r'计算中|Calculating|Analysis in progress',w['title'],re.I)]
        if busy or any(w['cls'] in ('TTranAnalDlg','TACTransferDlg','TDCTransferDlg','TTempAnalDlg','TNoiseAnalDlg') for w in ws):
            return {'status':'running','windows':busy}
        if job['analysis']=='operating_point':
            table=[w for w in ws if w['cls']=='TTinaAskVoltagesDlg']
            blocking=[w for w in ws if w['cls'] not in ('TSchematicEditor','TTinaAskVoltagesDlg','TERCForm','TDFWindow')]
            if table and not blocking:
                return {'status':'succeeded','table':table[0],'analysis':'operating_point'}
            if not blocking:
                # A pre-existing plot window is not evidence of this DC-table job.
                return {'status':'cancelled' if job.get('cancel_requested_utc') else 'running',
                        'analysis':'operating_point'}
        errors = [w for w in ws if w['cls'] not in ('TSchematicEditor','TDFWindow')]
        if errors:
            return {'status':'attention','windows':self.diagnostics()}
        results = self.result_state()
        if job.get('cancel_requested_utc'):
            return {'status':'cancelled','results':results,'partial_results':bool(results and results!=job['previous_results'])}
        if results and results != job['previous_results']:
            return {'status':'succeeded','results':results}
        return {'status':'running','windows':ws}

    def close_operating_point_table(self):
        place_windows(self.pid,restore=True)
        tables=[w for w in self.visible() if w['cls']=='TTinaAskVoltagesDlg']
        for table in tables:
            self.click_control([c for c in children(table['hwnd']) if c['visible']],r'^取消$|^Cancel$')
        if tables:
            self.wait(lambda:not any(w['cls']=='TTinaAskVoltagesDlg' for w in self.visible()),'Closing previous result table')
            # The modeless table disappears before Delphi restores editor actions.
            def editor_ready():
                editor=self.unique('TSchematicEditor')
                entries=native.flatten_menu(menu_items(U.GetMenu(editor['hwnd'])))
                return editor['enabled'] and any(len(m['path'])==2 and
                    re.search(r'^文件|^File',m['path'][0],re.I) and
                    re.search(r'^打开\(|^Open\(',m['path'][1],re.I) and not m['flags']&3 for m in entries)
            self.wait(editor_ready,'Waiting for editor actions after result table closes')

    def start_operating_point(self):
        self.close_operating_point_table()
        job={'pid':self.pid,'exe':self.exe,'analysis':'operating_point','settings':{},
             'editor':self.unique('TSchematicEditor')['title'],'previous_results':[],
             'started_utc':datetime.now(timezone.utc).isoformat()}
        self.menu('TSchematicEditor',[r'^分析|^Analysis',r'^直流分析|^DC Analysis',r'^直流结果表|^Table of DC'])
        return job

    def export_operating_point(self,path):
        from accessibility import invoke_popup
        place_windows(self.pid,restore=True)
        table=self.unique('TTinaAskVoltagesDlg')
        controls=[c for c in children(table['hwnd']) if c['visible']]
        for c in controls:
            if c['cls']=='TCheckBox':
                self.click_control([c],r'.*',True)
        buttons=[c for c in controls if c['cls']=='TBitBtn' and not c['title']]
        if len(buttons)!=1:
            raise BridgeError('Expected native result-table file button')
        U.PostMessageW(buttons[0]['hwnd'],0xf5,0,0)
        self.wait(lambda:any(w['cls']=='#32768' for w in windows(self.pid)),'Opening result-table file menu')
        invoke_popup(self.pid,r'另存为|Save\s+as')
        return self.file_dialog(path)

    def analysis_state(self):
        # TINA hides its progress dialog when running in the background; the
        # application title still reports calculation and percent complete.
        app=[w for w in windows(self.pid) if w['cls']=='TApplication']
        titles=[w['title'] for w in app]
        return {'running':any(re.search(r'计算|Calculat|Analysis in progress',s,re.I) for s in titles),
                'titles':titles}

    def request_cancel(self, job):
        if job['pid']!=self.pid:
            raise BridgeError('Job belongs to another process')
        if not self.analysis_state()['running']:
            return {'requested':False,'status':self.poll_run(job),
                    'note':'No native calculation progress reported yet; if status is running, poll and retry cancellation. No command sent.'}
        dialogs=[w for w in windows(self.pid) if w['cls']=='TPercentageDlg']
        if len(dialogs)!=1:
            raise BridgeError('Native progress window unavailable; no cancellation command sent')
        U.PostMessageW(dialogs[0]['hwnd'],0x100,0x1B,1)
        U.PostMessageW(dialogs[0]['hwnd'],0x101,0x1B,0xC0000001)
        return {'requested':True,'method':'process-local Escape to native progress dialog'}

    def export_result(self, path):
        if 'FourierTHD' in self.unique('TDFWindow')['title']:
            raise ValueError('Native Fourier line spectra have no validated numeric text export; save the .tdr instead')
        from analysis_extra import export_text_diagrams
        files=export_text_diagrams(self,path)
        return {**files[0],'diagrams':files}

    def save_results(self, path):
        if Path(path).suffix.lower() != '.tdr':
            raise ValueError('This TINA version saves native result diagrams as .tdr; provide that extension')
        if Path(path).exists():
            raise FileExistsError(path)
        self.menu('TDFWindow',[r'^文件|^File',r'^另存为|^Save as'])
        return self.file_dialog(path)

    def open_results(self, path):
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        if not any(w['cls']=='TDFWindow' for w in self.visible()):
            self.menu('TSchematicEditor',[r'^工具|^Tools',r'^图表窗口|^Diagram Window'])
            self.wait(lambda: any(w['cls']=='TDFWindow' for w in self.visible()),'Waiting for diagram window')
        before=self.result_pages()['count']
        self.menu('TDFWindow',[r'^文件|^File',r'^打开\(|^Open\('])
        result = self.file_dialog(path,save=False)
        # TINA 9 appends result pages; it does not replace the diagram document
        # or automatically select the imported page.
        self.wait(lambda: self.result_pages()['count']>before,'Waiting for imported result pages')
        selection=self.select_result_page(before)
        return {**result,'first_imported_page':before,'selection':selection}

    def result_pages(self):
        w=self.unique('TDFWindow')
        tabs=[c for c in children(w['hwnd']) if c['visible'] and c['cls']=='TTabControl']
        if len(tabs)!=1:
            raise BridgeError('Result page control not found')
        return {'hwnd':tabs[0]['hwnd'],'count':native.send(tabs[0]['hwnd'],0x1304),
                'selected':native.send(tabs[0]['hwnd'],0x130b),'title':w['title']}

    def select_result_page(self,index):
        tab=self.result_pages()
        if not 0<=int(index)<tab['count']:
            raise ValueError('Result page index outside available range')
        # TCM_SETCURFOCUS changes selection and sends VCL change notifications;
        # TCM_SETCURSEL alone would change only the tab's visual selection.
        native.send(tab['hwnd'],0x1330,int(index))
        self.wait(lambda: self.result_pages()['selected']==int(index),'Waiting for result page selection')
        return self.result_pages()

    def status(self):
        return {'pid': self.pid, 'exe': self.exe, 'windows': self.visible(),'dialogs':self.diagnostics(),
                'calculation':self.analysis_state()}

    def diagnostics(self):
        dialogs=[w for w in self.visible() if w['cls'] not in ('TSchematicEditor','TDFWindow')]
        for w in dialogs:
            w['controls']=[]
            for c in children(w['hwnd']):
                if not c['visible']:
                    continue
                item={'class':c['cls'],'text':native.read_text(c['hwnd'])}
                if c['cls'] in ('TListBox','ListBox'):
                    count=native.send(c['hwnd'],0x18b)
                    if 0<=count<10000:
                        item['items']=[]
                        for i in range(count):
                            length=native.send(c['hwnd'],0x18a,i)
                            if not 0<=length<65536:
                                break
                            buf=C.create_unicode_buffer(length+1)
                            native.send(c['hwnd'],0x189,i,C.addressof(buf))
                            item['items'].append(buf.value)
                w['controls'].append(item)
        return dialogs

    def dismiss_errors(self):
        before=self.diagnostics()
        for cls,pattern in [('TMessageForm',r'^确定$|^OK$'),('TERCForm',r'^关闭$|^Close$')]:
            candidates=[w for w in self.visible() if w['cls']==cls and w['enabled']]
            for d in candidates:
                if cls=='TMessageForm' and not re.search(r'^错误$|^Error$',d['title'],re.I):
                    continue
                self.click_control(children(d['hwnd']),pattern)
                self.wait(lambda: not any(w['hwnd']==d['hwnd'] for w in self.visible()),'Waiting for error dismissal')
        return {'dismissed_from':before,'remaining':self.diagnostics()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', type=int)
    ap.add_argument('--exe', default=DEFAULT_EXE)
    ap.add_argument('operation', choices=['list-sessions','create-session','status','new','close','open','import-xml','export-xml','export-netlist','save-as','start-transient','start-ac','start-dc','poll-run','export-result','save-results','open-results','result-pages','select-result-page'])
    ap.add_argument('--path')
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--initial',choices=['zero','use','operating_point'])
    ap.add_argument('--job')
    ap.add_argument('--index',type=int)
    ap.add_argument('--points',type=int)
    ap.add_argument('--sweep',choices=['log','linear'])
    ap.add_argument('--source')
    args = ap.parse_args()
    start = time.monotonic()
    try:
        if args.operation in ('list-sessions','create-session'):
            result=list_sessions(args.exe) if args.operation=='list-sessions' else create_session(args.exe)
        else:
            if args.pid is None:
                raise ValueError('--pid is required for a process-bound operation')
            t = Tina(args.pid, args.exe)
            method = getattr(t, args.operation.replace('-', '_'))
            if args.operation in ('start-transient','start-ac','start-dc'):
                if args.operation=='start-transient':
                    result=method(args.start,args.end,args.initial)
                elif args.operation=='start-ac':
                    result=method(args.start,args.end,args.points,args.sweep)
                else:
                    result=method(args.source,args.start,args.end,args.points)
                if args.job:
                    Path(args.job).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            elif args.operation=='poll-run':
                result=method(json.loads(Path(args.job).read_text(encoding='utf-8')))
            elif args.operation=='select-result-page':
                result=method(args.index)
            else:
                result = method() if args.operation in ('status','new','close','result-pages') else method(args.path)
        print(json.dumps({'ok':True, 'operation':args.operation, 'result':result,
                          'elapsed_s':round(time.monotonic()-start,3)},ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'ok':False, 'operation':args.operation, 'error':type(exc).__name__,
                          'message':str(exc)},ensure_ascii=False))
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
