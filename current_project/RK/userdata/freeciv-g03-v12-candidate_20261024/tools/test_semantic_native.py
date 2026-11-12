"""Compile and execute the same selection tests against actual native C code."""
import ctypes as C,importlib,io,json,random,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from semantic_selection import Selection
import test_semantic_selection as cases

def main():
    with tempfile.TemporaryDirectory(prefix='semantic-native-') as temporary:
        output=Path(temporary)/'selection.so'
        flags=subprocess.check_output(['pkg-config','--cflags','--libs','glib-2.0'],text=True).split()
        subprocess.run(['gcc','-std=c11','-shared','-fPIC','-Wall','-Wextra','-Wno-unused-function','-Werror',
            '-I'+str(ROOT/'upstream/freeciv-3.2.6/client/gui-gtk-3.22'),str(ROOT/'tests/semantic_native.c'),'-o',str(output),'-lm',*flags],check=True)
        lib=C.CDLL(str(output));P=C.c_void_p;D=C.c_double
        signatures={'selection_new':([],P),'selection_free':([P],None),'selection_reset':([P],None),
            'selection_sync':([P,C.POINTER(D),C.c_int],None),'selection_sample':([P,D,D,D,D,C.c_int],None),
            'selection_confirm':([P,D],C.c_int),'selection_preview':([P,D],C.c_int),'selection_read':([P,C.POINTER(D)],None),
            'parse_source':([C.c_char_p,C.c_longlong],C.c_int)}
        for name,(args,res) in signatures.items():fn=getattr(lib,name);fn.argtypes=args;fn.restype=res
        class Native:
            def __init__(self):self.ptr=lib.selection_new();self.update()
            def __del__(self):lib.selection_free(self.ptr)
            def update(self):
                values=(D*6)();lib.selection_read(self.ptr,values)
                self.pick,self.ready=int(values[0]),bool(values[1]);self.confidence,self.margin,self.x,self.y=values[2:]
            def reset(self):lib.selection_reset(self.ptr);self.update()
            def sync(self,targets):
                values=(D*(len(targets)*5))(*(v for t in targets for v in (*Selection.key(t),t['x'],t['y'])))
                lib.selection_sync(self.ptr,values,len(targets));self.update()
            def sample(self,x,y,targets,stamp,now,filtered=True):
                self.sync(targets);lib.selection_sample(self.ptr,x,y,stamp,now,int(filtered));self.update()
            def confirmable(self,now):return bool(lib.selection_confirm(self.ptr,now))
            def preview(self,now):return lib.selection_preview(self.ptr,now)
        cases.Selection=Native;stream=io.StringIO()
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(cases.Semantic))
        print(stream.getvalue());assert result.wasSuccessful()
        rng=random.Random(51);py=Selection();native=Native();stamp=100.
        for i in range(2000):
            stamp+=rng.choice([1/10,1/20,1/30,1/60]);x=rng.choice([100,100,100,195,205,300,900])
            targets=cases.T if i%17 else cases.T[::-1]
            py.sample(x,100,targets,stamp,stamp);native.sample(x,100,targets,stamp,stamp)
            assert (py.pick,py.ready)==(native.pick,native.ready),(i,py.pick,native.pick)
            assert py.preview(stamp)==native.preview(stamp)
            assert abs(py.confidence-native.confidence)<1e-10 and abs(py.margin-native.margin)<1e-10
        valid=['gaze2 1000000 .5 .5','gaze2 750000 0 1']
        invalid=['gaze2 749999 .5 .5','gaze2 1000001 .5 .5','gaze2 -1 .5 .5','gaze2 0 .5 .5',
            'gaze2 1000000 nan .5','gaze2 1000000 .5 2','gaze2 1000000 .5 .5 extra',
            'gaze2 18446744073709551615 .5 .5']
        for text in valid:assert lib.parse_source(text.encode(),1000000)==1,text
        for text in invalid:assert lib.parse_source(text.encode(),1000000)==0,text
        print(json.dumps(dict(status='PASS_NATIVE_SELECTION_AND_PYTHON_PARITY',native_tests=result.testsRun,parity_samples=2000,parser_cases=len(valid+invalid),human_test=False)))
if __name__=='__main__':main()
