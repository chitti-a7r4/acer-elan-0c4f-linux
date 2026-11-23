import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from elantouch import calibrate, match
from elantouch.engine import Engine, Touch, ACCEPT_Z
from elantouch.store import Calibration, Template

# Keep the trial separate from the system's calibration and fingerprint store.
Calibration.load = classmethod(lambda cls: cls())
Calibration.save_background = lambda self, image: setattr(self, "background", image)
messages = queue.Queue()
cancel = threading.Event()
go = threading.Event()
def say(title, body, button=False):
    messages.put((title, body, button))
def prompt(title, body):
    go.clear()
    say(title, body, True)
    go.wait()
    if cancel.is_set():
        raise RuntimeError("Trial stopped.")
def samples(eng, count, label, instruction):
    for n in range(count):
        while True:
            if cancel.is_set():
                raise RuntimeError("Trial stopped.")
            say(f"{label} · {n} accepted of {count}", instruction)
            status, image = eng.touch(timeout=25, cancel=cancel)
            if status == Touch.OK:
                break
            if status == Touch.CANCELLED:
                raise RuntimeError("Trial stopped.")
            if status == Touch.TIMEOUT:
                eng.sensor.close()
                prompt("Paused · progress kept", f"{label}: {n} of {count} complete. Click Continue when ready.")
                eng.sensor.open()
                continue
            say("Lift your finger", "Place it again when the next prompt appears.")
            eng.wait_lift(cancel)

        say(f"{label} · {n+1} accepted of {count}", "Touch accepted. Lift your finger fully.")
        eng.wait_lift(cancel)
        yield image
def run():
    try:
        prompt("Start with the reader empty", "Leave the sensor uncovered. Click Continue to check for false touches.")
        eng = Engine(raw=True)
        try:
            eng.sensor.open()
            idle = sum(eng.sensor.finger(220) for _ in range(8))
            print("Idle checks reporting a touch:", idle, "of 8", flush=True)
            if idle:
                raise RuntimeError(f"The reader reported a touch in {idle} of 8 empty-sensor checks. This touch driver cannot reliably detect an empty reader in this test.")
            say("Touch capture", "Rest your right index finger on the reader and hold still. Lift when asked.")
            for _ in samples(eng,1,"Touch capture","Rest your right index finger on the reader and hold still."):
                print("Captured stable touch",flush=True)
        finally:
            eng.sensor.close()
        prompt("Touch capture passed", "To test recognition, continue through 24 calibration touches using different fingers, then enroll your right index finger. Close to end the trial.")
        with eng:
            raws = list(samples(eng,24,"Calibration","Alternate between several fingers. Vary position and angle."))
        gain,ridge,detail = calibrate.build_maps(raws)
        residual = calibrate.residual_identity_correlation(raws,gain,ridge,detail)
        print("Calibration residual:",float(residual),flush=True)
        if not 0 <= residual < 0.10:
            raise RuntimeError("Calibration quality is too low to evaluate recognition.")
        del raws
        eng.cal.gain = gain
        eng.raw = False
        match.set_fixed_pattern(ridge,detail)
        tpl = Template("trial","right-index-finger")
        say("Calibration passed", "Next, use only your right index finger.")
        time.sleep(2)
        with eng:
            recent = []
            for im in samples(eng,64,"Enrollment","Rest your right index finger on the reader."):
                z,_,overlap,*_ = eng.score(tpl,im)
                recent = (recent + [z>=ACCEPT_Z])[-10:]
                if z<ACCEPT_Z or overlap<0.85:
                    tpl.add(im)
                if len(tpl.views)>=12 and sum(recent)>=8:
                    break
        counts = []
        for label, instruction in (("Right index","Use only the enrolled right index finger."),("Other fingers","Use five other fingers, excluding your right index finger.")):
            prompt(label,instruction)
            with eng:
                counts.append(sum(eng.score(tpl,im)[0]>=ACCEPT_Z for im in samples(eng,5,label,instruction)))
        result=f"Right index matched {counts[0]}/5. Other fingers matched {counts[1]}/5."
        say("Trial complete",result)
        print(result,flush=True)
    except Exception as exc:
        print("Trial stopped:",exc,flush=True)
        say("Trial stopped",str(exc))
root = tk.Tk()
root.title("Fingerprint touch trial")
root.geometry("650x265")
frame=ttk.Frame(root,padding=24); frame.pack(fill="both",expand=True)
title=tk.StringVar(); body=tk.StringVar()
ttk.Label(frame,textvariable=title,font=("Sans",19,"bold")).pack(anchor="w")
ttk.Label(frame,textvariable=body,wraplength=550,font=("Sans",12)).pack(anchor="w",pady=16)
button=ttk.Button(frame,text="Continue",command=go.set); button.pack(side="left")
def close():
    cancel.set(); go.set(); root.destroy()
ttk.Button(frame,text="End trial",command=close).pack(side="right")
root.protocol("WM_DELETE_WINDOW",close)
def poll():
    while not messages.empty():
        headline, text, enabled=messages.get_nowait(); title.set(headline); body.set(text)
        button.configure(state="normal" if enabled else "disabled")
    root.after(80,poll)
thread=threading.Thread(target=run,daemon=True); thread.start(); poll(); root.mainloop()
cancel.set(); go.set(); thread.join(9)
