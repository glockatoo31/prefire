#!/usr/bin/env python
# watchers_gui.py  –  Prefire GUI with Task-Scheduler automation, countdown,
# dark title bar and custom task-bar icon.

import json, pathlib, subprocess, sys, threading, time, re, platform, datetime
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser, getpass, ctypes, os

# ╔════════════════════════════════════════════════════════════════════╗
# ║            • WIN-SPECIFIC: dark caption & task-bar icon •          ║
# ╚════════════════════════════════════════════════════════════════════╝
if sys.platform == "win32":
    import ctypes.wintypes as wt

    APP_ID   = u"Prefire.Watchlist.Manager"                       # anything unique
    ICON_PATH = os.path.join(os.path.dirname(__file__), "prefire.ico")

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

    def _load_hicon(path):
        return ctypes.windll.user32.LoadImageW(
            None, path,                               # from file
            1,                                        # IMAGE_ICON
            0, 0,                                     # default sizes from .ico
            0x00000010 | 0x00000080)                  # LR_LOADFROMFILE | LR_DEFAULTSIZE

    def _apply_win_extras(hwnd: int):
        """Dark caption + big/small icon for the given window handle."""
        use_dark = ctypes.c_int(1)
        for attr in (20, 19):                         # Win10 ≥1903 else fallback
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                wt.HWND(hwnd), attr,
                ctypes.byref(use_dark), ctypes.sizeof(use_dark))

        WM_SETICON = 0x0080
        hicon = _load_hicon(ICON_PATH)
        for which in (0, 1):                         # 0 = small, 1 = big
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, which, hicon)

# ╔════════════════════════════════════════════════════════════════════╗
# ║                    • FILE PATHS & CONSTANTS •                      ║
# ╚════════════════════════════════════════════════════════════════════╝
CFG          = pathlib.Path("watchers.json")
SEEN_F       = pathlib.Path("seen.json")
NOTIFIED_F   = pathlib.Path("notified.json")
LAST_CHECK_F = pathlib.Path("last_check.txt")
JOBS_F       = pathlib.Path("jobs.json")           # written by sentinel.py
ATS_OPTIONS  = ("Greenhouse", "Lever", "Ashby", "Workday", "WorkdayIntercept")
SCHED_TASK_NAME = "SentinelJobChecker"             # Windows TaskScheduler task

# providers (unchanged) ---------------------------------------------------------
from providers import (
    GreenhouseProvider, LeverProvider, AshbyProvider,
    WorkdayProvider, WorkdayInterceptProvider
)
# from notifier import push  # only in sentinel.py

# helper load/save --------------------------------------------------------------
def load_cfg():
    if CFG.exists():
        try:
            txt = CFG.read_text().strip()
            return json.loads(txt) if txt else {}
        except json.JSONDecodeError:
            messagebox.showwarning("watchers.json", "Corrupted file – starting fresh.")
            CFG.unlink(missing_ok=True)
    return {}
def save_cfg(d): CFG.write_text(json.dumps(d, indent=2))
def load_seen():  return set(json.loads(SEEN_F.read_text()) if SEEN_F.exists() else [])
def save_seen(s): SEEN_F.write_text(json.dumps(list(s)))

# ────────────────── .env helpers ──────────────────
ENV_F = pathlib.Path(".env")

def _parse_env():
    data = {}
    if ENV_F.exists():
        for line in ENV_F.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    return data

def _write_env(d):
    lines = []
    already = _parse_env()
    already.update(d)                      # merge / overwrite keys we care about
    for k, v in already.items():
        lines.append(f"{k}={v}")
    ENV_F.write_text("\n".join(lines))


