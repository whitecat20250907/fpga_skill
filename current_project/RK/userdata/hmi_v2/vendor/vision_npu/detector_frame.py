"""Immutable, same-packet RGB640 + detector tensors. No frame lookup by 'latest'."""
import numpy as np
SMALL_BYTES=640*360*3
FACE_BYTES=128*128*3
PALM_BYTES=192*192*3
TOTAL_BYTES=SMALL_BYTES+FACE_BYTES+PALM_BYTES
CONTRACT='square640_warp_linear5_zero'

class DetectorFrame(np.ndarray):
    def __array_finalize__(self,parent):
        if parent is not None:
            for name in ('_source_pointer','_detector_tensors','source_identity'):
                setattr(self,name,getattr(parent,name,None))

def make_frame(data,meta):
    if type(data) is not bytes or len(data)!=TOTAL_BYTES:
        raise ValueError('Complete immutable three-plane packet required')
    if meta.get('detector_contract')!=CONTRACT or meta.get('fpga_crc_verified') is not True:
        raise ValueError('Unverified detector contract')
    identity=(meta['fpga_epoch'],meta['sequence'],meta['fpga_source_tick'])
    if not all(type(v) is int and v>=0 for v in identity) or not identity[0]:
        raise ValueError('Invalid same-frame identity')
    all_pixels=np.frombuffer(data,np.uint8)
    rgb=all_pixels[:SMALL_BYTES].reshape(360,640,3).view(DetectorFrame)
    rgb._source_pointer=rgb.__array_interface__['data'][0]
    rgb._detector_tensors={128:all_pixels[SMALL_BYTES:SMALL_BYTES+FACE_BYTES].reshape(128,128,3),
                           192:all_pixels[SMALL_BYTES+FACE_BYTES:].reshape(192,192,3)}
    rgb.source_identity=identity
    return rgb

def detector_input(rgb,size):
    if not isinstance(rgb,DetectorFrame):return None
    if (rgb.shape!=(360,640,3) or rgb.dtype!=np.uint8 or rgb.strides!=(1920,3,1)
            or rgb.flags.writeable or rgb.__array_interface__['data'][0]!=rgb._source_pointer):
        # A copy, colour conversion, ROI or mutation must never reuse old tensors.
        return None
    return rgb._detector_tensors[size]
