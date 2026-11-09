"""Structured TINA XML reading and external circuit edits.

Native XML carries macros verbatim. Model contents are read as opaque text and
hashed; editing a macro's internal parameters is deliberately not exposed.
"""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import uuid
from netlist import logical_lines, subckt_header


def xy(value):
    return [int(v) for v in value.split(',')]


class Schematic:
    def __init__(self, path):
        self.path = Path(path)
        self.root = ET.parse(self.path).getroot()
        if self.root.tag != 'schematic' or self.root.find('circuit') is None:
            raise ValueError('Not a TINA schematic XML document')

    def component(self, identifier):
        matches = []
        for c in self.root.findall('circuit/component'):
            label = c.find('image/label')
            if c.get('id') == identifier or (label is not None and label.get('textroot') == identifier):
                matches.append(c)
        if len(matches) != 1:
            raise ValueError(f'Expected one component {identifier}; found {len(matches)}')
        return matches[0]

    @staticmethod
    def public_interface(component):
        """Only plaintext interface declarations; never inspect encrypted payloads."""
        declarations = []
        for parameter in component.findall('parameter'):
            for entry in logical_lines(parameter.text or ''):
                if entry['statement'].upper().startswith('.SUBCKT '):
                    declarations.append(subckt_header(entry['statement']))
        declaration = next((d for d in declarations if d['name'].casefold() ==
                            component.get('type','').casefold()), None)
        if declaration is None and len(declarations)==1:
            declaration = declarations[0]
        explicit = component.get('pins','').split(',') if component.get('pins') else []
        if explicit:
            return {'terminal_names':explicit,'source':'native XML pins attribute',
                    'declaration':declaration}
        if declaration:
            return {'terminal_names':declaration['pins'],'source':'public .SUBCKT header in native XML',
                    'declaration':declaration}
        return None

    def model_hashes(self):
        result = {}
        definitions={c.get('id'):c for c in self.root.findall('subcircuits/circuit')}
        def canonical(element, names, instance=False, definition=False):
            attrs=dict(element.attrib)
            if instance:
                for key in ('id','position','orientation','mirrored','pininfos'):
                    attrs.pop(key,None)
            if definition:
                # TINA gives hierarchy definitions a new suffix in each process.
                # Resolve the actual definition; its session ID is not model data.
                attrs.pop('id',None)
            if attrs.get('subcircuit'):
                attrs['subcircuit']=names[attrs['subcircuit']]
            children=[]
            for child in element:
                if instance and child.tag=='image':
                    image=copy.deepcopy(child)
                    for label in image.findall('label'):
                        image.remove(label)
                    children.append(canonical(image,names))
                else:
                    children.append(canonical(child,names))
            return (element.tag,sorted(attrs.items()),(element.text or '').strip(),children)
        def referenced(circuit_id, seen):
            if circuit_id in seen:
                return
            if circuit_id not in definitions:
                raise ValueError(f'Macro refers to missing subcircuit definition: {circuit_id}')
            seen[circuit_id]=len(seen)
            for item in definitions[circuit_id].iter('component'):
                if item.get('subcircuit'):
                    referenced(item.get('subcircuit'),seen)
        for c in self.root.findall('circuit/component'):
            if c.get('macrotype') is not None:
                refs={}
                if c.get('subcircuit'):
                    referenced(c.get('subcircuit'),refs)
                payload={'instance_model':canonical(c,refs,True),
                         'subcircuits':[canonical(definitions[name],refs,definition=True) for name in refs]}
                result[c.get('id')] = hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        return result

    def describe(self):
        from geometry import terminal_positions
        comps = []
        for c in self.root.findall('circuit/component'):
            label = c.find('image/label')
            macro = c.get('macrotype') is not None
            try:
                connection_points=terminal_positions(c)
            except ValueError:
                connection_points=None
            params = []
            for p in c.findall('parameter'):
                item = dict(p.attrib)
                if p.text and p.text.strip():
                    item['content_bytes'] = len(p.text.encode())
                    item['content_sha256'] = hashlib.sha256(p.text.encode()).hexdigest()
                item['details'] = [{**d.attrib,'parameters':[
                    {**q.attrib,**({'text':q.text.strip()} if q.text and q.text.strip() else {})}
                    for q in d.findall('parameter')]} for d in p.findall('detail')]
                params.append(item)
            comps.append({'id':c.get('id'),'reference':label.get('textroot') if label is not None else '',
                          'type':c.get('type'),'type_id':c.get('typeid'),'position':xy(c.get('position')),
                          'orientation':int(c.get('orientation','0')),'mirrored':c.get('mirrored')=='1',
                          'model_protected':macro,'model_reference':c.get('homelib'),
                          'macro_interface':self.public_interface(c) if macro else None,
                          'encrypted':any(p.get('encrypted')=='1' for p in c.findall('parameter')),
                          'pin_order':c.get('pins','').split(',') if c.get('pins') else [],
                          'pins':[p.attrib for p in c.findall('image/pin')],
                          'connection_points':connection_points,
                          'parameters':params,'label':label.attrib if label is not None else None})
        return {'source':str(self.path),'components':comps,
                'wires':[{'index':i,**w.attrib} for i,w in enumerate(self.root.findall('circuit/wire'))],
                'annotations':[{'attributes':t.attrib,'text':t.text} for t in self.root.findall('circuit/text')],
                'analysis':{x.tag:{'attributes':x.attrib,'parameters':[p.attrib for p in x.findall('parameter')]}
                            for x in self.root.find('analysis') if x.tag!='mode'},
                'model_hashes':self.model_hashes(),
                'model_hash_scope':'Native macro structure and referenced subcircuits; instance placement/label excluded',
                'subcircuits':[{'id':c.get('id'),'component_count':len(c.findall('component')),
                                'wire_count':len(c.findall('wire'))} for c in self.root.findall('subcircuits/circuit')]}

    def copy_referenced_subcircuits(self, other, template):
        sources={c.get('id'):c for c in other.root.findall('subcircuits/circuit')}
        target=self.root.find('subcircuits')
        if target is None:
            target=ET.Element('subcircuits')
            self.root.insert(1,target)
        copied=set()
        def copy_one(name):
            if name in copied:
                return
            source=sources.get(name)
            if source is None:
                raise ValueError(f'Missing source subcircuit: {name}')
            existing=next((x for x in target if x.get('id')==name),None)
            if existing is not None and ET.tostring(existing)!=ET.tostring(source):
                raise ValueError(f'Different subcircuits share identifier {name}; choose an unambiguous source')
            if existing is None:
                target.append(copy.deepcopy(source))
            copied.add(name)
            for c in source.iter('component'):
                if c.get('subcircuit'):
                    copy_one(c.get('subcircuit'))
        if template.get('subcircuit'):
            copy_one(template.get('subcircuit'))
        return sorted(copied)

    def set_parameter(self, identifier, index, value):
        c = self.component(identifier)
        if c.get('macrotype') is not None:
            raise PermissionError('Factory macro internals are protected; only external circuit parameters may be edited')
        ps = [p for p in c.findall('parameter') if p.get('idx')==str(index)]
        if len(ps)!=1 or 'value' not in ps[0].attrib:
            raise ValueError('Parameter index not found or not a scalar value')
        before = ps[0].get('value')
        ps[0].set('value', str(value))
        return {'component':identifier,'parameter_index':index,'before':before,'after':str(value)}

    def set_detail_parameter(self, identifier, index, detail_type, detail_index, value):
        c=self.component(identifier)
        if c.get('macrotype') is not None:
            raise PermissionError('Factory macro internals are protected')
        matches=[q for p in c.findall('parameter') if p.get('idx')==str(index)
                 for d in p.findall('detail') if d.get('type')==detail_type
                 for q in d.findall('parameter') if q.get('idx')==str(detail_index)]
        if len(matches)!=1 or 'value' not in matches[0].attrib:
            raise ValueError('Detail parameter not found or not scalar')
        before=matches[0].get('value')
        matches[0].set('value',str(value))
        return {'component':identifier,'index':index,'detail':detail_type,'detail_index':detail_index,
                'before':before,'after':str(value)}

    def layout_component(self, identifier, position=None, orientation=None, mirrored=None):
        c=self.component(identifier)
        before={k:c.get(k) for k in ('position','orientation','mirrored')}
        if position is not None:
            if len(position)!=2:
                raise ValueError('Position must have two coordinates')
            old=xy(c.get('position'))
            lab=c.find('image/label')
            if lab is not None and lab.get('position'):
                lp=xy(lab.get('position'))
                lab.set('position',','.join(str(int(a+b-o)) for a,b,o in zip(lp,position,old)))
            c.set('position',','.join(str(int(v)) for v in position))
        if orientation is not None:
            if orientation%90:
                raise ValueError('Native component rotation must be a multiple of 90 degrees')
            c.set('orientation',str(int(orientation)%360))
        if mirrored is not None:
            c.set('mirrored','1' if mirrored else '0')
        return {'component':identifier,'before':before,'after':{k:c.get(k) for k in before},
                'wires':'unchanged; edit wire vertices explicitly when reconnecting'}

    def remove_component(self, identifier):
        c=self.component(identifier)
        result={'removed_id':c.get('id'),'wires':'unchanged'}
        self.root.find('circuit').remove(c)
        return result

    def remove_wire(self, index):
        wires=self.root.findall('circuit/wire')
        if not 0<=int(index)<len(wires):
            raise ValueError('Wire index outside current list')
        result=dict(wires[int(index)].attrib)
        self.root.find('circuit').remove(wires[int(index)])
        return result

    def write(self, path):
        p = Path(path)
        if p.exists():
            raise FileExistsError(p)
        self.root.tail = None
        ET.ElementTree(self.root).write(p,encoding='utf-8',xml_declaration=True)
        return str(p)

    def add_component(self, template, reference, position, orientation=0, parameters=None):
        if any(x['reference']==reference for x in self.describe()['components'] if reference):
            raise ValueError(f'Duplicate component reference: {reference}')
        c = copy.deepcopy(template)
        if len(position)!=2 or orientation%90:
            raise ValueError('Expected two coordinates and a multiple-of-90 rotation')
        c.set('id','T_'+uuid.uuid4().hex.upper())
        c.set('position',','.join(str(int(v)) for v in position))
        c.set('orientation',str(int(orientation)%360))
        c.set('mirrored','0')
        lab = c.find('image/label')
        if lab is None:
            raise ValueError('Native template has no label element')
        lab.set('textroot',reference)
        lab.set('text',reference)
        lab.set('position',f'{position[0]+12},{position[1]-20}')
        lab.set('orientation','0')
        self.root.find('circuit').append(c)
        for idx,value in (parameters or {}).items():
            self.set_parameter(c.get('id'),idx,value)
        return c.get('id')

    def add_wire(self, points, label=''):
        if len(points)<2:
            raise ValueError('A wire needs at least two vertices')
        for p in points:
            if len(p)!=2:
                raise ValueError('Expected x,y vertices')
        attrs = {'points':','.join(str(int(n)) for p in points for n in p),'label':label}
        ET.SubElement(self.root.find('circuit'),'wire',attrs)
        return attrs

    def set_analysis(self, kind, parameters):
        a=self.root.find('analysis/'+kind)
        if a is None:
            raise ValueError(f'Analysis configuration not present: {kind}')
        changes=[]
        for idx,value in parameters.items():
            ps=[p for p in a.findall('parameter') if p.get('idx')==str(idx)]
            if len(ps)!=1:
                raise ValueError(f'Analysis parameter {kind}/{idx} not found')
            changes.append({'index':idx,'before':ps[0].get('value'),'after':str(value)})
            ps[0].set('value',str(value))
        return changes
