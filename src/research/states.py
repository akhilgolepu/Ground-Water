"""
Research Pipeline — State tags for wells from geoBoundaries ADM1 (ODbL 1.0).
The source file's State/District encodings are broken (2 values for all of India), so wells are
tagged by point-in-polygon against geoBoundaries gbOpen IND ADM1 (2021). Wells that fall just
outside every polygon (coastline simplification) take the nearest state within 0.1°.
"""

import json
import unicodedata
import urllib.request

import numpy as np
import pandas as pd

from src.research.config import DATA_PROCESSED_DIR, EXTERNAL_DIR

ADM1_URL = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM1/geoBoundaries-IND-ADM1_simplified.geojson"
ADM1_PATH = EXTERNAL_DIR / "boundaries" / "geoBoundaries-IND-ADM1_simplified.geojson"

# Atal Bhujal Yojana states (Ministry of Jal Shakti; 80 districts in these 7 states)
ATAL_BHUJAL_STATES = ["Gujarat", "Haryana", "Karnataka", "Madhya Pradesh", "Maharashtra", "Rajasthan", "Uttar Pradesh"]


def load_states():
    from shapely.geometry import shape

    if not ADM1_PATH.exists():
        ADM1_PATH.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(ADM1_URL, headers={"User-Agent": "aquasense-research"}), timeout=120) as r:
            ADM1_PATH.write_bytes(r.read())
    gj = json.loads(ADM1_PATH.read_text())
    return [(ascii_name(f["properties"]["shapeName"]), shape(f["geometry"])) for f in gj["features"]]


def ascii_name(name: str) -> str:
    """'Rājasthān' → 'Rajasthan' (geoBoundaries uses diacritics; official lists do not)."""
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()


def tag_states(lat: pd.Series, lon: pd.Series) -> pd.Series:
    from shapely import STRtree, points

    states = load_states()
    names = np.array([n for n, _ in states])
    geoms = [g for _, g in states]
    tree = STRtree(geoms)
    pts = points(np.asarray(lon, float), np.asarray(lat, float))
    out = np.full(len(pts), None, dtype=object)
    pt_idx, poly_idx = tree.query(pts, predicate="within")
    out[pt_idx] = names[poly_idx]
    missing = np.flatnonzero(out == None)  # noqa: E711
    if len(missing):
        near, dist = tree.query_nearest(pts[missing], return_distance=True)
        for k, (i, j) in enumerate(zip(*near)):
            if dist[k] <= 0.1:
                out[missing[i]] = names[j]
    return pd.Series(out, index=lat.index, name="state")


def station_states() -> pd.DataFrame:
    """Cached well → state table (data/processed/station_states.parquet)."""
    path = DATA_PROCESSED_DIR / "station_states.parquet"
    if path.exists():
        return pd.read_parquet(path)
    cat = pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet")
    out = cat[["well_id"]].assign(state=tag_states(cat["latitude"], cat["longitude"]).to_numpy())
    out["atal_bhujal_state"] = out["state"].isin(ATAL_BHUJAL_STATES)
    out.to_parquet(path, index=False)
    return out
