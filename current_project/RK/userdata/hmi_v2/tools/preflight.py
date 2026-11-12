"""Read-only target prerequisites. Does not open video/DMA/BAR or load models."""
from pathlib import Path
import importlib.util,json,platform,subprocess,sys,ctypes.util
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from core.config import load
def inspect():
 c=load();checks={'linux_arm64':sys.platform=='linux' and platform.machine() in ('aarch64','arm64')}
 for name in ['numpy','cv2','zmq','msgpack','yaml','pygame','Xlib','rknnlite','mediapipe','sklearn']:
  try:checks['module:'+name]=importlib.util.find_spec(name) is not None
  except (ValueError,ImportError):checks['module:'+name]=False
 for lib in ['X11','Xtst']:checks['library:'+lib]=bool(ctypes.util.find_library(lib))
 for key in ('dma','bar'):checks['device:'+key]=Path(c['hardware'][key]).exists()
 for name in ('fpga_io','libring.so'):checks['native:'+name]=(R/'native/fpga_io'/name).exists()
 try:checks['HDMI']=subprocess.run(['xrandr','--current'],capture_output=True,text=True,timeout=5).returncode==0
 except (OSError,subprocess.TimeoutExpired):checks['HDMI']=False
 return {'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'hardware_access':'none'}
if __name__=='__main__':
 result=inspect();print(json.dumps(result,indent=2));raise SystemExit(result['status']!='PASS')
