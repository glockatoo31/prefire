# Prefire – ATS Watch-List & Notifier  

## 📸 What it does

| Module | Purpose | Runs as… |
| ------ | ------- | -------- |
| **`watchers_gui.py`** | Beautiful dark-themed GUI to manage the companies you watch, test fetches, and set up automatic background checks | windowed app |
| **`sentinel.py`** | Headless checker that scrapes all configured boards and sends Pushover notifications for brand-new jobs | spawned by the GUI **or** Windows Task Scheduler |
| **`providers.py`** | Scrapers for Greenhouse, Lever, Ashby, Workday (classic + Intercept) | imported |
| **`notifier.py`** | Tiny helper that POSTs to Pushover | imported |

Boards supported: **Greenhouse · Lever · AshbyHQ · Workday**

---

## ✨ Key features

* One-click **Run check now**
* Green highlighting for unseen postings
* Double-click a row → opens the job page
* Optional headless Playwright scraping for Workday
* Windows-only “Enable background automation” (Task Scheduler creator + live countdown)
* `.env`-based **Pushover** integration – edit straight from the GUI
* All state in plain JSON – no DB

---

## 🕹️ Quick-start

```bash
git clone https://github.com/glockatoo31/prefire.git
cd prefire

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install                # downloads headless Chromium

cp .env.example .env              # rename, then edit with your Pushover keys
python watchers_gui.py
