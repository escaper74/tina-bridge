"""Read TINA text exports, preserving each signal's native sampling grid."""
import bisect
import csv
import io
import math
import re
from pathlib import Path


def read_operating_point(path):
    from circuit_view import scalar_value
    raw=Path(path).read_bytes()
    try:
        text=raw.decode('utf-8-sig');encoding='utf-8'
    except UnicodeDecodeError:
        text=raw.decode('gb18030');encoding='gb18030'
    lines=text.splitlines()
    if not lines or not re.search(r'Nodes\s+Values',lines[0]):
        raise ValueError('Not a native TINA DC operating-point table')
    rows=[];unknown=[]
    for lineno,line in enumerate(lines[1:],2):
        if not line.strip():continue
        m=re.fullmatch(r'(.+?)\s{2,}(\S+)\s*',line)
        if not m or m[2][-1:] not in ('V','A'):
            unknown.append({'line':lineno,'text':line});continue
        name,value=m[1].strip(),m[2];unit=value[-1];number=scalar_value(value[:-1])
        if number is None:
            unknown.append({'line':lineno,'text':line});continue
        row={'name':name,'value':number,'unit':unit,'native_value':value,'line':lineno}
        branch=re.fullmatch(r'([IV])_(.+?)\[(.+)\]',name)
        if branch:
            row.update(quantity='current' if branch[1]=='I' else 'voltage',
                       component=branch[2],nodes=[n.strip() for n in branch[3].split(',')])
        elif re.match(r'^[IV]_.+\[',name) and not name.endswith(']'):
            # The native fixed-width table truncates long branch labels. Keep
            # its value but do not fabricate an output name or complete nodes.
            row.update(quantity='current' if name[0]=='I' else 'voltage',name_truncated=True)
        elif name.startswith('VP_'):
            row.update(quantity='node_voltage',node=name[3:])
        else:
            row.update(quantity='output')
        rows.append(row)
    return {'source':str(path),'encoding':encoding,'analysis':'operating_point',
            'rows':rows,'unparsed':unknown,'complete':not unknown,
            'truncated_names':[r['name'] for r in rows if r.get('name_truncated')],
            'note':'Values retain native table precision. Branch signs follow the listed node order; long native labels can be truncated and are explicitly flagged rather than assigned invented nodes.'}


def read_results(path):
    raw=Path(path).read_bytes()
    try:
        text=raw.decode('utf-8-sig')
        encoding='utf-8'
    except UnicodeDecodeError:
        text=raw.decode('gb18030')
        encoding='gb18030'
    blocks=[]
    active=None
    for lineno,line in enumerate(text.splitlines(),1):
        if not line.strip():
            continue
        values=line.split('\t')
        if line.startswith('*'):
            active={'columns':[v.lstrip('*').strip() for v in values],'rows':[]}
            blocks.append(active)
            continue
        if active is None:
            raise ValueError(f'Data before header at line {lineno}')
        if len(values)!=len(active['columns']):
            raise ValueError(f'Column count mismatch at line {lineno}')
        row=[float(v) for v in values]
        if not all(math.isfinite(v) for v in row):
            raise ValueError(f'Non-finite result at line {lineno}')
        if active['rows'] and row[0] < active['rows'][-1][0]:
            raise ValueError(f'Non-monotonic axis at line {lineno}')
        active['rows'].append(row)
    signals=[]
    for i,b in enumerate(blocks):
        for col,name in enumerate(b['columns'][1:],1):
            signals.append({'name':name,'block':i,'axis_label':b['columns'][0],
                            'x':[r[0] for r in b['rows']],'y':[r[col] for r in b['rows']]})
    return {'source':str(path),'encoding':encoding,'signals':signals}


def summarize(data):
    results=[]
    for s in data['signals']:
        xs,ys=s['x'],s['y']
        if not xs:
            raise ValueError(f'Empty signal: {s["name"]}')
        integral=sum((x1-x0)*(y1+y0)/2 for x0,x1,y0,y1 in zip(xs,xs[1:],ys,ys[1:]))
        results.append({'name':s['name'],'block':s['block'],'axis_label':s['axis_label'],
                        'samples':len(xs),'x_start':xs[0],'x_end':xs[-1],
                        'min':min(ys),'max':max(ys),'first':ys[0],'last':ys[-1],
                        'mean_over_axis':integral/(xs[-1]-xs[0]) if xs[-1]!=xs[0] else ys[0]})
    return {'source':data['source'],'encoding':data['encoding'],'signals':results}


def select(data, name, start=None, end=None, max_points=1000):
    matches=[s for s in data['signals'] if s['name']==name]
    if len(matches)!=1:
        raise ValueError(f'Expected one signal {name}; found {len(matches)}')
    s=matches[0]
    first=0 if start is None else bisect.bisect_left(s['x'],start)
    last=len(s['x']) if end is None else bisect.bisect_right(s['x'],end)
    count=last-first
    if count>max_points:
        raise ValueError(f'{count} points exceed max_points={max_points}; choose a smaller interval or explicitly increase the limit')
    return {'name':name,'axis_label':s['axis_label'],'x':s['x'][first:last],'y':s['y'][first:last]}
