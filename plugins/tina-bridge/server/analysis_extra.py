"""Additional native analyses available in TINA-TI 9.3.

The adapter uses the same job structure and native result exports as bridge.py.
All settings below are read back from the actual analysis dialog before launch.
"""
from datetime import datetime, timezone
from pathlib import Path
import ctypes as C
import re
import time

from bridge import BridgeError
from win32_probe import children,windows
import tina_native as native


NOISE_OUTPUTS={
    'output':r'^输出噪声|^Output noise',
    'input':r'^输入噪声|^Input noise',
    'total':r'^总噪声|^Total noise',
    'snr':r'^信号与噪声|^Signal.*noise',
}


def _dialog(tina,cls):
    d=tina.wait(lambda:next((w for w in tina.visible() if w['cls']==cls),None),
                'Waiting for '+cls)
    return d,[c for c in children(d['hwnd']) if c['visible']]


def _job(tina,kind,settings,previous):
    return {'pid':tina.pid,'exe':tina.exe,'analysis':kind,'settings':settings,
            'editor':tina.unique('TSchematicEditor')['title'],'previous_results':previous,
            'started_utc':datetime.now(timezone.utc).isoformat()}


def start_temperature(tina,start=None,end=None,points=None):
    """Native DC temperature sweep; temperatures are degrees Celsius."""
    previous=tina.result_state()
    tina.menu('TSchematicEditor',[r'^分析|^Analysis',r'^直流分析|^DC Analysis',r'^温度分析|^Temperature'])
    _,cs=_dialog(tina,'TTempAnalDlg')
    floats=sorted([c for c in cs if c['cls']=='TFloatEdit'],key=lambda c:c['rect'][1])
    integers=[c for c in cs if c['cls']=='TIntEdit']
    if len(floats)!=2 or len(integers)!=1:
        raise BridgeError('Unexpected native temperature-analysis controls')
    for control,value in zip(floats+integers,(start,end,points)):
        if value is not None:tina.set_text(control['hwnd'],value)
    settings={'start':native.read_text(floats[0]['hwnd']),'end':native.read_text(floats[1]['hwnd']),
              'points':native.read_text(integers[0]['hwnd']),'temperature_unit':'degC'}
    job=_job(tina,'temperature',settings,previous)
    tina.click_control(cs,r'^确定$|^OK$')
    return job


def start_noise(tina,start=None,end=None,points=None,signal_amplitude=None,outputs=None):
    """Native frequency-domain noise analysis; a native input source is required.

    Only output noise is exposed: this TINA version exports the same underlying
    output-noise array for input/total/SNR plots, not those displayed transforms.
    Voltage-output amplitude densities have units V/sqrt(Hz); the text format
    omits that unit. The exported '-phase' column is native auxiliary data and
    is not interpreted as a meaningful noise phase.
    """
    outputs=['output'] if outputs is None else list(outputs)
    if outputs!=['output']:
        raise ValueError('Only outputs=["output"] is supported for numeric noise export. TINA-TI 9.3 text exports do not preserve input/total/SNR plot transformations.')
    previous=tina.result_state()
    tina.menu('TSchematicEditor',[r'^分析|^Analysis',r'^噪声分析|^Noise'])
    _,cs=_dialog(tina,'TNoiseAnalDlg')
    floats=sorted([c for c in cs if c['cls']=='TFloatEdit'],key=lambda c:c['rect'][1])
    integers=[c for c in cs if c['cls']=='TIntEdit']
    if len(floats)!=3 or len(integers)!=1:
        raise BridgeError('Unexpected native noise-analysis controls')
    for control,value in zip(floats+integers,(start,end,signal_amplitude,points)):
        if value is not None:tina.set_text(control['hwnd'],value)
    captions={}
    for name,pattern in NOISE_OUTPUTS.items():
        matches=[c for c in cs if c['cls']=='TCheckBox' and re.search(pattern,c['title'],re.I)]
        if len(matches)!=1:raise BridgeError('Native noise output absent or ambiguous: '+name)
        tina.click_control(matches,r'.*',name in outputs)
        captions[name]=matches[0]['title']
    settings={'start':native.read_text(floats[0]['hwnd']),'end':native.read_text(floats[1]['hwnd']),
              'signal_amplitude':native.read_text(floats[2]['hwnd']),
              'points':native.read_text(integers[0]['hwnd']),
              'outputs':outputs,'native_plot_names':{n:captions[n] for n in outputs}}
    job=_job(tina,'noise',settings,previous)
    tina.click_control(cs,r'^确定$|^OK$')
    return job


