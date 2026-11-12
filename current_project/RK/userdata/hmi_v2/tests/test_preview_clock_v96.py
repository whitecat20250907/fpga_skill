import sys
from types import SimpleNamespace
import pytest
from console.basic_preview import BasicPreview


def preview(monkeypatch,tmp_path,stamp):
    from core import frame_ring
    from vision import bootstrap
    monkeypatch.setattr(bootstrap,'install_vendor_resolver',lambda:None)
    monkeypatch.setitem(sys.modules,'detector_frame',SimpleNamespace(detector_input=lambda rgb,size:rgb))
    frame=SimpleNamespace(rgb=object(),serial=8,meta=dict(timestamp_ns=stamp,fpga_epoch=1,sequence=8,pub_ns=stamp))
    ring=SimpleNamespace(latest=lambda:frame,close=lambda:None,check_owner=lambda:None)
    monkeypatch.setattr(frame_ring,'FrameRing',lambda path:ring)
    monkeypatch.setitem(sys.modules,'vision.preview_reader',SimpleNamespace(OwnerPreview=lambda *a:SimpleNamespace(read_latest=lambda:None,close=lambda:None)))
    monkeypatch.setattr(BasicPreview,'jpeg',staticmethod(lambda *a:b'jpeg'))
    times=iter([1_000_000_000,1_020_000_000,1_030_000_000])
    monkeypatch.setattr('console.basic_preview.time.monotonic_ns',lambda:next(times,1_030_000_000))
    return BasicPreview(tmp_path)


def test_publication_during_snapshot_is_not_future_frame(monkeypatch,tmp_path):
    p=preview(monkeypatch,tmp_path,1_010_000_000)
    try:
        d=p._capture({},{});assert d['publication_serial']==8 and d['age_ms']==20
    finally:p.close()


@pytest.mark.parametrize('stamp',[500_000_000,1_040_000_000])
def test_stale_or_actually_future_frame_still_rejected(monkeypatch,tmp_path,stamp):
    p=preview(monkeypatch,tmp_path,stamp)
    try:
        with pytest.raises(ValueError,match='等待新的'):p._capture({},{})
    finally:p.close()


def test_cached_packet_age_is_current(monkeypatch,tmp_path):
    p=BasicPreview(tmp_path);p.cached_ns=1_000_000_000
    p.cached={'source_ns':990_000_000,'age_ms':10,'publication_serial':7}
    from vision import bootstrap
    monkeypatch.setattr(bootstrap,'install_vendor_resolver',lambda:None)
    monkeypatch.setitem(sys.modules,'detector_frame',SimpleNamespace(detector_input=lambda *a:None))
    monkeypatch.setitem(sys.modules,'vision.preview_reader',SimpleNamespace(OwnerPreview=None))
    monkeypatch.setattr('console.basic_preview.time.monotonic_ns',lambda:1_020_000_000)
    try:
        d=p._capture({},{});assert d['age_ms']==30 and d['publication_serial']==7
        assert p.cached['age_ms']==10
    finally:p.close()
