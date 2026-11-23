"""Evaluate the ELAN OEM engine with genuine local ELAN 0c4f captures."""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk

import numpy as np
from elantouch.engine import Engine, Touch
from elantouch import store

os.umask(0o077)
home = Path.home() / ".local/share"
app = home / "acer-oem-touch"
source = home / "acer-touch-test/profile"
data = app / "profile"
data.mkdir(mode=0o700, exist_ok=True)
template = data / "right-index.oem"
engine_dll = app / "EngineAdapter.dll"
expected_hash = "8f9254d10594ff7479741e72d22abec9417807257ac0c7a967ec7eaa8865a9e9"
events = queue.Queue()
stop = threading.Event()
groups = [("right index", 5), ("right pinky", 5), ("right middle", 5)]
log = data / "verification.jsonl"

def load_calibration(cls):
    c = cls()
    with np.load(source / "calibration.npz", allow_pickle=False) as z:
        c.gain, c.fpn_ridge, c.fpn_detail = (z[k] for k in ("gain", "ridge", "detail"))
    return c

store.Calibration.load = classmethod(load_calibration)
store.Calibration.save_background = lambda self, image: setattr(self, "background", image)

def pixels(im):
    if im.shape != (80, 80) or not np.isfinite(im).all() or np.percentile(im, 90) < 500:
        raise ValueError("Too little signal. Lift and try a fresh touch.")
    lo, hi = im.min(), im.max()
    if hi == lo:
        raise ValueError("No fingerprint contrast.")
    return np.clip((im - lo) * 255 / (hi - lo), 0, 255).astype(np.uint8)

def probe(mode, images):
    if hashlib.sha256(engine_dll.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("Unexpected ELAN engine version.")
    fds = []
    try:
        for image in images:
            fd = os.memfd_create("fingerprint-frame")
            fds.append(fd)
            os.write(fd, image.tobytes())
        proc = subprocess.run([app / "probe", engine_dll, mode, template,
                               *(f"/proc/self/fd/{fd}" for fd in fds)],
                              pass_fds=fds, capture_output=True, timeout=20)
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"Engine process failed ({proc.returncode}).")
        return proc.returncode == 0
    finally:
        for fd in fds:
            os.close(fd)

def enrollment_images():
    with np.load(source / "enrolled/right-index-finger.npz", allow_pickle=False) as z:
        frames = [pixels(im.astype(np.float32)) for im in z["views"]]
    frames.extend(np.load(p, allow_pickle=False) for p in sorted(data.glob("index-*.npy")))
    return frames

def notify(title, text):
    events.put((title, text))

def results():
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines()]

def target():
    for name, n in groups:
        if sum(r["finger"] == name for r in results()) < n:
            return name
    return None

def capture(engine, label):
    notify(label, "Rest the indicated finger on the reader and hold still.")
    status, image = engine.touch(timeout=30, cancel=stop)
    if status != Touch.OK or stop.is_set():
        raise RuntimeError("Touch incomplete. Lift fully, then resume when ready.")
    return pixels(image)

def test_group(engine, name):
    count = sum(r["finger"] == name for r in results())
    for i in range(count, 5):
        frame = capture(engine, f"{name.capitalize()} · touch {i+1} of 5")
        accepted = probe("verify", [frame])
        with log.open("a") as out:
            out.write(json.dumps({"finger":name,"match":accepted})+"\n")
        notify("MATCH" if accepted else "NO MATCH", "Lift fully before the next touch.")
        engine.wait_lift(stop)
        if stop.is_set():
            break
    notify("Group saved", "Click the next named group when ready.")

def worker(mode):
    try:
        if mode == "enroll":
            frames = enrollment_images()
            with Engine() as engine:
                while not stop.is_set() and len(frames) < 45:
                    im = capture(engine, f"Right index only · {len(frames)} views available")
                    path = data / f"index-{len(frames):03d}.npy"
                    with path.open("xb") as out:
                        np.save(out, im, allow_pickle=False)
                    frames.append(im)
                    complete = probe("enroll", frames)
                    notify("Right index touch saved", "Lift fully.")
                    engine.wait_lift(stop)
                    if complete:
                        break
            if not template.exists():
                raise RuntimeError("Enrollment incomplete. Your accepted views are saved.")
            empty_match = probe("verify", [np.full((80, 80), 127, np.uint8)])
            if empty_match:
                (data / "failed-empty-control").touch()
                raise RuntimeError("Engine matched the empty control; verification disabled.")
            notify("OEM right index saved", "Click the right-index test when ready.")
        else:
            with Engine() as engine:
                if mode == "single":
                    accepted = probe("verify", [capture(engine,"Test one touch")])
                    notify("MATCH" if accepted else "NO MATCH","Compared with your saved OEM right index.")
                else:
                    test_group(engine,mode)
    except Exception as exc:
        notify("Capture paused", str(exc))
    finally:
        events.put(None)

root = tk.Tk(className="AcerOemTouch")
root.title("ELAN OEM fingerprint test")
root.geometry("720x270")
frame = ttk.Frame(root,padding=24); frame.pack(fill="both",expand=True)
heading = tk.StringVar(value="ELAN OEM right-index enrollment")
body = tk.StringVar(value="Keep the reader empty until prompted. Your earlier right-index views are available.")
counts = tk.StringVar()
ttk.Label(frame,textvariable=heading,font=("Sans",19,"bold")).pack(anchor="w")
ttk.Label(frame,textvariable=body,wraplength=640,font=("Sans",12)).pack(anchor="w",pady=12)
ttk.Label(frame,textvariable=counts).pack(anchor="w")
button = ttk.Button(frame); button.pack(anchor="w",pady=12)
busy=False
def start(mode):
    global busy
    if busy: return
    busy=True; button.configure(state="disabled")
    threading.Thread(target=worker,args=(mode,),daemon=True).start()
def refresh():
    entries = results()
    counts.set("    ".join(f"{name}: {sum(r['match'] for r in entries if r['finger']==name)}/{sum(r['finger']==name for r in entries)} matched" for name,_ in groups))
    mode = (target() or "single") if template.exists() else "enroll"
    text = "Continue right-index enrollment" if mode=="enroll" else "Test one touch" if mode=="single" else f"Test {mode} finger"
    button.configure(text=text,command=lambda:start(mode),state="disabled" if busy or (data/"failed-empty-control").exists() else "normal")
def poll():
    global busy
    while not events.empty():
        e=events.get_nowait()
        if e is None:
            busy=False
        else:
            heading.set(e[0]);body.set(e[1])
        refresh()
    if stop.is_set() and not busy:
        root.destroy()
    else:
        root.after(100,poll)
root.protocol("WM_DELETE_WINDOW",stop.set)
refresh();poll();root.mainloop()