def collect_pages(tina,job,directory):
    """Export all pages appended by a completed noise/temperature job.

    This must be called before another analysis changes the same diagram.
    The .tdr is the native complete diagram document, which may include older
    pages. Only the pages introduced by this job are returned under pages.
    """
    from results import read_results,summarize
    from accessibility import tab_names
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    current=tina.result_pages()
    previous=job.get('previous_results',[])
    first=previous[0].get('count',0) if previous else 0
    if first>=current['count']:
        raise BridgeError('No new diagram pages for this analysis')
    pages=[]
    captions=tab_names(current['hwnd'])
    for index in range(first,current['count']):
        tina.select_result_page(index)
        path=directory/f'result-page-{index}.txt'
        files=export_text_diagrams(tina,path)
        data=read_output_noise(path) if job['analysis']=='noise' else read_results(path)
        entry={'index':index,'caption':captions[index],'text_path':str(path),'data':summarize(data),
               'text_diagrams':files,'settings':job['settings'],
               'axis_unit':{'noise':'Hz','temperature':'degC'}.get(job['analysis'])}
        if job['analysis']=='noise':
            entry['data'].update(quantity=data['quantity'],unit_note=data['unit_note'],
                                 auxiliary_native_columns=data['auxiliary_native_columns'])
        pages.append(entry)
    tina.select_result_page(current['selected'])
    native_path=directory/'result.tdr';tina.save_results(native_path)
    active=next((p for p in pages if p['index']==current['selected']),pages[-1])
    return {'native_path':str(native_path),'pages':pages,
            'text_path':active['text_path'],'data':active['data'],
            'native_document_scope':'All native diagram pages; exported text pages belong to this job only.'}


def read_output_noise(path):
    """Read verified output-noise amplitude densities; retain raw auxiliary columns on disk."""
    from results import read_results
    raw=read_results(path)
    signals=[s for s in raw['signals'] if s['name'].endswith('-abs')]
    if not signals:raise ValueError('No output-noise amplitude column found')
    return {**raw,'signals':signals,'quantity':'output_noise_amplitude_spectral_density',
            'axis_unit':'Hz',
            'unit_note':'The native text omits amplitude units. For voltage outputs these values are V/sqrt(Hz); other output types are not unit-validated.',
            'auxiliary_native_columns':[s['name'] for s in raw['signals'] if s not in signals]}


def export_text_diagrams(tina,path):
    """Complete every Save diagram dialog belonging to one native text export.

    A page containing several coordinate diagrams (e.g. Fourier amplitude and
    phase) prompts once per diagram. Each file is preserved and returned; its
    format/content still needs analysis-specific validation before numeric use.
    """
    path=Path(path).resolve()
    if path.exists():raise FileExistsError(path)
    tina.menu('TDFWindow',[r'^文件|^File',r'^导出|^Export',r'^作为文本|^As text'])
    files=[]
    while True:
        target=path if not files else path.with_name(path.stem+f'-diagram-{len(files)+1}'+path.suffix)
        files.append(tina.file_dialog(target))
        stable_since=None
        def next_state():
            nonlocal stable_since
            ws=tina.visible()
            dialogs=[w for w in ws if w['cls']=='#32770' and re.search(r'^Save diagram',w['title'],re.I)]
            if dialogs:return 'more'
            editor=next((w for w in ws if w['cls']=='TDFWindow'),None)
            if editor and editor['enabled']:
                stable_since=time.monotonic() if stable_since is None else stable_since
                if time.monotonic()-stable_since>=.4:return 'done'
            else:stable_since=None
            return None
        if tina.wait(next_state,'Waiting for subsequent text-export diagrams')=='done':return files


