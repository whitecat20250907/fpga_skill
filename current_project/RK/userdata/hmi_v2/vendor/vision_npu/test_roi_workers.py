import threading,unittest
from roi_workers import OwnerPool
class Workers(unittest.TestCase):
    def test_two_simultaneous_owners_and_stable_result_order(self):
        barrier=threading.Barrier(2);records=[]
        class Model:
            def __init__(self,core):self.owner=threading.get_ident();self.core=core
            def __call__(self,x):
                assert threading.get_ident()==self.owner
                barrier.wait(timeout=2);return self.core,x
            def close(self):records.append((self.owner,threading.get_ident()))
        p=OwnerPool(Model,[1,2])
        try:self.assertEqual(p.map([(i,) for i in range(4)]),[(1,0),(2,1),(1,2),(2,3)])
        finally:p.close()
        self.assertEqual(len({x[0] for x in records}),2)
        self.assertTrue(all(a==b for a,b in records));self.assertFalse(any(t.is_alive() for t in p.threads))
    def test_exception_drains_other_owner_then_can_close(self):
        completed=[]
        class Model:
            def __init__(self,c):pass
            def __call__(self,x):
                if x==0:raise ValueError('expected')
                completed.append(x);return x
            def close(self):pass
        p=OwnerPool(Model,[1,2])
        try:
            with self.assertRaises(ValueError):p.map([(0,),(1,),(2,),(3,)])
            self.assertEqual(sorted(completed),[1,2,3])
        finally:p.close()
        self.assertFalse(any(t.is_alive() for t in p.threads))
    def test_initialization_failure_closes_successful_owner(self):
        closed=[]
        class Model:
            def __init__(self,c):
                if c==2:raise ValueError('expected')
            def close(self):closed.append(True)
        with self.assertRaises(ValueError):OwnerPool(Model,[1,2])
        self.assertEqual(closed,[True])
if __name__=='__main__':unittest.main()
