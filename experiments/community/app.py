from score_trial import Trial
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import numpy as np
from elantouch import calibrate, match, store
from elantouch.engine import ACCEPT_Z, Engine, Touch

os.umask(0o077)
data = Path.home() / ".local/share/acer-touch-test/profile"
data.mkdir(mode=0o700, exist_ok=True)
store.USERS = str(data)
maps = data / "calibration.npz"
done = data / "right-index.enrolled"
finger = "right-index-finger"
# Persist only the calibration maps and the explicitly enrolled right index.
store.Calibration.save_background = lambda self, image: setattr(self, "background", image)
def load_maps(cls):
    cal = cls()
    if maps.exists():
        with np.load(maps, allow_pickle=False) as z:
            cal.gain, cal.fpn_ridge, cal.fpn_detail = (z[k] for k in ("gain","ridge","detail"))
    return cal
store.Calibration.load = classmethod(load_maps)
events = queue.Queue()
closing = threading.Event()
busy = False
cal_samples = []
def report(head, text):
    events.put((head, text))
def collect(engine, instruction, heading):
    while not closing.is_set():
        report(heading, instruction)
        status, image = engine.touch(timeout=30, cancel=closing)
        if status == Touch.OK:
            return image
        if status == Touch.TIMEOUT:
            raise RuntimeError("Reader paused. Click the button to resume when ready.")
        if closing.is_set():
            break
        report("Lift and try again", "Hold still until the reader captures the touch.")
        engine.wait_lift(closing)
    raise RuntimeError("Window closed.")
def score_trial():
    return Trial(data, data/"enrolled"/(finger+".npz"), maps, ACCEPT_Z)

def compare(eng, tpl):
    trial = score_trial()
    name, offset, count = trial.target()
    for index in range(offset,count):
        im = collect(eng, f"Use the same {name} finger for this entire group.", f"{name.capitalize()} · {index} of {count} recorded")
        trial.add(eng.score(tpl,im)[0])
        report("Touch recorded","Lift your finger completely.")
        eng.wait_lift(closing)
    if trial.finished():
        report("Score comparison complete",trial.summary())
    else:
        report("Group saved",f"Next: {trial.target()[0]} finger. Click the comparison button when ready.")

def capture(mode):
    try:
        raw = mode == "calibrate"
        eng = Engine(raw=raw)
        with eng:
            if raw:
                while len(cal_samples) < 24:
                    im = collect(eng,"Alternate fingers and vary placement. Hold still until accepted.",f"Calibration · {len(cal_samples)} of 24 accepted")
                    cal_samples.append(im)
                    report(f"Calibration · {len(cal_samples)} of 24 accepted","Lift your finger fully.")
                    eng.wait_lift(closing)
                gain,ridge,detail = calibrate.build_maps(cal_samples)
                residual = calibrate.residual_identity_correlation(cal_samples,gain,ridge,detail)
                if not 0 <= residual < 0.10:
                    cal_samples.clear()
                    raise RuntimeError("Calibration quality was too low. Start again with more varied placements.")
                store._atomic_save(str(maps),gain=gain,ridge=ridge,detail=detail)
                cal_samples.clear()
                report("Calibration saved","Next, enroll only your right index finger. Use that same finger for every enrollment touch.")
            else:
                tpl = store.Template.load("enrolled",finger)
                if mode == "enroll":
                    recent = []
                    while not tpl.full and not closing.is_set():
                        im = collect(eng,"Place only your RIGHT INDEX finger on the reader. Vary its position slightly.",f"Right index · {len(tpl.views)} views saved")
                        z,_,overlap,*_ = eng.score(tpl,im)
                        recent = (recent + [z >= ACCEPT_Z])[-10:]
                        if z < ACCEPT_Z or overlap < 0.85:
                            tpl.add(im)
                            tpl.save()
                        report(f"Right index · {len(tpl.views)} views saved","Lift fully before the next touch.")
                        eng.wait_lift(closing)
                        if len(tpl.views)>=12 and sum(recent)>=8:
                            break
                    if not closing.is_set():
                        done.touch(mode=0o600)
                        report("Right index enrolled and saved","Choose Test one touch. Try your right index, then another finger.")
                elif mode == "compare":
                    compare(eng,tpl)
                else:
                    im = collect(eng,"Place the finger you want to test on the reader. Hold still.","Waiting for one touch")
                    z = eng.score(tpl,im)[0]
                    trial = score_trial()
                    cutoff = trial.cutoff() if trial.validated() else ACCEPT_Z
                    result = "MATCH" if z>=cutoff else "NO MATCH"
                    report(result,f"Touch score {z:.2f} · cutoff {cutoff:.2f}")
                    print("One-touch verification:",result,flush=True)
    except Exception as exc:
        report("Capture paused",str(exc))
    finally:
        events.put(None)
def phase():
    if not maps.exists():
        return "calibrate"
    return "test" if done.exists() else "enroll"
def controls():
    button.configure(text={"calibrate":"Calibrate reader","enroll":"Enroll right index","test":"Test one touch"}[phase()],state="disabled" if busy else "normal")
    summary.set("Saved enrollment: right index finger" if done.exists() else "Enrollment target: right index finger")
    if done.exists():
        trial=score_trial()
        compare_button.configure(text=("View comparison result" if trial.finished() else f"Compare: {trial.target()[0]} finger"),state="disabled" if busy else "normal")
    else:
        compare_button.configure(state="disabled")
def start(mode=None):
    global busy
    if busy: return
    if mode=="compare" and score_trial().finished():
        report("Score comparison complete",score_trial().summary()); return
    busy=True
    controls()
    threading.Thread(target=capture,args=(mode or phase(),),daemon=True).start()
def poll():
    global busy
    while not events.empty():
        message=events.get_nowait()
        if message is None:
            busy=False
            controls()
        else:
            title.set(message[0]); detail.set(message[1])
    if closing.is_set() and not busy:
        root.destroy()
    else:
        root.after(70,poll)
def close():
    closing.set()
    if not busy: root.destroy()
root=tk.Tk(className="AcerTouchTest")
root.title("Acer Fingerprint Touch Test")
root.minsize(620,236)
frame=ttk.Frame(root,padding=24);frame.pack(fill="both",expand=True)
summary=tk.StringVar(); title=tk.StringVar(value={"calibrate":"Calibrate the reader","enroll":"Ready to enroll your right index","test":"Ready to test a finger"}[phase()])
detail=tk.StringVar(value="Use different fingers for calibration. After 24 accepted touches, the app saves the sensor correction and prompts you to enroll." if phase()=="calibrate" else "Click below when ready. Closing the app preserves your saved profile.")
ttk.Label(frame,textvariable=summary).pack(anchor="w")
ttk.Label(frame,textvariable=title,font=("Sans",21,"bold")).pack(anchor="w",pady=8)
ttk.Label(frame,textvariable=detail,font=("Sans",12),wraplength=550).pack(anchor="w")
button=ttk.Button(frame,command=start);button.pack(anchor="w",pady=16)
compare_button=ttk.Button(frame,command=lambda: start("compare"));compare_button.pack(anchor="w")
controls();root.protocol("WM_DELETE_WINDOW",close);poll();root.mainloop()
