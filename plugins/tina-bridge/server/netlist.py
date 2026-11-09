"""Read TINA SPICE exports with native statements, public interfaces and hierarchy.

Connections come from the solver netlist, never from crossing drawing lines.
Unknown syntax is returned. Encrypted models remain opaque.
"""
import re
from pathlib import Path


def logical_lines(text):
    result = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('*'):
            continue
        line = line.split(';', 1)[0].strip()
        if not line:
            continue
        if line.startswith('+') and result:
            result[-1]['statement'] += ' ' + line[1:].strip()
        else:
            result.append({'line':number, 'statement':line})
    return result


def subckt_header(statement):
    tokens = statement.split()
    if len(tokens) < 2 or tokens[0].upper() != '.SUBCKT':
        return None
    pins = []
    for token in tokens[2:]:
        if '=' in token or token.upper() in ('PARAMS:', 'PARAMETERS:'):
            break
        pins.append(token)
    return {'name':tokens[1], 'pins':pins, 'statement':statement}


TERMINALS = {
    'R':['1','2'], 'C':['+','-'], 'L':['1','2'],
    'V':['+','-'], 'I':['+','-'], 'D':['A','K'],
    'M':['D','G','S','B'], 'J':['D','G','S'],
    'E':['+','-','control+','control-'], 'G':['+','-','control+','control-'],
    'F':['+','-'], 'H':['+','-'], 'B':['+','-'],
    'S':['+','-','control+','control-'], 'W':['+','-'],
    'T':['port1+','port1-','port2+','port2-'],
    'O':['port1+','port1-','port2+','port2-'],
}


