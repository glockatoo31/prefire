# providers.py
import re, httpx
from typing import Iterator, Dict, Any, List
from playwright.sync_api import sync_playwright, TimeoutError

# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
_INTERN_RE = re.compile(r"\bIntern(ship)?s?\b", re.I)

# --------------------------------------------------------------------------- #
# Greenhouse
# --------------------------------------------------------------------------- #
class GreenhouseProvider:
    def __init__(self, slug, extra_filter=lambda j: True):
        self.url   = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"
        self.extra = extra_filter

    def fetch(self):
        res = httpx.get(self.url, timeout=15)
        res.raise_for_status()
        for j in res.json()["jobs"]:
            if (j.get("employment_type", "").lower() == "intern" or _INTERN_RE.search(j["title"])) \
                    and self.extra(j):
                yield {"id": j["id"], "title": j["title"], "url": j["absolute_url"]}

    def fingerprint(self, job): return str(job["id"])

# --------------------------------------------------------------------------- #
# Lever
# --------------------------------------------------------------------------- #
class LeverProvider:
    """Public endpoint:  https://api.lever.co/v0/postings/<account>?mode=json"""
    def __init__(self, org, extra_filter=lambda j: True):
        self.url   = f"https://api.lever.co/v0/postings/{org}?mode=json"
        self.extra = extra_filter

    def fetch(self):
        r = httpx.get(self.url, timeout=15); r.raise_for_status()
        for j in r.json():
            if _INTERN_RE.search(j["text"]) and self.extra(j):
                yield {"id": j["id"], "title": j["text"], "url": j["hostedUrl"]}

    def fingerprint(self, job): return str(job["id"])

# --------------------------------------------------------------------------- #
# Ashby
# --------------------------------------------------------------------------- #
class AshbyProvider:
    """Public endpoint:  https://api.ashbyhq.com/posting-api/job-board/<slug>"""
    def __init__(self, slug, extra_filter=lambda j: True):
        self.url   = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        self.extra = extra_filter

    def fetch(self):
        r = httpx.get(self.url, timeout=15); r.raise_for_status()
        for j in r.json()["jobs"]:
            if _INTERN_RE.search(j["title"]) and self.extra(j):
                yield {"id": j["id"], "title": j["title"], "url": j["applyUrl"]}

    def fingerprint(self, job): return str(job["id"])

# --------------------------------------------------------------------------- #
# Universal Workday provider (GET → POST → intercept)
# --------------------------------------------------------------------------- #
class WorkdayProvider:
    """
    Works for every Workday tenant.
    • Tier-1: GET  /getJobs
    • Tier-2: POST /jobs   (optional applied_facets)
    • Tier-3: head-less intercept (XHR / fetch with jobPostings)
    """

    def __init__(self,
                 tenant: str,
                 cluster: str = "wd5",
                 site: str = "External",
                 locale: str = "en-US",
                 applied_facets: Dict[str, List[str]] | None = None,
                 extra_filter=lambda j: True):
        self.tenant, self.cluster, self.site, self.locale = tenant, cluster, site, locale
        self.facets  = applied_facets or {}
        self.extra   = extra_filter

    # ---------- public entry ----------
    def fetch(self) -> Iterator[Dict[str, Any]]:
        for strat in (self._get_loop, self._post_loop, self._intercept_loop):
            found = False
            try:
                for job in strat():
                    found = True
                    if self.extra(job):
                        yield job
                if found:
                    return            # stop once we produced rows
            except Exception as e:
                print(f"[{self.tenant}] {strat.__name__} failed:", e)

    def fingerprint(self, job): return job["id"]

    # ---------- Tier-1: GET ----------
    def _get_loop(self):
        offset = 0
        base = (f"https://{self.tenant}.{self.cluster}.myworkdayjobs.com/"
                f"wday/cxs/{self.tenant}/{self.site}/getJobs")
        while True:
            url = f"{base}?$top=50&$skip={offset}&$searchText=Intern"
            data = httpx.get(url, timeout=30).json()
            posts = data.get("jobPostings", [])
            if not posts:
                break
            yield from self._filter(posts)
            offset += 50

    # ---------- Tier-2: POST ----------
    def _post_loop(self):
        offset = 0
        url = (f"https://{self.tenant}.{self.cluster}.myworkdayjobs.com/"
               f"wday/cxs/{self.tenant}/{self.site}/jobs")
        while True:
            payload = {"appliedFacets": self.facets,
                       "limit": 50, "offset": offset, "searchText": ""}
            r = httpx.post(url, json=payload, timeout=30)
            if r.status_code >= 400:
                raise httpx.HTTPStatusError("POST failed", request=r.request, response=r)
            posts = r.json().get("jobPostings", [])
            if not posts:
                break
            yield from self._filter(posts)
            offset += 50

    # ---------- Tier-3: Playwright intercept ----------
    def _intercept_loop(self):
        locale_part = f"{self.locale}/" if self.locale else ""
        ui = (f"https://{self.tenant}.{self.cluster}.myworkdayjobs.com/"
              f"{locale_part}{self.site}?q=Internship").replace("//", "/")

        def looks_like_feed(resp):
            if resp.request.resource_type not in ("xhr", "fetch") or resp.status != 200:
                return False
            url = resp.url
            return url.endswith("/jobs") or "/getJobs" in url

        with sync_playwright() as p:
            page = p.chromium.launch(headless=True).new_page()
            page.goto(ui, timeout=90_000)
            try:
                resp = page.wait_for_event("response", predicate=looks_like_feed,
                                           timeout=150_000)
                data = resp.json()
            except Exception:
                return
            yield from self._filter(data.get("jobPostings", []))

    # ---------- common filter ----------
    def _filter(self, posts: List[Dict[str, Any]]):
        for j in posts:
            title = j.get("title") or j.get("titleText", "")
            if not _INTERN_RE.search(title):
                continue
            yield {
                "id": str(j.get("jobPostingId") or j.get("id") or j.get("externalPath")),
                "title": title,
                "url": (f"https://{self.tenant}.{self.cluster}.myworkdayjobs.com/"
                        f"{self.locale}/{self.site}/job/{j['externalPath']}").replace("//", "/")
            }

# --------------------------------------------------------------------------- #
# Thin wrapper for intercept-only boards (keeps sentinel logic unchanged)
# --------------------------------------------------------------------------- #
class WorkdayInterceptProvider:
    """Simply delegates to WorkdayProvider but skips GET/POST noise."""
    def __init__(self, **info):
        self.provider = WorkdayProvider(**info)

    def fetch(self):
        # go straight to the provider's intercept tier by calling _intercept_loop
        yield from self.provider._intercept_loop()

    def fingerprint(self, job):
        return self.provider.fingerprint(job)
