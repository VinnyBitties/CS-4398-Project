import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[2] / 'scripts/issue_tracker.py'
spec = importlib.util.spec_from_file_location('tracker', path)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class FakeGitHub:
    def __init__(self):
        self.issues = []
        self.links = set()
        self.writes = []

    def pages(self, path):
        if 'sub_issues' in path:
            return iter([{'id': i} for i in self.links])
        return iter(self.issues)

    def call(self, path, data=None, method=None):
        self.writes.append((path, data, method))
        if path.endswith('sub_issues'):
            self.links.add(data['sub_issue_id'])
            return {}
        issue = {'id': len(self.issues)+100, 'number': len(self.issues)+1, **data}
        self.issues.append(issue)
        return issue


class Tests(unittest.TestCase):
    def setUp(self):
        self.plan = {'areas': [{'id':'ml','title':'ML','owners':'Axel and Diego','branches':['ML-Axel','ML-Diego'],
                      'goal':'Classify','done_when':'Reviewed', 'tasks':[
                          {'id':'ml-01','title':'Evaluate','goal':'Evaluate model','done_when':'Metrics recorded'}]}]}
        self.context = {'tasks':[{'id':'ml-01'}], 'diff':[{'path':'model.py'}]}
        self.report = {'summary':'Changed','tasks':[{'id':'ml-01','assessment':'review_needed','evidence':'Inference added',
                       'paths':['model.py'],'next_step':'Review it'}], 'suggestions':[]}

    def test_real_plan_valid(self):
        plan=t.load_plan()
        self.assertEqual(sum(len(a['tasks']) for a in plan['areas']),40)
        self.assertIs(type(plan['automatic_closures']),bool)

    def test_plan_rejects_non_boolean_closure_setting(self):
        plan={'automatic_reviews':False,'automatic_closures':'false','areas':self.plan['areas']}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'.github').mkdir()
            (root/'.github/issue-plan.json').write_text(json.dumps(plan))
            with patch.object(t,'ROOT',root):
                with self.assertRaises(ValueError):
                    t.load_plan()

    def test_dry_seed_no_writes(self):
        gh=FakeGitHub()
        changes=t.seed(gh,self.plan)
        self.assertEqual(len(changes),3)
        self.assertEqual(gh.writes,[])

    def test_seed_is_idempotent_and_links_native_subissue(self):
        gh=FakeGitHub()
        t.seed(gh,self.plan,True)
        self.assertEqual(len(gh.issues),2)
        self.assertEqual(gh.links,{101})
        gh.issues[1]['body']+='\nHuman note'
        count=len(gh.writes)
        self.assertEqual(t.seed(gh,self.plan,True),[])
        self.assertEqual(len(gh.writes),count)
        self.assertIn('Human note',gh.issues[1]['body'])

    def test_partial_seed_repairs_link(self):
        gh=FakeGitHub()
        t.seed(gh,self.plan,True)
        gh.links.clear()
        changes=t.seed(gh,self.plan,True)
        self.assertEqual(len(gh.issues),2)
        self.assertEqual(len(changes),1)

    def test_duplicate_markers_stop(self):
        gh=FakeGitHub()
        t.seed(gh,self.plan,True)
        gh.issues.append(dict(gh.issues[0]))
        with self.assertRaises(ValueError):t.seed(gh,self.plan,True)

    def test_valid_report(self):
        t.validate(self.report,self.context)

    def test_default_model_uses_current_flash(self):
        response={'candidates':[{'finishReason':'STOP','content':{'parts':[{
            'text':json.dumps(self.report)}]}}]}
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test-key'},clear=True):
            with patch.object(t,'api',return_value=response) as request:
                self.assertEqual(t.ask_gemini(self.context),self.report)
        self.assertIn('/models/gemini-3.8-flash:generateContent',request.call_args.args[0])
        generation=request.call_args.args[2]['generationConfig']
        self.assertEqual(generation['thinkingConfig'],{'thinkingLevel':'low'})
        self.assertEqual(request.call_args.kwargs['timeout'],180)

    def test_complete_with_current_evidence_is_valid(self):
        self.report['tasks'][0].update(assessment='complete',
                                       evidence='model.py records every required evaluation metric.',
                                       next_step='Close the task.')
        t.validate(self.report,self.context)

    def test_complete_rejects_inherited_only_evidence(self):
        self.context['previous_report']={'tasks':[{'id':'ml-01','paths':['old_model.py']}]}
        self.report['tasks'][0].update(assessment='complete',
                                       evidence='Previously reported implementation.',
                                       paths=['old_model.py'],next_step='Close the task.')
        with self.assertRaises(ValueError):
            t.validate(self.report,self.context)

    def test_unknown_task_rejected(self):
        self.report['tasks'][0]['id']='made-up'
        with self.assertRaises(ValueError):t.validate(self.report,self.context)

    def test_false_evidence_rejected(self):
        self.report['tasks'][0]['paths']=['unseen.py']
        with self.assertRaises(ValueError):t.validate(self.report,self.context)

    def test_missing_task_rejected(self):
        self.report['tasks']=[]
        with self.assertRaises(ValueError):t.validate(self.report,self.context)

    def test_render_preserves_uncertainty_and_unassigned(self):
        self.context.update(branch={'name':'ML-Axel','head_sha':'abc','base_sha':'def','comparison':'first analysis','default_branch':'main','contained_in_default':False}, omitted_paths=['big.py'])
        self.context['tasks'][0].update(title='Evaluate',issue_number=2,state='open',assignees=[])
        body=t.render(self.report,self.context)
        self.assertIn('Unassigned',body)
        self.assertIn('1 omitted',body)
        self.assertIn('may close mapped subissues',body)
        self.assertIn(t.branch_marker('ML-Axel'),body)


if __name__=='__main__':unittest.main()
