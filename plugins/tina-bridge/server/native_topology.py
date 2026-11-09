"""Native palette and drawing commands scoped to a TINA editor process."""
import ctypes as C
import time
from native_parameters import canvas_point,visible_children,key,select_component,open_properties,one_control
from win32_probe import children
import tina_native as native


def palette(tina):
    editor=tina.unique('TSchematicEditor')
    boxes=[c for c in children(editor['hwnd']) if c['cls']=='TComboBox' and c['visible']
           and native.send(c['hwnd'],0x146)>20]
    if len(boxes)!=1:
        raise ValueError('Expected native component selector')
    combo=boxes[0];items=[]
    for index in range(native.send(combo['hwnd'],0x146)):
        length=native.send(combo['hwnd'],0x149,index)
        buffer=C.create_unicode_buffer(length+1)
        native.send(combo['hwnd'],0x148,index,C.addressof(buffer))
        items.append({'index':index,'name':buffer.value})
    return combo,items


def insert(tina,index,position):
    canvas,point=canvas_point(tina,position)
    combo,items=palette(tina)
    if not 0<=index<len(items):
        raise ValueError('Unknown palette index')
    native.send(combo['hwnd'],0x14e,index,0)
    native.send(combo['parent'],0x111,(1<<16)|(combo['control_id']&0xffff),combo['hwnd'])
    _place(canvas,point)
    return items[index]


def insert_macro(tina,path,position):
    from pathlib import Path
    source=Path(path).resolve()
    if not source.is_file() or source.suffix.lower()!='.tsm':
        raise ValueError('Macro insertion requires an existing native .TSM file')
    canvas,point=canvas_point(tina,position)
    tina.menu('TSchematicEditor',[r'^插入|^Insert',r'^宏\(|^Macro'])
    tina.file_dialog(source,save=False)
    _place(canvas,point)
    return {'macro_file':str(source)}


def _place(canvas,point):
    time.sleep(.5)  # TINA processes its placement preview on a deferred UI cycle.
    native.send(canvas['hwnd'],0x200,0,point)
    time.sleep(.5)
    native.send(canvas['hwnd'],0x201,1,point)
    time.sleep(.2)
    native.send(canvas['hwnd'],0x202,0,point)
    time.sleep(.3)
    key(canvas['hwnd'],0x1b)
    time.sleep(.2)


def wire(tina,start,end):
    # Both endpoints must remain in the same viewport throughout placement.
    canvas,a=canvas_point(tina,start)
    canvas,b=canvas_point(tina,end)
    canvas,a2=canvas_point(tina,start)
    if a!=a2:
        raise ValueError('Wire endpoints span different viewports; use shorter segments')
    tina.menu('TSchematicEditor',[r'^插入|^Insert',r'^连线|^Wire'])
    time.sleep(.5)
    native.send(canvas['hwnd'],0x200,0,a);time.sleep(.5)
    native.send(canvas['hwnd'],0x201,1,a);time.sleep(.2)
    native.send(canvas['hwnd'],0x200,1,b);time.sleep(.5)
    native.send(canvas['hwnd'],0x202,0,b);time.sleep(.3)
    key(canvas['hwnd'],0x1b)
    time.sleep(.2)


def delete(tina,component):
    select_component(tina,component)
    time.sleep(.3)
    tina.menu('TSchematicEditor',[r'^编辑|^Edit',r'^删除|^Delete'])
    time.sleep(.5)


def rename(tina,component,reference):
    dialog=open_properties(tina,component)
    grid=one_control(dialog['hwnd'],'TAttributeGrid')
    mask=one_control(dialog['hwnd'],'TpiMaskEdit')
    # The native table has a label row and a parameter heading above parameter 0.
    key(grid['hwnd'],0x26);key(grid['hwnd'],0x26)
    old=component.find('image/label').get('textroot')
    if native.read_text(mask['hwnd'])!=old:
        raise ValueError('Native label row does not match selected component')
    tina.set_text(mask['hwnd'],reference)
    tina.click_control(visible_children(dialog['hwnd']),r'^确定$|^OK$')
    tina.wait(lambda:not any(w['cls']=='TSchPropertyEditor' for w in tina.visible()),'Committing component label')


def rotate(tina,component,steps=1):
    select_component(tina,component);time.sleep(.3)
    for _ in range(steps%4):
        tina.menu('TSchematicEditor',[r'^编辑|^Edit',r'^向右旋转|^Rotate Right'])
        time.sleep(.5)


def mirror(tina,component):
    select_component(tina,component);time.sleep(.3)
    tina.menu('TSchematicEditor',[r'^编辑|^Edit',r'^镜像|^Mirror']);time.sleep(.5)


def move(tina,component,position):
    from geometry import hit_point
    from schematic import xy
    old=xy(component.get('position'));a=hit_point(component)
    b=[a[i]+position[i]-old[i] for i in range(2)]
    canvas,start=canvas_point(tina,a);_,end=canvas_point(tina,b);_,check=canvas_point(tina,a)
    if check!=start:
        raise ValueError('Move spans different viewports; use an intermediate position')
    native.send(canvas['hwnd'],0x200,0,start);time.sleep(.5)
    native.send(canvas['hwnd'],0x201,1,start);time.sleep(.2)
    native.send(canvas['hwnd'],0x200,1,end);time.sleep(.5)
    native.send(canvas['hwnd'],0x202,0,end);time.sleep(.5)


def delete_wire(tina,points):
    segments=[(a,b) for a,b in zip(points,points[1:]) if list(a)!=list(b)]
    if not segments:raise ValueError('A zero-length native junction has no selectable wire segment')
    a,b=max(segments,key=lambda s:abs(s[0][0]-s[1][0])+abs(s[0][1]-s[1][1]))
    point=[(a[i]+b[i])//2 for i in range(2)]
    canvas,lp=canvas_point(tina,point)
    native.send(canvas['hwnd'],0x200,0,lp);time.sleep(.5)
    native.send(canvas['hwnd'],0x201,1,lp);native.send(canvas['hwnd'],0x202,0,lp);time.sleep(.3)
    tina.menu('TSchematicEditor',[r'^编辑|^Edit',r'^删除|^Delete']);time.sleep(.5)
