#!/usr/bin/python3
"""Local enrollment and verification for an fprintd fingerprint reader."""
import os
import queue
import re
import subprocess
import threading
import tkinter as tk
from tkinter import ttk

BG, CARD, INK, MUTED = "#eff4f2", "#ffffff", "#183930", "#49645d"
GREEN, PALE, OUTLINE = "#147358", "#dcebe4", "#9db5a9"
NAMES = ("thumb", "index-finger", "middle-finger", "ring-finger", "little-finger")
FINGERS = [f"{side}-{name}" for side in ("left", "right") for name in NAMES]


def title(finger):
    return finger.replace("-", " ").capitalize()


class Studio:
    def __init__(self, root):
        self.root = root
        root.title("Fingerprint Studio")
        root.configure(bg=BG)
        root.minsize(650, 590)
        self.first_load = True
        self.finger = "right-index-finger"
        self.saved = set()
        self.ready = False
        self.proc = None
        self.generation = 0
        self.events = queue.Queue()
        self.stages = 6
        self.press = False
        self.step = 0
        self.summary = tk.StringVar(value="Looking for your fingerprint reader…")
        self.status = tk.StringVar()
        self.detail = tk.StringVar()
        body = tk.Frame(root, bg=BG, padx=24, pady=16)
        body.pack(fill="both", expand=True)
        def label(parent, text, size, bold=False, color=INK, **kw):
            return tk.Label(parent, text=text, font=("Sans", size, "bold" if bold else "normal"),
                            bg=parent["bg"], fg=color, **kw)
        label(body, "Your fingerprints", 23, True).pack(anchor="w")
        label(body, "", 11, color=MUTED, textvariable=self.summary).pack(anchor="w", pady=(1, 12))
        card = tk.Frame(body, bg=CARD, padx=12, pady=8)
        card.pack(fill="x")
        label(card, "Select a fingertip", 13, True).pack(anchor="w")
        self.map = tk.Canvas(card, width=580, height=225, bg=CARD, highlightthickness=0)
        self.map.pack()
        label(card, "Filled dot = saved     •     Outer ring = selected", 10, color=MUTED).pack()
        panel = tk.Frame(body, bg=BG)
        panel.pack(fill="x", pady=(14, 0))
        self.choice = ttk.Combobox(panel, values=[title(f) for f in FINGERS], state="readonly", width=22)
        self.choice.set(title(self.finger))
        self.choice.pack(side="left")
        self.choice.bind("<<ComboboxSelected>>", lambda _: self.select(FINGERS[self.choice.current()]))
        self.action = ttk.Button(panel, command=self.scan)
        self.action.pack(side="left", padx=8)
        self.cancel = ttk.Button(panel, text="Cancel scan", command=self.stop)
        self.cancel.pack(side="left")
        self.refresh = ttk.Button(panel, text="Refresh", command=self.reload)
        self.refresh.pack(side="right")
        label(body, "", 13, True, textvariable=self.status).pack(anchor="w", pady=(14, 3))
        label(body, "", 11, color=MUTED, textvariable=self.detail, wraplength=590,
              justify="left", anchor="nw").pack(fill="x")
        self.bar = ttk.Progressbar(body, maximum=self.stages)
        self.bar.pack(fill="x", pady=10)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.reload()
        root.after(60, self.poll)

    def draw(self):
        c = self.map
        c.delete("all")
        for side in ("left", "right"):
            def x(v):
                return v if side == "left" else 580-v
            # Palm view, thumbs facing the center.
            c.create_polygon(*[v for a,b in [(100,102),(190,97),(198,149),(224,115),
                             (239,129),(202,183),(181,199),(121,199),(100,165)]
                             for v in (x(a), b)], smooth=True, fill=PALE, outline=OUTLINE, width=2)
            for name, a, b, base in zip(NAMES, (234,181,155,129,103), (114,54,36,50,78),
                                        (157,127,122,128,137)):
                finger = side+"-"+name
                end = a-30 if name=="thumb" else a
                tag = "pick-"+finger
                for color,width in ((OUTLINE,25),(PALE,22)):
                    c.create_line(x(a),b,x(end),base, width=width, fill=color, capstyle="round",tags=tag)
                cx = x(a)
                c.create_oval(cx-7,b-7,cx+7,b+7,fill=GREEN if finger in self.saved else CARD,
                              outline=GREEN,width=2,tags=tag)
                if finger==self.finger:
                    c.create_oval(cx-15,b-15,cx+15,b+15,outline=INK,width=2,tags=tag)
                c.tag_bind(tag,"<Button-1>",lambda _, f=finger:self.select(f))
            c.create_text(x(153),214,text=side.capitalize()+" hand",fill=INK,font=("Sans",11,"bold"))

    def buttons(self):
        busy = self.proc is not None
        self.action.configure(text="Test fingerprint" if self.finger in self.saved else "Enroll fingerprint",
                              state="normal" if self.ready and not busy else "disabled")
        self.cancel.configure(state="normal" if busy and self.mode!="list" else "disabled")
        self.refresh.configure(state="disabled" if busy else "normal")
        self.choice.configure(state="disabled" if busy else "readonly")
        self.draw()

    def select(self, finger):
        if self.proc:
            return
        self.finger = finger
        self.choice.set(title(finger))
        self.bar["value"] = 0
        if self.ready:
            self.status.set(title(finger) + (" is saved" if finger in self.saved else " is empty"))
            self.detail.set("Choose Test fingerprint to check a match." if finger in self.saved
                            else "Choose Enroll fingerprint when you are ready.")
        self.buttons()

    def run(self, mode, args):
        self.mode = mode
        self.generation += 1
        token = self.generation
        try:
            p = subprocess.Popen(["stdbuf","-oL","-eL",*args], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, env={**os.environ,"LC_ALL":"C"})
        except OSError as exc:
            self.status.set("Could not start fingerprint service")
            self.detail.set(str(exc))
            self.buttons()
            return
        self.proc = p
        self.lines = []
        self.buttons()
        def read():
            with p.stdout:
                for line in p.stdout:
                    self.events.put((token,line.strip()))
            p.wait()
            self.events.put((token,None))
        threading.Thread(target=read,daemon=True).start()

    def reload(self, keep=False):
        self.keep = keep
        self.ready = False
        if not keep:
            self.status.set("Checking saved fingers…")
            self.detail.set("")
        self.run("list",["fprintd-list",__import__("pwd").getpwuid(os.getuid()).pw_name])

    def scan(self):
        self.step = 0
        self.result = ""
        self.bar["value"] = 0
        mode = "verify" if self.finger in self.saved else "enroll"
        self.status.set(("Place your " if self.press else "Swipe your ") + title(self.finger).lower())
        self.detail.set("Start with the reader empty. Rest the finger pad on the reader, hold still, then lift fully."
                        if self.press else "Draw the pad slowly across the reader, then lift fully.")
        self.run(mode,["fprintd-"+mode,"-f",self.finger])

    def line(self, line):
        self.lines.append(line)
        if self.mode=="list":
            return
        match = re.search(r'(?:Enroll|Verify) result: ([\w-]+)',line)
        if not match:
            return
        self.result = match[1]
        if self.result=="enroll-stage-passed":
            self.step += 1
            self.bar["value"] = self.step
            self.status.set(f"Samples accepted · {self.step}")
            self.detail.set("Lift fully, then scan the same finger again.")
        elif self.result in ("enroll-completed","verify-match"):
            self.bar["value"] = self.stages
            self.status.set("Fingerprint saved" if self.mode=="enroll" else "Fingerprint matched")
            self.detail.set(title(self.finger) + (" is enrolled. Choose Test fingerprint to try it." if self.mode=="enroll" else " was recognized."))
        elif self.result=="verify-no-match":
            self.status.set("Fingerprint didn’t match")
            self.detail.set("Try the same finger again at the angle you used during enrollment.")
        elif "disconnected" in self.result or "failed" in self.result or "unknown-error" in self.result:
            self.status.set("Reader stopped responding")
            self.detail.set("The scan ended. Lift your finger and try again. If this repeats, the reader or driver needs attention.")
        else:
            self.status.set("Try another scan")
            self.detail.set({"enroll-swipe-too-short":"The reader reported a short swipe. Move the whole finger pad slowly across it.",
                             "enroll-finger-not-centered":"Center the finger pad over the reader.",
                             "enroll-remove-and-retry":"Lift your finger fully before swiping again."}.get(self.result,self.result.replace("-"," ")))

    def finish(self):
        self.proc = None
        if self.mode=="list":
            output = "\n".join(self.lines)
            self.press = "(press)" in output or "ELAN Fingerprint Sensor (OEM matcher)" in output
            device_path = re.search(r"Using device (/net/reactivated/Fprint/Device/\d+)",output)
            if device_path:
                try:
                    value = subprocess.check_output(["busctl","get-property","net.reactivated.Fprint",
                        device_path[1],"net.reactivated.Fprint.Device","num-enroll-stages"],text=True,timeout=1)
                    self.stages = int(value.split()[1])
                except (OSError, ValueError, IndexError, subprocess.SubprocessError):
                    pass
            self.bar.configure(maximum=self.stages)
            entries = re.findall(r'^\s*- #\d+: ([a-z-]+)\s*$', output, re.MULTILINE)
            self.saved = set(entries).intersection(FINGERS)
            self.ready = bool(self.saved) or " has no fingers enrolled for " in output
            if self.first_load and self.ready:
                self.first_load = False
                if self.saved:
                    self.finger = next(f for f in FINGERS if f in self.saved)
            self.summary.set(f"ElanTech reader  ·  {len(self.saved)} of 10 fingers saved" if self.ready
                             else "Saved fingerprints unavailable")
            if not self.ready:
                self.status.set("Couldn’t read enrollment status")
                self.detail.set(self.lines[-1] if self.lines else "Choose Refresh to try again.")
            elif not self.keep:
                self.select(self.finger)
        elif self.result=="enroll-completed":
            self.reload(keep=True)
            return
        elif not self.result or self.result=="enroll-stage-passed":
            self.status.set("Scan ended before completion")
            self.detail.set(self.lines[-1] if self.lines else "Try again when the reader is ready.")
        self.buttons()

    def poll(self):
        while not self.events.empty():
            token,line = self.events.get_nowait()
            if token==self.generation:
                if line is None:
                    self.finish()
                else:
                    self.line(line)
        self.root.after(60,self.poll)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=3)
            self.proc = None
            self.generation += 1
        self.status.set("Scan canceled")
        self.detail.set("Choose a finger to start again.")
        self.bar["value"] = 0
        self.reload(keep=True)

    def close(self):
        if self.proc:
            self.proc.terminate()
        self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk(className="FingerprintStudio")
    Studio(window)
    window.mainloop()