# ─────────────────────── Tk theme ────────────────────────
def azure_dark_style(rt: tk.Tk):
    style = ttk.Style(rt)
    dark, fg, hdr, hl = "#232323", "#f0f0f0", "#292929", "#39FF14"
    style.theme_use("default")
    style.configure(".", background=dark, foreground=fg)
    style.configure("TEntry",    fieldbackground=dark, foreground=fg, insertcolor=fg, padding=8)
    style.configure("TSpinbox",  fieldbackground=dark, foreground=fg, insertcolor=fg, padding=8)
    style.configure("TCombobox", fieldbackground=dark, foreground=fg, insertcolor=fg, padding=8)
    style.map("TCombobox", fieldbackground=[("readonly", dark)], foreground=[("readonly", fg)])
    style.configure("Treeview", background=dark, fieldbackground=dark, foreground=fg,
                    rowheight=27, borderwidth=0, font=("Segoe UI", 11))
    style.configure("Treeview.Heading", background=hdr, foreground=hl,
                    font=("Segoe UI", 10, "bold"))
    style.configure("TLabel", background=dark, foreground=fg, font=("Segoe UI", 10))
    style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"),
                    foreground=hl, background=dark, padding=4)
    style.configure("TButton", background="#363636", foreground=fg,
                    font=("Segoe UI", 10, "bold"), padding=6)
    style.map("TButton", background=[("active", "#444444")])
    style.configure("TFrame", background=dark, borderwidth=0, relief="flat")

# ╔════════════════════════════════════════════════════════════════════╗
# ║                         • MAIN WINDOW •                            ║
# ╚════════════════════════════════════════════════════════════════════╝
root = tk.Tk()
root.title("Prefire")

# ▲▲ call the NEW helper: dark caption + icons
if sys.platform == "win32":
    _apply_win_extras(root.winfo_id())

# small icon for title-bar / Alt-Tab
try:
    root.iconbitmap(ICON_PATH)
except tk.TclError:
    pass

# root fundamentals
root.configure(bg="#232323", highlightthickness=0)
root.geometry("1200x670"); root.minsize(900, 540)
azure_dark_style(root)

font_bold = ("Segoe UI", 11, "bold")
root.columnconfigure(0, weight=2, minsize=390)
root.columnconfigure(1, weight=3, minsize=380)
root.rowconfigure(0, weight=1); root.rowconfigure(1, weight=0); root.rowconfigure(2, weight=0)                             

# ────────────────── variables ──────────────────
last_check_var = tk.StringVar(value="Last check: Never")
name_var, ats_var = tk.StringVar(), tk.StringVar(value=ATS_OPTIONS[0])
fields = {k: tk.StringVar() for k in ("slug","tenant","cluster","site","locale")}
fields["cluster"].set("wd5"); fields["site"].set("External"); fields["locale"].set("en-US")
company_roles  = {}
pushover_user_var = tk.StringVar(value=_parse_env().get("PUSHOVER_USER_KEY", ""))
pushover_app_var  = tk.StringVar(value=_parse_env().get("PUSHOVER_APP_TOKEN", ""))


# ╔════════════════ LEFT PANE ════════════════╗
left = ttk.Frame(root, padding=(20, 18, 10, 12))
left.grid(row=0, column=0, sticky="nsew", padx=(10,4), pady=10)
left.rowconfigure(1, weight=1)

ttk.Label(left, text="Currently watching", style="Header.TLabel").grid(row=0, column=0, sticky="w")

button_row = ttk.Frame(left); button_row.grid(row=0, column=1, sticky="e")
def _btn(text): btn=ttk.Button(button_row,text=text,width=17); btn.pack(side="left",padx=2); return btn
run_btn   = _btn("Run check now")
ack_btn   = _btn("Acknowledge all as seen")
clr_btn   = _btn("Clear seen list")
del_btn   = _btn("Delete selected")
test_btn  = _btn("Test Fetch")
clear_notified_btn = _btn("Clear notifications")

tree = ttk.Treeview(left, columns=("dot","title","roles"), show="tree headings",
                    height=14, selectmode="browse")
tree.heading("dot", text=""); tree.column("dot", width=14, anchor="center", stretch=False)
tree.heading("title", text="Position Title"); tree.column("title", width=310, anchor="w")
tree.heading("roles", text="# Roles"); tree.column("roles", width=70, anchor="center")
tree.tag_configure("odd", background="#1a1a1a")
tree.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(5,10))

alert_console = tk.Text(left, height=8, bg="#181818", fg="#e0ffe5",
                        wrap="word", state="disabled",
                        font=("Consolas",11,"bold"), relief="flat",
                        borderwidth=0, padx=10, pady=10)
alert_console.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0,6))

