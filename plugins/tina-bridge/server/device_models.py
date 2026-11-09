"""Choose existing native discrete-device catalog entries; never edit their model data."""
import ctypes as C
import math
import time
from native_parameters import open_properties, one_control, visible_children, key
import tina_native as native
from win32_probe import U, children


SUPPORTED_TYPES = {'23':'diode', '64':'Schottky diode', '87':'NPN', '88':'PNP',
                   '89':'NMOS enhancement', '90':'PMOS enhancement'}


def _supported(component):
    if component.get('macrotype') is not None or component.get('typeid') not in SUPPORTED_TYPES:
        raise ValueError('Native catalog selection supports discrete D/Schottky/NPN/PNP/NMOS/PMOS only')
    return component.get('typeid')


def _property(tina, component):
    _supported(component)
    dialog = open_properties(tina,component)
    expected = component.find("parameter[@idx='0']").get('value')
    tina.wait(lambda:any(c['visible'] and c['cls']=='TpiMaskEdit' and native.read_text(c['hwnd'])==expected
                         for c in children(dialog['hwnd'])),
              'Waiting for the native initial model row to finish rendering')
    return dialog


def _catalog(tina, prop):
    editor = one_control(prop['hwnd'],'TAttributeEditor')
    mask = one_control(editor['hwnd'],'TpiMaskEdit')
    x = (mask['rect'][2]+editor['rect'][2])//2-editor['rect'][0]
    y = (editor['rect'][3]-editor['rect'][1])//2
    native.send(editor['hwnd'],0x201,1,x|(y<<16))
    U.PostMessageW(editor['hwnd'],0x202,0,x|(y<<16))
    dialog = tina.wait(lambda:next((w for w in tina.visible() if w['cls']=='TTlrCatalogEditorDlg'),None),
                       'Opening native discrete-device catalog')
    tina.wait(lambda:any(c['visible'] and c['cls']=='TListBox' and native.send(c['hwnd'],0x18b)>0
                         for c in children(dialog['hwnd'])), 'Waiting for native model catalog entries')
    return dialog


def _items(control):
    combo = control['cls']=='TComboBox'
    hwnd = control['hwnd']
    count = native.send(hwnd,0x146 if combo else 0x18b)
    selected = native.send(hwnd,0x147 if combo else 0x188)
    values = []
    for index in range(count):
        length = native.send(hwnd,0x149 if combo else 0x18a,index)
        buffer = C.create_unicode_buffer(length+1)
        native.send(hwnd,0x148 if combo else 0x189,index,C.addressof(buffer))
        values.append(buffer.value)
    return {'selected':values[selected] if 0<=selected<count else None,
            'selected_index':selected, 'items':values}


def _catalog_state(dialog):
    controls = [c for c in children(dialog['hwnd']) if c['visible']]
    combos = sorted((c for c in controls if c['cls']=='TComboBox'),key=lambda c:c['rect'][1])
    if len(combos)!=2:
        raise ValueError('Expected native library and model-family selectors')
    listing = one_control(dialog['hwnd'],'TListBox')
    return {'library':_items(combos[0]),'family':_items(combos[1]),'models':_items(listing)},listing


def _close(tina, dialog, commit=False):
    tina.click_control(visible_children(dialog['hwnd']),r'^确定$|^OK$' if commit else r'^取消$|^Cancel$')
    tina.wait(lambda:not any(w['hwnd']==dialog['hwnd'] for w in tina.visible()),'Closing native device dialog')


def read_models(tina, component, query='', limit=50):
    """Read this device's currently selected library/family; cancel both dialogs."""
    if not 1<=limit<=1000:
        raise ValueError('limit must be between 1 and 1000')
    prop = _property(tina,component)
    dialog = _catalog(tina,prop)
    state,_ = _catalog_state(dialog)
    _close(tina,dialog)
    _close(tina,prop)
    matched = [name for name in state['models']['items'] if query.casefold() in name.casefold()]
    return {'component':component.find('image/label').get('textroot'),
            'type_id':component.get('typeid'), 'library':state['library']['selected'],
            'family':state['family']['selected'], 'current_model':state['models']['selected'],
            'models':matched[:limit], 'matching_count':len(matched),
            'catalog_count':len(state['models']['items']),
            'instance_parameters':public_fields(component),
            'scope':'Existing entries in the current native library/family; model parameters are not edited'}


