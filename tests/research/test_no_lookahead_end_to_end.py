"""
Internal review (Phase 6.5): end-to-end look-ahead check on the real data.

For several cutoff campaigns, delete every groundwater reading after the cutoff, rebuild the supervised
features with the production code, and require that the features of origins at the cutoff are
identical to those built from the full record. If any feature used data after its origin, the two would
differ. Oracle columns are excluded by design (they are the hindsight upper bound). Skipped when the
processed data are absent.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.research.skill_decomposition import ARMS, load_dataset

ROOT = Path(__file__).resolve().parents[2]
CAMPAIGNS = ROOT / "data" / "processed" / "gwl_campaigns.parquet"
FEATURES = [c for c in ARMS["M2 + ENSO/IOD"]]  # every non-oracle model input

pytestmark = pytest.mark.skipif(not CAMPAIGNS.exists(), reason="processed data not built")


@pytest.mark.parametrize("h", [1, 4])
@pytest.mark.parametrize("cutoff", [2017 * 4 + 1, 2020 * 4 + 3, 2022 * 4 + 1])  # May 2017, Nov 2020, May 2022
def test_features_at_origin_ignore_later_readings(h, cutoff):
    campaigns = pd.read_parquet(CAMPAIGNS)
    full = load_dataset(h, keep_unlabelled=True)
    cut = load_dataset(h, campaigns=campaigns[campaigns["campaign_idx"] <= cutoff], keep_unlabelled=True)
    a = full[full["campaign_idx"] == cutoff].set_index("well_id")[FEATURES].sort_index()
    b = cut[cut["campaign_idx"] == cutoff].set_index("well_id")[FEATURES].sort_index()
    assert len(a) > 500 and a.index.equals(b.index)
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9, atol=1e-9)
    # and the target really is unavailable in the truncated build
    assert cut[cut["campaign_idx"] == cutoff]["y_target"].isna().all()
    assert np.isfinite(a.select_dtypes("number").to_numpy(dtype=float)).mean() > 0.8
