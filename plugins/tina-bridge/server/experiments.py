"""Small, durable batches over the existing native TINA bridge.

One explicit PID executes one case at a time. Each advance performs one bounded
phase; a recorded job is polled rather than started again after client restart.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import shutil
import uuid


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _save(path,data):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temp.replace(path)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def _lock(path):
    import msvcrt
    with Path(str(path)+'.lock').open('a+b') as stream:
        if Path(str(path)+'.lock').stat().st_size==0:stream.write(b'0');stream.flush()
        stream.seek(0)
        try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        except OSError as exc:raise RuntimeError('Another client is advancing this batch') from exc
        try:yield
        finally:
            stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)


def _analysis(spec):
    if not isinstance(spec,dict) or not isinstance(spec.get('kind'),str):
        raise ValueError('An analysis requires kind and explicit settings')
    settings=spec.get('settings',{})
    if not isinstance(settings,dict):raise ValueError('Analysis settings must be an object')
    required={'transient':{'start','end','initial'},'ac':{'start','end','points','sweep'},
              'dc':{'start','end','points','source'},'operating_point':set(),
              'temperature':{'start','end','points'},
              'noise':{'start','end','points','signal_amplitude'},
              'fourier':{'signal','start','fundamental','samples','harmonics','initial'}}
    if spec['kind'] not in required:raise ValueError('Unsupported batch analysis: '+spec['kind'])
    if spec['kind'] in required and not required[spec['kind']]<=settings.keys():
        raise ValueError('Batch analyses need explicit settings: '+str(required[spec['kind']]))
    return {'kind':spec['kind'],'settings':settings}


def prepare_batch(source_tsc,directory,cases,analysis,solver_parameters=None,measurements=None,close_completed=True):
    """Freeze an explicit source and plan, without touching any TINA process."""
    source=Path(source_tsc).resolve();folder=Path(directory).resolve()
    if not source.is_file() or source.suffix.lower()!='.tsc':raise ValueError('source_tsc must be an existing .TSC')
    if not cases:raise ValueError('At least one case is required')
    default_analysis=_analysis(analysis);normalized=[];names=set()
    for i,case in enumerate(cases,1):
        name=case.get('id',f'case-{i:04d}')
        if not isinstance(name,str) or not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
            raise ValueError('Case IDs use letters, digits, underscore, and hyphen')
        if name in names:raise ValueError('Duplicate case ID: '+name)
        names.add(name)
        normalized.append({'id':name,'status':'pending','values':case.get('values',{}),
                           'operations':case.get('operations',[]),'analysis':_analysis(case.get('analysis',default_analysis)),
                           'solver_parameters':{**(solver_parameters or {}),**case.get('solver_parameters',{})},
                           'measurements':case.get('measurements',measurements or [])})
    # JSON serializability is checked before creating any artifacts.
    if any(c['analysis']['kind']=='fourier' and c['measurements'] for c in normalized):
        raise ValueError('Native Fourier results provide a TDR plot, not numeric measurement data')
    json.dumps(normalized,allow_nan=False)
    folder.mkdir(parents=True,exist_ok=False);baseline=folder/'baseline.TSC';shutil.copy2(source,baseline)
    manifest=folder/'batch.json'
    data={'batch_id':uuid.uuid4().hex[:10],'created_utc':datetime.now(timezone.utc).isoformat(),
          'source':{'path':str(source),'sha256':_sha(source),'baseline':str(baseline)},
          'session':None,'baseline_solver_parameters':None,'close_completed':bool(close_completed),'cases':normalized}
    if _sha(baseline)!=data['source']['sha256']:raise RuntimeError('Source changed while freezing baseline')
    _save(manifest,data)
    return batch_status(manifest)


def _summary(path,data):
    counts={}
    for c in data['cases']:counts[c['status']]=counts.get(c['status'],0)+1
    done=counts.get('succeeded',0)==len(data['cases'])
    attention=any(c['status'] in ('attention','preparing','starting','cancelled') or c.get('measurement_error') for c in data['cases'])
    return {'manifest':str(Path(path).resolve()),'batch_id':data['batch_id'],
            'status':'succeeded' if done else 'attention' if attention else 'active',
            'counts':counts,'session':data['session'],
            'cases':[{k:v for k,v in c.items() if k in ('id','status','values','circuit_file','job_file','result_file',
                       'metrics_file','metrics','error','measurement_error','latest_status','cleanup')} for c in data['cases']]}


def batch_status(manifest):
    """Read durable progress only; does not query or operate TINA."""
    return _summary(manifest,_load(manifest))


class NativeBackend:
    """Thin adapter to the existing service; imported only during live work."""
    def __init__(self,exe=None):
        from bridge import DEFAULT_EXE
        self.exe=exe or DEFAULT_EXE

    def identity(self,pid):
        import ctypes as C
        from ctypes import wintypes as W
        import tina_native as native
        from bridge import Tina
        Tina(pid,self.exe)
        handle=native.K.OpenProcess(0x1000,False,pid)
        if not handle:raise OSError('Cannot inspect batch process identity')
        native.K.GetProcessTimes.argtypes=[W.HANDLE,*([C.POINTER(C.c_ulonglong)]*4)]
        native.K.GetProcessTimes.restype=W.BOOL
        times=[C.c_ulonglong() for _ in range(4)]
        try:
            if not native.K.GetProcessTimes(handle,*(C.byref(t) for t in times)):
                raise OSError('Cannot inspect process creation time')
        finally:native.K.CloseHandle(handle)
        return {'pid':pid,'exe':str(Path(self.exe).resolve()),'creation_time':times[0].value}

    def editor(self,pid):
        from win32_probe import windows
        editors=[w for w in windows(pid) if w['cls']=='TSchematicEditor']
        if len(editors)!=1:raise RuntimeError('Expected one batch schematic editor')
        return editors[0]['title']

    def prepare(self,pid,baseline,operations,target):
        from service import native_edit_parameters
        return native_edit_parameters(pid,baseline,operations,target,self.exe)

    def configure(self,pid,parameters=None):
        from native_parameters import analysis_parameters
        from bridge import Tina
        return analysis_parameters(Tina(pid,self.exe),parameters)['parameters']

    def start(self,pid,analysis):
        from service import run_analysis
        return run_analysis(pid,analysis['kind'],analysis['settings'],self.exe)

    def poll(self,job_file):
        from service import job_status
        return job_status(job_file)

    def close_completed_case(self,pid,case):
        from bridge import Tina
        return close_completed_document(Tina(pid,self.exe),case)


def close_completed_document(tina,case):
    """Save/close only this completed case when it is still the unique active page."""
    source=Path(case['circuit_file'])
    if not source.is_file():return {'closed':False,'kept_reason':'Saved case file is missing'}
    editor=tina.unique('TSchematicEditor')
    if editor['title']!=case['editor']:
        return {'closed':False,'kept_reason':'Active page changed; no save or close was sent'}
    documents=tina.documents()
    matches=[d for d in documents['documents'] if d['name']==source.stem]
    if len(matches)!=1 or documents['selected']!=matches[0]['index']:
        return {'closed':False,'kept_reason':'Case page is absent, ambiguous, or not active'}
    final=source.with_name(source.stem+'-final.TSC')
    saved=tina.save_as(final)
    if not final.is_file():raise RuntimeError('Native final case save was not created')
    tina.close()
    return {'closed':True,'final_circuit_file':str(final),'saved':saved}


def advance_batch(manifest,pid,backend=None):
    """Prepare, start, or collect ONE case phase. Never auto-retry a native edit/run."""
    path=Path(manifest).resolve()
    with _lock(path):
        data=_load(path)
        case=next((c for c in data['cases'] if c['status']!='succeeded'),None)
        if case is None:return _summary(path,data)
        # A dialog or changed active tab can temporarily block collection. A
        # recorded job may be polled again; no new analysis is dispatched here.
        if case['status']=='attention' and case.get('job_file'):
            case['status']='running'
        if case['status'] in ('attention','cancelled','preparing','starting'):
            if case['status'] in ('preparing','starting'):
                case['error']='A client stopped during a native operation. Inspect the case artifacts and TINA before any retry; this batch will not dispatch it again.'
                _save(path,data)
            return _summary(path,data)
        backend=backend or NativeBackend()
        current=backend.identity(pid)
        if data['session'] is not None and current!=data['session']:
            raise ValueError('Batch is bound to another TINA process identity; no command was sent')
        if data['session'] is None:data['session']=current;_save(path,data)
        if _sha(data['source']['baseline'])!=data['source']['sha256']:
            raise ValueError('Frozen baseline changed; no command was sent')
        folder=path.parent/case['id']
        try:
            if case['status']=='pending':
                folder.mkdir(exist_ok=False)
                case['status']='preparing';_save(path,data)
                target=folder/(case['id']+'-'+data['batch_id']+'.TSC')
                receipt=backend.prepare(pid,data['source']['baseline'],case['operations'],str(target))
                _save(folder/'edit.json',receipt)
                case.update(circuit_file=str(target),editor=backend.editor(pid),status='ready')
                if data['baseline_solver_parameters'] is None:
                    data['baseline_solver_parameters']={k:v['value'] for k,v in backend.configure(pid).items()}
                _save(path,data)
            elif case['status']=='ready':
                if backend.editor(pid)!=case['editor']:
                    raise RuntimeError('Active document differs from this prepared case; no analysis was started')
                case['status']='starting';_save(path,data)
                parameters={**data['baseline_solver_parameters'],**case['solver_parameters']}
                case['actual_solver_parameters']=backend.configure(pid,parameters)
                job=backend.start(pid,case['analysis'])
                case.update(job_file=job['job_file'],status='running');_save(path,data)
            elif case['status']=='running':
                result=backend.poll(case['job_file']);case['latest_status']=result['status']
                if result['status']=='succeeded':
                    _save(folder/'result.json',result)
                    if 'error' in case:case['previous_attention']=case.pop('error')
                    case.update(result_file=str(folder/'result.json'),status='collected');_save(path,data)
                elif result['status']=='cancelled':case['status']='cancelled'
                elif result['status']=='attention':
                    case.update(status='attention',error=result)
                _save(path,data)
            if case['status']=='collected':
                from metrics import measure_file
                result=_load(case['result_file'])
                try:
                    measured=[measure_file(result['text_path'],**spec) for spec in case['measurements']]
                except Exception as exc:
                    case['measurement_error']=str(exc);_save(path,data)
                    return _summary(path,data)
                _save(folder/'metrics.json',measured)
                case.update(metrics_file=str(folder/'metrics.json'),metrics=measured,status='succeeded')
                case.pop('measurement_error',None);_save(path,data)
                if data.get('close_completed',False):
                    try:case['cleanup']=backend.close_completed_case(pid,case)
                    except Exception as exc:
                        case['cleanup']={'closed':False,'kept_reason':str(exc)}
                    _save(path,data)
        except Exception as exc:
            case.update(status='attention',error={'type':type(exc).__name__,'message':str(exc)})
            _save(path,data)
        return _summary(path,data)


def grid_cases(axes,base_operations=None):
    """Cartesian product of explicit external component parameter values."""
    names=[a.get('name',f"{a['component']}:{a['index']}") for a in axes]
    targets=[(a['component'],a['index']) for a in axes]
    if not axes or len(set(names))!=len(names) or len(set(targets))!=len(targets) or any(not a['values'] for a in axes):
        raise ValueError('Axes need distinct names/targets and at least one value each')
    result=[]
    for i,values in enumerate(itertools.product(*(a['values'] for a in axes)),1):
        operations=list(base_operations or [])+[{'op':'set_parameter','component':a['component'],'index':a['index'],'value':str(v)} for a,v in zip(axes,values)]
        result.append({'id':f'case-{i:04d}','values':dict(zip(names,values)),'operations':operations})
    return result


def tolerance_cases(parameters,count,seed,distribution='uniform',base_operations=None):
    """Seeded independent variations: uniform half-width or normal 1-sigma relative spread."""
    from circuit_view import scalar_value
    if distribution not in ('uniform','normal') or count<1 or not parameters:
        raise ValueError('Choose uniform/normal, a positive case count, and parameters')
    targets=[(p['component'],p['index']) for p in parameters]
    if len(set(targets))!=len(targets):raise ValueError('Repeated tolerance target')
    names=[p.get('name',f"{p['component']}:{p['index']}") for p in parameters]
    if len(set(names))!=len(names):raise ValueError('Repeated tolerance parameter name')
    nominal=[scalar_value(p['nominal']) for p in parameters]
    if any(v is None for v in nominal) or any(not math.isfinite(p['relative']) or p['relative']<0 for p in parameters):
        raise ValueError('Use finite numeric nominal values and nonnegative relative spreads')
    rng=random.Random(seed);cases=[]
    for i in range(count):
        operations=list(base_operations or []);values={}
        for p,base in zip(parameters,nominal):
            spread=p['relative'];offset=rng.uniform(-spread,spread) if distribution=='uniform' else rng.gauss(0,spread)
            value=base*(1+offset);text=format(value,'.15g');name=p.get('name',f"{p['component']}:{p['index']}")
            operations.append({'op':'set_parameter','component':p['component'],'index':p['index'],'value':text});values[name]=value
        cases.append({'id':f'sample-{i+1:04d}','operations':operations,'values':values})
    return {'seed':seed,'distribution':distribution,'spread_definition':'relative uniform half-width' if distribution=='uniform' else 'relative standard deviation; unbounded, not clipped','cases':cases}


def sensitivity_cases(parameters,relative_step=.01,base_operations=None):
    """Nominal plus one-at-a-time low/high cases, with every nominal value explicit."""
    from circuit_view import scalar_value
    if not parameters or not math.isfinite(relative_step) or not 0<relative_step<1:
        raise ValueError('Use parameters and a relative step between zero and one')
    values=[scalar_value(p['nominal']) for p in parameters]
    if any(v is None or v==0 for v in values):raise ValueError('Relative sensitivity needs nonzero numeric nominal values')
    targets=[(p['component'],p['index']) for p in parameters]
    names=[p.get('name',f"{p['component']}:{p['index']}") for p in parameters]
    if len(set(targets))!=len(targets) or len(set(names))!=len(names):raise ValueError('Sensitivity parameters must be distinct')
    def case(name,actual):
        return {'id':name,'values':dict(zip(names,actual)),'operations':list(base_operations or [])+
                [{'op':'set_parameter','component':p['component'],'index':p['index'],'value':format(v,'.15g')} for p,v in zip(parameters,actual)]}
    result=[case('nominal',values)]
    for i in range(len(parameters)):
        for suffix,direction in [('low',-1),('high',1)]:
            actual=list(values);actual[i]+=direction*abs(values[i])*relative_step
            result.append(case(f'axis-{i+1:03d}-{suffix}',actual))
    return result


def sensitivity_estimate(low,nominal,high):
    """Use three measured [parameter, result] pairs; return a local secant estimate."""
    if not all(math.isfinite(v) for pair in (low,nominal,high) for v in pair) or not low[0]<nominal[0]<high[0]:
        raise ValueError('Supply finite low < nominal < high parameter/result pairs')
    slope=(high[1]-low[1])/(high[0]-low[0])
    return {'slope':slope,'normalized_sensitivity':None if nominal[1]==0 else nominal[0]*slope/nominal[1],
            'low':low,'nominal':nominal,'high':high,'method':'Secant between measured perturbations; local linear approximation, not a convergence claim.'}


def boundary_candidate(samples,target):
    """Propose one bisection point from measured (parameter, result) pairs; runs nothing."""
    points=sorted(samples)
    if len(points)<2 or not all(math.isfinite(v) for pair in points for v in pair) or not math.isfinite(target):
        raise ValueError('At least two finite (parameter, measured value) pairs are required')
    if any(a[0]==b[0] for a,b in zip(points,points[1:])):raise ValueError('Parameter samples must be distinct')
    exact=[p[0] for p in points if p[1]==target]
    brackets=[(a,b) for a,b in zip(points,points[1:]) if (a[1]-target)*(b[1]-target)<0]
    if exact:return {'status':'observed_target','parameters':exact,'target':target}
    if len(brackets)!=1:return {'status':'unbracketed' if not brackets else 'multiple_brackets','brackets':brackets,'target':target}
    a,b=brackets[0]
    return {'status':'candidate','parameter':(a[0]+b[0])/2,'bracket':[a,b],'width':b[0]-a[0],
            'target':target,'note':'This proposes a point only. Run TINA and add the measured result; monotonicity between samples is not proved.'}
