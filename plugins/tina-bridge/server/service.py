"""Reusable circuit/simulation operations shared by MCP and local clients."""
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
from pathlib import Path
import uuid
import settings

from bridge import Tina, DEFAULT_EXE, list_sessions, create_session
from schematic import Schematic
from netlist import read_netlist
from results import read_results, read_operating_point, summarize, select

HERE = Path(__file__).resolve().parent
WORKSPACE = settings.workspace()


def new_artifacts(label):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    p = WORKSPACE/(stamp+'-'+label+'-'+uuid.uuid4().hex[:8])
    p.mkdir(parents=True, exist_ok=False)
    return p


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(Path(path).resolve())


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def describe_xml(path, netlist_path=None):
    schematic = Schematic(path)
    result = schematic.describe()
    if netlist_path:
        from circuit_view import normalize_native_sources
        pins = {c['reference']:c['macro_interface'] for c in result['components'] if c['macro_interface']}
        result['connectivity'] = normalize_native_sources(read_netlist(netlist_path, pins),result['components'])
    result['xml_sha256'] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return result


def read_circuit(pid, exe=DEFAULT_EXE, include_connectivity=True):
    tina = Tina(pid, exe)
    from display import place_windows
    place_windows(pid,restore=True)
    folder = new_artifacts('circuit')
    before = tina.unique('TSchematicEditor')
    tina.export_xml(folder/'circuit.xml')
    if include_connectivity:
        tina.export_netlist(folder/'circuit.cir')
    after = tina.unique('TSchematicEditor')
    if (before['hwnd'],before['title']) != (after['hwnd'],after['title']):
        raise RuntimeError(f'Active document changed during export; partial artifacts: {folder}')
    result = {'pid':pid, 'editor':after,'connectivity_available':include_connectivity,
              **describe_xml(folder/'circuit.xml',folder/'circuit.cir' if include_connectivity else None)}
    if include_connectivity:
        from circuit_view import build_view, render_text
        view = build_view(result)
        result['view_file'] = write_json(folder/'circuit-view.json',view)
        (folder/'circuit.txt').write_text(render_text(view),encoding='utf-8')
        result['readable_file'] = str(folder/'circuit.txt')
    result['snapshot'] = write_json(folder/'snapshot.json', result)
    return result


def catalog():
    from native_edits import PRIMITIVES
    from waveforms import catalog as waveform_catalog
    data = read_json(HERE/'assets/catalog.json')
    descriptions={c['id']:c for c in Schematic(HERE/'assets/primitives.xml').describe()['components']}
    for c in data['components']:
        c['native']=descriptions[c['id']]
    return {**data, 'empty_xml':str(HERE/'assets/empty.xml'),
            'templates_xml':str(HERE/'assets/primitives.xml'),
            'native_templates':{name:{'type_id':spec[1]} for name,spec in PRIMITIVES.items()},
            'native_macro_insertion':{'operation':'add_macro','file_type':'.TSM','source':'installed or user-provided macro file; no model rewriting'},
            'native_waveforms':waveform_catalog()}


def apply_operations(schematic, operations):
    changes=[]
    for op in operations:
        kind=op['op']
        if kind=='set_parameter':
            changes.append(schematic.set_parameter(op['component'],op['index'],op['value']))
        elif kind=='set_detail':
            changes.append(schematic.set_detail_parameter(op['component'],op['index'],
                           op['detail_type'],op['detail_index'],op['value']))
        elif kind=='layout':
            changes.append(schematic.layout_component(op['component'],op.get('position'),
                           op.get('orientation'),op.get('mirrored')))
        elif kind=='remove_component':
            changes.append(schematic.remove_component(op['component']))
        elif kind=='remove_wire':
            changes.append(schematic.remove_wire(op['index']))
        elif kind=='add_wire':
            changes.append(schematic.add_wire(op['points'],op.get('label','')))
        elif kind=='connect':
            from routing import path
            changes.append(schematic.add_wire(path(schematic,op['a'],op['b'],op.get('via')),op.get('label','')))
        elif kind=='set_analysis':
            changes.append(schematic.set_analysis(op['kind'],op['parameters']))
        elif kind in ('add_component','clone_component'):
            if kind=='add_component':
                candidates=[c for c in catalog()['components'] if c['name']==op['template']]
                if len(candidates)!=1:
                    raise ValueError(f'Unknown primitive template: {op["template"]}')
                templates=Schematic(HERE/'assets/primitives.xml')
                template=templates.component(candidates[0]['id'])
            else:
                templates=Schematic(op['template_xml'])
                template=templates.component(op['template_component'])
            if template.get('subcircuit'):
                schematic.copy_referenced_subcircuits(templates,template)
            new_id=schematic.add_component(template,op['reference'],op['position'],
                                          op.get('orientation',0),op.get('parameters'))
            changes.append({'added_id':new_id,'reference':op['reference']})
        else:
            raise ValueError(f'Unknown edit operation: {kind}')
    return changes


