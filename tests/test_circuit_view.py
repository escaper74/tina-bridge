"""Parser contracts that affect connectivity; no Windows GUI needed."""
import tempfile
import unittest
from pathlib import Path
from netlist import read_netlist,connection_signature
from circuit_view import scalar_value


class NetlistTests(unittest.TestCase):
    def parse(self,text,hints=None):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'circuit.cir';p.write_text(text,encoding='utf-8')
            return read_netlist(p,hints)

    def test_macro_public_header_and_hierarchy(self):
        n=self.parse('XU1 a b 0 CHIP\nXC1 b 0 CAP P=2\n.SUBCKT CAP 1 2 PARAMS: P=1\nC1 1 2 1u\n.ENDS\n',
                     {'U1':{'terminal_names':['IN','OUT','GND'],'source':'public header'}})
        self.assertEqual([],n['unparsed'])
        self.assertEqual(['a','b','0'],n['devices'][0]['nodes'])
        self.assertEqual('OUT',n['nets']['b'][0]['pin'])
        self.assertEqual('CAP P=2',n['devices'][1]['parameters'])
        self.assertEqual(1,len(n['subcircuits'][0]['devices']))
        self.assertNotIn('1',n['nets'])

    def test_bjt_substrate_and_coupling(self):
        n=self.parse('Q1 c b e NMOD\nQ2 c b e s NMOD\n.MODEL NMOD NPN(BF=100)\nK1 L1 L2 .99\nL1 a 0 1m\nL2 b 0 1m')
        self.assertEqual([],n['unparsed'])
        self.assertEqual(['C','B','E','S'],[p['name'] for p in n['devices'][1]['terminals']])
        self.assertNotIn('L1',n['nets'])
        self.assertEqual(['L1','L2'],n['devices'][2]['referenced_devices'])

    def test_continuation_comments_and_unknown(self):
        n=self.parse('V1 a 0 PWL\n+ (0 0) (1m 1) ; source\nZ99 a b anything\nXU1 a b MISSING')
        self.assertIn('(1m 1)',n['devices'][0]['parameters'])
        self.assertEqual(2,len(n['unparsed']))
        self.assertFalse(n['coverage']['top_level_complete'])

    def test_interface_mismatch_does_not_guess(self):
        n=self.parse('XU1 a b CKT\n.SUBCKT CKT 1 2\nR1 1 2 1k\n.ENDS',{'U1':3})
        self.assertEqual(1,len(n['unparsed']))

    def test_numeric_node_renumbering(self):
        a=self.parse('R1 IN 2 1k\nC1 2 0 1u')
        b=self.parse('R1 IN 9 2k\nC1 9 0 1u')
        c=self.parse('R1 IN 0 1k\nC1 9 0 1u')
        self.assertEqual(connection_signature(a),connection_signature(b))
        self.assertNotEqual(connection_signature(a),connection_signature(c))

    def test_spice_units(self):
        self.assertEqual(.02,scalar_value('20M'))
        self.assertEqual(1e6,scalar_value('1MEG'))
        self.assertIsNone(scalar_value('{RBASE*2}'))


if __name__=='__main__':
    unittest.main()
