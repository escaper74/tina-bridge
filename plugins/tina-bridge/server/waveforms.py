"""Set native voltage-generator waveforms in the validated TINA-TI 9.3 UI.

Signal icons are non-windowed controls in the dialog's top panel. Their ten
slots were inspected in the installed UI; parameters and final mode are checked
against native XML. No screenshots, global mouse/keyboard input, or XML import
are used by this module.
"""
import copy
import hashlib
from pathlib import Path
import shutil

from circuit_view import scalar_value


# Native parameter order, observed in TSignalEditorDlg and exported XML.
WAVEFORMS={
    'sine':{'slot':2,'native_names':('正弦波','Sine'),
            'fields':('amplitude','frequency','phase'),
            'units':('V','Hz','deg')},
    'square':{'slot':4,'native_names':('方波','Square'),
              'fields':('amplitude','frequency','rise_fall'),
              'units':('V','Hz','s')},
    'pulse':{'slot':0,'native_names':('脉冲','Pulse'),
             'fields':('amplitude','width'),'units':('V','s')},
    'pwl':{'slot':7,'native_names':('分段线性','Piecewise linear'),
           'fields':('text',),'units':('time/value pairs in s and V',)},
}


def catalog():
    return {'component_type':'voltage_generator','type_id':'16','version':'9.3.150.328SF-TI',
            'waveforms':{name:{'parameters':dict(zip(spec['fields'],spec['units']))}
                         for name,spec in WAVEFORMS.items()},
            'semantics':{'sine':'DC level + A*sin(2*pi*f*t + phase*pi/180)',
                         'square':'Bipolar +/- amplitude about DC level; native 50% square wave. rise_fall is the native tau: a full -A to +A transition spans 2*tau',
                         'pulse':'Single positive-duration pulse from t=0; not a periodic PWM generator',
                         'pwl':'PSpice time/value pairs; no repetition extension is exposed'},
            'dc_level':'Optional generator DC level in V; preserved when omitted'}


def _text(value):
    return '\n'.join(line.strip() for line in str(value).replace('\r','').splitlines() if line.strip())


def validate_request(waveform,parameters,dc_level=None):
    """Validate this small numeric API before opening any native dialog."""
    if waveform not in WAVEFORMS:raise ValueError('Supported waveforms: '+', '.join(WAVEFORMS))
    spec=WAVEFORMS[waveform]
    if not isinstance(parameters,dict) or set(parameters)!=set(spec['fields']):
        raise ValueError(f'{waveform} requires exactly these parameters: {spec["fields"]}')
    values={key:str(value).strip() for key,value in parameters.items()}
    if waveform=='pwl':
        values['text']=_text(values['text']);tokens=values['text'].split()
        numbers=[scalar_value(token) for token in tokens]
        if len(tokens)<4 or len(tokens)%2 or any(n is None for n in numbers):
            raise ValueError('PWL text requires at least two numeric time/value pairs; SI suffixes are allowed')
        times=numbers[::2]
        if times[0]<0 or any(b<a for a,b in zip(times,times[1:])):
            raise ValueError('PWL times must be nonnegative and nondecreasing')
    else:
        numeric={key:scalar_value(value) for key,value in values.items()}
        if any(value is None for value in numeric.values()):
            raise ValueError('Waveform parameters must be finite numeric literals; SI suffixes are allowed')
        for key in ('frequency','width','rise_fall'):
            if key in numeric and numeric[key]<=0:raise ValueError(key+' must be positive')
    if dc_level is not None:
        dc_level=str(dc_level).strip()
        if scalar_value(dc_level) is None:raise ValueError('dc_level must be a finite numeric literal')
    return {'waveform':waveform,'parameters':values,'dc_level':dc_level}


def state(component):
    """Read the known waveform fields from an actual exported generator."""
    if component.get('typeid')!='16' or component.get('macrotype') is not None:
        raise ValueError('Waveform editing currently supports native voltage generators (type 16)')
    wave=component.find("parameter[@idx='1']")
    name=wave.get('value') if wave is not None else None
    kind=next((k for k,v in WAVEFORMS.items() if name in v['native_names']),None)
    result={'waveform':kind,'native_name':name,
            'dc_level':component.find("parameter[@idx='0']").get('value'),'parameters':{}}
    if kind is None:return result
    detail=wave.find('detail')
    if detail is None or detail.get('type')!=name:raise ValueError('Native waveform detail does not match its selected type')
    fields=WAVEFORMS[kind]['fields'];entries=detail.findall('parameter')
    if {p.get('idx') for p in entries}!={str(i) for i in range(len(fields))}:
        raise ValueError('Unexpected native waveform parameter layout')
    for i,field in enumerate(fields):
        p=detail.find(f"parameter[@idx='{i}']")
        result['parameters'][field]=_text(p.text or '') if field=='text' else p.get('value')
    return result