ttk.Label(root, textvariable=last_check_var, anchor="w",
          padding=(12,4), style="TLabel").grid(row=1,column=0,columnspan=2,sticky="ew")
status=ttk.Label(root,text="Ready",anchor="w",padding=(12,4),style="TLabel")
status.grid(row=2,column=0,columnspan=2,sticky="ew")

# ╔════════════════ RIGHT PANE ════════════════╗
right = ttk.Frame(root, padding=(24,18,22,16), relief="solid", borderwidth=2)
right.grid(row=0,column=1,sticky="nsew", padx=(6,12), pady=10)
right.grid_columnconfigure(1, weight=1)

# --- Watcher form ---
form = ttk.Frame(right); form.pack(fill="both",expand=True); form.grid_columnconfigure(1,weight=1)
def row(label, var, r):
    ttk.Label(form, text=label+":", anchor="w", font=font_bold)\
        .grid(row=r,column=0,sticky="w",pady=6,padx=2)
    e=ttk.Entry(form,textvariable=var,width=30)
    e.grid(row=r,column=1,sticky="ew",pady=6,padx=2); return e
row("Company", name_var, 0)
ttk.Label(form,text="ATS:",anchor="w",font=font_bold).grid(row=1,column=0,sticky="w",pady=(12,4))
ats_cb=ttk.Combobox(form,textvariable=ats_var,values=ATS_OPTIONS,state="readonly",width=27)
ats_cb.grid(row=1,column=1,sticky="ew",pady=4)
fields_entries={k:row(k.capitalize(),v,i+2) for i,(k,v) in enumerate(fields.items())}
ATS_USAGE = {
    "slug":{"Greenhouse","Lever","Ashby"}, "tenant":{"Workday","WorkdayIntercept"},
    "cluster":{"Workday","WorkdayIntercept"},"site":{"Workday","WorkdayIntercept"},
    "locale":{"Workday","WorkdayIntercept"}
}
def _update_vis(*_):
    sel=ats_var.get()
    for k,e in fields_entries.items():
        e.configure(state="normal" if sel in ATS_USAGE.get(k,()) else "disabled")
ats_var.trace_add("write",_update_vis); _update_vis()

def add_company():
    name=name_var.get().strip()
    if not name: messagebox.showerror("Input","Company name required"); return
    info={"ats":ats_var.get()}
    if info["ats"] in ("Greenhouse","Lever","Ashby"):
        slug=fields["slug"].get().strip()
        if not slug: messagebox.showerror("Input","slug/org required"); return
        info["slug"]=slug
    else:
        for k in ("tenant","cluster","site","locale"):
            v=fields[k].get().strip()
            if not v and k!="locale": messagebox.showerror("Input",f"{k} required"); return
            info[k]=v
    cfg=load_cfg(); cfg[name]=info; save_cfg(cfg); refresh_tree()
    status.config(text=f"✔ {name} saved"); root.after(2500,lambda:status.config(text="Ready"))
ttk.Button(form,text="Add / Update",command=add_company,style="TButton")\
   .grid(row=8,column=0,columnspan=2,pady=(20,2))

# --- Auto-extract URL helper ---
ex_frame=ttk.Frame(right,padding=(0,14,0,0)); ex_frame.pack(fill="x",pady=(0,6))
url_var=tk.StringVar()
ttk.Label(ex_frame,text="Job board URL:",font=font_bold).pack(side="left")
ttk.Entry(ex_frame,textvariable=url_var,width=46).pack(side="left",padx=(4,6))
def auto_extract():
    url=url_var.get().strip(); res=None
    m=re.match(r"https?://boards\.greenhouse\.io/([^/]+)/?",url)
    if m: slug=m.group(1); name_var.set(slug.capitalize()); ats_var.set("Greenhouse"); fields["slug"].set(slug); res="Greenhouse"
    m=re.match(r"https?://jobs\.lever\.co/([^/]+)/?",url)
    if m: slug=m.group(1); name_var.set(slug.capitalize()); ats_var.set("Lever"); fields["slug"].set(slug); res="Lever"
    m=re.match(r"https?://([^/]+)\.ashbyhq\.com/job_board/([^/]+)",url)
    if m: slug=m.group(2); name_var.set(slug.capitalize()); ats_var.set("Ashby"); fields["slug"].set(slug); res="Ashby"
    m=re.match(r"https?://([^.]+)\.([^.]+)\.myworkdayjobs\.com/([^/]+)?/?([^/?#]+)?",url)
    if m:
        tenant,cluster,p3,p4=m.groups(); site="External"; locale="en-US"
        if p4 and p3: locale=p3; site=p4
        elif p3: site=p3
        name_var.set(tenant.upper()); ats_var.set("Workday")
        fields["tenant"].set(tenant); fields["cluster"].set(cluster)
        fields["site"].set(site); fields["locale"].set(locale); res="Workday"
    status.config(text=f"✔ Detected {res}" if res else "❌ Unknown URL")
    root.after(2500,lambda:status.config(text="Ready"))
