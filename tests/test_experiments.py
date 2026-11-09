"""Orchestration tests use an explicit fake; they do not claim native TINA validation."""
import json
from pathlib import Path
import tempfile
import unittest
from experiments import prepare_batch,advance_batch,batch_status,grid_cases,tolerance_cases,boundary_candidate,sensitivity_cases,sensitivity_estimate,close_completed_document,_lock


class FakeBackend:
    def __init__(self,folder,state=None):
        self.folder=Path(folder)
        self.state=state if state is not None else {'calls':[],'editor':'original','parameters':{'0':'27','30':'1u'},'starts':0,'polls':0,'creation_time':101}
    def identity(self,pid):
        return {'pid':pid,'exe':'test-only-fake.exe','creation_time':self.state['creation_time']}
    def editor(self,pid):return self.state['editor']
    def prepare(self,pid,baseline,operations,target):
        self.state['calls'].append(('prepare',pid,operations));Path(target).write_bytes(Path(baseline).read_bytes())
        self.state['editor']=Path(target).stem
        return {'saved':{'path':target},'checks':{'test_fake':True}}
    def configure(self,pid,parameters=None):
        if parameters:self.state['parameters'].update(parameters)
        self.state['calls'].append(('configure',dict(self.state['parameters'])))
        return {k:{'name':'test_parameter','value':v} for k,v in self.state['parameters'].items()}
    def start(self,pid,analysis):
        self.state['starts']+=1;self.state['polls']=0
        path=self.folder/f'fake-job-{self.state["starts"]}.json'
        path.write_text(json.dumps({'pid':pid,'analysis':analysis}),encoding='utf-8')
        self.state['calls'].append(('start',pid,analysis))
        return {'job_file':str(path)}
    def poll(self,job_file):
        self.state['polls']+=1
        if self.state['polls']==1:return {'status':'running'}
        output=self.folder/'fake-wave.txt';output.write_text('*Time (s)\tVOUT\n0\t0\n0.1\t0.1\n1\t1\n',encoding='utf-8')
        return {'status':'succeeded','text_path':str(output),'solver_parameters':self.configure(1)}
    def close_completed_case(self,pid,case):
        self.state['calls'].append(('close_completed',case['id']))
        return {'closed':True}


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.source=self.folder/'source.TSC';self.source.write_bytes(b'explicit fake native file')
        self.backend=FakeBackend(self.folder)
    def tearDown(self):self.temp.cleanup()
    def prepare(self,cases=None):
        return prepare_batch(self.source,self.folder/'batch',cases or [{'id':'a'}],
                             {'kind':'transient','settings':{'start':'0','end':'1','initial':'zero'}},
                             measurements=[{'signal':'VOUT'}])['manifest']
    def test_resume_new_client_polls_existing_job_and_never_restarts_completed_case(self):
        p=self.prepare([{'id':'a','solver_parameters':{'0':'80'}},{'id':'b'}])
        self.assertEqual({'ready':1,'pending':1},advance_batch(p,42,self.backend)['counts'])
        self.assertEqual({'running':1,'pending':1},advance_batch(p,42,self.backend)['counts'])
        new_client=FakeBackend(self.folder,self.backend.state)
        advance_batch(p,42,new_client)
        state=advance_batch(p,42,new_client)
        self.assertEqual({'succeeded':1,'pending':1},state['counts'])
        self.assertEqual(.5,state['cases'][0]['metrics'][0]['mean'])
        self.assertEqual(1,new_client.state['starts'])
        advance_batch(p,42,new_client);advance_batch(p,42,new_client)
        self.assertEqual('27',new_client.state['parameters']['0'])
        advance_batch(p,42,new_client);state=advance_batch(p,42,new_client)
        self.assertEqual('succeeded',state['status']);self.assertEqual(2,new_client.state['starts'])
        advance_batch(p,42,new_client);self.assertEqual(2,new_client.state['starts'])
        self.assertEqual(b'explicit fake native file',self.source.read_bytes())
    def test_pid_reuse_and_wrong_pid_do_not_dispatch(self):
        p=self.prepare();advance_batch(p,42,self.backend)
        count=len(self.backend.state['calls'])
        with self.assertRaises(ValueError):advance_batch(p,43,self.backend)
        self.backend.state['creation_time']=202
        with self.assertRaises(ValueError):advance_batch(p,42,self.backend)
        self.assertEqual(count,len(self.backend.state['calls']))
    def test_changed_active_document_is_not_run(self):
        p=self.prepare();advance_batch(p,42,self.backend)
        self.backend.state['editor']='unrelated user circuit'
        result=advance_batch(p,42,self.backend)
        self.assertEqual('attention',result['status']);self.assertEqual(0,self.backend.state['starts'])
        advance_batch(p,42,self.backend);self.assertEqual(0,self.backend.state['starts'])
    def test_baseline_is_frozen_and_modified_snapshot_is_rejected(self):
        p=self.prepare();self.source.write_bytes(b'user later changed original')
        self.assertEqual('ready',advance_batch(p,42,self.backend)['cases'][0]['status'])
        (Path(p).parent/'baseline.TSC').write_bytes(b'changed frozen copy')
        with self.assertRaises(ValueError):advance_batch(p,42,self.backend)
        self.assertEqual(0,self.backend.state['starts'])
    def test_interrupted_start_is_not_repeated(self):
        p=self.prepare();data=json.loads(Path(p).read_text(encoding='utf-8'))
        data['cases'][0]['status']='starting';Path(p).write_text(json.dumps(data),encoding='utf-8')
        result=advance_batch(p,42,self.backend)
        self.assertEqual('attention',result['status']);self.assertEqual([],self.backend.state['calls'])
    def test_measurement_failure_keeps_collected_native_result(self):
        p=self.prepare([{'id':'a','measurements':[{'signal':'missing'}]}])
        for _ in range(4):result=advance_batch(p,42,self.backend)
        self.assertEqual('collected',result['cases'][0]['status'])
        self.assertEqual('attention',result['status']);self.assertEqual(1,self.backend.state['starts'])
        advance_batch(p,42,self.backend);self.assertEqual(1,self.backend.state['starts'])
    def test_attention_during_poll_can_resume_only_the_same_recorded_job(self):
        p=self.prepare();advance_batch(p,42,self.backend);advance_batch(p,42,self.backend)
        poll=self.backend.poll
        self.backend.poll=lambda _: {'status':'attention','reason':'test dialog'}
        self.assertEqual('attention',advance_batch(p,42,self.backend)['status'])
        self.backend.poll=poll
        advance_batch(p,42,self.backend)
        self.assertEqual('succeeded',advance_batch(p,42,self.backend)['status'])
        self.assertEqual(1,self.backend.state['starts'])
    def test_missing_settings_are_rejected_before_artifacts(self):
        with self.assertRaises(ValueError):prepare_batch(self.source,self.folder/'bad',[{}],{'kind':'transient','settings':{'end':'1'}})
        self.assertFalse((self.folder/'bad').exists())
    def test_completed_case_closes_once_without_repeating_solve(self):
        p=self.prepare()
        for _ in range(5):result=advance_batch(p,42,self.backend)
        self.assertEqual('succeeded',result['status'])
        self.assertEqual([('close_completed','a')],[x for x in self.backend.state['calls'] if x[0]=='close_completed'])
        self.assertEqual(1,self.backend.state['starts'])
    def test_close_completed_false_keeps_tabs(self):
        p=prepare_batch(self.source,self.folder/'batch',[{'id':'a'}],
                        {'kind':'operating_point','settings':{}},close_completed=False)['manifest']
        for _ in range(4):advance_batch(p,42,self.backend)
        self.assertFalse(any(x[0]=='close_completed' for x in self.backend.state['calls']))
    def test_cleanup_does_not_save_or_close_changed_or_ambiguous_page(self):
        class Editor:
            def __init__(self,title,docs):self.title=title;self.docs=docs
            def unique(self,_):return {'title':self.title}
            def documents(self):return {'documents':self.docs,'selected':0}
            def save_as(self,_):raise AssertionError('Must not save')
            def close(self):raise AssertionError('Must not close')
        case={'circuit_file':str(self.source),'editor':'source - editor'}
        changed=Editor('user page',[])
        self.assertFalse(close_completed_document(changed,case)['closed'])
        ambiguous=Editor(case['editor'],[{'name':'source','index':0},{'name':'source','index':1}])
        self.assertFalse(close_completed_document(ambiguous,case)['closed'])
    def test_cleanup_error_keeps_completed_result_and_does_not_retry(self):
        p=self.prepare()
        def error(*args):raise RuntimeError('test native prompt')
        self.backend.close_completed_case=error
        for _ in range(5):result=advance_batch(p,42,self.backend)
        self.assertEqual('succeeded',result['status'])
        self.assertEqual('test native prompt',result['cases'][0]['cleanup']['kept_reason'])
        self.assertEqual(1,self.backend.state['starts'])
    def test_manifest_lock_and_read_only_status(self):
        p=self.prepare()
        with _lock(p):
            with self.assertRaises(RuntimeError):advance_batch(p,42,self.backend)
            self.assertEqual('pending',batch_status(p)['cases'][0]['status'])
        self.assertEqual([],self.backend.state['calls'])
    def test_cartesian_grid_and_seeded_tolerances(self):
        cases=grid_cases([{'component':'V1','index':0,'values':['10','12']},
                          {'component':'R1','index':0,'values':['1k','2k','3k']}])
        self.assertEqual(6,len(cases));self.assertEqual('12',cases[3]['operations'][0]['value'])
        args=([{'component':'R1','index':0,'nominal':'1k','relative':.05}],10,123)
        a=tolerance_cases(*args);b=tolerance_cases(*args)
        self.assertEqual(a,b)
        self.assertTrue(all(950<=c['values']['R1:0']<=1050 for c in a['cases']))
    def test_boundary_search_needs_one_measured_bracket(self):
        r=boundary_candidate([(1,4),(3,8)],6)
        self.assertEqual('candidate',r['status']);self.assertEqual(2,r['parameter'])
        self.assertEqual('unbracketed',boundary_candidate([(1,4),(3,5)],6)['status'])
        self.assertEqual('multiple_brackets',boundary_candidate([(1,4),(2,8),(3,3)],6)['status'])
    def test_sensitivity_changes_one_axis_and_restores_all_other_nominals(self):
        cases=sensitivity_cases([{'component':'R1','index':0,'nominal':'1k'},
                                 {'component':'V1','index':0,'nominal':'12'}],.01)
        self.assertEqual(5,len(cases))
        self.assertEqual({'R1:0':990,'V1:0':12},cases[1]['values'])
        self.assertEqual({'R1:0':1000,'V1:0':12.12},cases[4]['values'])
        r=sensitivity_estimate([.99,1.98],[1,2],[1.01,2.02])
        self.assertAlmostEqual(2,r['slope']);self.assertAlmostEqual(1,r['normalized_sensitivity'])


if __name__=='__main__':unittest.main()
