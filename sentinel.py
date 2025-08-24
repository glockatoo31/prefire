import json, pathlib, time, traceback
from providers import (
    GreenhouseProvider, LeverProvider, AshbyProvider,
    WorkdayProvider, WorkdayInterceptProvider,
)
from notifier import push
from sys import exit
import os, pathlib, sys
os.chdir(pathlib.Path(__file__).parent)  


# ──────────────── WATCH LIST ────────────────
CFG = pathlib.Path("watchers.json")
if not CFG.exists():
    raise FileNotFoundError("Run watchers_gui.py to create watchers.json first")

raw = json.loads(CFG.read_text())
WATCHERS = {}
for name, info in raw.items():
    ats = info["ats"]
    if ats == "Greenhouse":
        WATCHERS[name] = GreenhouseProvider(info["slug"])
    elif ats == "Lever":
        WATCHERS[name] = LeverProvider(info["slug"])
    elif ats == "Ashby":
        WATCHERS[name] = AshbyProvider(info["slug"])
    elif ats == "Workday":
        WATCHERS[name] = WorkdayProvider(
            tenant=info["tenant"], cluster=info["cluster"],
            site=info["site"],   locale=info["locale"]
        )
    elif ats == "WorkdayIntercept":
        WATCHERS[name] = WorkdayInterceptProvider(
            tenant=info["tenant"], cluster=info["cluster"],
            site=info["site"],   locale=info["locale"]
        )
    else:
        print((f"[WARN] Unknown ATS {ats} for {name}").encode('ascii', errors='replace').decode())

# ──────────── NOTIFIED TRACKING ─────────────
NOTIFIED_F = pathlib.Path("notified.json")
JOBS_F = pathlib.Path("jobs.json")

def load_notified():
    return set(json.loads(NOTIFIED_F.read_text()) if NOTIFIED_F.exists() else [])
def save_notified(notified):
    NOTIFIED_F.write_text(json.dumps(list(notified)))

def safe_print(*args, **kwargs):
    msg = " ".join(str(x) for x in args)
    print(msg.encode('ascii', errors='replace').decode(), **kwargs)

if __name__ == "__main__":
    notified = load_notified()
    all_jobs = {}
    for name, watcher in WATCHERS.items():
        try:
            jobs = list(watcher.fetch())
            all_jobs[name] = jobs
            for job in jobs:
                fid = watcher.fingerprint(job)
                if fid in notified:
                    continue
                push(f"[{name}] {job['title']} → {job['url']}")
                safe_print("ALERT:", name, "→", job["title"])
                notified.add(fid)
        except Exception as e:
            safe_print(f"[WARN] {name} watcher failed:", e)
            tb_str = traceback.format_exc()
            safe_print(tb_str)
    save_notified(notified)
    JOBS_F.write_text(json.dumps(all_jobs, indent=2))
    exit(0)
