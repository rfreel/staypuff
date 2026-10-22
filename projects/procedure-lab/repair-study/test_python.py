import unittest
import numpy as np
import torch
import run

class PublicMaskTests(unittest.TestCase):
    def test_goal_does_not_select_actions(self):
        o=torch.zeros(16,52)
        o[:,48:52]=torch.tensor((np.arange(16)[:,None]>>np.arange(4))&1)
        m=run.mask(o)
        self.assertTrue(torch.all(m==m[0]))
    def test_test_and_retain_require_evidence(self):
        o=torch.zeros(1,52);m=run.mask(o)
        self.assertFalse(m[0,5*20])
        self.assertFalse(m[0,7*20])
        o[0,18]=1;o[0,8]=1;m=run.mask(o)
        self.assertTrue(m[0,5*20]);self.assertTrue(m[0,7*20])
        o[0,26]=1;self.assertFalse(run.mask(o)[0,7*20])
    def test_abandon_is_available(self):
        o=torch.zeros(4,52)
        self.assertTrue(torch.all(run.mask(o)[:,185]))
    def test_all_actions_preserved_without_exploration(self):
        policy=run.Policy(False)
        _,_,_,_,p=policy(torch.zeros(3,52))
        self.assertTrue(torch.all(p>0))

if __name__=='__main__':unittest.main()
