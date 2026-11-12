"""Optional RGA display resize; never used by model preprocessing."""
import ctypes
from core.config import ROOT


class DisplayResize:
    def __init__(self):
        self.lib = None
        self.handle = None
        self.output = None
        self.output_size = 0
        try:
            lib = ctypes.CDLL(str(ROOT / 'native/display/librga_preview.so'))
            lib.hmi_rga_create.restype = ctypes.c_void_p
            lib.hmi_rga_destroy.argtypes = [ctypes.c_void_p]
            lib.hmi_rga_resize.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            lib.hmi_rga_resize.restype = ctypes.c_int
            self.handle = lib.hmi_rga_create()
            self.lib = lib
        except OSError:
            pass

    def image(self, data, width, height):
        from PIL import Image
        scale = min(1., 960 / width, 600 / height)
        dw, dh = max(2, int(width * scale)), max(2, int(height * scale))
        # Packed BGRX is the verified X11 format. Padded or unusual layouts
        # retain the existing PIL path rather than reading beyond the buffer.
        if self.handle and scale < 1 and len(data) == width * height * 4:
            size = dw * dh * 4
            if self.output_size != size:
                self.output = ctypes.create_string_buffer(size)
                self.output_size = size
            source = ctypes.c_char_p(data)
            status = self.lib.hmi_rga_resize(self.handle, source, width, height, self.output, dw, dh)
            if status == 0:
                return Image.frombytes('RGB', (dw, dh), self.output.raw, 'raw', 'BGRX'), 'RGA'
        image = Image.frombytes('RGB', (width, height), data, 'raw', 'BGRX')
        image.thumbnail((960, 600))
        return image, 'PIL'

    def rgb_image(self, pixels):
        from PIL import Image
        height,width=pixels.shape[:2]
        dw,dh=960,540
        if self.handle and hasattr(self.lib,'hmi_rga_resize_rgb') and pixels.dtype.name=='uint8' and pixels.flags.c_contiguous and pixels.shape==(1080,1920,3):
            fn=self.lib.hmi_rga_resize_rgb;fn.argtypes=self.lib.hmi_rga_resize.argtypes;fn.restype=ctypes.c_int
            size=dw*dh*3
            if self.output_size!=size:self.output=ctypes.create_string_buffer(size);self.output_size=size
            status=fn(self.handle,ctypes.c_void_p(pixels.ctypes.data),width,height,self.output,dw,dh)
            if status==0:return Image.frombytes('RGB',(dw,dh),self.output.raw),'RGA'
        image=Image.fromarray(pixels,'RGB');image.thumbnail((960,540),Image.Resampling.BILINEAR)
        return image,'PIL'

    def close(self):
        if self.handle:
            self.lib.hmi_rga_destroy(self.handle)
            self.handle = None

    def rgb_bytes(self, pixels, width, height):
        """Small HDMI display-only resize; keep the model source immutable."""
        sw,sh=int(pixels.shape[1]),int(pixels.shape[0])
        if self.handle and hasattr(self.lib,'hmi_rga_resize_rgb') and pixels.dtype.name=='uint8' and pixels.flags.c_contiguous:
            fn=self.lib.hmi_rga_resize_rgb;fn.argtypes=self.lib.hmi_rga_resize.argtypes;fn.restype=ctypes.c_int
            size=width*height*3
            if self.output_size!=size:self.output=ctypes.create_string_buffer(size);self.output_size=size
            status=fn(self.handle,ctypes.c_void_p(pixels.ctypes.data),sw,sh,self.output,width,height)
            if status==0:return self.output.raw,'RGA'
        import cv2
        return cv2.resize(pixels,(width,height),interpolation=cv2.INTER_AREA).tobytes(),'OpenCV'
