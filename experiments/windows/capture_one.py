import os, subprocess, sys, time
from pathlib import Path
import numpy as np
from elantouch.engine import Engine, Touch
from elantouch.store import Calibration
Calibration.load = classmethod(lambda cls:cls())
Calibration.save_background = lambda self,image:setattr(self,'background',image)
def message(text):
    return subprocess.run(['zenity','--info','--title=Acer engine capture test','--text='+text]).returncode
if message('Leave the reader empty. Click OK, then place your right index finger on the reader after one second and hold still.'):
    sys.exit('Canceled.')
with Engine(raw=True) as e:
    status,image=e.touch(timeout=30)
    if status != Touch.OK:
        sys.exit('No stable touch: '+status)
lo,hi=np.percentile(image,[1,99])
if not np.isfinite(hi-lo) or hi<=lo:
    sys.exit('Insufficient image contrast')
frame=np.clip((image-lo)*255/(hi-lo),0,255).astype(np.uint8)
d=Path(__file__).parent
env=dict(os.environ,WINEPREFIX=str(d/'wine-prefix'),WINEDEBUG='-all',WINEDLLOVERRIDES='winemenubuilder.exe=d;winedbg.exe=d')
r=subprocess.run(['wine',str(d/'sample.exe'),'--frame-stdin'],cwd=d,env=env,input=frame.tobytes(),stdout=subprocess.PIPE,timeout=50)
print(r.stdout.decode(errors='replace'),flush=True)