ttk.Button(ex_frame,text="Auto Detect",command=auto_extract,style="TButton").pack(side="left")

# ╔═════ Windows Task-Scheduler automation panel ═════╗
def is_windows(): return platform.system().lower().startswith("win")
def task_exists(): return is_windows() and subprocess.run(
        ["schtasks","/Query","/TN",SCHED_TASK_NAME],capture_output=True).returncode==0
def raw_next_run():
    if not task_exists(): return "N/A"
    r=subprocess.run(["schtasks","/Query","/TN",SCHED_TASK_NAME,"/V","/FO","LIST"],
                     capture_output=True,text=True)
    if r.returncode==0:
        for l in r.stdout.splitlines():
            if "Next Run Time:" in l: return l.split(":",1)[1].strip()
    return "Unknown"
def create_or_update_task(minutes: int):
    """Create / replace the SentinelJobChecker task (window-less)."""
    if platform.system().lower() != "windows":
        return False, "Scheduler only on Windows"

    script_dir  = pathlib.Path(__file__).parent.absolute()
    pythonw_exe = pathlib.Path(sys.executable).with_name("pythonw.exe")
    sentinel_py = script_dir / "sentinel.py"
    current_user = getpass.getuser()      # e.g. 'DESKTOP\\bob' or just 'bob'

    cmd = [
        "schtasks", "/Create",
        "/SC", "MINUTE", "/MO", str(minutes),
        "/TN", SCHED_TASK_NAME,
        "/TR", f'"{pythonw_exe}" "{sentinel_py}"',   # ← no wrapper, no window
        "/RU", current_user,                         # run in your context
        "/F"                                         # replace if exists
    ]

    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())

def delete_task():
    if not is_windows(): return True,"No scheduler"
    if not task_exists(): return True,"No task"
    r=subprocess.run(["schtasks","/Delete","/TN",SCHED_TASK_NAME,"/F"],
                     capture_output=True,text=True)
    return r.returncode==0,(r.stdout.strip() or r.stderr.strip())

auto_panel=ttk.LabelFrame(right,text="Background Automation",padding=(10,8))
## ╔═════ Pushover keys panel ═════╗
push_frame = ttk.LabelFrame(right, text="Pushover Settings", padding=(10, 8))
push_frame.pack(fill="x", pady=(14, 0))

ttk.Label(push_frame, text="User key:").grid(row=0, column=0, sticky="w")
ttk.Entry(push_frame, textvariable=pushover_user_var, width=46)\
    .grid(row=0, column=1, sticky="ew", padx=4, pady=2)

ttk.Label(push_frame, text="App token:").grid(row=1, column=0, sticky="w")
ttk.Entry(push_frame, textvariable=pushover_app_var, width=46)\
    .grid(row=1, column=1, sticky="ew", padx=4, pady=2)

def _save_env_click():
    _write_env({
        "PUSHOVER_USER_KEY":  pushover_user_var.get().strip(),
        "PUSHOVER_APP_TOKEN": pushover_app_var.get().strip()
    })
    status.config(text="✔  .env updated")
    root.after(2500, lambda: status.config(text="Ready"))

ttk.Button(push_frame, text="Save to .env", command=_save_env_click)\
    .grid(row=2, column=1, sticky="e", pady=(6, 0))

if is_windows(): auto_panel.pack(fill="x",pady=(16,0))