def select_model(tina, component, model):
    """Commit one exact existing entry in the current native library/family."""
    prop = _property(tina,component)
    dialog = _catalog(tina,prop)
    state,listing = _catalog_state(dialog)
    matches = [i for i,name in enumerate(state['models']['items']) if name.casefold()==model.casefold()]
    if len(matches)!=1:
        _close(tina,dialog)
        _close(tina,prop)
        raise ValueError('Choose one existing model in this device library/family using read_models')
    index = matches[0]
    actual_name = state['models']['items'][index]
    # LB_SETCURSEL alone updates the highlight, but not TINA's chosen model.
    # Native key events execute its selection handler without foreground input.
    key(listing['hwnd'],0x24)
    for _ in range(index):
        key(listing['hwnd'],0x28)
    if _items(listing)['selected']!=actual_name:
        raise RuntimeError('Native catalog selection did not reach the requested model')
    # The list highlight moves synchronously; TINA loads the chosen catalog
    # record on a deferred UI cycle. Closing immediately can keep the old model.
    time.sleep(.5)
    _close(tina,dialog,commit=True)
    if native.read_text(one_control(prop['hwnd'],'TpiMaskEdit')['hwnd'])!=actual_name:
        raise RuntimeError('Native model choice was not returned to the property row')
    _close(tina,prop,commit=True)
    return {'model':actual_name,'library':state['library']['selected'],
            'family':state['family']['selected'],'previous_model':state['models']['selected']}


def public_fields(component):
    """Small instance-only set mapped from actual native property dialogs.

    Temperature means an offset from the analysis temperature in the verified
    relative mode. Absolute-mode editing and model equations are not exposed.
    """
    type_id = _supported(component)
    diode = type_id in ('23','64')
    temperature_index = 2 if diode else 3
    mode = component.find("parameter[@idx='"+str(temperature_index-1)+"']").get('value')
    specs = {}
    if mode.casefold() in ('相对','relative'):
        specs['temperature_delta_C'] = (temperature_index,'degC','温度 [摄] / relative temperature')
    if type_id in ('89','90'):
        specs['multiplicity'] = (14,'1','M 区域乘法器')
    else:
        specs['area_factor'] = (3 if diode else 4,'1','区域因数')
    return {'native_temperature_mode':mode, 'fields':{
        name:{'index':index,'unit':unit,'native_label':label,
              'value':component.find("parameter[@idx='"+str(index)+"']").get('value')}
        for name,(index,unit,label) in specs.items()}}


def instance_change(component, field, value):
    """Validate a public field before opening any native dialog."""
    fields = public_fields(component)['fields']
    if field not in fields:
        raise ValueError('Choose a supported public instance field: '+', '.join(fields))
    number = float(value)
    if not math.isfinite(number) or (field in ('area_factor','multiplicity') and number<=0):
        raise ValueError('Use a finite temperature offset or a positive area/multiplicity')
    return {**fields[field], 'field':field, 'before':fields[field]['value'], 'value':str(value)}


def set_instance(tina, component, field, value):
    """Edit one verified public instance value, leaving its catalog model alone."""
    change = instance_change(component,field,value)
    prop = _property(tina,component)
    grid = one_control(prop['hwnd'],'TAttributeGrid')
    for _ in range(change['index']):
        key(grid['hwnd'],0x28)
    if change['index']>=10:
        # TINA's property grid does not scroll when direct key messages select a
        # lower row. Its native vertical scrollbar exposes the MOS M field.
        native.send(grid['hwnd'],0x115,7,0)  # WM_VSCROLL / SB_BOTTOM
    mask = tina.wait(lambda:next((c for c in children(prop['hwnd']) if c['visible'] and
                     c['cls']=='TpiMaskEdit' and native.read_text(c['hwnd'])==change['before']),None),
                     'Reading public instance field '+field)
    tina.set_text(mask['hwnd'],change['value'])
    _close(tina,prop,commit=True)
    return change
