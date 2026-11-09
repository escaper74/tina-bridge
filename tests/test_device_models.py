"""Public-field boundaries and catalog-only selection, without opening TINA."""
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import device_models as dm


def component(type_id,mode='相对',macro=False):
    c=ET.Element('component',typeid=type_id)
    if macro:c.set('macrotype','2')
    image=ET.SubElement(c,'image');ET.SubElement(image,'label',textroot='TEST')
    diode=type_id in ('23','64')
    values={0:'existing_model',1:mode,2:'0',3:'1'} if diode else {0:'existing_model',1:'',2:mode,3:'0',4:'1',14:'1'}
    for index,value in values.items():ET.SubElement(c,'parameter',idx=str(index),value=value)
    return c


class DeviceModelTests(unittest.TestCase):
    def test_verified_public_fields_across_all_six_device_types(self):
        for type_id in ('23','64','87','88','89','90'):
            with self.subTest(type_id=type_id):
                fields=dm.public_fields(component(type_id))['fields']
                self.assertEqual(2 if type_id in ('23','64') else 3,fields['temperature_delta_C']['index'])
                if type_id in ('89','90'):
                    self.assertEqual(14,fields['multiplicity']['index'])
                    self.assertNotIn('area_factor',fields)
                else:
                    self.assertEqual(3 if type_id in ('23','64') else 4,fields['area_factor']['index'])

    def test_model_constants_cannot_be_requested_as_instance_fields(self):
        for name in ('IS','VTO','KP','BF','model','0'):
            with self.subTest(field=name),self.assertRaises(ValueError):
                dm.instance_change(component('89'),name,'2')

    def test_macro_and_unverified_device_types_are_rejected_before_ui(self):
        with self.assertRaises(ValueError):dm.public_fields(component('89',macro=True))
        with self.assertRaises(ValueError):dm.public_fields(component('57'))

    def test_temperature_offset_is_not_offered_for_absolute_mode(self):
        c=component('87',mode='绝对')
        self.assertNotIn('temperature_delta_C',dm.public_fields(c)['fields'])
        with self.assertRaises(ValueError):dm.instance_change(c,'temperature_delta_C','15')

    def test_nonfinite_or_nonpositive_instance_scales_are_rejected(self):
        for type_id,field in [('23','area_factor'),('89','multiplicity')]:
            for value in ('0','-1','nan','inf','-inf'):
                with self.subTest(type_id=type_id,value=value),self.assertRaises(ValueError):
                    dm.instance_change(component(type_id),field,value)
        with self.assertRaises(ValueError):dm.instance_change(component('87'),'temperature_delta_C','nan')

    def test_negative_temperature_offset_preserves_relative_meaning(self):
        change=dm.instance_change(component('87'),'temperature_delta_C','-12.5')
        self.assertEqual(3,change['index'])
        self.assertEqual('0',change['before'])
        self.assertEqual('-12.5',change['value'])
        self.assertEqual('degC',change['unit'])

    def test_unknown_model_cancels_both_dialogs_without_setting_any_field(self):
        state={'models':{'items':['1N4007']}}
        with patch.object(dm,'_property',return_value={'hwnd':1}), \
             patch.object(dm,'_catalog',return_value={'hwnd':2}), \
             patch.object(dm,'_catalog_state',return_value=(state,{'hwnd':3})), \
             patch.object(dm,'_close') as close,patch.object(dm,'key') as key:
            with self.assertRaises(ValueError):dm.select_model(object(),component('23'),'custom-model')
            self.assertEqual([2,1],[call.args[1]['hwnd'] for call in close.call_args_list])
            key.assert_not_called()


if __name__=='__main__':
    unittest.main()
