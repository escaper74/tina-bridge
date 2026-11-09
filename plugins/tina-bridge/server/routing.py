"""Resolve explicit component terminals to native schematic wire vertices."""
from geometry import terminal_positions


def endpoint(schematic,spec):
    if isinstance(spec,(list,tuple)):
        if len(spec)!=2 or any(not isinstance(n,int) for n in spec):
            raise ValueError('A coordinate endpoint is [integer x, integer y]')
        return list(spec)
    component=schematic.component(spec['component'])
    terminals=terminal_positions(component)
    pin=str(spec['pin'])
    if pin in ('+','-') and component.get('typeid') in ('10','13','15','16','67'):
        pin='1' if pin=='+' else '2'
    if pin.upper() in ('A','K') and component.get('typeid') in ('23','43','64'):
        pin='1' if pin.upper()=='A' else '2'
    matches=[p for p in terminals if (p['name'] or '').casefold()==pin.casefold()]
    if not matches and pin.isdigit() and 1<=int(pin)<=len(terminals):
        matches=[terminals[int(pin)-1]]
    if len(matches)!=1:
        raise ValueError('Choose one native symbol terminal: '+str(terminals))
    return matches[0]['position']


def path(schematic,a,b,via=None):
    points=[endpoint(schematic,a),*(via or []),endpoint(schematic,b)]
    return validate_points(points)


def validate_points(points):
    if len(points)<2:
        raise ValueError('A wire needs at least two vertices')
    if any(len(p)!=2 or any(not isinstance(n,int) for n in p) for p in points):
        raise ValueError('Wire vertices are integer x,y pairs')
    for p,q in zip(points,points[1:]):
        if list(p)==list(q):
            raise ValueError('Wire vertices must be distinct')
        if p[0]!=q[0] and p[1]!=q[1]:
            raise ValueError('Specify orthogonal via points between non-aligned terminals')
    return points


def covered(points,wires):
    """Every requested straight segment must be present in the native XML."""
    # Native polylines can repeat a bend/endpoint; keep request validation in
    # path()/validate_points(), but accept that representation for delete checks.
    points=[p for i,p in enumerate(points) if not i or list(p)!=list(points[i-1])]
    if len(points)<2:return False
    validate_points(points)
    segments=[]
    for w in wires:
        nums=[int(n) for n in w['points'].split(',')]
        ps=list(zip(nums[::2],nums[1::2]));segments.extend(zip(ps,ps[1:]))
    for a,b in zip(points,points[1:]):
        axis=0 if a[1]==b[1] else 1;fixed=1-axis
        lo,hi=sorted((a[axis],b[axis]));ends=[]
        for p,q in segments:
            if p[fixed]==q[fixed]==a[fixed]:ends.append(sorted((p[axis],q[axis])))
        reach=lo
        for start,end in sorted(ends):
            if start<=reach:reach=max(reach,end)
        if reach<hi:return False
    return True
