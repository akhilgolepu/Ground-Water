"""
Research Pipeline — Approximate hydro-geographic regions for stratified evaluation.

The source file's state/district encodings are broken, so wells are grouped by simple
latitude/longitude boxes that follow India's main groundwater settings. The boxes are
deliberately coarse; Phase 5 can swap them for CGWB principal-aquifer polygons.

  Himalaya & north-east  lat ≥ 32, or lon ≥ 89.5 north of 21.5 °N
  Arid north-west        west Rajasthan and Kutch/north Gujarat (lon < 75.5, 22.5 ≤ lat < 30)
  Indo-Gangetic plain    alluvial north (24 ≤ lat < 32, 74 ≤ lon < 89.5), excluding the arid box
  Peninsular             everything else: mostly hard-rock aquifers of the Deccan and south
"""

import numpy as np
import pandas as pd

REGIONS = ["Indo-Gangetic plain", "Peninsular", "Arid north-west", "Himalaya & north-east"]


def assign_region(lat: pd.Series, lon: pd.Series) -> pd.Series:
    lat, lon = np.asarray(lat, dtype=float), np.asarray(lon, dtype=float)
    himalaya_ne = (lat >= 32) | ((lon >= 89.5) & (lat >= 21.5))
    arid_nw = (lon < 75.5) & (lat >= 22.5) & (lat < 30) & ~himalaya_ne
    igp = (lat >= 24) & (lat < 32) & (lon >= 74) & (lon < 89.5) & ~arid_nw & ~himalaya_ne
    out = np.select([himalaya_ne, arid_nw, igp], ["Himalaya & north-east", "Arid north-west", "Indo-Gangetic plain"],
                    default="Peninsular")
    return pd.Series(out, name="region")
