# Prefire – ATS Watch-List & Notifier

> **Boards supported:** **Greenhouse · Lever · AshbyHQ · Workday**

---

## ✨ Key features

* **One-click “Run check now”** – scrapes all configured boards
* Green highlight for **unseen postings**; double-click opens the job URL
* Optional **headless Playwright scraping** for Workday & Workday-Intercept
* Windows-only **Background Automation**

  * Creates/updates a Task-Scheduler entry
  * Live *next-run* time & countdown
* Built-in editor for `.env` – manage your **Pushover** keys straight from the GUI
* All state in plain JSON (`watchers.json`, `seen.json`, `notified.json`, `jobs.json`) – **no DB**

---

## 🕹️ Quick-start

```bash
# 1) clone & enter
git clone https://github.com/glockatoo31/prefire.git
cd prefire

# 2) virtual-env  (Python ≥ 3.9 recommended)
python -m venv venv
#  ➟ Windows
.\venv\Scripts\Activate
#  ➟ macOS / Linux
source venv/bin/activate

# 3) dependencies
pip install -r requirements.txt
playwright install      # downloads headless Chromium

# 4) copy env-template & launch GUI
cp .env.example .env
python watchers_gui.py
```

---

## 🛠️ Full setup (step-by-step)

### 1. Clone & create a virtual-env   *(skip if you ran the quick-start)*

```bash
git clone https://github.com/glockatoo31/prefire.git
cd prefire

python -m venv venv
#  ➟ Windows PowerShell
.\venv\Scripts\Activate
#  ➟ macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
# Playwright needs its own browser download:
playwright install
```

### 3. Configure **Pushover** for phone alerts

1. Create a free account at [https://pushover.net](https://pushover.net)

2. Copy your **User Key** (top of the dashboard)

3. Click **Create an Application / API Token**

   * Name: `Prefire`
   * Type: **Application**
   * Click **Create Application** → copy the **API Token**


### 4. Create a shortcut to the GUI

Right clovk **make_shortcut.ps1** > Run with powershell

A shortcut will be made on your desktop

### 5. Enable Background Automation and Notifications (Windows)

1.  Open the GUI via the desktop shortcut.
2.  Enter your pushover API and account key.
3.  Open the **Background Automation** panel on the right.
4. Choose a **Frequency (min)** and press **Enable** – Prefire creates/updates the
   *SentinelJobChecker* task pointing to `sentinel.py`.
5. The panel shows **Status**, **Next run** and a live **Countdown**.

---


---

## 🤔 Troubleshooting

| Issue                                             | Fix                                                                                                                                                                    |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Playwright error “Executable doesn’t exist …”** | You skipped `playwright install` – run it inside the venv.                                                                                                             |
| **No Pushover notifications**                     | Ensure the Pushover app is installed & your phone isn’t muted. Re-enter keys via *File ▸ Edit Pushover Credentials…*.                                                  |
| **Windows task won’t run**                        | Open *Task Scheduler → Task Scheduler Library → SentinelJobChecker* and read the *History* tab. Disable then re-enable automation from the GUI to regenerate the task. |

---

## 🏢 Adding companies to watch

1. **Open the GUI** (`watchers_gui.py`) and focus the **Add / Update** panel on the right.
2. Paste a public job‑board URL (e.g. `https://boards.greenhouse.io/example`) and hit **Auto Detect** – the form auto‑fills the required fields.
3. Tweak the friendly *Company* name if you like, then press **Add / Update**.

### Manually filling the form
If you prefer manual entry, choose the **ATS** from the drop‑down and fill only the fields that light up:

| ATS | Required fields |
|-----|-----------------|
| Greenhouse | **slug** (everything after `boards.greenhouse.io/`) |
| Lever | **slug** (after `jobs.lever.co/`) |
| AshbyHQ | **slug** (second part of the URL) |
| Workday | **tenant**, **cluster**, **site**, **locale** |
| Workday Intercept | **tenant**, **cluster**, **site**, **locale** |

Click **Add / Update** to start watching.

#### How to get Workday fields (tenant, cluster, site, locale)

For **Workday** and **Workday Intercept**, you need:
- **tenant**: The subdomain before the first dot in the URL
- **cluster**: The next part after the subdomain (e.g., `myworkdayjobs.com/` is usually after `cluster`)
- **site**: Usually `External`, or the last part of the path in the URL
- **locale**: Usually `en-US` (default)

**Example:**
- Job board: `https://company.wd5.myworkdayjobs.com/External`
  - **tenant**: `company`
  - **cluster**: `wd5`
  - **site**: `External`
  - **locale**: `en-US`

If the URL is more complex, Prefire's **Auto Detect** can usually figure it out for you—just paste the full job board URL and hit Auto Detect.

### Workday vs. Workday Intercept
| Mode | What it does | When to use |
|------|--------------|-------------|
| **Workday** | Uses the public JSON/atom feed offered by many Workday career sites. Fast & light, but some companies disable this endpoint. | Works on most Workday boards – always try this first. |
| **Workday Intercept** | Launches a headless Chromium instance (via Playwright) and **captures XHR calls** while the page loads, pulling job data even when the JSON feed is blocked. Slightly slower and needs the Playwright browser download. | Use only if **Workday** returns 0 roles or errors out – this mode is your fallback. |

You can switch between the two at any time; Prefire will quietly refresh the list on the next run.
