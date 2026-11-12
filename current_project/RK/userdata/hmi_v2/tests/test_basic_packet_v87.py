import json,struct
import pytest
from console.basic_preview import pack_images


def test_binary_snapshot_keeps_exact_blobs_and_independent_frame_identities():
    original=dict(epoch='7',sequence=200,publication_serial=100,source_ns=1000,
        raw_publication=70,raw_sequence=197,raw_image=b'raw-jpeg',model_image=b'model-jpeg',
        planes=[dict(size=128,image=b'face'),dict(size=192,image=b'palm')])
    packet=pack_images(original)
    assert packet[:4]==b'HBP1'
    n=struct.unpack_from('<I',packet,4)[0];meta=json.loads(packet[8:8+n]);offset=8+n
    images={}
    for image in meta['images']:
        images[image['key']]=packet[offset:offset+image['length']];offset+=image['length']
    assert offset==len(packet)
    assert images=={'raw':b'raw-jpeg','model':b'model-jpeg','plane128':b'face','plane192':b'palm'}
    assert meta['raw_publication']==70 and meta['publication_serial']==100
    assert original['planes'][0]['image']==b'face'


def test_unavailable_hd_preview_does_not_duplicate_model_as_hd():
    packet=pack_images(dict(raw_image=None,model_image=b'm',planes=[]))
    n=struct.unpack_from('<I',packet,4)[0];meta=json.loads(packet[8:8+n])
    assert meta['raw_image'] is None and len(meta['images'])==1


def test_legacy_base64_is_not_double_wrapped_in_binary():
    with pytest.raises(ValueError):pack_images(dict(raw_image=None,model_image='data:image/jpeg;base64,abc',planes=[]))
