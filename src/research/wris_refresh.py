"""
Research Pipeline — Phase 5.4: Refresh manual groundwater levels from India-WRIS.

India-WRIS has no documented API. This uses the JSON/CSV endpoints its own web page calls (the
same ones the open-source QGIS plugin "CGWB Groundwater Data Downloader" uses):

  POST /masterState/StateList                 {"datasetcode": "GWATERLVL"}
  POST /masterDistrict/getDistrictbyState     {"statecode": …, "datasetcode": "GWATERLVL"}
  POST /Dataset/Ground Water Level?stateName=…&districtName=…&agencyName=CGWB
       &startdate=YYYY-MM-DD&enddate=YYYY-MM-DD&download=true&page=N&size=S   (Accept: text/csv)

Observed behaviour (2026-10-24): HTTP 406 means "no rows"; pages hold at most `size` rows and must be
walked; there is no server-side filter by acquisition mode, so 6-hourly telemetry rows dominate; the
CSV header does not match the row layout — fields are read by position (mode 10, status 11, value 15,
time 16). Districts appear twice (e.g. "Ambala" and "AMBALA") and both are fetched.

The research snapshot used in Phases 0–4 is NOT modified. Refreshed manual readings are written to
data/processed/wris_manual_updates.parquet and used only for the dashboard's operational forecasts.

Usage:  python -m src.research.wris_refresh --states "Rajasthan,Gujarat" --since 2023-01-01
Requests are paced (PAUSE_S) and every district response is cached under data/external/wris/.
"""

import argparse
import csv
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

import pandas as pd

from src.research.config import DATA_PROCESSED_DIR, EXTERNAL_DIR
from src.research.states import ATAL_BHUJAL_STATES

BASE = "https://indiawris.gov.in"
CACHE_DIR = EXTERNAL_DIR / "wris"
PAGE_SIZE = 5000
MAX_PAGES = 60
PAUSE_S = 1.5
HEADERS = {"User-Agent": "aquasense-research (groundwater forecasting; contact via repository)",
           "Content-Type": "application/json", "Origin": BASE, "Referer": f"{BASE}/wris/"}
FIELDS = {"code": 0, "name": 1, "lat": 3, "lon": 4, "state": 6, "district": 7, "mode": 10, "status": 11,
          "datatype": 14, "value": 15, "time": 16}


def _post(path: str, body: dict, params: dict | None = None, accept: str = "application/json") -> str | None:
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**HEADERS, "Accept": accept}, method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code == 406:  # the portal's way of saying "no rows"
                return None
            if attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(5 * (attempt + 1))
    return None


def list_districts(state: str) -> list[str]:
    states = json.loads(_post("/masterState/StateList", {"datasetcode": "GWATERLVL"}))["data"]
    code = next(s["statecode"] for s in states if s["state"].lower() == state.lower())
    time.sleep(PAUSE_S)
    data = json.loads(_post("/masterDistrict/getDistrictbyState", {"statecode": code, "datasetcode": "GWATERLVL"}))["data"]
    return sorted({d["districtname"] for d in data})


def parse_rows(text: str) -> list[dict]:
    """Manual readings from one CSV page, read by position (the header is misaligned)."""
    out = []
    for r in list(csv.reader(io.StringIO(text)))[1:]:
        if len(r) <= FIELDS["time"] or r[FIELDS["mode"]] != "Manual":
            continue
        try:
            out.append({"well_id": r[FIELDS["code"]], "lat": float(r[FIELDS["lat"]]), "lon": float(r[FIELDS["lon"]]),
                        "state": r[FIELDS["state"]], "district": r[FIELDS["district"]], "status": r[FIELDS["status"]],
                        "timestamp": r[FIELDS["time"]], "water_level_raw": float(r[FIELDS["value"]])})
        except ValueError:
            continue
    return out


def fetch_district(state: str, district: str, since: str, until: str) -> pd.DataFrame:
    cache = CACHE_DIR / f"{state}_{district}_{since}_{until}.parquet".replace(" ", "_").replace("/", "-")
    if cache.exists():
        return pd.read_parquet(cache)
    rows, n_pages = [], 0
    for page in range(MAX_PAGES):
        text = _post("/Dataset/Ground%20Water%20Level", {}, accept="text/csv", params={
            "stateName": state, "districtName": district, "agencyName": "CGWB", "startdate": since,
            "enddate": until, "download": "true", "page": page, "size": PAGE_SIZE})
        n_pages += 1
        if text is None:
            break
        rows += parse_rows(text)
        if text.count("\n") - 1 < PAGE_SIZE:
            break
        time.sleep(PAUSE_S)
    df = pd.DataFrame(rows, columns=["well_id", "lat", "lon", "state", "district", "status", "timestamp", "water_level_raw"])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return df


def run_refresh(states: list[str], since: str, until: str):
    print(f"=== Phase 5.4: India-WRIS refresh ({', '.join(states)}; {since} → {until}) ===")
    catalog = pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet")
    parts, log = [], []
    for state in states:
        districts = list_districts(state)
        print(f"{state}: {len(districts)} district names")
        for d in districts:
            time.sleep(PAUSE_S)
            try:
                df = fetch_district(state, d, since, until)
            except Exception as exc:  # keep going; the failure is logged and the district can be retried
                log.append({"state": state, "district": d, "error": f"{type(exc).__name__}: {exc}"[:200]})
                continue
            log.append({"state": state, "district": d, "manual_rows": len(df)})
            parts.append(df)
    upd = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if not upd.empty:
        upd["timestamp"] = pd.to_datetime(upd["timestamp"], errors="coerce")
        upd = upd.dropna(subset=["timestamp"]).drop_duplicates(["well_id", "timestamp"])
        upd["in_research_snapshot"] = upd["well_id"].isin(catalog["well_id"])
        upd.to_parquet(DATA_PROCESSED_DIR / "wris_manual_updates.parquet", index=False)
    summary = {
        "run_date": date.today().isoformat(), "states": states, "since": since, "until": until,
        "districts": len(log), "failed": sum("error" in r for r in log),
        "manual_readings": int(len(upd)), "stations": int(upd["well_id"].nunique()) if len(upd) else 0,
        "stations_matching_snapshot": int(upd.loc[upd["in_research_snapshot"], "well_id"].nunique()) if len(upd) else 0,
        "latest_reading": str(upd["timestamp"].max().date()) if len(upd) else None,
        "readings_by_year": upd["timestamp"].dt.year.value_counts().sort_index().to_dict() if len(upd) else {},
    }
    (DATA_PROCESSED_DIR.parent.parent / "reports" / "wris_refresh.json").write_text(
        json.dumps({"summary": summary, "districts": log}, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--states", default=",".join(ATAL_BHUJAL_STATES))
    ap.add_argument("--since", default="2023-01-01")
    ap.add_argument("--until", default=date.today().isoformat())
    a = ap.parse_args()
    run_refresh([s.strip() for s in a.states.split(",")], a.since, a.until)
