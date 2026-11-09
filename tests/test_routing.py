import unittest
from pathlib import Path
from schematic import Schematic
from routing import endpoint,covered,validate_points


class RoutingTests(unittest.TestCase):
    def test_native_parameter_readback_pin_names(self):
        s=Schematic(Path(__file__).resolve().parents[1]/'plugins/tina-bridge/server/assets/primitives.xml')
        c=next(c for c in s.root.findall('circuit/component') if c.get('typeid')=='10')
        name=c.get('id')
        self.assertEqual(endpoint(s,{'component':name,'pin':'1'}),endpoint(s,{'component':name,'pin':'+'}))
        self.assertEqual(endpoint(s,{'component':name,'pin':'2'}),endpoint(s,{'component':name,'pin':'-'}))
        # Same two-terminal symbol geometry and netlist A/K convention.
        c.set('typeid','23')
        self.assertEqual(endpoint(s,{'component':name,'pin':'1'}),endpoint(s,{'component':name,'pin':'A'}))
        self.assertEqual(endpoint(s,{'component':name,'pin':'2'}),endpoint(s,{'component':name,'pin':'K'}))

    def test_empty_degenerate_and_diagonal_routes_rejected(self):
        for points in ([],[[0,0]],[[0,0],[0,0]],[[0,0],[8,8]]):
            with self.subTest(points=points),self.assertRaises(ValueError):validate_points(points)

    def test_wire_coverage_allows_native_segment_merge_but_not_gaps(self):
        self.assertTrue(covered([[0,0],[40,0]],[{'points':'0,0,16,0'},{'points':'16,0,40,0'}]))
        self.assertFalse(covered([[0,0],[40,0]],[{'points':'0,0,16,0'},{'points':'24,0,40,0'}]))
        self.assertFalse(covered([[0,0],[40,0]],[{'points':'0,8,40,8'}]))

    def test_native_repeated_vertices_are_valid_for_removal_check(self):
        points=[[1072,256],[1072,256],[1008,256]]
        self.assertTrue(covered(points,[{'points':'1072,256,1008,256'}]))
        self.assertFalse(covered(points,[]))


if __name__=='__main__':unittest.main()
