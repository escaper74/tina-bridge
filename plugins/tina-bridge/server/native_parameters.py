"""Edit external values in a native TSC, retaining encrypted factory macros.

Canvas messages are scoped to the selected process. Coordinates come from its
XML, native zoom and scroll position; the property title/value confirm identity.
No global cursor, keyboard, clipboard, screenshot, or model decoding is used.
"""
import ctypes as C
from ctypes import wintypes as W

from bridge import BridgeError
from schematic import xy
import tina_native as native
from win32_probe import U, children


class ScrollInfo(C.Structure):
    _fields_=[('cbSize',W.UINT),('fMask',W.UINT),('nMin',C.c_int),('nMax',C.c_int),
              ('nPage',W.UINT),('nPos',C.c_int),('nTrackPos',C.c_int)]


U.GetScrollInfo.argtypes=[W.HWND,C.c_int,C.POINTER(ScrollInfo)]
U.GetClientRect.argtypes=[W.HWND,C.POINTER(W.RECT)]


def visible_children(hwnd):
    return [c for c in children(hwnd) if c['visible']]


def one_control(hwnd, cls):
    matches=[c for c in visible_children(hwnd) if c['cls']==cls]
    if len(matches)!=1:
        raise BridgeError(f'Expected one visible {cls}; found {len(matches)}')
    return matches[0]


def key(hwnd, vk):
    native.send(hwnd,0x100,vk,1)
    native.send(hwnd,0x101,vk,0xC0000001)


def validate_operation(schematic, op):
    c=schematic.component(op['component'])
    if c.get('macrotype') is not None:
        raise PermissionError('Factory macro internals cannot be edited')
    from geometry import hit_point
    hit_point(c)
    if op['op']=='set_parameter':
        from device_models import SUPPORTED_TYPES
        if c.get('typeid') in SUPPORTED_TYPES:
            raise ValueError('Discrete devices use set_device_model or set_device_instance; select a catalog model and named public instance field')
        schematic.set_parameter(op['component'],op['index'],op['value'])
    elif op['op']=='set_pwl':
        p=c.find("parameter[@idx='1']/detail/parameter[@idx='0']")
        wave=c.find("parameter[@idx='1']")
        if c.get('typeid')!='16' or p is None or wave.get('value') not in ('分段线性','Piecewise linear'):
            raise ValueError('set_pwl requires an existing piecewise-linear voltage generator')
        if not op['text'].strip():
            raise ValueError('PWL text cannot be empty')
        p.text=op['text'].strip()
    else:
        raise ValueError(f'Unsupported native operation: {op["op"]}')
    return c