def edit_circuit(pid, source_xml, operations, save_path, exe=DEFAULT_EXE):
    """Create a new native document from an explicit snapshot; keep source intact."""
    save_path=Path(save_path).resolve()
    if save_path.suffix.lower()!='.tsc':
        raise ValueError('save_path must end in .TSC')
    if save_path.exists():
        raise FileExistsError(save_path)
    if not save_path.parent.is_dir():
        raise FileNotFoundError(f'Output parent directory does not exist: {save_path.parent}')
    schematic=Schematic(source_xml)
    changes=apply_operations(schematic,operations)
    folder=new_artifacts('edit')
    source_copy=folder/'requested.xml'
    schematic.write(source_copy)
    expected=schematic.model_hashes()
    write_json(folder/'request.json',{'source_xml':str(Path(source_xml).resolve()),'pid':pid,
               'save_path':str(save_path),'operations':operations,'changes':changes,'model_hashes':expected})
    tina=Tina(pid,exe)
    tina.import_xml(source_copy)
    actual=read_circuit(pid,exe)
    identity=lambda cs:sorted((c['id'],c['type_id']) for c in cs)
    if identity(actual['components'])!=identity(schematic.describe()['components']):
        raise RuntimeError(f'Native import changed component inventory; inspect {folder} and {actual["snapshot"]}')
    if actual['model_hashes']!=expected:
        raise RuntimeError(f'Model contents changed on native roundtrip; inspect {folder} and {actual["snapshot"]}')
    saved=tina.save_as(save_path)
    # TINA may canonicalize labels and default options; expose its actual readback.
    result={'saved':saved,'source_preserved':str(Path(source_xml).resolve()),'changes':changes,
            'model_contents_preserved':True,'circuit':actual,'request':str(folder/'request.json')}
    write_json(folder/'receipt.json',result)
    return result


