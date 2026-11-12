"""Actual Linux memfd/record-lock tests without any camera or model."""
import mmap
import multiprocessing
import os
from pathlib import Path
import sys
import time
import unittest

if sys.platform=='linux':
    import fcntl
    import pcie_preview_reader as module

def child_lock(fd,ready,release):
    fcntl.lockf(fd,fcntl.LOCK_EX,1,0)
    ready.send(True)
    if not release.poll(2):raise RuntimeError('Bounded test release timeout')
    release.recv()

@unittest.skipUnless(sys.platform=='linux','Linux memfd/record locks required')
class PreviewContractTest(unittest.TestCase):
    def test_exact_original_and_optional_wrapper_entry(self):
        app=Path('/userdata/fixture/app_v28')
        root=Path(module.__file__).resolve().parent
        allowed=[['python','run_gaze.py','--continuous'],
                 ['python',str(app/'run_gaze.py')],
                 ['python',str(root/'tools/run_main_with_freeciv.py'),'--app-dir',str(app)]]
        denied=[['python','other.py','run_gaze.py'],
                ['python',str(root/'tools/run_main_with_freeciv.py'),'--app-dir','/wrong/app'],
                ['python',str(root/'tools/run_main_with_freeciv.py'),'--app-dir']]
        for args in allowed:self.assertTrue(module.expected_main_command(b'\0'.join(x.encode() for x in args)+b'\0',app))
        for args in denied:self.assertFalse(module.expected_main_command(b'\0'.join(x.encode() for x in args)+b'\0',app))
    def setUp(self):
        self.reader=module.ExistingPreview.__new__(module.ExistingPreview)
        self.reader.fd=os.memfd_create('inert-test',os.MFD_ALLOW_SEALING)
        os.ftruncate(self.reader.fd,module.HEADER.size+module.PAYLOAD)
        self.writer=mmap.mmap(self.reader.fd,0)
        self.reader.map=mmap.mmap(self.reader.fd,0,prot=mmap.PROT_READ)
        self.reader.last_serial=0;self.reader.last_stamp=0
        self.reader.stats=dict(busy=0,stale=0,duplicate=0,invalid=0,accepted=0)
        self.reader.check_owners=lambda:None # Discovery is separately verified against actual app28.
        self.publish()
    def publish(self,valid=None,stamp=None,serial=1):
        now=time.monotonic_ns()
        self.writer[:64]=module.HEADER.pack(b'GZPRV001',1,1920,1080,5760,
            module.PAYLOAD if valid is None else valid,3,stamp or now-10_000_000,now-5_000_000,serial,now-1_000_000)
    def tearDown(self):self.reader.close();self.writer.close()
    def test_private_RGB_copy_does_not_alias_mmap(self):
        self.writer[64:]=b'\x11'*module.PAYLOAD
        rgb,meta=self.reader.read()
        self.writer[64:]=b'\x22'*module.PAYLOAD
        self.assertEqual(rgb.shape,(360,640,3));self.assertTrue((rgb==17).all())
        self.assertEqual(meta['sequence'],3)
    def test_invalid_commit_after_writer_death_rejected(self):
        self.publish(valid=0)
        self.assertIsNone(self.reader.read())
    def test_stale_and_future_timestamp_rejected(self):
        self.publish(stamp=time.monotonic_ns()-500_000_000)
        self.assertIsNone(self.reader.read())
        self.publish(stamp=time.monotonic_ns()+1_000_000_000)
        self.assertIsNone(self.reader.read())
    def test_duplicate_and_regressed_publication(self):
        self.reader.read();self.assertIsNone(self.reader.read())
        self.publish(serial=1);self.assertIsNone(self.reader.read())
        self.publish(serial=2,stamp=self.reader.last_stamp-1)
        with self.assertRaises(RuntimeError):self.reader.read()
    def test_actual_other_process_writer_lock_never_waits(self):
        ctx=multiprocessing.get_context('fork')
        ready_parent,ready_child=ctx.Pipe();release_parent,release_child=ctx.Pipe()
        owner=ctx.Process(target=child_lock,args=(self.reader.fd,ready_child,release_child))
        owner.start()
        try:
            self.assertTrue(ready_parent.poll(2));self.assertTrue(ready_parent.recv())
            start=time.monotonic();self.assertIsNone(self.reader.read())
            self.assertLess(time.monotonic()-start,.1)
        finally:
            release_parent.send(True);owner.join(2)
            if owner.is_alive():owner.kill();owner.join(2)
        self.assertEqual(owner.exitcode,0)
        self.assertIsNotNone(self.reader.read())

if __name__=='__main__':unittest.main()
