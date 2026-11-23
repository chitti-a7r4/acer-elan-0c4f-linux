import os, subprocess, tkinter as tk
from pathlib import Path
from tkinter import ttk
b=Path(__file__).parent
data=Path.home()/'.local/share/acer-oem-touch'
env=dict(os.environ,ELAN_OEM_ENGINE_DLL=str(data/'EngineAdapter.dll'))
root=tk.Tk();root.title("Native ELAN verification")
name=tk.StringVar(); msg=tk.StringVar(value="Leave the reader empty and click Start.")
targets=['right index']*5+['right pinky']*5+['right middle']*5
outcomes=[];process=None
def prepare():
    name.set(f"Test your {targets[len(outcomes)]} finger" if len(outcomes)<len(targets) else "Testing complete")
def start():
    global process
    if process: return
    btn.configure(state="disabled")
    msg.set("Keep the reader empty while it calibrates.")
    process=subprocess.Popen([b/'native-check',data/'profile/right-index.oem'],env=env,stdout=subprocess.PIPE)
    os.set_blocking(process.stdout.fileno(),False)
    root.after(75,poll)
def poll():
    global process
    output=process.stdout.read() or b''
    if b'READY' in output:msg.set(f"Place only your {targets[len(outcomes)]} finger on the reader and hold still.")
    result=process.poll()
    if result is None:
        root.after(75,poll);return
    process.stdout.close();process=None
    if result in (0,1):
        finger=targets[len(outcomes)]
        outcomes.append((finger,result==0))
        print(f"{finger}: {'MATCH' if result==0 else 'NO MATCH'}",flush=True)
        msg.set(f"{finger}: {'MATCH' if result==0 else 'NO MATCH'}. Lift fully before the next test.")
    else:msg.set("Scan incomplete. Lift fully, then retry.")
    prepare()
    if len(outcomes)<len(targets):btn.configure(state="normal",text="Start next touch")
    else:
        msg.set("   ".join(f"{f}: {sum(m for n,m in outcomes if n==f)}/5 matched" for f in dict.fromkeys(targets)))
def close():
    if process:process.terminate()
    root.destroy()
root.protocol("WM_DELETE_WINDOW",close)
frame=ttk.Frame(root,padding=22);frame.pack()
ttk.Label(frame,textvariable=name,font=("Sans",22)).pack(anchor="w")
ttk.Label(frame,textvariable=msg,font=("Sans",13),wraplength=600).pack(pady=14)
btn=ttk.Button(frame,text="Start",command=start);btn.pack(anchor="w")
prepare();root.mainloop()
