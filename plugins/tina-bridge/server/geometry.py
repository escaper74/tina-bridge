"""Native symbol coordinates used for process-local selection and wiring."""
from schematic import xy


def transform(component, point):
    x,y=point
    if component.get('mirrored')=='1':
        x=-x
    angle=int(component.get('orientation','0'))%360
    rotations={0:(x,y),90:(-y,x),180:(-x,-y),270:(y,-x)}
    if angle not in rotations:
        raise ValueError('Only orthogonal native symbol orientations are supported')
    dx,dy=rotations[angle];px,py=xy(component.get('position'))
    return [round(px+dx),round(py+dy)]


def hit_point(component):
    hot=component.find('image/hotzone')
    if hot is not None:
        a=xy(hot.get('points'))
        return transform(component,[(a[0]+a[2])/2,(a[1]+a[3])/2])
    if component.get('typeid') in ('9','10','11','13','15','16','23','43','64'):
        return transform(component,[20,0])
    if component.get('typeid')=='67':
        return transform(component,[0,20])
    if component.get('typeid') in ('87','88','89','90'):
        return transform(component,[0,0])
    if component.get('typeid')=='2':
        return transform(component,[0,8])
    if component.get('typeid')=='4':
        return transform(component,[8,0])
    raise ValueError('No verified native hit geometry for type '+str(component.get('typeid')))


def terminal_positions(component):
    pins=component.findall('image/pin')
    if pins:
        return [{'name':p.get('text'),'position':transform(component,xy(p.get('position')))} for p in pins]
    if component.get('typeid') in ('9','10','11','13','15','16','23','43','64'):
        return [{'name':str(i),'position':transform(component,p)} for i,p in enumerate(([0,0],[40,0]),1)]
    if component.get('typeid')=='67':
        return [{'name':str(i),'position':transform(component,p)} for i,p in enumerate(([0,0],[0,40]),1)]
    if component.get('typeid') in ('87','88'):
        return [{'name':name,'position':transform(component,p)} for name,p in
                [('C',[16,-24]),('B',[-16,0]),('E',[16,24])]]
    if component.get('typeid') in ('89','90'):
        return [{'name':name,'position':transform(component,p)} for name,p in
                [('D',[16,-24]),('G',[-16,8]),('S',[16,24])]]+[
                {'name':'B','position':transform(component,[16,24]),'shared_with':'S','separate_pin':False}]
    if component.get('typeid') in ('2','3','4'):
        return [{'name':'1','position':xy(component.get('position'))}]
    raise ValueError('Native terminal geometry is not yet verified for type '+str(component.get('typeid')))