def canvas_point(tina, position):
    """Convert native drawing coordinates to this process's 100% viewport."""
    tina.menu('TSchematicEditor',[r'^视图|^View',r'^缩放|^Zoom',r'^普通|^Normal'])
    editor=tina.unique('TSchematicEditor')
    tina.wait(lambda:any(c['cls']=='TComboBox' and native.read_text(c['hwnd'])=='100%'
                         for c in visible_children(editor['hwnd'])),'Waiting for native 100% zoom')
    canvas=one_control(editor['hwnd'],'TSchEditBox')
    cx,cy=position
    r=W.RECT();U.GetClientRect(canvas['hwnd'],C.byref(r))
    coords=[]
    for axis,(position,size) in enumerate(((cx,r.right),(cy,r.bottom))):
        si=ScrollInfo(C.sizeof(ScrollInfo),0x17)
        if not U.GetScrollInfo(canvas['hwnd'],axis,C.byref(si)):
            raise BridgeError('Cannot read native canvas scroll state')
        if not 12<=position-si.nPos<size-12:
            target=max(si.nMin,min(position-size//2,si.nMax-int(si.nPage)+1))
            if not 0<=target<=65535:
                raise ValueError('Component is outside supported native scroll range')
            native.send(canvas['hwnd'],0x114+axis,4|(target<<16),0)
            U.GetScrollInfo(canvas['hwnd'],axis,C.byref(si))
        coords.append(position-si.nPos)
    if not (0<=coords[0]<r.right and 0<=coords[1]<r.bottom):
        raise BridgeError('Component is outside the native viewport')
    return canvas,coords[0]|(coords[1]<<16)


def select_component(tina, component):
    from geometry import hit_point
    canvas,lp=canvas_point(tina,hit_point(component))
    native.send(canvas['hwnd'],0x201,1,lp)
    native.send(canvas['hwnd'],0x202,0,lp)


def open_properties(tina, component):
    select_component(tina,component)
    tina.menu('TSchematicEditor',[r'^编辑|^Edit',r'^属性|^Properties'])
    dialog=tina.wait(lambda:next((w for w in tina.visible() if w['cls']=='TSchPropertyEditor'),None),
                     'Waiting for component properties')
    reference=component.find('image/label').get('textroot')
    if not dialog['title'].startswith(reference+' - '):
        raise BridgeError(f'Component selection mismatch: expected {reference}, got {dialog["title"]}')
    tina.wait(lambda:any(c['cls']=='TpiMaskEdit' for c in visible_children(dialog['hwnd'])),
              'Waiting for native property value editor')
    return dialog


def edit_parameter(tina, component, op):
    dialog=open_properties(tina,component)
    grid=one_control(dialog['hwnd'],'TAttributeGrid')
    parameters=component.findall('parameter')
    target_index=op['index'] if op['op']=='set_parameter' else 0
    target_row=next(i for i,p in enumerate(parameters) if p.get('idx')==str(target_index))
    for _ in range(target_row):
        key(grid['hwnd'],0x28)
    mask=one_control(dialog['hwnd'],'TpiMaskEdit')
    before=parameters[target_row].get('value')
    if native.read_text(mask['hwnd'])!=before:
        raise BridgeError('Native property value differs from fresh XML; inspect the open dialog')
    if op['op']=='set_parameter':
        tina.set_text(mask['hwnd'],op['value'])
    else:
        grid=one_control(dialog['hwnd'],'TAttributeGrid')
        key(grid['hwnd'],0x28)
        expected=component.find("parameter[@idx='1']").get('value')
        tina.wait(lambda:native.read_text(mask['hwnd'])==expected,'Waiting for waveform property row')
        editor=one_control(dialog['hwnd'],'TAttributeEditor')
        mask=one_control(editor['hwnd'],'TpiMaskEdit')
        x=(mask['rect'][2]+editor['rect'][2])//2-editor['rect'][0]
        y=(editor['rect'][3]-editor['rect'][1])//2
        # Mouse-up opens a nested modal loop, so dispatch it asynchronously.
        native.send(editor['hwnd'],0x201,1,x|(y<<16))
        U.PostMessageW(editor['hwnd'],0x202,0,x|(y<<16))
        signal=tina.wait(lambda:next((w for w in tina.visible() if w['cls']=='TSignalEditorDlg'),None),
                         'Waiting for signal editor')
        memo=one_control(signal['hwnd'],'TMemo')
        original=component.find("parameter[@idx='1']/detail/parameter[@idx='0']").text
        if native.read_text(memo['hwnd']).replace('\r','').strip()!=original.strip():
            raise BridgeError('Native PWL text differs from fresh XML')
        value=op['text'].replace('\r','').strip().replace('\n','\r\n')+'\r\n'
        tina.set_text(memo['hwnd'],value)
        tina.click_control(visible_children(signal['hwnd']),r'^确定$|^OK$')
        tina.wait(lambda:not any(w['cls']=='TSignalEditorDlg' for w in tina.visible()),'Waiting for PWL commit')
    tina.click_control(visible_children(dialog['hwnd']),r'^确定$|^OK$')
    tina.wait(lambda:not any(w['cls']=='TSchPropertyEditor' for w in tina.visible()),'Waiting for component commit')


def parameter_state(schematic):
    """Electrical parameters and placement; normalize XML pretty-print whitespace."""
    def norm(e):
        text='\n'.join(line.strip() for line in (e.text or '').strip().splitlines())
        return (e.tag,tuple(sorted(e.attrib.items())),text,tuple(norm(c) for c in e))
    return {c.get('id'):{'type':c.get('typeid'),'position':c.get('position'),
                       'orientation':c.get('orientation'),'mirrored':c.get('mirrored'),
                       'parameters':tuple(norm(p) for p in c.findall('parameter'))}
            for c in schematic.root.findall('circuit/component')}


def wire_state(schematic):
    return sorted(tuple(sorted(w.attrib.items())) for w in schematic.root.findall('circuit/wire'))


ANALYSIS_ROWS=[('0','temperature_C'),('1','dc_absolute_current_A'),('3','dc_absolute_voltage_V'),
               ('4','dc_relative_error'),('5','minimum_conductance_S'),('25','transient_relative_error'),
               ('27','transient_truncation_order'),('30','maximum_time_step_s'),
               ('37','subdivision_factor'),('39','maximum_saved_transient_points')]


def analysis_parameters(tina, parameters=None):
    """Read/set the ten parameters actually exposed by free TINA-TI 9.3."""
    parameters=parameters or {}
    if set(parameters)-{index for index,_ in ANALYSIS_ROWS}:
        raise ValueError(f'Native analysis parameters support these XML indices: {ANALYSIS_ROWS}')
    tina.menu('TSchematicEditor',[r'^分析|^Analysis',r'^设定分析参数|^Set Analysis Parameters'])
    d=tina.wait(lambda:next((w for w in tina.visible() if w['cls']=='TAnalParametersDlg'),None),
                'Waiting for native analysis parameters')
    grid=one_control(d['hwnd'],'TAttributeGrid')
    # The numeric column ends at the grid's right edge. Select its first row,
    # then use local row navigation so font/row height does not affect indexing.
    x=grid['rect'][2]-grid['rect'][0]-40;lp=x|(6<<16)
    native.send(grid['hwnd'],0x201,1,lp);native.send(grid['hwnd'],0x202,0,lp)
    mask=one_control(d['hwnd'],'TpiMaskEdit')
    actual={};changes=[]
    for row,(index,name) in enumerate(ANALYSIS_ROWS):
        if row:
            key(grid['hwnd'],0x28)
        value=native.read_text(mask['hwnd'])
        actual[index]={'name':name,'value':value}
        if index in parameters:
            tina.set_text(mask['hwnd'],parameters[index])
            changes.append({'index':index,'name':name,'before':value,'after':parameters[index]})
    tina.click_control(visible_children(d['hwnd']),r'^确定$|^OK$' if parameters else r'^取消$|^Cancel$')
    tina.wait(lambda:not any(w['cls']=='TAnalParametersDlg' for w in tina.visible()),'Waiting for analysis parameter completion')
    if parameters:
        actual=analysis_parameters(tina)['parameters']
        if any(actual[index]['value']!=value for index,value in parameters.items()):
            raise BridgeError('Native analysis parameter readback differs from requested values')
    return {'parameters':actual,'changes':changes,'scope':'active TINA process settings',
            'persistence':'Saved/exported circuit analysis metadata can remain older; apply these settings after opening a project and before running.'}
