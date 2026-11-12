import math
import pytest
from ui.face_geometry import relative_pixels
from ui.mipi_composer import compose
from hft2_wire import decode


def dense_pixels():
    return [[round(320 + 70 * math.cos(i)), round(180 + 95 * math.sin(i)),
             round(20 * math.sin(i * .3))] for i in range(478)]


@pytest.mark.parametrize('profile', ['legacy', 'theater'])
def test_dense_pixel_face_survives_hft2_and_translation(profile):
    stamp = 10**10
    state = dict(epoch=7, state='ONBOARD', people='single', calibrated=False)
    face = dict(epoch=7, seq=11, src_ns=stamp, faces=[dict(
        track_id=7, primary=True, valid=True, landmarks=dense_pixels())])
    def render():
        return decode(compose(state, face, None, stamp, 1, profile)[0])
    before = render()
    assert before['scene'].valid == 4
    assert len(before['scene'].vertices) == 29
    assert before['scene'].face_timestamp_ns == stamp
    assert not before['metadata'].ui_status & (7 << 13)
    face['faces'][0]['landmarks'] = [[x+900, y+500, z-120] for x,y,z in dense_pixels()]
    after = render()
    assert after['scene'].vertices == before['scene'].vertices
    assert after['scene'].offsets == before['scene'].offsets


def test_pixel_conversion_preserves_proportions_and_depth():
    p = relative_pixels([[300,150,-10], [400,200,10], [320,170,0]])
    assert p[1][0]-p[0][0] == pytest.approx(1)
    assert p[1][1]-p[0][1] == pytest.approx(.5)
    assert p[1][2]-p[0][2] == pytest.approx(.2)


@pytest.mark.parametrize('points', [[], [[1,2]], [[1,2,float('nan')]],
                                  [[1,2,3]]*3, [[0,0,0],[40000,2,3]]])
def test_invalid_geometry_is_not_normalized_into_a_valid_face(points):
    with pytest.raises(ValueError): relative_pixels(points)
