"""Small queryable views over native XML + solver-netlist snapshots."""
import json
import copy
import math
import re
from pathlib import Path
from netlist import connection_signature


PRIMARY_PARAMETERS = {
    '9':('resistance','ohm'), '10':('capacitance','F'), '11':('inductance','H'),
    '67':('voltage','V'), '16':('dc_voltage','V'),
    '13':('current','A'),'15':('dc_current','A'),
}
SCALES = {'t':1e12,'g':1e9,'meg':1e6,'k':1e3,'m':1e-3,'u':1e-6,
          'n':1e-9,'p':1e-12,'f':1e-15,'':1.0}


def scalar_value(raw):
    """SPICE numeric literal only. Expressions stay as native strings."""
    m = re.fullmatch(r'\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(meg|[tgkmunpfµ]?)\s*',str(raw),re.I)
    if not m:
        return None
    value = float(m[1])*SCALES[m[2].lower().replace('µ','u')]
    return value if math.isfinite(value) else None


def normalize_native_sources(netlist,native):
    """Map a VG's generated series DC source back to its two schematic terminals.

    TINA expands a nonzero VG bias into Vref + Vref_DC. The internal junction
    is not the original symbol's negative terminal. Match the native type,
    exact DC value, absent native alias and private two-device junction before
    folding; retain all solver devices/nets and statements for inspection.
    """
    result=copy.deepcopy(netlist);by_name={d['name'].casefold():d for d in result['devices']}
    references={c['reference'].casefold() for c in native if c['reference']}
    expansions=[];removed=set()
    for component in native:
        if component['type_id']!='16' or component.get('model_protected'):continue
        name=component['reference'];bias=next((scalar_value(p.get('value')) for p in component['parameters'] if p['idx']=='0'),None)
        if bias is None or bias==0 or (name+'_DC').casefold() in references:continue
        main=by_name.get(name.casefold());offset=by_name.get((name+'_DC').casefold())
        if not main or not offset or main['kind']!='V' or offset['kind']!='V':continue
        offset_value=scalar_value(re.sub(r'^DC\s+','',offset['parameters'],flags=re.I))
        if offset_value is None or not math.isclose(offset_value,bias,rel_tol=1e-12,abs_tol=1e-15):continue
        internal=main['nodes'][1]
        if offset['nodes'][0]!=internal or internal=='0' or not internal.isdigit():continue
        incident=netlist['nets'].get(internal,[])
        actual={(t['device'].casefold(),t['terminal']) for t in incident}
        if len(incident)!=2 or actual!={(main['name'].casefold(),2),(offset['name'].casefold(),1)}:continue
        expansions.append({'component':name,'kind':'series_dc_bias','dc_value':bias,
                           'internal_node':internal,'solver_devices':copy.deepcopy([main,offset])})
        main['nodes'][1]=offset['nodes'][1];main['terminals'][1]['node']=offset['nodes'][1]
        main['terminal_source']='native voltage-generator terminals after folding its verified series DC bias'
        removed.add(offset['name'])
    if expansions:
        result['solver_devices']=netlist['devices'];result['solver_nets']=netlist['nets']
        result['devices']=[d for d in result['devices'] if d['name'] not in removed]
        result['nets']={}
        for d in result['devices']:
            for terminal in d['terminals']:
                result['nets'].setdefault(terminal['node'],[]).append(
                    {'device':d['name'],'terminal':terminal['index'],'pin':terminal['name']})
    result['native_source_expansions']=expansions
    return result