auto_freq_var=tk.IntVar(value=60)
ttk.Label(auto_panel,text="Frequency (min):").grid(row=0,column=0,sticky="w")
ttk.Spinbox(auto_panel,from_=5,to=1440,increment=5,width=6,textvariable=auto_freq_var)\
    .grid(row=0,column=1,sticky="w",padx=4)
auto_status_var=tk.StringVar(value="Disabled")
auto_next_var  =tk.StringVar(value="N/A")
countdown_var  =tk.StringVar(value="--:--")

def _refresh_sched():
    auto_status_var.set("Enabled" if task_exists() else "Disabled")
    auto_next_var.set(raw_next_run())
def _start_auto():
    ok,msg=create_or_update_task(auto_freq_var.get()); status.config(text=msg)
    _refresh_sched()
def _stop_auto():
    ok,msg=delete_task(); status.config(text=msg); _refresh_sched()
ttk.Button(auto_panel,text="Enable",command=_start_auto).grid(row=0,column=2,padx=6)
ttk.Button(auto_panel,text="Disable",command=_stop_auto).grid(row=0,column=3,padx=4)
ttk.Label(auto_panel,text="Status:").grid(row=1,column=0,sticky="w",pady=(8,0))
ttk.Label(auto_panel,textvariable=auto_status_var,foreground="#39FF14")\
    .grid(row=1,column=1,sticky="w",pady=(8,0))
ttk.Label(auto_panel,text="Next run:").grid(row=1,column=2,sticky="e",padx=(6,2),pady=(8,0))
ttk.Label(auto_panel,textvariable=auto_next_var).grid(row=1,column=3,sticky="w",pady=(8,0))
ttk.Label(auto_panel,text="Countdown:").grid(row=2,column=0,sticky="w",pady=(4,2))
ttk.Label(auto_panel,textvariable=countdown_var,
          foreground="#39FF14",font=font_bold)\
          .grid(row=2,column=1,sticky="w",pady=(4,2))

def _update_countdown():
    nxt=auto_next_var.get()
    if auto_status_var.get()=="Enabled" and nxt not in ("N/A","Unknown"):
        try:
            dt=datetime.datetime.strptime(nxt,"%m/%d/%Y %I:%M:%S %p")
            delta=int((dt-datetime.datetime.now()).total_seconds())
            if delta<0: delta=0
            h,rem=divmod(delta,3600); m,s=divmod(rem,60)
            countdown_var.set(f"{h:02}:{m:02}:{s:02}")
        except Exception: countdown_var.set("--:--")
    else: countdown_var.set("--:--")
    root.after(1000,_update_countdown)
def _poll_sched(): _refresh_sched(); root.after(20000,_poll_sched)

if is_windows():
    _poll_sched(); _update_countdown()
else:
    auto_panel.pack_forget()

# ────────────────── tree refresh ──────────────────
def refresh_tree():
    exp={i:tree.item(i,"open") for i in tree.get_children()}
    tree.delete(*tree.get_children()); company_roles.clear()
    seen=load_seen()
    for idx,(name,info) in enumerate(load_cfg().items()):
        tag=("odd",) if idx%2 else ()
        jobs=json.loads(JOBS_F.read_text()).get(name,[]) if JOBS_F.exists() else []
        company_roles[name]=jobs
        new_present=any(str(j["id"]) not in seen for j in jobs)
        comp_tag=f"{name}_tag"
        tree.tag_configure(comp_tag,foreground="#39FF14" if new_present else "#f0f0f0",
                           font=("Segoe UI",11,"bold"))
        parent=tree.insert("", "end", iid=name, values=("",name,len(jobs)),
                           tags=(comp_tag,)+tag, open=exp.get(name,False))
        for j in jobs:
            jid=str(j["id"]); new=jid not in seen
            dot="\u25CF" if new else ""
            dtag,titag=f"d{jid}",f"t{jid}"
            tree.tag_configure(dtag,foreground="#39FF14" if new else "#f0f0f0")
            tree.tag_configure(titag,foreground="#39FF14" if new else "#f0f0f0")
            tree.insert(parent,"end",iid=f"{name}::{jid}",
                        values=(dot,j["title"],""), tags=(dtag,titag)+tag)

