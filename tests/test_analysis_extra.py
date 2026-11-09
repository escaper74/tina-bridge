"""Boundaries that prevent native noise/Fourier exports being misrepresented."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analysis_extra import start_noise,read_output_noise,export_text_diagrams,poll_fourier
from results import read_results


class ExtraAnalysisTests(unittest.TestCase):
    def test_unsupported_noise_transforms_rejected_before_ui(self):
        for outputs in (['input'],['total'],['snr'],['output','input'],[]):
            with self.subTest(outputs=outputs),self.assertRaises(ValueError):
                start_noise(None,outputs=outputs)

    def test_noise_auxiliary_column_is_not_reported_as_physical_phase(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'noise.txt'
            path.write_text('*Frequency\tVOUT-abs\tVOUT-phase (deg)\n10\t4e-9\t2e-7\n100\t3e-9\t2e-7\n',encoding='utf-8')
            result=read_output_noise(path)
            self.assertEqual(['VOUT-abs'],[s['name'] for s in result['signals']])
            self.assertEqual([4e-9,3e-9],result['signals'][0]['y'])
            self.assertEqual(['VOUT-phase (deg)'],result['auxiliary_native_columns'])
            self.assertEqual(2,len(read_results(path)['signals']))

    def test_fourier_coordinate_placeholders_are_not_coefficients(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fourier.txt'
            path.write_text('Fundamental 100\t\n0\t0\n1\t0\n',encoding='utf-8')
            with self.assertRaises(ValueError):read_results(path)
            with self.assertRaises(ValueError):read_output_noise(path)

    def test_fourier_hidden_progress_still_blocks_draw(self):
        class Calculating:
            pid=123
            def visible(self):
                return [{'cls':'TSchematicEditor','title':'RC'},
                        {'cls':'THarmonicDistorsionDlg','enabled':True}]
            def analysis_state(self):return {'running':False,'titles':['TINA']}
        with patch('analysis_extra.windows',return_value=[{'cls':'TPercentageDlg','visible':False}]):
            self.assertEqual('running',poll_fourier(Calculating(),{'pid':123,'editor':'RC'})['status'])

    def test_fourier_transient_page_alone_is_not_completion(self):
        class Preparing:
            pid=123
            def visible(self):return [{'cls':'TSchematicEditor','title':'RC'}]
            def analysis_state(self):return {'running':False,'titles':['TINA']}
            def poll_run(self,job):return {'status':'succeeded','results':[{'title':'TR result1'}]}
        with patch('analysis_extra.windows',return_value=[]):
            self.assertEqual('running',poll_fourier(Preparing(),{'pid':123,'editor':'RC'})['status'])

    def test_multi_coordinate_export_completes_successive_dialogs(self):
        class NativeExport:
            def __init__(self):self.files=[];self.menu_count=0
            def menu(self,*args):self.menu_count+=1
            def file_dialog(self,path):
                path.write_text('native diagram',encoding='utf-8');self.files.append(path)
                return {'path':str(path),'bytes':path.stat().st_size}
            def visible(self):
                return ([{'cls':'#32770','title':'Save diagram 2'}] if len(self.files)==1 else
                        [{'cls':'TDFWindow','enabled':True}])
            def wait(self,predicate,description):
                for _ in range(20):
                    answer=predicate()
                    if answer:return answer
                raise AssertionError(description)
        ticks=iter(i*.2 for i in range(40))
        with tempfile.TemporaryDirectory() as folder,patch('analysis_extra.time.monotonic',side_effect=lambda:next(ticks)):
            tina=NativeExport();result=export_text_diagrams(tina,Path(folder)/'result.txt')
            self.assertEqual(1,tina.menu_count)
            self.assertEqual(['result.txt','result-diagram-2.txt'],[Path(p['path']).name for p in result])
            self.assertEqual('TDFWindow',tina.visible()[0]['cls'])


if __name__=='__main__':unittest.main()
