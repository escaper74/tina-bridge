import math
from pathlib import Path
import tempfile
import unittest
from metrics import waveform_metrics,window,crossings,measure_file


def signal(x,y):
    return {'name':'VOUT','axis_label':'Time (s)','x':x,'y':y}


class MetricsTests(unittest.TestCase):
    def test_nonuniform_linear_ramp_integrals(self):
        result=waveform_metrics(signal([0,.01,.2,1],[0,.01,.2,1]))
        self.assertAlmostEqual(.5,result['mean'])
        self.assertAlmostEqual(math.sqrt(1/3),result['rms'])
        self.assertAlmostEqual(math.sqrt(1/12),result['ac_rms'])
        self.assertEqual(1,result['peak_to_peak'])

    def test_clipped_interval_with_no_native_interior_sample(self):
        result=waveform_metrics(signal([0,1],[0,10]),start=.2,end=.8)
        self.assertEqual([.2,.8],result['interpolated_boundaries'])
        self.assertEqual(0,result['native_samples'])
        self.assertAlmostEqual(5,result['mean'])
        self.assertAlmostEqual(math.sqrt(28),result['rms'])

    def test_duplicate_times_are_zero_duration_jumps(self):
        result=waveform_metrics(signal([0,1,1,2],[0,0,2,2]))
        self.assertEqual(1,result['mean'])
        self.assertAlmostEqual(math.sqrt(2),result['rms'])

    def test_no_extrapolation(self):
        with self.assertRaises(ValueError):window(signal([0,1],[0,1]),-.1,.5)
        with self.assertRaises(ValueError):window(signal([0,1],[0,1]),.5,.5)

    def test_settling_uses_last_band_entry(self):
        result=waveform_metrics(signal([0,1,2,3,4],[0,1.1,1,1.04,1]),target=1,absolute_band=.02)
        self.assertAlmostEqual(3.5,result['response']['settling_axis_value'])
        self.assertAlmostEqual(10,result['response']['overshoot_percent'])
        self.assertEqual(4,result['response']['observed_until'])

    def test_unsettled_and_negative_step(self):
        r=waveform_metrics(signal([0,1,2],[0,-1.2,-1.1]),target=-1,absolute_band=.02)
        self.assertFalse(r['response']['observed_settled'])
        self.assertIsNone(r['response']['settling_duration'])
        self.assertAlmostEqual(20,r['response']['overshoot_percent'])
        with self.assertRaises(ValueError):waveform_metrics(signal([0,1],[1,0]),target=0)

    def test_log_crossing_and_plateau_are_explicit(self):
        r=crossings(signal([10,1000],[20,-20]),0,'log')
        self.assertAlmostEqual(100,r['crossings'][0]['x'])
        self.assertEqual('falling',r['crossings'][0]['direction'])
        r=crossings(signal([0,1,2,3,4],[-1,0,0,0,1]),0)
        self.assertEqual([],r['crossings'])
        self.assertEqual([{'start':1,'end':3}],r['plateaus'])

    def test_exact_touch_not_counted_twice(self):
        r=crossings(signal([0,1,2],[1,0,1]),0)
        self.assertEqual([{'x':1,'direction':'touch','native_sample':True}],r['crossings'])

    def test_native_export_name_ambiguity_and_operating_point_units(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'wave.txt'
            p.write_text('*Time (s)\tVOUT\n0\t0\n1\t1\n*Time (s)\tVOUT\n0\t2\n1\t4\n',encoding='utf-8')
            with self.assertRaises(ValueError):measure_file(p,'VOUT')
            self.assertEqual(3,measure_file(p,'VOUT',block=1)['mean'])
            p=Path(folder)/'op.txt';p.write_text('Nodes    Values\nVOUT                  8V\nI_R1[1,VOUT]          -4mA\n',encoding='utf-8')
            r=measure_file(p,'I_R1[1,VOUT]')
            self.assertEqual(-.004,r['value']);self.assertEqual('A',r['unit'])
            with self.assertRaises(ValueError):measure_file(p,'VOUT',start=0)


if __name__=='__main__':unittest.main()
