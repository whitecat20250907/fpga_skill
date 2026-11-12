"""Bounded, authenticated-by-caller preview stream; no independent capture owner."""
import struct
import time


def frame_chunk(packet):
    if not 8 <= len(packet) <= 4*1024*1024 or packet[:4] != b'HBP1':
        raise ValueError('Invalid preview packet')
    return struct.pack('<I',len(packet))+packet


def serve(handler, preview, snapshot, running, slots, duration=30.):
    if not slots.acquire(blocking=False):
        return handler.reply(429,{'error':'实时预览连接已占用，请关闭其他预览页'})
    opened=False
    try:
        handler.connection.settimeout(3.)
        handler.send_response(200)
        for k,v in {'Content-Type':'application/vnd.hmi.preview-stream','Transfer-Encoding':'chunked',
                    'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}.items():handler.send_header(k,v)
        handler.end_headers();opened=True
        deadline=time.monotonic()+duration;last=None
        while running() and time.monotonic()<deadline:
            started=time.monotonic();values,telemetry=snapshot()
            value=preview._dispatch(values,telemetry)
            identity=(value['epoch'],value['publication_serial'],value.get('raw_publication'))
            if identity!=last:
                from .basic_preview import pack_images
                chunk=frame_chunk(pack_images(value))
                handler.wfile.write(('%x\r\n'%len(chunk)).encode()+chunk+b'\r\n')
                handler.wfile.flush();last=identity
            time.sleep(max(.001,1/60-(time.monotonic()-started)))
        handler.wfile.write(b'0\r\n\r\n');handler.wfile.flush()
    except (OSError,ValueError,RuntimeError,TimeoutError):
        # End a stale/broken stream; the client reconnects instead of replaying frames.
        handler.close_connection=True
    finally:
        slots.release()
        if opened and not handler.close_connection:handler.connection.settimeout(10.)
