import unittest
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET
from waveforms import validate_request,state,matches,restore_after_xml_export


class WaveformTests(unittest.TestCase):
    def test_numeric_units_and_required_fields(self):
        r=validate_request('square',{'amplitude':'2.5','frequency':'20k','rise_fall':'100n'},'2.5')
        self.assertEqual(r['parameters']['frequency'],'20k')
        with self.assertRaises(ValueError):validate_request('square',{'amplitude':'2.5','frequency':'20k'})
        with self.assertRaises(ValueError):validate_request('pulse',{'amplitude':'1','width':'0'})

    def test_pwl_retains_steps_but_rejects_backwards_time(self):
        self.assertEqual(validate_request('pwl',{'text':' 0 0\r\n1m 0\r\n1m 5 '})['parameters']['text'],'0 0\n1m 0\n1m 5')
        for value in ('0 0 1m','0 0 1m 1 100u 2','0 0 nan 1','R=1m'):
            with self.subTest(value=value),self.assertRaises(ValueError):validate_request('pwl',{'text':value})

    def test_single_pulse_does_not_accept_pwm_fields(self):
        with self.assertRaises(ValueError):validate_request('pulse',{'amplitude':'1','width':'1m','frequency':'100'})

    def test_unknown_waveform_is_not_misreported(self):
        c=ET.fromstring('<component typeid="16"><parameter idx="0" value="0"/><parameter idx="1" value="三角波"/></component>')
        self.assertIsNone(state(c)['waveform'])

    def test_native_sine_mapping_and_dc_preservation(self):
        c=ET.fromstring('<component typeid="16"><parameter idx="0" value="500m"/><parameter idx="1" value="正弦波"><detail type="正弦波"><parameter idx="0" value="2"/><parameter idx="1" value="100"/><parameter idx="2" value="30"/></detail></parameter></component>')
        actual=state(c);request=validate_request('sine',{'amplitude':'2','frequency':'100','phase':'30'})
        self.assertTrue(matches(actual,request,'0.5'))
        self.assertFalse(matches(actual,request,'1'))
        request['waveform']='square'
        self.assertFalse(matches(actual,request,'0.5'))

    def test_export_repair_only_touches_top_level_native_generator(self):
        top='<component id="top" typeid="16"><parameter idx="0" value="0"/><parameter idx="1" value="正弦波"><detail type="正弦波"><parameter idx="0" value="1"/><parameter idx="1" value="50"/><parameter idx="2" value="30"/></detail></parameter><image><label textroot="VG1"/></image></component>'
        root=ET.fromstring('<schematic><circuit>'+top+'<component id="macro" typeid="16" macrotype="1"/></circuit><subcircuit>'+top.replace('id="top"','id="internal"')+'</subcircuit></schematic>')
        actual=state(root.find('circuit/component'))
        with patch('schematic.Schematic',return_value=SimpleNamespace(root=root)),patch('waveforms.configure') as write,patch('waveforms.inspect_controls',return_value=actual):
            repaired=restore_after_xml_export(None,'unused.xml')
            self.assertEqual([call.args[1].get('id') for call in write.call_args_list],['top'])
            self.assertEqual(repaired[0]['native_readback']['parameters']['phase'],'30')


if __name__=='__main__':unittest.main()