# ────────────────── core actions ──────────────────
def add_alert(msg):
    alert_console.config(state="normal"); alert_console.insert("end",msg+"\n")
    alert_console.see("end"); alert_console.config(state="disabled")

def acknowledge_all():
    ids={str(j["id"]) for jobs in company_roles.values() for j in jobs}
    save_seen(load_seen()|ids); refresh_tree()
    status.config(text="✔ marked seen"); root.after(2000,lambda:status.config(text="Ready"))
def clear_seen(): SEEN_F.write_text("[]"); refresh_tree(); status.config(text="✔ seen cleared")
def clear_notified(): NOTIFIED_F.write_text("[]"); status.config(text="✔ notified cleared")
for b,f in ((ack_btn,acknowledge_all),(clr_btn,clear_seen),(clear_notified_btn,clear_notified)):
    b.config(command=lambda fn=f: (fn(), root.after(2000,lambda:status.config(text="Ready"))))

# open job link on double-click
tree.bind("<Double-1>",lambda e: (
    sel:=tree.selection(),
    webbrowser.open(
        next((j["url"] for c in [sel[0].split("::")[0]]
              for j in company_roles.get(c,[]) if sel[0].endswith(str(j["id"]))),""),
        new=2)
    )[0] if tree.selection() else None)

# run sentinel.py
CREATE_NO_WINDOW = 0x08000000 
PYTHONW = pathlib.Path(sys.executable).with_name("pythonw.exe")
def run_check():
    def runner():
        status.config(text="⚡ running sentinel …")
        add_alert("[RUN] sentinel.py")
        res = subprocess.run(
            [PYTHONW, "sentinel.py"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW  # extra safety
        )
        if res.stdout: add_alert(res.stdout.strip())
        if res.stderr: add_alert("[stderr] "+res.stderr.strip())
        status.config(text="✔ check complete" if res.returncode==0 else "⚠ sentinel error")
        LAST_CHECK_F.write_text(time.strftime('%Y-%m-%d %H:%M:%S'))
        last_check_var.set("Last check: "+LAST_CHECK_F.read_text())
        refresh_tree(); root.after(3000,lambda:status.config(text="Ready"))
    threading.Thread(target=runner,daemon=True).start()
run_btn.config(command=run_check)

# delete watcher
def delete_selected():
    sels=[i for i in tree.selection() if "::" not in i]
    if not sels: messagebox.showinfo("Delete","Select a company"); return
    name=sels[0]
    if messagebox.askyesno("Delete",f"Delete '{name}'?"):
        cfg=load_cfg(); cfg.pop(name,None); save_cfg(cfg); refresh_tree()
        status.config(text=f"❌ {name} deleted"); root.after(2000,lambda:status.config(text="Ready"))
del_btn.config(command=delete_selected)

# test fetch
def test_fetch_any():
    alert_console.config(state="normal"); alert_console.insert("end","=== Any-role Test ===\n")
    cfg=load_cfg()
    for name,info in cfg.items():
        try:
            cls={"Greenhouse":GreenhouseProvider,"Lever":LeverProvider,"Ashby":AshbyProvider,
                 "Workday":WorkdayProvider,"WorkdayIntercept":WorkdayInterceptProvider}[info["ats"]]
            if info["ats"] in ("Greenhouse","Lever","Ashby"):
                prov=cls(info["slug"],extra_filter=lambda _:True)
            else:
                prov=cls(tenant=info["tenant"],cluster=info["cluster"],
                         site=info["site"],locale=info["locale"],extra_filter=lambda _:True)
            num=len(list(prov.fetch()))
            alert_console.insert("end",f"{name}: {'YES' if num else 'NO'} ({num})\n")
        except Exception as e: alert_console.insert("end",f"{name}: ERROR {e}\n")
    alert_console.insert("end","====================\n"); alert_console.config(state="disabled")
test_btn.config(command=lambda: threading.Thread(target=test_fetch_any,daemon=True).start())

# initial load & periodic refresh
def load_last_check():
    if LAST_CHECK_F.exists(): last_check_var.set("Last check: "+LAST_CHECK_F.read_text())
load_last_check(); refresh_tree()
def periodic(): refresh_tree(); load_last_check(); root.after(60000,periodic)
periodic()

root.mainloop()
