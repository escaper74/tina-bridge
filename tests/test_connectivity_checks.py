"""Offline topology postconditions, including existing native TINA exports."""
import json
from pathlib import Path
import unittest

from connectivity_checks import ConnectivityError, check_additive_connectivity


def netlist(groups):
    return {'nets':{node:[{'device':device, 'terminal':pin} for device,pin in terms]
                    for node,terms in groups.items()},
            'coverage':{'top_level_complete':True}}


class ConnectivityTests(unittest.TestCase):
    def test_numeric_renumbering_and_new_components_are_allowed(self):
        before = netlist({'1':[('R1',1),('R2',1)], '0':[('R1',2),('R2',2)]})
        after = netlist({'7':[('R1',1),('R2',1),('R3',1)],
                         '0':[('R1',2),('R2',2),('R3',2)]})
        report = check_additive_connectivity(before,after)
        self.assertTrue(report['passed'])
        self.assertEqual({'1':'7','0':'0'},report['node_mapping'])

    def test_split_old_net_reports_affected_terminals(self):
        before = netlist({'VOUT':[('R1',1),('R2',1)]})
        after = netlist({'VOUT':[('R1',1)],'2':[('R2',1)]})
        with self.assertRaises(ConnectivityError) as caught:
            check_additive_connectivity(before,after)
        error = caught.exception.report['errors'][0]
        self.assertEqual('net_split',error['code'])
        self.assertEqual([{'device':'R2','terminal':1}],error['after_groups']['2'])

    def test_missing_component_terminal_is_not_an_allowed_merge(self):
        before = netlist({'1':[('R1',1),('R2',1)]})
        report = check_additive_connectivity(before,netlist({'1':[('R1',1)]}),raise_on_error=False)
        self.assertFalse(report['passed'])
        self.assertEqual('missing_terminal',report['errors'][0]['code'])
        self.assertEqual('R2',report['errors'][0]['terminals'][0]['device'])

    def test_ground_becoming_an_ordinary_node_is_rejected(self):
        before = netlist({'0':[('R1',2),('V1',2)]})
        after = netlist({'8':[('R1',2),('V1',2)]})
        report = check_additive_connectivity(before,after,raise_on_error=False)
        self.assertEqual('ground_lost',report['errors'][0]['code'])

    def test_named_output_disappearing_into_numeric_node_is_rejected(self):
        before = netlist({'VOUT':[('R1',1),('R2',1)]})
        after = netlist({'8':[('R1',1),('R2',1),('R3',1)]})
        report = check_additive_connectivity(before,after,raise_on_error=False)
        self.assertEqual([{'code':'named_node_lost','before_node':'VOUT','after_node':'8'}],report['errors'])

    def test_explicit_short_of_named_nets_is_reported_as_merge(self):
        before = netlist({'VOUT':[('R1',1)],'FB':[('R2',1)]})
        after = netlist({'FB':[('R1',1),('R2',1)]})
        report = check_additive_connectivity(before,after)
        self.assertEqual([{'before_nodes':['VOUT','FB'],'after_node':'FB'}],report['merges'])
        self.assertEqual([{'before_node':'VOUT','after_node':'FB'}],report['named_node_merges'])

    def test_named_net_grounding_is_allowed_but_explicit(self):
        before = netlist({'VOUT':[('R1',1)],'0':[('R1',2)]})
        report = check_additive_connectivity(before,netlist({'0':[('R1',1),('R1',2)]}))
        self.assertEqual([{'before_node':'VOUT','after_node':'0'}],report['named_node_merges'])

    def test_swapped_names_without_a_merge_are_rejected(self):
        before = netlist({'VOUT':[('R1',1)],'FB':[('R2',1)]})
        after = netlist({'FB':[('R1',1)],'VOUT':[('R2',1)]})
        report = check_additive_connectivity(before,after,raise_on_error=False)
        self.assertEqual(['named_node_changed','named_node_changed'],[e['code'] for e in report['errors']])

    def test_duplicate_device_terminal_cannot_silently_replace_its_net(self):
        before = netlist({'1':[('R1',1)]})
        after = netlist({'1':[('R1',1)],'2':[('r1',1)]})
        report = check_additive_connectivity(before,after,raise_on_error=False)
        self.assertEqual('net_split',report['errors'][0]['code'])

    def test_incomplete_native_netlist_does_not_claim_success(self):
        before = netlist({'1':[('R1',1)]})
        after = netlist({});after['coverage']['top_level_complete'] = False
        with self.assertRaises(ConnectivityError) as caught:
            check_additive_connectivity(before,after)
        self.assertEqual('incomplete_connectivity',caught.exception.report['errors'][0]['code'])


if __name__=='__main__':unittest.main()