def build_view(snapshot):
    netlist = snapshot['connectivity']
    native = snapshot['components']
    by_reference = {c['reference'].casefold():c for c in native if c['reference']}
    current_arrows = {'V'+c['reference'].replace(':','_').upper():c for c in native if c['type_id']=='34'}
    components=[]; aliases={}; unresolved=[]
    for device in netlist['devices']:
        key = device['name']; source = None
        if device['kind']=='X':
            source = by_reference.get(key[1:].casefold())
        elif key.upper() in current_arrows:
            source = current_arrows[key.upper()]
        else:
            source = by_reference.get(key.casefold())
        if source is None and key[0].upper() in ('Q','M','D'):
            candidate=by_reference.get(key[1:].casefold())
            native_types={'Q':('87','88'),'M':('89','90'),'D':('23','43','64')}
            if candidate and candidate['type_id'] in native_types[key[0].upper()]:
                source=candidate
        reference = source['reference'] if source else key
        aliases[key] = reference
        parameters=[]
        for p in (source or {}).get('parameters',[]):
            item = {k:v for k,v in p.items() if k not in ('content_bytes','content_sha256')}
            item['name'] = 'parameter_'+str(p['idx'])
            item['write_policy'] = 'factory_model_protected' if source['model_protected'] else 'requires_supported_edit_route'
            if p['idx']=='0' and source['type_id'] in PRIMARY_PARAMETERS:
                name,unit = PRIMARY_PARAMETERS[source['type_id']]
                item.update(name=name,unit=unit,si_value=scalar_value(p.get('value','')))
            parameters.append(item)
        component={'reference':reference,'netlist_name':key,
                   'type':source['type'] if source else device['kind'],
                   'native_id':source['id'] if source else None,
                   'terminals':device['terminals'],'parameters':parameters,
                   'native_statement':device['statement'],
                   'source':{'netlist':netlist['source'],'line':device['line'],
                             'xml':snapshot['source'] if source else None,
                             'terminal_mapping':device.get('terminal_source')},
                   'model':device.get('model'),'definition_scope':device.get('definition_scope'),
                   'encrypted':bool(source and source.get('encrypted')),
                   'model_protected':bool(source and source['model_protected'])}
        if source:
            component['layout']={k:source[k] for k in ('position','orientation','mirrored')}
            component['symbol_pins']=source['pins']
            component['connection_points']=source.get('connection_points')
        else:
            unresolved.append(key)
        components.append(component)
    nets={node:[{**term,'component':aliases[term['device']]} for term in terms]
          for node,terms in netlist['nets'].items()}
    return {'source_xml':snapshot['source'],'source_netlist':netlist['source'],
            'xml_sha256':snapshot['xml_sha256'],'components':components,'nets':nets,
            'subcircuits':netlist['subcircuits'],
            'native_source_expansions':netlist.get('native_source_expansions',[]),
            'annotations':snapshot.get('annotations',[]),
            'coverage':{**netlist['coverage'],'unparsed':netlist['diagnostics'],
                        'netlist_devices_without_native_identity':unresolved},
            'note':'Connectivity is topology, not instantaneous current flow. Pin numbers here are model terminals, not package pad numbers.'}


def load_view(snapshot_path):
    data=json.loads(Path(snapshot_path).read_text(encoding='utf-8-sig'))
    if 'structuredContent' in data:
        data=data['structuredContent']
    if 'source_netlist' in data:
        return data
    if 'connectivity' not in data:
        raise ValueError('This is an XML-only snapshot of an unfinished circuit. Read components/parameters directly, or export a connected circuit with include_connectivity=True before network queries.')
    # Refresh an older snapshot from its immutable original XML/netlist files.
    from service import describe_xml
    return build_view(describe_xml(data['source'],data['connectivity']['source']))