def _combo_items(control):
    items=[]
    for index in range(native.send(control['hwnd'],0x146)):
        length=native.send(control['hwnd'],0x149,index)
        buf=C.create_unicode_buffer(length+1)
        native.send(control['hwnd'],0x148,index,C.addressof(buf));items.append(buf.value)
    return items


def _select_combo(tina,control,value):
    items=_combo_items(control)
    if str(value) not in items:raise ValueError('Choose a native item from '+str(items))
    index=items.index(str(value));native.send(control['hwnd'],0x14e,index)
    native.send(control['parent'],0x111,(1<<16)|(control['control_id']&0xffff),control['hwnd'])
    if native.send(control['hwnd'],0x147)!=index:raise BridgeError('Native combo readback failed')


def start_fourier(tina,signal,start=None,fundamental=None,samples=4096,harmonics=16,initial=None):
    """Calculate a native Fourier-series plot. Numeric text export is not supported.

    TINA computes one period from start and fundamental. The native plot/TDR is
    the deliverable; its line objects are not represented by text-export arrays.
    """
    if not 2<=harmonics<=16:raise ValueError('Native harmonic count is 2..16')
    previous=tina.result_state()
    tina.menu('TSchematicEditor',[r'^分析|^Analysis',r'^傅立叶分析|^Fourier',r'^傅立叶级数|^Fourier Series'])
    _,cs=_dialog(tina,'THarmonicDistorsionDlg')
    floats=sorted([c for c in cs if c['cls']=='TFloatEdit'],key=lambda c:c['rect'][1])
    combos=sorted([c for c in cs if c['cls']=='TComboBox'],key=lambda c:c['rect'][1])
    spins=[c for c in cs if c['cls']=='TSpinEdit']
    if len(floats)!=2 or len(combos)!=3 or len(spins)!=1:raise BridgeError('Unexpected native Fourier controls')
    for control,value in zip(floats,(start,fundamental)):
        if value is not None:tina.set_text(control['hwnd'],value)
    _select_combo(tina,combos[0],samples)
    _select_combo(tina,combos[1],'D * cos(kwt + fi)')
    _select_combo(tina,combos[2],signal)
    tina.set_text(spins[0]['hwnd'],harmonics)
    if initial is not None:
        pattern={'zero':r'^零初始|^Zero initial','use':r'^使用初始|^Use initial',
                 'operating_point':r'^计算操作点|^Calculate operating'}[initial]
        tina.click_control(cs,pattern,True)
    settings={'start':native.read_text(floats[0]['hwnd']),'fundamental':native.read_text(floats[1]['hwnd']),
              'samples':native.read_text(combos[0]['hwnd']),'format':native.read_text(combos[1]['hwnd']),
              'signal':native.read_text(combos[2]['hwnd']),'harmonics':native.read_text(spins[0]['hwnd']),
              'initial':next(c['title'] for c in cs if c['cls']=='TGroupButton' and native.send(c['hwnd'],0xf0)==1)}
    job=_job(tina,'fourier',settings,previous)
    job['native_only']=True
    tina.click_control([c for c in cs if c['cls']=='TBitBtn'],r'^计算\(|^Calculate')
    # Fourier keeps its Draw button enabled and its application title unchanged
    # while solving. The progress window initially exists hidden; wait for that
    # native acknowledgement (or a completed new transient page) after posting.
    tina.wait(lambda:any(w['cls']=='TPercentageDlg' for w in windows(tina.pid)) or
              tina.result_state()!=previous,'Waiting for Fourier calculation to start')
    return job


