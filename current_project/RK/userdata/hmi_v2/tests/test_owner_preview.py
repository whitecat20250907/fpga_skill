import sys
import pytest
if sys.platform!='linux':pytest.skip('Linux memfd and record locks',allow_module_level=True)
import os,time,mmap,subprocess
from core.config import ROOT
sys.path.insert(0,str(ROOT/'vendor/gaze_app'))
from shared_preview import HEADER,MAGIC,WIDTH,HEIGHT,STRIDE,PAYLOAD,TOTAL
from vision.preview_reader import OwnerPreview


@pytest.fixture
def attached(tmp_path):
    fd=os.memfd_create('preview-test',os.MFD_CLOEXEC)
    model=os.memfd_create('model-owner-test',os.MFD_CLOEXEC)
    os.ftruncate(fd,TOTAL);mm=mmap.mmap(fd,TOTAL)
    path=tmp_path/'preview.memfd';path.symlink_to(f'/proc/{os.getpid()}/fd/{fd}')
    ring=tmp_path/'frames.memfd';ring.symlink_to(f'/proc/{os.getpid()}/fd/{model}')
    reader=OwnerPreview(path,ring)
    try:yield reader,mm,path,ring,fd
    finally:reader.close();mm.close();os.close(fd);os.close(model)


def publish(mm,serial=1,stamp=None,valid=PAYLOAD):
    now=stamp or time.monotonic_ns()
    mm[64:]=b'\x5a'*PAYLOAD
    mm[:64]=HEADER.pack(MAGIC,1,WIDTH,HEIGHT,STRIDE,valid,12,now,now,serial,now)
    return now


def test_full_resolution_new_frame_and_private_copy(attached):
    r,mm,_,_,_=attached;publish(mm)
    image,meta=r.read_latest()
    assert image.shape==(1080,1920,3) and meta['sequence']==12
    mm[64]=0
    assert int(image[0,0,0])==90
    assert r.read_latest() is None


def test_stale_incomplete_or_replaced_owner_never_replayed(attached):
    r,mm,path,ring,_=attached
    publish(mm,stamp=time.monotonic_ns()-600_000_000)
    assert r.read_latest() is None
    publish(mm,valid=0)
    assert r.read_latest() is None
    publish(mm);ring.unlink()
    assert r.read_latest() is None


def test_cross_process_writer_lock_is_nonblocking(attached):
    r,mm,path,_,_=attached;publish(mm)
    code='import os,fcntl,sys; f=os.open(sys.argv[1],os.O_RDWR); fcntl.lockf(f,fcntl.LOCK_EX,1); print("locked",flush=True); sys.stdin.readline()'
    p=subprocess.Popen([sys.executable,'-c',code,str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert p.stdout.readline().strip()=='locked'
        begin=time.monotonic();assert r.read_latest() is None
        assert time.monotonic()-begin<.2
    finally:p.communicate('\n',timeout=5)
    assert p.returncode==0 and r.read_latest() is not None


def test_model_inode_replacement_under_same_process_is_rejected(attached):
    r,mm,_,ring,_=attached;publish(mm)
    replacement=os.memfd_create('different-model-ring',os.MFD_CLOEXEC)
    try:
        ring.unlink();ring.symlink_to(f'/proc/{os.getpid()}/fd/{replacement}')
        assert r.read_latest() is None
    finally:os.close(replacement)
