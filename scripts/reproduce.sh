#!/usr/bin/env bash
# Rebuilds every research artefact from the raw CGWB file and checks it.
#   bash scripts/reproduce.sh            # ingest → benchmark → tests
#   bash scripts/reproduce.sh --forcing  # also download/refresh forcing data and features (Phase 1)
set -euo pipefail
cd "$(dirname "$0")/.."

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate anpr

python -m pytest tests/research

if [[ "${1:-}" == "--forcing" ]]; then
  python -m src.research.forcing_download
  python -m src.research.forcing_features
fi

python -m src.research.ingest
python -m src.research.benchmark

python - <<'EOF'
import json
m = json.load(open("reports/benchmark/benchmark_metrics.json"))
rmse = m["horizons"]["1"]["metrics"]["XGBoost (memory-only)"]["rmse"]
print(f"Check: XGBoost memory-only RMSE at h=1 = {rmse:.3f} m (pilot reference 2.406 m)")
assert abs(rmse - 2.406) < 0.0005, "pilot benchmark changed — investigate before continuing"
EOF
echo "Reproduction complete."