def poll_fourier(tina,job):
    """Finish the native calculation by drawing the spectrum once it is ready."""
    if job['pid']!=tina.pid:raise BridgeError('Job belongs to another process')
    ws=tina.visible()
    editor=next((w for w in ws if w['cls']=='TSchematicEditor'),None)
    if editor and editor['title']!=job['editor']:
        return {'status':'attention','reason':'Active document changed during Fourier analysis'}
    if tina.analysis_state()['running'] or any(w['cls']=='TPercentageDlg' for w in ws+windows(tina.pid)):
        return {'status':'running','calculation':tina.analysis_state()}
    dialogs=[w for w in ws if w['cls']=='THarmonicDistorsionDlg']
    errors=[w for w in ws if w['cls'] not in ('TSchematicEditor','TDFWindow','THarmonicDistorsionDlg')]
    if errors:return {'status':'attention','windows':tina.diagnostics()}
    if job.get('cancel_requested_utc'):
        if dialogs:
            tina.click_control(children(dialogs[0]['hwnd']),r'^取消$|^Cancel$')
            tina.wait(lambda:not any(w['cls']=='THarmonicDistorsionDlg' for w in tina.visible()),'Closing cancelled Fourier table')
        return {'status':'cancelled','native_only':True}
    if dialogs:
        cs=[c for c in children(dialogs[0]['hwnd']) if c['visible']]
        draw=[c for c in cs if c['cls']=='TBitBtn' and re.search(r'^绘制|^Draw',c['title'],re.I)]
        if len(draw)!=1 or not draw[0]['enabled']:return {'status':'running'}
        tina.click_control(draw,r'.*')
        tina.wait(lambda:not any(w['cls']=='THarmonicDistorsionDlg' for w in tina.visible()),'Drawing Fourier spectrum')
    state=tina.poll_run(job)
    # The hidden calculation window can disappear just before the Fourier
    # table is shown again. A new TR page alone is not the Fourier result.
    if state['status']=='attention' and all(w['cls']=='THarmonicDistorsionDlg' for w in state.get('windows',[])):
        return {'status':'running'}
    if state['status']=='succeeded' and not any('FourierTHD' in w['title'] for w in state.get('results',[])):
        return {'status':'running'}
    return state


def request_cancel_fourier(tina,job):
    """Request native cancellation even when Fourier does not change the app title."""
    if job['pid']!=tina.pid:raise BridgeError('Job belongs to another process')
    progress=[w for w in windows(tina.pid) if w['cls']=='TPercentageDlg']
    if len(progress)==1:
        native.U.PostMessageW(progress[0]['hwnd'],0x100,0x1B,1)
        native.U.PostMessageW(progress[0]['hwnd'],0x101,0x1B,0xC0000001)
        return {'requested':True,'method':'process-local Escape to native Fourier progress dialog'}
    table=[w for w in tina.visible() if w['cls']=='THarmonicDistorsionDlg']
    if table:
        tina.click_control(children(table[0]['hwnd']),r'^取消$|^Cancel$')
        return {'requested':True,'method':'close pending native Fourier table before drawing'}
    return {'requested':False,'note':'No Fourier calculation or pending table to cancel'}


def collect_fourier(tina,job,directory):
    """Preserve the native line-spectrum document without claiming placeholder text as coefficients."""
    from accessibility import tab_names
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    page=tina.result_pages();captions=tab_names(page['hwnd'])
    path=directory/'result.tdr';tina.save_results(path)
    return {'native_path':str(path),'page':page,'caption':captions[page['selected']],
            'native_only':True,'numeric_export_supported':False,
            'native_document_scope':'All native diagram pages. page.selected identifies this Fourier spectrum within the saved document.',
            'numeric_export_limitation':'Native Fourier bars are diagram line objects. Text export returns coordinate placeholders, not the harmonic table. The TDR retains the actual amplitude/phase spectrum.',
            'settings':job['settings']}
