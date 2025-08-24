# workday_intercept.py
import re, json
from playwright.sync_api import sync_playwright, TimeoutError

# --------- filter pattern -------------------------------------------------- #
_INTERN_RE = re.compile(r"\bIntern(ship)?\b", re.I)

# --------- helper ---------------------------------------------------------- #
def fetch_workday_intercept(tenant: str,
                            cluster: str,
                            site: str,
                            locale: str | None = None,
                            timeout_ms: int = 90_000):
    """
    Open the Workday page head-less, wait for the first XHR / fetch response
    whose JSON contains `jobPostings`, and return [{id,title,url}, …].
    """

    # --- include ?q=Internship so the SPA fetches internship rows --------
    locale_part = f"{locale}/" if locale else ""
    ui_url = (
        f"https://{tenant}.{cluster}.myworkdayjobs.com/"
        f"{locale_part}{site}?q=Internship"       # ← added query-string
    ).replace("//", "/")

    # --- predicate: any 200 OK XHR / fetch whose body has jobPostings ----
    def _has_job_postings(resp):
        if resp.request.resource_type not in ("xhr", "fetch"):
            return False
        if resp.status != 200:
            return False
        try:
            body = resp.json()
        except Exception:
            return False
        return isinstance(body, dict) and "jobPostings" in body

    # ---------------------------------------------------------------------
    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_page()
        page.goto(ui_url, timeout=timeout_ms)

        try:
            resp = page.wait_for_event(
                "response",
                predicate=_has_job_postings,
                timeout=max(timeout_ms, 120_000),  # allow up to 120 s
            )
        except TimeoutError:
            print(f"[{tenant}] intercept timed-out (no jobPostings)")
            return []

        data = resp.json()
        print(f"[{tenant}] raw rows: {len(data.get('jobPostings', []))}")  # debug

        jobs = []
        for j in data.get("jobPostings", []):
            title = j.get("title") or j.get("titleText", "")
            if _INTERN_RE.search(title):
                jobs.append({
                    "id": str(j.get("jobPostingId") or
                              j.get("id") or
                              j.get("externalPath")),
                    "title": title,
                    "url": f"{ui_url}/job/{j['externalPath']}",
                })

        print(f"[{tenant}] intercept captured {len(jobs)} rows")  # debug
        return jobs