def read_netlist(path, macro_pins=None):
    """macro_pins maps native references to counts or public interface metadata."""
    hints = {k.upper():v for k,v in (macro_pins or {}).items()}
    raw = Path(path).read_bytes()
    try:
        text = raw.decode('utf-8-sig'); encoding = 'utf-8-sig'
    except UnicodeDecodeError:
        text = raw.decode('gb18030'); encoding = 'gb18030'
    scopes = {'':{'lines':[], 'directives':[]}}; stack = ['']
    definitions = {}; model_types = {}
    for entry in logical_lines(text):
        line = entry['statement']; header = subckt_header(line)
        if header:
            key = '/'.join(x for x in [stack[-1],header['name']] if x)
            definitions[key.upper()] = {**header,'scope':key,'line':entry['line']}
            scopes[key] = {'lines':[], 'directives':[]}; stack.append(key)
        elif re.match(r'(?i)^\.ENDS\b', line):
            if len(stack) > 1:
                stack.pop()
            else:
                scopes['']['lines'].append(entry)
        elif line.startswith('.'):
            scopes[stack[-1]]['directives'].append(line)
            m = re.match(r'(?i)^\.MODEL\s+(\S+)\s+(\w+)',line)
            if m:
                model_types[(stack[-1].upper(),m[1].upper())] = m[2].upper()
        elif 'Netlist Editor format)' not in line:
            scopes[stack[-1]]['lines'].append(entry)

    def definition(name, scope):
        while True:
            key = '/'.join(x for x in [scope,name] if x).upper()
            if key in definitions:
                return definitions[key]
            if not scope:
                return None
            scope = scope.rpartition('/')[0]

    def model_kind(name, scope):
        while True:
            value = model_types.get((scope.upper(),name.upper()))
            if value or not scope:
                return value
            scope = scope.rpartition('/')[0]

    def parse(entry, scope):
        line = entry['statement']; tokens = line.split()
        name = tokens[0]; prefix = name[0].upper()
        labels = list(TERMINALS[prefix]) if prefix in TERMINALS else None
        provenance = 'SPICE terminal order'; extra = {}
        if prefix == 'X':
            hint = hints.get(name[1:].upper()) if not scope else None
            if isinstance(hint, int):
                labels = [str(i) for i in range(1,hint+1)]
                provenance = 'native XML pin count'
            elif isinstance(hint, dict):
                labels = hint.get('terminal_names') or hint.get('pins')
                if labels:
                    labels = list(labels)
                    provenance = hint.get('source','native XML public interface')
            candidates = []
            for index, token in enumerate(tokens[1:],1):
                d = definition(token,scope)
                if d and len(d['pins']) == index-1:
                    candidates.append((index,d))
            if len(candidates) == 1:
                index,d = candidates[0]
                if labels and len(labels) != len(d['pins']):
                    return None, 'XML interface and .SUBCKT pin counts differ'
                if not labels:
                    labels = d['pins']; provenance = 'native netlist .SUBCKT header'
                extra.update(formal_pins=d['pins'],definition_scope=d['scope'])
            if not labels:
                return None, 'no verified subcircuit interface'
            if len(tokens) <= len(labels)+1:
                return None, 'missing subcircuit model name'
            extra['model'] = tokens[len(labels)+1]
        elif prefix == 'Q':
            matches = [i for i in (4,5) if len(tokens)>i and model_kind(tokens[i],scope) in ('NPN','PNP')]
            if len(matches) != 1:
                return None, 'BJT node count requires a declared NPN/PNP model'
            labels = ['C','B','E'] + (['S'] if matches[0]==5 else [])
        elif prefix == 'K':
            if len(tokens)<4:
                return None,'invalid mutual coupling statement'
            return {**entry,'name':name,'nodes':[],'terminals':[],
                    'referenced_devices':tokens[1:3],'parameters':' '.join(tokens[3:]),
                    'kind':'mutual_coupling','scope':scope},None
        elif prefix in ('E','G') and len(tokens)>3:
            if tokens[3].upper().startswith(('VALUE','TABLE','LAPLACE')):
                labels = ['+','-']; extra['control_expression'] = ' '.join(tokens[3:])
            elif tokens[3].upper().startswith('POLY'):
                return None,'POLY controlled-source terminals need explicit parsing'
        if not labels or len(tokens)<=len(labels):
            return None,'unsupported or incomplete device statement'
        count = len(labels); nodes = tokens[1:count+1]
        if prefix in ('D','M','J','Q') and len(tokens)>count+1:
            extra['model'] = tokens[count+1]
        return {**entry,'name':name,'nodes':nodes,'parameters':' '.join(tokens[count+1:]),
                'kind':prefix,'scope':scope,'terminal_source':provenance,
                'terminals':[{'index':i,'name':label,'node':node}
                             for i,(label,node) in enumerate(zip(labels,nodes),1)],**extra},None

    def build(scope):
        devices=[]; unknown=[]; diagnostics=[]; nets={}
        for entry in scopes[scope]['lines']:
            dev, reason = parse(entry,scope)
            if dev is None:
                unknown.append(entry['statement']); diagnostics.append({**entry,'reason':reason})
                continue
            devices.append(dev)
            for term in dev['terminals']:
                nets.setdefault(term['node'],[]).append({'device':dev['name'],
                    'terminal':term['index'],'pin':term['name']})
        return {'devices':devices,'nets':nets,'directives':scopes[scope]['directives'],
                'unparsed':unknown,'diagnostics':diagnostics}

    top = build('')
    return {'source':str(path),'encoding':encoding,**top,
            'subcircuits':[{**d,**build(d['scope'])} for d in definitions.values()],
            'coverage':{'top_level_complete':not top['unparsed'],
                        'encrypted_model_internals':'opaque; public interfaces only'}}


def connection_signature(netlist):
    """Numeric nodes may be renumbered by import; compare terminal partitions."""
    groups = []
    for node,terms in netlist['nets'].items():
        terminals = sorted((t['device'].upper(),t['terminal']) for t in terms)
        if node == '0':
            terminals.append(('GROUND',0))
        elif not node.isdigit():
            terminals.append(('NAMED_NODE:'+node.upper(),0))
        groups.append(tuple(sorted(terminals)))
    return tuple(sorted(groups))
