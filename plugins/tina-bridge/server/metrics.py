"""Measurements on exported native samples; no solver, resampling, or FFT."""
import bisect
import math
from pathlib import Path
from results import read_results, read_operating_point


def window(signal, start=None, end=None):
    """Clip a sampled signal, adding linearly interpolated boundary samples."""
    xs,ys=signal['x'],signal['y']
    if len(xs)!=len(ys) or len(xs)<2:
        raise ValueError('Measurements require at least two x/y samples')
    if not all(math.isfinite(v) for v in [*xs,*ys]):
        raise ValueError('Non-finite samples cannot be measured')
    if any(b<a for a,b in zip(xs,xs[1:])):
        raise ValueError('The native axis must be nondecreasing')
    start=xs[0] if start is None else start
    end=xs[-1] if end is None else end
    if not (math.isfinite(start) and math.isfinite(end) and xs[0]<=start<end<=xs[-1]):
        raise ValueError('Requested interval must have positive width and lie inside the recorded axis')
    left=bisect.bisect_left(xs,start);right=bisect.bisect_right(xs,end)
    x=list(xs[left:right]);y=list(ys[left:right]);added=[]
    def interpolate(value,index):
        ratio=(value-xs[index-1])/(xs[index]-xs[index-1])
        return ys[index-1]+ratio*(ys[index]-ys[index-1])
    if not x or x[0]!=start:
        x.insert(0,start);y.insert(0,interpolate(start,left));added.append(start)
    if x[-1]!=end:
        x.append(end);y.append(interpolate(end,right));added.append(end)
    return {'name':signal['name'],'axis_label':signal['axis_label'],'x':x,'y':y,
            'native_samples':right-left,'interpolated_boundaries':added}


def crossings(signal, level=0.0, axis='linear'):
    """Find all crossings; log interpolation applies to x, never to y."""
    xs,ys=signal['x'],signal['y']
    if axis not in ('linear','log'):
        raise ValueError('Crossing axis must be linear or log')
    if not math.isfinite(level) or (axis=='log' and any(x<=0 for x in xs)):
        raise ValueError('Crossing level must be finite; log axes require positive samples')
    points=[];plateaus=[];i=0
    while i<len(xs):
        if ys[i]==level:
            j=i
            while j+1<len(xs) and ys[j+1]==level:j+=1
            if j>i and xs[j]>xs[i]:
                plateaus.append({'start':xs[i],'end':xs[j]})
            else:
                before=ys[i-1]-level if i else None
                after=ys[j+1]-level if j+1<len(xs) else None
                direction='touch'
                if before is not None and after is not None:
                    if before<0<after:direction='rising'
                    elif before>0>after:direction='falling'
                points.append({'x':xs[i],'direction':direction,'native_sample':True})
            i=j+1;continue
        if i+1<len(xs) and (ys[i]-level)*(ys[i+1]-level)<0:
            fraction=(level-ys[i])/(ys[i+1]-ys[i])
            a,b=(math.log(xs[i]),math.log(xs[i+1])) if axis=='log' else (xs[i],xs[i+1])
            value=a+fraction*(b-a)
            points.append({'x':math.exp(value) if axis=='log' else value,
                           'direction':'rising' if ys[i+1]>ys[i] else 'falling','native_sample':False})
        i+=1
    return {'level':level,'axis_interpolation':axis,'crossings':points,'plateaus':plateaus}


def waveform_metrics(signal, start=None, end=None, target=None, relative_band=.02,
                     absolute_band=None, initial=None, crossing_level=None, crossing_axis='linear'):
    s=window(signal,start,end);xs,ys=s['x'],s['y'];duration=xs[-1]-xs[0]
    area=math.fsum((b-a)*(u+v)/2 for a,b,u,v in zip(xs,xs[1:],ys,ys[1:]))
    square_area=math.fsum((b-a)*(u*u+u*v+v*v)/3 for a,b,u,v in zip(xs,xs[1:],ys,ys[1:]))
    mean=area/duration;rms=math.sqrt(max(0,square_area/duration))
    result={k:s[k] for k in ('name','axis_label','native_samples','interpolated_boundaries')}
    result.update(start=xs[0],end=xs[-1],duration=duration,first=ys[0],last=ys[-1],
                  minimum=min(ys),maximum=max(ys),peak_to_peak=max(ys)-min(ys),
                  mean=mean,rms=rms,ac_rms=math.sqrt(max(0,rms*rms-mean*mean)),
                  method='Piecewise-linear native samples; exact integral of y and y squared. No uniform resampling.')
    if target is not None:
        if not math.isfinite(target):raise ValueError('Target must be finite')
        band=absolute_band if absolute_band is not None else abs(target)*relative_band
        if not math.isfinite(band) or band<=0:
            raise ValueError('Settling band must be positive; use absolute_band for a zero target')
        outside=[i for i,y in enumerate(ys) if abs(y-target)>band]
        settling=None
        if not outside:settling=xs[0]
        elif outside[-1]<len(xs)-1:
            i=outside[-1];boundary=target+math.copysign(band,ys[i]-target)
            fraction=(boundary-ys[i])/(ys[i+1]-ys[i])
            settling=xs[i]+fraction*(xs[i+1]-xs[i])
        baseline=ys[0] if initial is None else initial
        if not math.isfinite(baseline):raise ValueError('Initial value must be finite')
        step=target-baseline
        overshoot=max(0,max((y-target)*math.copysign(1,step) for y in ys)) if step else None
        result['response']={'target':target,'band':band,'initial':baseline,
                            'settling_axis_value':settling,
                            'settling_duration':None if settling is None else settling-xs[0],
                            'observed_settled':settling is not None,'observed_until':xs[-1],
                            'overshoot':overshoot,
                            'overshoot_percent':None if not step else 100*overshoot/abs(step),
                            'note':'Settling is assessed only over the supplied recorded interval.'}
    if crossing_level is not None:
        result['threshold']=crossings(s,crossing_level,crossing_axis)
    return result


def measure_file(path, signal, block=None, **options):
    """Measure one exact native signal or select one DC operating-point row."""
    path=Path(path).resolve()
    if path.read_bytes().lstrip().startswith(b'Nodes'):
        if options or block is not None:
            raise ValueError('Operating-point rows have no time/frequency measurement options')
        table=read_operating_point(path)
        rows=[r for r in table['rows'] if r['name']==signal]
        if len(rows)!=1:raise ValueError('Choose exactly one operating-point row: '+signal)
        return {'source':str(path),'analysis':'operating_point',**rows[0]}
    data=read_results(path)
    matches=[s for s in data['signals'] if s['name']==signal and (block is None or s['block']==block)]
    if len(matches)!=1:
        raise ValueError(f'Expected one native signal {signal!r}; found {len(matches)}. Specify block if needed.')
    return {'source':str(path),'block':matches[0]['block'],**waveform_metrics(matches[0],**options)}