def query(view, component=None, net=None, pin=None, depth=0, hierarchy=None, limit=80):
    if depth<0 or depth>4 or limit<1 or limit>500:
        raise ValueError('depth must be 0..4; limit must be 1..500')
    if hierarchy:
        matches=[s for s in view['subcircuits'] if s['scope'].casefold()==hierarchy.casefold()]
        if len(matches)!=1:
            raise ValueError('Choose an available subcircuit scope: '+str([s['scope'] for s in view['subcircuits']]))
        scope=matches[0]
        if len(scope['devices'])>limit:
            return {'scope':hierarchy,'device_count':len(scope['devices']),
                    'devices':scope['devices'][:limit],'truncated':True,'unparsed':scope['diagnostics']}
        return scope
    by_ref={c['reference'].casefold():c for c in view['components']}
    by_name={c['netlist_name'].casefold():c for c in view['components']}
    selected=set(); nodes=set()
    if component:
        c=by_ref.get(component.casefold()) or by_name.get(component.casefold())
        if not c:
            raise ValueError('Component not found: '+component)
        selected.add(c['reference'])
        terms=c['terminals']
        if pin:
            terms=[t for t in terms if t['name'].casefold()==pin.casefold() or str(t['index'])==pin]
            if len(terms)!=1:
                raise ValueError('Choose a unique model terminal name or index: '+str(c['terminals']))
        nodes.update(t['node'] for t in terms)
    elif pin:
        raise ValueError('pin requires component')
    if net:
        matches=[n for n in view['nets'] if n.casefold()==net.casefold() or (net.upper()=='GND' and n=='0')]
        if len(matches)!=1:
            raise ValueError('Network not found or ambiguous: '+net)
        nodes.add(matches[0])
    if not component and not net:
        selected={c['reference'] for c in view['components']}
        nodes=set(view['nets'])
    # First show all incident components; additional depth crosses components.
    for level in range(depth+1):
        selected.update(t['component'] for n in nodes for t in view['nets'].get(n,[]))
        if level<depth:
            nodes.update(t['node'] for name in selected for t in by_ref[name.casefold()]['terminals'])
    components=[c for c in view['components'] if c['reference'] in selected]
    result={'components':components[:limit], 'nets':{n:view['nets'][n] for n in sorted(nodes)},
            'coverage':view['coverage'],'total_selected_components':len(components),
            'truncated':len(components)>limit,'source_xml':view['source_xml'],
            'source_netlist':view['source_netlist'],'note':view['note']}
    return result


def render_text(view):
    lines=['TINA circuit: '+view['source_xml'],
           f"Electrical instances: {len(view['components'])}; networks: {len(view['nets'])}"]
    for c in view['components']:
        scalar=[f"{p['name']}={p['value']} {p.get('unit','')}" for p in c['parameters']
                if p['idx']=='0' and 'value' in p]
        pins=', '.join(f"{t['name']}={t['node']}" for t in c['terminals'])
        lines.append(f"{c['reference']} [{c['type']}] {'; '.join(scalar)} | {pins}")
    lines.append('\nNetworks:')
    for name,terms in view['nets'].items():
        lines.append(name+': '+', '.join(f"{t['component']}.{t['pin']}" for t in terms))
    lines.append('\nCoverage: '+json.dumps(view['coverage'],ensure_ascii=False))
    lines.append(view['note'])
    return '\n'.join(lines)+'\n'


def compare(before, after):
    left={c['reference']:c for c in before['components']}
    right={c['reference']:c for c in after['components']}
    common=left.keys()&right.keys(); changes=[]
    for ref in sorted(common):
        a,b=left[ref],right[ref]
        for field in ('parameters','model','layout'):
            if a.get(field)!=b.get(field):
                changes.append({'component':ref,'field':field,'before':a.get(field),'after':b.get(field)})
    def signature(view):
        return connection_signature({'nets':{n:[{'device':t['component'],'terminal':t['terminal']} for t in terms]
                                             for n,terms in view['nets'].items()}})
    a=set(signature(before));b=set(signature(after))
    return {'added_components':sorted(right.keys()-left.keys()),'removed_components':sorted(left.keys()-right.keys()),
            'changes':changes,'connections_equal':a==b,
            'removed_connection_groups':sorted(a-b),'added_connection_groups':sorted(b-a),
            'coverage_before':before['coverage'],'coverage_after':after['coverage']}