def matches(actual,request,original_dc=None):
    if actual['waveform']!=request['waveform']:return False
    def equal(a,b):
        return a==b or (scalar_value(a) is not None and scalar_value(a)==scalar_value(b))
    for key,value in request['parameters'].items():
        found=actual['parameters'].get(key)
        if not (_text(found)==_text(value) if key=='text' else equal(found,value)):return False
    wanted=request['dc_level'] if request['dc_level'] is not None else original_dc
    return wanted is None or equal(actual['dc_level'],wanted)


def configure(tina,component,waveform,parameters,dc_level=None):
    """Set controls on the current document. Caller exports XML to verify/save."""
    from native_parameters import open_properties,one_control,visible_children,key
    import tina_native as native
    from win32_probe import U
    request=validate_request(waveform,parameters,dc_level);before=state(component)
    d=open_properties(tina,component);grid=one_control(d['hwnd'],'TAttributeGrid')
    mask=one_control(d['hwnd'],'TpiMaskEdit')
    if native.read_text(mask['hwnd'])!=before['dc_level']:
        raise RuntimeError('Fresh XML and native generator DC level differ')
    if request['dc_level'] is not None:tina.set_text(mask['hwnd'],request['dc_level'])
    key(grid['hwnd'],0x28)
    tina.wait(lambda:native.read_text(mask['hwnd'])==before['native_name'],'Waiting for native waveform property')
    editor=one_control(d['hwnd'],'TAttributeEditor');mask=one_control(editor['hwnd'],'TpiMaskEdit')
    x=(mask['rect'][2]+editor['rect'][2])//2-editor['rect'][0]
    y=(editor['rect'][3]-editor['rect'][1])//2
    native.send(editor['hwnd'],0x201,1,x|(y<<16));U.PostMessageW(editor['hwnd'],0x202,0,x|(y<<16))
    signal=tina.wait(lambda:next((w for w in tina.visible() if w['cls']=='TSignalEditorDlg'),None),'Waiting for signal editor')
    panels=[c for c in visible_children(signal['hwnd']) if c['cls']=='TPanel' and c['parent']==signal['hwnd']]
    panel=min(panels,key=lambda c:c['rect'][1]);slot=WAVEFORMS[waveform]['slot']
    x=round((panel['rect'][2]-panel['rect'][0])*(slot+.5)/10)
    y=(panel['rect'][3]-panel['rect'][1])//2
    native.send(panel['hwnd'],0x201,1,x|(y<<16));native.send(panel['hwnd'],0x202,0,x|(y<<16))
    if waveform=='pwl':
        memo=one_control(signal['hwnd'],'TMemo')
        tina.set_text(memo['hwnd'],request['parameters']['text'].replace('\n','\r\n')+'\r\n')
    else:
        grid=one_control(signal['hwnd'],'TAttributeGrid')
        x=grid['rect'][2]-grid['rect'][0]-40
        native.send(grid['hwnd'],0x201,1,x|(6<<16));native.send(grid['hwnd'],0x202,0,x|(6<<16))
        mask=one_control(signal['hwnd'],'TpiMaskEdit')
        for i,field in enumerate(WAVEFORMS[waveform]['fields']):
            if i:key(grid['hwnd'],0x28)
            tina.set_text(mask['hwnd'],request['parameters'][field])
    for dialog,cls in ((signal,'TSignalEditorDlg'),(d,'TSchPropertyEditor')):
        tina.click_control(visible_children(dialog['hwnd']),r'^确定$|^OK$')
        tina.wait(lambda:not any(w['cls']==cls for w in tina.visible()),'Waiting for waveform commit')
    return request


def inspect_controls(tina,component):
    """Read current native fields without XML export or a committed edit."""
    from native_parameters import open_properties,one_control,visible_children,key
    import tina_native as native
    from win32_probe import U
    state(component)
    d=open_properties(tina,component);grid=one_control(d['hwnd'],'TAttributeGrid')
    mask=one_control(d['hwnd'],'TpiMaskEdit');dc=native.read_text(mask['hwnd'])
    key(grid['hwnd'],0x28);name=native.read_text(mask['hwnd'])
    kind=next((k for k,v in WAVEFORMS.items() if name in v['native_names']),None)
    if kind is None:
        tina.click_control(visible_children(d['hwnd']),r'^取消$|^Cancel$')
        raise ValueError('Native waveform inspection supports '+', '.join(WAVEFORMS))
    editor=one_control(d['hwnd'],'TAttributeEditor');mask=one_control(editor['hwnd'],'TpiMaskEdit')
    x=(mask['rect'][2]+editor['rect'][2])//2-editor['rect'][0];y=(editor['rect'][3]-editor['rect'][1])//2
    native.send(editor['hwnd'],0x201,1,x|(y<<16));U.PostMessageW(editor['hwnd'],0x202,0,x|(y<<16))
    signal=tina.wait(lambda:next((w for w in tina.visible() if w['cls']=='TSignalEditorDlg'),None),'Waiting for signal editor')
    values={}
    if kind=='pwl':values['text']=_text(native.read_text(one_control(signal['hwnd'],'TMemo')['hwnd']))
    else:
        grid=one_control(signal['hwnd'],'TAttributeGrid');x=grid['rect'][2]-grid['rect'][0]-40
        native.send(grid['hwnd'],0x201,1,x|(6<<16));native.send(grid['hwnd'],0x202,0,x|(6<<16))
        mask=one_control(signal['hwnd'],'TpiMaskEdit')
        for i,field in enumerate(WAVEFORMS[kind]['fields']):
            if i:key(grid['hwnd'],0x28)
            values[field]=native.read_text(mask['hwnd'])
    for dialog,cls in ((signal,'TSignalEditorDlg'),(d,'TSchPropertyEditor')):
        tina.click_control(visible_children(dialog['hwnd']),r'^取消$|^Cancel$')
        tina.wait(lambda:not any(w['cls']==cls for w in tina.visible()),'Waiting for waveform inspection close')
    return {'waveform':kind,'native_name':name,'dc_level':dc,'parameters':values}