def native_edit_parameters(pid, source_tsc, operations, save_path, exe=DEFAULT_EXE):
    """Open a private native copy, edit external values, verify, then save a new TSC."""
    from native_parameters import validate_operation, edit_parameter, parameter_state, wire_state
    source=Path(source_tsc).resolve();target=Path(save_path).resolve()
    if source.suffix.lower()!='.tsc' or not source.is_file():
        raise ValueError('source_tsc must be an existing native .TSC file')
    if target.suffix.lower()!='.tsc' or not target.parent.is_dir():
        raise ValueError('save_path must be a .TSC in an existing directory')
    if target.exists():
        raise FileExistsError(target)
    folder=new_artifacts('native-edit')
    working=folder/'working.TSC';shutil.copy2(source,working)
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    tina=Tina(pid,exe);tina.open(working)
    before=read_circuit(pid,exe,include_connectivity=False)
    original=Schematic(before['source']);expected=Schematic(before['source'])
    for op in operations:
        validate_operation(expected,op)
    write_json(folder/'request.json',{'source_tsc':str(source),'source_sha256':source_hash,
                                    'save_path':str(target),'operations':operations,'before_snapshot':before['snapshot']})
    for op in operations:
        edit_parameter(tina,original.component(op['component']),op)
        validate_operation(original,op)
    after=read_circuit(pid,exe,include_connectivity=False);actual=Schematic(after['source'])
    adjustments=[]
    # TINA recalculates dormant sweep/optimization range defaults when a value
    # changes. Report those native metadata changes; active ranges remain strict.
    for op in operations:
        if op['op']!='set_parameter':
            continue
        a=expected.component(op['component']);b=actual.component(op['component'])
        for kind in ('Parameter stepping','Optimization object'):
            path=f"parameter[@idx='{op['index']}']/detail[@type='{kind}']"
            ad=a.find(path);bd=b.find(path)
            if ad is None or bd is None:
                continue
            if ad.find("parameter[@idx='0']").get('value')!= '0' or bd.find("parameter[@idx='0']").get('value')!='0':
                continue
            for index in ('1','2'):
                av=ad.find(f"parameter[@idx='{index}']");bv=bd.find(f"parameter[@idx='{index}']")
                if av.get('value')!=bv.get('value'):
                    adjustments.append({'component':op['component'],'inactive_detail':kind,'index':index,
                                        'before':av.get('value'),'after':bv.get('value')})
                    av.set('value',bv.get('value'))
    checks={'requested_parameters_and_other_components':parameter_state(expected)==parameter_state(actual),
            'wires_unchanged':wire_state(expected)==wire_state(actual),
            'factory_models_unchanged':expected.model_hashes()==actual.model_hashes(),
            'source_file_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==source_hash}
    write_json(folder/'verification.json',{'checks':checks,'after_snapshot':after['snapshot'],
                                         'native_adjustments':adjustments})
    if not all(checks.values()):
        raise RuntimeError(f'Native edit readback failed: {checks}; inspect {folder}')
    saved=tina.save_as(target)
    result={'saved':saved,'checks':checks,'circuit':after,'request':str(folder/'request.json'),
            'native_adjustments':adjustments,'route':'native TSC property controls; no XML import'}
    write_json(folder/'receipt.json',result)
    return result


def run_analysis(pid, kind, settings=None, exe=DEFAULT_EXE):
    from native_parameters import analysis_parameters
    settings=settings or {}
    allowed={'transient':{'start','end','initial'},'ac':{'start','end','points','sweep'},
             'dc':{'source','start','end','points'},'operating_point':set(),
             'temperature':{'start','end','points'},
             'noise':{'start','end','points','signal_amplitude'},
             'fourier':{'signal','start','fundamental','samples','harmonics','initial'}}
    if kind not in allowed or set(settings)-allowed[kind]:
        raise ValueError(f'Unsupported analysis or setting: {kind}, {settings}')
    folder=new_artifacts(kind)
    tina=Tina(pid,exe)
    tina.close_operating_point_table()
    active_parameters=analysis_parameters(tina)
    if kind in ('temperature','noise','fourier'):
        import analysis_extra
        job=getattr(analysis_extra,'start_'+kind)(tina,**settings)
    else:
        job=getattr(tina,'start_'+kind)(**settings)
    job['solver_parameters']=active_parameters['parameters']
    job['job_file']=str(folder/'job.json')
    job['persistent_settings']=False
    job['note']=('Dialog settings apply to this run. For encrypted/native TSC projects, apply '
                 'tina_analysis_parameters after each open and pass start/end/initial explicitly when running. '
                 'XML set_analysis persistence is only for unencrypted XML-edit workflows; never import encrypted macro XML.')
    write_json(folder/'job.json',job)
    return job


def job_status(job_file, collect=True):
    job=read_json(job_file)
    folder=Path(job_file).resolve().parent
    receipt=folder/'result.json'
    if receipt.exists():
        return read_json(receipt)
    tina=Tina(job['pid'],job['exe'])
    if job['analysis']=='fourier':
        from analysis_extra import poll_fourier
        status=poll_fourier(tina,job)
    else:
        status=tina.poll_run(job)
    status['job_file']=str(Path(job_file).resolve())
    if status['status']=='succeeded' and collect:
        if job['analysis'] in ('temperature','noise','fourier'):
            from analysis_extra import collect_pages,collect_fourier
            collector=collect_fourier if job['analysis']=='fourier' else collect_pages
            status.update(collector(tina,job,folder),solver_parameters=job['solver_parameters'])
            write_json(receipt,status)
            return status
        if job['analysis']=='operating_point':
            tina.export_operating_point(folder/'result.txt')
            status.update(text_path=str(folder/'result.txt'),data=read_operating_point(folder/'result.txt'),
                          solver_parameters=job['solver_parameters'])
            write_json(receipt,status)
            return status
        page=tina.result_pages()
        tina.export_result(folder/'result.txt')
        tina.save_results(folder/'result.tdr')
        status.update(page=page, text_path=str(folder/'result.txt'),native_path=str(folder/'result.tdr'),
                      data=summarize(read_results(folder/'result.txt')))
        write_json(receipt,status)
    elif status['status']=='cancelled':
        write_json(receipt,status)
    return status


def cancel_job(job_file):
    job=read_json(job_file)
    if (Path(job_file).parent/'result.json').exists():
        return job_status(job_file,collect=False)
    tina=Tina(job['pid'],job['exe'])
    if job['analysis']=='fourier':
        from analysis_extra import request_cancel_fourier
        request=request_cancel_fourier(tina,job)
    else:
        request=tina.request_cancel(job)
    if request['requested']:
        job['cancel_requested_utc']=datetime.now(timezone.utc).isoformat()
        write_json(job_file,job)
    return {'cancellation':request,**job_status(job_file,collect=False)}


def export_results(pid, directory=None, exe=DEFAULT_EXE):
    folder=Path(directory).resolve() if directory else new_artifacts('results')
    folder.mkdir(parents=True,exist_ok=True)
    tina=Tina(pid,exe)
    if 'FourierTHD' in tina.unique('TDFWindow')['title']:
        from analysis_extra import collect_fourier
        result=collect_fourier(tina,{'settings':{}},folder)
        write_json(folder/'result.json',result)
        return result
    tina.export_result(folder/'result.txt')
    tina.save_results(folder/'result.tdr')
    result={'page':tina.result_pages(),'text_path':str(folder/'result.txt'),
            'native_path':str(folder/'result.tdr'),'data':summarize(read_results(folder/'result.txt'))}
    write_json(folder/'result.json',result)
    return result


def read_result(path, signal=None, start=None, end=None, max_points=1000):
    if Path(path).read_bytes().lstrip().startswith(b'Nodes'):
        data=read_operating_point(path)
        if start is not None or end is not None:
            raise ValueError('Operating-point tables do not have a time/frequency interval')
        if signal is None:return data
        rows=[r for r in data['rows'] if r['name']==signal]
        if len(rows)!=1:raise ValueError('Expected one operating-point row named '+signal)
        return rows[0]
    # Noise and AC use similar column names; use the persisted analysis identity,
    # never guess a physical quantity from an '-abs'/'-phase' suffix alone.
    job_file=Path(path).resolve().parent/'job.json'
    if job_file.is_file() and read_json(job_file).get('analysis')=='noise':
        from analysis_extra import read_output_noise
        data=read_output_noise(path)
    else:
        data=read_results(path)
    if signal is None:
        return {**summarize(data),**{key:data[key] for key in ('quantity','axis_unit','unit_note','auxiliary_native_columns') if key in data}}
    if max_points<1:
        raise ValueError('max_points must be positive')
    if start is not None and end is not None and start>end:
        raise ValueError('start must not exceed end')
    return {**select(data,signal,start,end,max_points),
            **{key:data[key] for key in ('quantity','axis_unit','unit_note','auxiliary_native_columns') if key in data}}


def find_library(query='',limit=40,exe=DEFAULT_EXE):
    root=Path(exe).parent
    matches=[]
    for category in ('EXAMPLES','SPICELIB','MACROLIB'):
        folder=root/category
        if not folder.is_dir():
            continue
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix.lower() in ('.tsc','.tsm','.lib','.cir','.mod') and query.casefold() in str(path.relative_to(root)).casefold():
                matches.append({'path':str(path),'kind':path.suffix.lower(),'bytes':path.stat().st_size})
    return {'root':str(root),'total_matches':len(matches),'items':matches[:max(1,min(limit,200))],
            'note':'Native/library files are references; their internal model text is not edited.'}
