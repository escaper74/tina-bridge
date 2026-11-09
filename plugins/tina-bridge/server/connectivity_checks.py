"""Postconditions for native edits that only add wiring/components or change values.

Use actual exported solver connectivity. Drawing coverage cannot establish that a
native wire bend or probe is electrically joined. Numeric node renumbering and
intentional merges are allowed; old terminals, ground and named outputs remain
accounted for. This is not a check for layout, deletion or rename operations.
"""
import json


class ConnectivityError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('Native additive connectivity check failed: '+
                         json.dumps(report['errors'], ensure_ascii=False))


def check_additive_connectivity(before, after, *, raise_on_error=True):
    """Require every old net's terminals to remain together in the native netlist.

    Inputs are the ``connectivity`` dictionaries returned by read_circuit. The
    report includes old-to-new node mapping and merges, not a claim that an added
    circuit meets its electrical specification. Missing/incomplete native
    connectivity is an error rather than a successful empty comparison.
    """
    errors = []
    for side, data in [('before', before), ('after', after)]:
        if 'nets' not in data or data.get('coverage', {}).get('top_level_complete') is False:
            errors.append({'code':'incomplete_connectivity', 'side':side,
                           'source':data.get('source')})
    report = {'passed':False, 'errors':errors, 'node_mapping':{}, 'merges':[],
              'named_node_merges':[], 'before_source':before.get('source'),
              'after_source':after.get('source')}
    if errors:
        if raise_on_error:
            raise ConnectivityError(report)
        return report

    def key(term):
        return term['device'].upper(), term['terminal']

    # Values are sets so a duplicate device name cannot silently overwrite a pin.
    locations = {}
    after_names = {}
    for node, terms in after['nets'].items():
        canonical = node.upper()
        after_names[canonical] = node
        for term in terms:
            locations.setdefault(key(term), set()).add(canonical)
    mappings = {}
    for node, terms in before['nets'].items():
        destinations = {}
        missing = []
        for term in terms:
            found = locations.get(key(term), set())
            if not found:
                missing.append({'device':term['device'], 'terminal':term['terminal'],
                                'pin':term.get('pin')})
            for destination in found:
                destinations.setdefault(destination, []).append(
                    {'device':term['device'], 'terminal':term['terminal']})
        if missing:
            errors.append({'code':'missing_terminal', 'before_node':node, 'terminals':missing})
        if len(destinations)>1:
            errors.append({'code':'net_split', 'before_node':node,
                           'after_groups':{after_names[n]:v for n,v in destinations.items()}})
        if node == '0' and set(destinations) != {'0'}:
            errors.append({'code':'ground_lost', 'before_node':'0',
                           'after_nodes':[after_names[n] for n in destinations]})
        if not missing and len(destinations)==1:
            mappings[node] = next(iter(destinations))
            report['node_mapping'][node] = after_names[mappings[node]]

    old_names = {node.upper():node for node in before['nets'] if not node.isdigit()}
    for node, destination in mappings.items():
        if node.isdigit() or node.upper()==destination:
            continue
        # A short to an old named net may select that net's name. Require its old
        # terminals to have joined too, so a coincidental name change is not a merge.
        merged_old_name = old_names.get(destination)
        if destination == '0' or (merged_old_name is not None and
                                 mappings.get(merged_old_name)==destination):
            report['named_node_merges'].append({'before_node':node,
                                               'after_node':after_names[destination]})
        else:
            errors.append({'code':'named_node_lost' if destination.isdigit() else 'named_node_changed',
                           'before_node':node, 'after_node':after_names[destination]})

    by_destination = {}
    for node, destination in mappings.items():
        by_destination.setdefault(destination, []).append(node)
    report['merges'] = [{'before_nodes':nodes, 'after_node':after_names[destination]}
                        for destination,nodes in by_destination.items() if len(nodes)>1]
    report['checked_old_nets'] = len(before['nets'])
    report['checked_old_terminals'] = sum(len(terms) for terms in before['nets'].values())
    report['passed'] = not errors
    if errors and raise_on_error:
        raise ConnectivityError(report)
    return report
