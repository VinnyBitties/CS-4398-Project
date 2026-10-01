import base64
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from test_tracker import t

A='a'*40
B='b'*40
C='c'*40

class FakeBranchGitHub:
    repo='VinnyBitties/CS-4398-Project'
    def __init__(self):
        self.sha=B
        self.previous=None
        self.rewritten=False
        self.writes=[]
        self.comparisons=[]
        self.patch_files=[{'filename':'model.py','status':'modified','patch':'+def predict(): pass'}]

    def pages(self,path):
        if '/comments' in path:
            return iter([self.previous] if self.previous else [])
        return iter([{'id':1,'number':1,'body':t.marker('ml'),'state':'open'},
                     {'id':2,'number':2,'body':t.marker('ml-01'),'state':'open','assignees':[]}])

    def call(self,path,data=None,method=None):
        if data:
            self.writes.append((path,data))
            self.previous={'id':3,'body':data['body'],'user':{'login':'github-actions[bot]'}}
            return self.previous
        if path=='':return {'default_branch':'main'}
        if path.startswith('/branches/'):return {'commit':{'sha':self.sha}}
        if path.startswith('/compare/'):
            self.comparisons.append(path)
            base=path.split('/compare/')[1].split('...')[0]
            ancestor=A if base=='main' or self.rewritten else base
            return {'status':'ahead','merge_base_commit':{'sha':ancestor},'files':self.patch_files}
        if '/check-runs?' in path:return {'check_runs':[], 'total_count':0}
        if path.endswith('/status'):return {'state':'pending'}
        if path=='/issues/comments/3':return self.previous
        raise AssertionError(path)

class BranchTests(unittest.TestCase):
    def setUp(self):
        self.gh=FakeBranchGitHub()
        self.area={'id':'ml','title':'ML','branches':['ML-Axel'],
                   'tasks':[{'id':'ml-01','title':'Predict','goal':'Predict','done_when':'Inference exists'}]}
        self.plan={'areas':[self.area]}
        self.report={'summary':'Prediction added','tasks':[{'id':'ml-01','assessment':'review_needed',
                    'evidence':'Prediction function','paths':['model.py'],'next_step':'Test inference'}], 'suggestions':[]}

    def run_review(self,apply=False,force=False):
        with patch.object(t,'ask_gemini',return_value=self.report) as model:
            result=t.review(self.gh,self.plan,'ML-Axel',apply,force)
            return result,model.call_count

    def test_first_read_no_pr_and_dry_run_no_checkpoint(self):
        result,count=self.run_review()
        self.assertEqual(count,1)
        self.assertEqual(self.gh.writes,[])
        self.assertIsNone(self.gh.previous)
        self.assertIn('first analysis',result['comment'])

    def test_incremental_reuses_comment_and_skips_unchanged(self):
        self.run_review(True)
        self.assertEqual(t.checkpoint(self.gh.previous)['sha'],B)
        self.assertEqual(self.run_review(True)[1],0)
        self.gh.sha=C
        result,count=self.run_review(True)
        self.assertEqual(count,1)
        self.assertIn('/compare/'+B+'...'+C,self.gh.comparisons)
        self.assertEqual(self.gh.writes[-1][0],'/issues/comments/3')
        self.assertIn('since last published',result['comment'])
        self.assertEqual(t.checkpoint(self.gh.previous)['sha'],C)

    def test_force_full_reassessment(self):
        self.run_review(True)
        result,count=self.run_review(False,True)
        self.assertEqual(count,1)
        self.assertIn('full refresh',result['comment'])

    def test_rewritten_history_resets_baseline(self):
        self.run_review(True)
        self.gh.sha=C
        self.gh.rewritten=True
        context=t.collect(self.gh,'ML-Axel',self.area,{},self.gh.previous)
        self.assertIsNone(context['previous_report'])
        self.assertIn('history rewritten',context['branch']['comparison'])
        self.assertEqual(context['branch']['base_sha'],A)

    def test_quota_does_not_advance_checkpoint(self):
        self.run_review(True)
        before=self.gh.previous['body']
        self.gh.sha=C
        with patch.object(t,'ask_gemini',side_effect=HTTPError('url',429,'quota',{},None)):
            with self.assertRaises(HTTPError):t.review(self.gh,self.plan,'ML-Axel',True)
        self.assertEqual(self.gh.previous['body'],before)

    def test_stale_branch_never_published(self):
        def model(_):
            self.gh.sha=C
            return self.report
        with patch.object(t,'ask_gemini',side_effect=model):
            with self.assertRaises(ValueError):t.review(self.gh,self.plan,'ML-Axel',True)
        self.assertEqual(self.gh.writes,[])

    def test_previous_paths_can_support_inherited_evidence(self):
        self.run_review(True)
        self.gh.sha=C
        self.gh.patch_files=[]
        self.assertEqual(self.run_review(True)[1],1)

    def test_file_cap_rejected(self):
        self.gh.patch_files=self.gh.patch_files*300
        with self.assertRaises(ValueError):self.run_review(True)
        self.assertEqual(self.gh.writes,[])

    def test_branch_marker_isolated(self):
        self.assertNotEqual(t.branch_marker('ML-Axel'),t.branch_marker('ML-Diego'))

    def test_corrupt_checkpoint_fails_closed(self):
        self.gh.previous={'id':3,'body':t.branch_marker('ML-Axel'),'user':{'login':'github-actions[bot]'}}
        with self.assertRaises(ValueError):self.run_review(True)

if __name__=='__main__':unittest.main()
