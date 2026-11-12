import threading
import pytest
from console.basic_preview import BasicPreview


def test_affinity_applies_only_to_persistent_worker(monkeypatch,tmp_path):
    main=threading.get_ident();calls=[]
    monkeypatch.setattr('console.basic_preview.os.sched_setaffinity',lambda pid,cpus:calls.append((threading.get_ident(),pid,cpus)),raising=False)
    p=BasicPreview(tmp_path,[7]);p._capture=lambda *a:threading.get_ident()
    try:
        first=p._dispatch({},{});second=p._dispatch({},{})
        assert first==second and first!=main
        assert calls==[(first,0,{7})]
    finally:p.close()


def test_unconfigured_worker_preserves_inherited_affinity(monkeypatch,tmp_path):
    monkeypatch.setattr('console.basic_preview.os.sched_setaffinity',lambda *a:pytest.fail('unexpected affinity change'),raising=False)
    p=BasicPreview(tmp_path);p._capture=lambda *a:1
    try:assert p._dispatch({},{})==1
    finally:p.close()


@pytest.mark.parametrize('cpus',[[],[8],[-1],[True],[7,7],'7'])
def test_invalid_worker_configuration_rejected(tmp_path,cpus):
    with pytest.raises(ValueError,match='affinity'):BasicPreview(tmp_path,cpus)
