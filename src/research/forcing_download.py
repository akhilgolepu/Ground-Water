"""
Research Pipeline — Phase 1.1–1.3: Forcing Data Download
Downloads IMD gridded daily rainfall (0.25°) and Tmax/Tmin (1°) via `imdlib`, and the
monthly Niño 3.4 and Dipole Mode Index (IOD) series from NOAA PSL.

Raw downloads live in data/external/ (git-ignored). Re-running skips years already on disk.
Sources and licences are documented in docs/07-forcing-data.md.
"""

import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from src.research.config import EXTERNAL_DIR, FORCING_FIRST_YEAR, FORCING_LAST_YEAR

IMD_DIR = EXTERNAL_DIR / "imd"


def imd_file(var_type: str, year: int) -> Path | None:
    """IMD names rain files `<year>.grd` and temperature files `<year>.GRD`."""
    for name in (f"{year}.grd", f"{year}.GRD"):
        path = IMD_DIR / var_type / name
        if path.exists() and path.stat().st_size > 0:
            return path
    return None
INDEX_URLS = {
    # Both from HadISST so the two indices share one SST source (anomalies vs 1981–2010).
    "nino34": "https://psl.noaa.gov/data/timeseries/month/data/nino34.long.anom.data",
    "dmi": "https://psl.noaa.gov/data/timeseries/month/data/dmi.had.long.data",
}


def download_imd(var_type: str, first_year: int, last_year: int) -> dict:
    """Downloads one IMD variable year by year; a failed year is recorded, not fatal."""
    import imdlib

    status = {}
    for year in range(first_year, last_year + 1):
        if imd_file(var_type, year):
            status[year] = "cached"
            continue
        try:
            imdlib.get_data(var_type, year, year, fn_format="yearwise", file_dir=str(IMD_DIR), sub_dir=True)
            status[year] = "ok" if imd_file(var_type, year) else "missing after download"
        except Exception as exc:  # IMD server returns HTML or 404 for unpublished years
            status[year] = f"failed: {type(exc).__name__}: {exc}"[:200]
    return status


def parse_psl_table(text: str) -> pd.Series:
    """
    Parses the NOAA PSL 'long' table format:
    first line = 'first_year last_year', then 'year v1 … v12' rows, then the missing-value code.
    """
    lines = [l for l in text.strip().splitlines() if l.strip()]
    first, last = (int(v) for v in lines[0].split()[:2])
    rows = []
    missing = None
    for line in lines[1:]:
        parts = line.split()
        if len(parts) == 13 and parts[0].lstrip("-").isdigit() and first <= int(parts[0]) <= last:
            year = int(parts[0])
            for month, val in enumerate(parts[1:], start=1):
                rows.append((pd.Timestamp(year=year, month=month, day=1), float(val)))
        elif len(parts) == 1 and missing is None:
            try:
                missing = float(parts[0])
            except ValueError:
                pass
    s = pd.Series(dict(rows)).sort_index()
    if missing is not None:
        s = s.mask(np.isclose(s, missing))
    return s


def download_climate_indices() -> pd.DataFrame:
    frames = {}
    for name, url in INDEX_URLS.items():
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "aquasense-research"}), timeout=60) as r:
            text = r.read().decode("utf-8", "ignore")
        (EXTERNAL_DIR / f"{name}.txt").write_text(text)
        frames[name] = parse_psl_table(text)
    df = pd.DataFrame(frames)
    df.index.name = "month"
    df = df.reset_index()
    df.to_parquet(EXTERNAL_DIR / "climate_indices.parquet", index=False)
    return df


def run_download():
    print("=== Phase 1: Forcing Data Download ===")
    IMD_DIR.mkdir(parents=True, exist_ok=True)
    report = {}
    for var in ("rain", "tmax", "tmin"):
        print(f"IMD {var} {FORCING_FIRST_YEAR}–{FORCING_LAST_YEAR} ...")
        report[var] = download_imd(var, FORCING_FIRST_YEAR, FORCING_LAST_YEAR)
        bad = {y: s for y, s in report[var].items() if s not in ("ok", "cached")}
        print(f"  {len(report[var]) - len(bad)} years available; problems: {bad or 'none'}")

    print("NOAA PSL climate indices ...")
    idx = download_climate_indices()
    valid = idx.dropna(how="all", subset=["nino34", "dmi"])
    print(f"  {len(valid)} months ({valid['month'].min():%Y-%m} → {valid['month'].max():%Y-%m})")
    report["indices"] = {"first": f"{valid['month'].min():%Y-%m}", "last": f"{valid['month'].max():%Y-%m}",
                         "last_nino34": f"{idx.dropna(subset=['nino34'])['month'].max():%Y-%m}",
                         "last_dmi": f"{idx.dropna(subset=['dmi'])['month'].max():%Y-%m}"}

    with open(EXTERNAL_DIR / "download_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Saved download report to {EXTERNAL_DIR / 'download_report.json'}")


if __name__ == "__main__":
    run_download()
