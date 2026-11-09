"""Native topology edits in a private TSC, with actual XML and netlist readback."""
import hashlib
import shutil
from pathlib import Path
from schematic import Schematic,xy
from native_parameters import parameter_state,edit_parameter
import native_topology as draw
from routing import path as connection_path,covered,validate_points

# Actual selector indices in the supported TINA-TI 9.3 build.
PRIMITIVES={'resistor':(6,'9'),'capacitor':(8,'10'),'inductor':(9,'11'),
            'battery':(2,'67'),'voltage_generator':(3,'16'),
            'ground':(0,'2'),'voltage_probe':(35,'4'),
            'current_source':(47,'13'),'current_generator':(49,'15'),
            'diode':(65,'23'),'schottky_diode':(69,'64'),
            'npn':(70,'87'),'pnp':(71,'88'),'nmos':(72,'89'),'pmos':(73,'90')}


def edit(pid,source_tsc,operations,save_path,include_connectivity=True):
    from bridge import Tina
    from service import new_artifacts,read_circuit,write_json
    source=Path(source_tsc).resolve();target=Path(save_path).resolve()
    if not source.is_file() or source.suffix.lower()!='.tsc':
        raise ValueError('source_tsc must be an existing native TSC')
    if target.exists():raise FileExistsError(target)
    if target.suffix.lower()!='.tsc' or not target.parent.is_dir():
        raise ValueError('save_path must be a new TSC in an existing directory')
    for op in operations:
        if op['op']=='add_wire':validate_points(op['points'])
        if op['op']=='set_waveform':
            from waveforms import validate_request
            validate_request(op['waveform'],op['parameters'],op.get('dc_level'))
        if op['op']=='add_macro':
            if not Path(op['macro_file']).is_file() or Path(op['macro_file']).suffix.lower()!='.tsm':
                raise ValueError('add_macro requires an existing native .TSM file')
    folder=new_artifacts('native-topology');working=folder/'working.TSC'
    shutil.copy2(source,working);original_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    t=Tina(pid);t.open(working)
    before=read_circuit(pid,include_connectivity=include_connectivity)
    current=Schematic(before['source']);steps=[];deleted=set()
    record={'source_tsc':str(source),'source_sha256':original_hash,'save_path':str(target),
            'before_snapshot':before['snapshot'],'operations':operations,'steps':steps}
    write_json(folder/'request.json',record)

    def snapshot(label):
        p=folder/(str(len(steps)).zfill(3)+'-'+label+'.xml')
        t.export_xml(p);return Schematic(p)

    def require_equal(a,b,allowed):
        sa,sb=parameter_state(a),parameter_state(b)
        changed=[i for i,v in sa.items() if i not in allowed and sb.get(i)!=v]
        if changed:raise RuntimeError('An unrelated component changed; inspect '+str(folder)+': '+str(changed))
        ma,mb=a.model_hashes(),b.model_hashes()
        if any(mb.get(i)!=v for i,v in ma.items() if i not in deleted):
            raise RuntimeError('Existing factory macro changed; inspect '+str(folder))

    for op in operations:
        kind=op['op'];old=current;old_ids=set(parameter_state(old));allowed=set();info={'operation':op}
        if kind=='add_component':
            if op['template'] not in PRIMITIVES:
                raise ValueError('Native primitive templates: '+', '.join(PRIMITIVES))
            if op['reference'] and any(c['reference']==op['reference'] for c in old.describe()['components']):
                raise ValueError('Duplicate component reference: '+op['reference'])
            selector,type_id=PRIMITIVES[op['template']]
            draw.insert(t,selector,op['position']);current=snapshot('insert')
            additions=set(parameter_state(current))-old_ids
            if len(additions)!=1:raise RuntimeError('Native insertion did not add exactly one component')
            ident=additions.pop();c=current.component(ident)
            if c.get('typeid')!=type_id or xy(c.get('position'))!=list(op['position']):
                raise RuntimeError('Native placement differs from request; inspect '+str(folder))
            if op['reference'] and c.find('image/label').get('textroot')!=op['reference']:
                draw.rename(t,c,op['reference']);current=snapshot('rename');c=current.component(ident)
            angle=op.get('orientation',0)
            if angle%90:raise ValueError('orientation must be a multiple of 90 degrees')
            turns=((angle-int(c.get('orientation','0')))%360)//90
            if turns:
                draw.rotate(t,c,turns);current=snapshot('rotate');c=current.component(ident)
            for index,value in (op.get('parameters') or {}).items():
                from native_parameters import validate_operation
                validate_operation(Schematic(current.path),{'op':'set_parameter','component':ident,'index':int(index),'value':value})
                edit_parameter(t,c,{'op':'set_parameter','index':int(index),'value':value})
                # The next native property dialog must be checked against its fresh value.
                current=snapshot('parameter-'+str(index));c=current.component(ident)
                if c.find("parameter[@idx='"+str(index)+"']").get('value')!=value:
                    raise RuntimeError('New component parameter differs from request')
            if int(c.get('orientation','0'))!=angle%360:
                raise RuntimeError('New component orientation differs from request')
            info['added_id']=ident;info['reference']=c.find('image/label').get('textroot')
            info['actual_parameters']=[p.attrib for p in c.findall('parameter')]
        elif kind=='add_macro':
            angle=op.get('orientation',0)
            if angle%90:raise ValueError('orientation must be a multiple of 90 degrees')
            info.update(draw.insert_macro(t,op['macro_file'],op['position']))
            current=snapshot('macro-insert');additions=set(parameter_state(current))-old_ids
            if len(additions)!=1:raise RuntimeError('Native macro insertion did not add exactly one component')
            ident=additions.pop();c=current.component(ident)
            if c.get('macrotype') is None or xy(c.get('position'))!=list(op['position']):
                raise RuntimeError('Inserted native macro or position differs from request')
            turns=((angle-int(c.get('orientation','0')))%360)//90
            if turns:
                draw.rotate(t,c,turns);current=snapshot('macro-rotate');c=current.component(ident)
            if int(c.get('orientation','0'))!=angle%360:raise RuntimeError('Native macro orientation differs from request')
            info.update(added_id=ident,reference=c.find('image/label').get('textroot'),
                        macro_sha256=hashlib.sha256(Path(op['macro_file']).read_bytes()).hexdigest())
        elif kind in ('set_parameter','set_pwl','set_waveform','set_device_model','set_device_instance','rename','layout','remove_component'):
            c=old.component(op['component']);ident=c.get('id');allowed.add(ident)
            if kind=='set_device_model':
                from device_models import select_model
                info['model_selection']=select_model(t,c,op['model'])
            elif kind=='set_device_instance':
                from device_models import set_instance
                info['instance_change']=set_instance(t,c,op['field'],op['value'])
            elif kind=='set_waveform':
                from waveforms import configure,state,matches
                original_waveform=state(c)
                request=configure(t,c,op['waveform'],op['parameters'],op.get('dc_level'))
            elif kind in ('set_parameter','set_pwl'):
                from native_parameters import validate_operation
                expected=Schematic(old.path);validate_operation(expected,op)
                edit_parameter(t,c,op)
            elif kind=='rename':
                if any(v['reference']==op['reference'] for v in old.describe()['components']):
                    raise ValueError('Duplicate reference: '+op['reference'])
                draw.rename(t,c,op['reference'])
            elif kind=='remove_component':
                draw.delete(t,c);deleted.add(ident)
            else:
                if op.get('orientation') is not None:
                    angle=op['orientation']
                    if angle%90:raise ValueError('orientation must be a multiple of 90 degrees')
                    turns=((angle-int(c.get('orientation','0')))%360)//90
                    if turns:
                        draw.rotate(t,c,turns);current=snapshot('rotate');c=current.component(ident)
                if op.get('mirrored') is not None and (c.get('mirrored')=='1')!=op['mirrored']:
                    draw.mirror(t,c);current=snapshot('mirror');c=current.component(ident)
                if op.get('position') is not None and xy(c.get('position'))!=list(op['position']):
                    draw.move(t,c,op['position'])
            current=snapshot('after')
            if kind=='remove_component':
                if set(parameter_state(current))!=old_ids-{ident}:raise RuntimeError('Native removal differs from request')
            else:
                actual=current.component(ident)
                if kind=='rename' and actual.find('image/label').get('textroot')!=op['reference']:
                    raise RuntimeError('Native label readback differs from request')
                if kind=='set_device_model':
                    if actual.find("parameter[@idx='0']").get('value')!=info['model_selection']['model']:
                        raise RuntimeError('Native device model readback differs from requested library entry')
                elif kind=='set_device_instance':
                    from circuit_view import scalar_value
                    change=info['instance_change']
                    if scalar_value(actual.find("parameter[@idx='"+str(change['index'])+"']").get('value'))!=float(op['value']):
                        raise RuntimeError('Native instance field readback differs from request')
                elif kind=='set_waveform':
                    if not matches(state(actual),request,original_waveform['dc_level']):
                        raise RuntimeError('Native waveform readback differs from request')
                elif kind=='layout':
                    for field in ('position','orientation','mirrored'):
                        if op.get(field) is not None:
                            value=actual.get(field)
                            value=xy(value) if field=='position' else (value=='1' if field=='mirrored' else int(value))
                            requested=list(op[field]) if field=='position' else (op[field]%360 if field=='orientation' else op[field])
                            if value!=requested:raise RuntimeError('Native '+field+' readback differs from request')
                elif kind=='set_parameter':
                    p=actual.find("parameter[@idx='"+str(op['index'])+"']")
                    if p is None or p.get('value')!=op['value']:raise RuntimeError('Native parameter readback differs from request')
                elif kind=='set_pwl':
                    p=actual.find("parameter[@idx='1']/detail/parameter[@idx='0']")
                    if p.text.strip()!=op['text'].strip():raise RuntimeError('Native PWL readback differs from request')
        elif kind in ('add_wire','connect'):
            points=op['points'] if kind=='add_wire' else connection_path(old,op['a'],op['b'],op.get('via'))
            if op.get('label'):raise ValueError('Native wire labels are not yet exposed; use a voltage probe')
            for a,b in zip(points,points[1:]):
                if a[0]!=b[0] and a[1]!=b[1]:raise ValueError('Native wire segments must be orthogonal')
                # Start at the free endpoint. Starting on an existing routed lead can
                # merge its old segments and detach a probe at a bend in TINA 9.3.
                wires=current.describe()['wires']
                # Drawing over an already present segment can trim that segment
                # out of the existing lead. Reuse it instead of drawing twice.
                if covered([a,b],wires):
                    info.setdefault('reused_segments',[]).append([a,b])
                    continue
                def touches(p):
                    count=0
                    for w in wires:
                        nums=xy(w['points']);ps=list(zip(nums[::2],nums[1::2]))
                        for x,y in zip(ps,ps[1:]):
                            if ((x[0]==y[0]==p[0] and min(x[1],y[1])<=p[1]<=max(x[1],y[1])) or
                                (x[1]==y[1]==p[1] and min(x[0],y[0])<=p[0]<=max(x[0],y[0]))):count+=1
                    return count
                if touches(a)>touches(b):a,b=b,a
                draw.wire(t,a,b)
            current=snapshot('wire')
            if not covered(points,current.describe()['wires']):raise RuntimeError('Requested wire route absent from native readback')
            info['resolved_points']=points
        elif kind=='remove_wire':
            wires=old.describe()['wires']
            if not 0<=op['index']<len(wires):raise ValueError('Wire index outside current snapshot')
            nums=xy(wires[op['index']]['points']);points=list(zip(nums[::2],nums[1::2]))
            draw.delete_wire(t,points);current=snapshot('wire-removal')
            if covered(points,current.describe()['wires']):raise RuntimeError('Requested wire still present after native deletion')
        else:
            raise ValueError('Unsupported native edit operation: '+kind)
        require_equal(old,current,allowed)
        info['actual_xml']=str(current.path);steps.append(info);write_json(folder/'request.json',record)
    after=read_circuit(pid,include_connectivity=include_connectivity)
    checks={'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==original_hash,
            'remaining_factory_models_preserved':all(after['model_hashes'].get(i)==v for i,v in before['model_hashes'].items() if i not in deleted)}
    if not all(checks.values()):raise RuntimeError('Native edit verification failed: '+str(checks))
    connectivity_check=None
    additive={'add_component','add_macro','add_wire','connect','set_parameter','set_pwl','set_waveform','set_device_model','set_device_instance'}
    if include_connectivity and all(op['op'] in additive for op in operations):
        from connectivity_checks import check_additive_connectivity
        connectivity_check=check_additive_connectivity(before['connectivity'],after['connectivity'],raise_on_error=False)
        write_json(folder/'connectivity-check.json',connectivity_check)
        if not connectivity_check['passed']:
            raise RuntimeError('Native edit disconnected an existing network or lost its named output: '+
                               str(connectivity_check['errors'])+'; inspect '+str(folder))
    result={'saved':t.save_as(target),'checks':checks,'steps':steps,'before_snapshot':before['snapshot'],
            'circuit':after,'request':str(folder/'request.json'),'route':'native controls; no XML import',
            'note':'Actual wiring is returned for inspection. Moving/deleting native objects can change adjacent wire geometry.'}
    if connectivity_check is not None:result['additive_connectivity_check']=connectivity_check
    if include_connectivity:
        from circuit_view import build_view,compare
        result['circuit_changes']=compare(build_view(before),build_view(after))
    write_json(folder/'receipt.json',result);return result
