import importlib.util
from pathlib import Path
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
        self.context = {'tasks':[{'id':'ml-01'}], 'cumulative_diff':[{'path':'model.py'}]}
        self.report = {'summary':'Changed','tasks':[{'id':'ml-01','assessment':'review_needed','evidence':'Inference added',
                       'paths':['model.py'],'next_step':'Review it'}], 'suggestions':[]}

    def test_real_plan_valid(self):
        plan=t.load_plan()
        self.assertEqual(sum(len(a['tasks']) for a in plan['areas']),40)

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
        self.context.update(pr={'number':7,'branch':'ML-Axel','head_sha':'abc'}, omitted_paths=['big.py'])
        self.context['tasks'][0].update(title='Evaluate',issue_number=2,state='open',assignees=[])
        body=t.render(self.report,self.context)
        self.assertIn('Unassigned',body)
        self.assertIn('1 omitted',body)
        self.assertIn('sentinel-progress:pr-7',body)


if __name__=='__main__':unittest.main()