def restore_after_xml_export(tina,path):
    """Undo the observed +90 deg sine-phase mutation in TINA 9.3 XML export.

    Only top-level native voltage generators are considered; factory macros and
    their internal subcircuits are never traversed or edited. The exported XML
    contains the phase from before the export; the running
    document has already advanced it. Restore via native controls, without a
    second export. Call immediately after the XML file has finished writing.
    """
    from schematic import Schematic
    schematic=Schematic(path);restored=[]
    for component in schematic.root.findall('circuit/component'):
        if component.get('typeid')!='16' or component.get('macrotype') is not None:continue
        saved=state(component)
        if saved['waveform']!='sine':continue
        configure(tina,component,'sine',saved['parameters'])
        actual=inspect_controls(tina,component)
        request={'waveform':'sine','parameters':saved['parameters'],'dc_level':saved['dc_level']}
        if not matches(actual,request):raise RuntimeError('Native sine phase was not restored after XML export: '+str(actual))
        restored.append({'component':component.find('image/label').get('textroot'),
                         'phase':saved['parameters']['phase'],'native_readback':actual})
    return restored


def edit(pid,source_tsc,component,waveform,parameters,save_path,dc_level=None):
    """Configure a private native copy, check its exported XML, then save a TSC."""
    from bridge import Tina
    from native_parameters import parameter_state,wire_state
    from schematic import Schematic
    from service import new_artifacts,read_circuit,write_json
    request=validate_request(waveform,parameters,dc_level)
    source=Path(source_tsc).resolve();target=Path(save_path).resolve()
    if not source.is_file() or source.suffix.lower()!='.tsc':raise ValueError('source_tsc must be an existing native TSC')
    if target.exists():raise FileExistsError(target)
    if target.suffix.lower()!='.tsc' or not target.parent.is_dir():raise ValueError('save_path must be a new TSC in an existing directory')
    folder=new_artifacts('waveform');working=folder/'waveform-working.TSC'
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest();shutil.copy2(source,working)
    tina=Tina(pid);tina.open(working)
    before=read_circuit(pid,include_connectivity=False);old=Schematic(before['source'])
    c=old.component(component);original=state(c)
    configure(tina,c,waveform,parameters,dc_level)
    after=read_circuit(pid,include_connectivity=False);actual=Schematic(after['source']);changed=actual.component(c.get('id'))
    observed=state(changed);expected=Schematic(before['source']);allowed=expected.component(c.get('id'))
    # Only the waveform detail and optional DC scalar may change. Preserve every
    # other component field, topology and opaque factory-model hash.
    for index in ('0','1'):
        previous=allowed.find(f"parameter[@idx='{index}']")
        allowed.remove(previous);allowed.insert(int(index),copy.deepcopy(changed.find(f"parameter[@idx='{index}']")))
    checks={'requested_waveform':matches(observed,request,original['dc_level']),
            'other_parameters_and_components_unchanged':parameter_state(expected)==parameter_state(actual),
            'wires_unchanged':wire_state(old)==wire_state(actual),
            'factory_models_unchanged':old.model_hashes()==actual.model_hashes(),
            'source_file_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==source_hash}
    record={'component':component,'request':request,'before':original,'actual':observed,'checks':checks,
            'source_tsc':str(source),'source_sha256':source_hash,'before_snapshot':before['snapshot'],'after_snapshot':after['snapshot']}
    write_json(folder/'verification.json',record)
    if not all(checks.values()):raise RuntimeError('Native waveform readback differs; inspect '+str(folder/'verification.json'))
    result={'saved':tina.save_as(target),'checks':checks,'waveform':observed,'circuit':after,
            'verification':str(folder/'verification.json'),'route':'native signal-editor controls; no XML import'}
    write_json(folder/'receipt.json',result);return result
