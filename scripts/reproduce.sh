#!/usr/bin/env bash
# Rebuilds every research artefact from the raw CGWB file and checks it.
#   bash scripts/reproduce.sh                    # tests → ingest → benchmark
#   bash scripts/reproduce.sh --forcing          # also download/refresh forcing data and features (Phase 1)
#   bash scripts/reproduce.sh --forcing --phase2 # also the skill decomposition, reference models,
#                                                #   robustness and figures (Phase 2, ~45 min, GPU for Chronos-2)
set -euo pipefail
cd "$(dirname "$0")/.."

FORCING=0
PHASE2=0
for arg in "$@"; do
  case "$arg" in
    --forcing) FORCING=1 ;;
    --phase2) PHASE2=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate anpr

python -m pytest tests/research

# Ingest first: forcing features need the station catalog it writes.
python -m src.research.ingest

if [[ $FORCING == 1 ]]; then
  python -m src.research.forcing_download
  python -m src.research.forcing_features
fi

python -m src.research.benchmark

python - <<'EOF'
import json
m = json.load(open("reports/benchmark/benchmark_metrics.json"))
rmse = m["horizons"]["1"]["metrics"]["XGBoost (memory-only)"]["rmse"]
print(f"Check: XGBoost memory-only RMSE at h=1 = {rmse:.3f} m (pilot reference 2.406 m)")
assert abs(rmse - 2.406) < 0.0005, "pilot benchmark changed — investigate before continuing"
EOF

if [[ $PHASE2 == 1 ]]; then
  python -m src.research.skill_decomposition
  python -m src.research.reference_models
  python -m src.research.skill_robustness
  python -m src.research.skill_figures
  python - <<'EOF'
import pandas as pd
m = pd.read_csv("reports/skill/metrics.csv").set_index(["h", "model"])
skill = m.loc[(2, "M2 + ENSO/IOD"), "skill_vs_persistence"]
print(f"Check: M2 skill vs persistence at 6 months = {skill:.3f} (Phase 2 reference 0.572)")
assert abs(skill - 0.572) < 0.002, "Phase 2 result changed — investigate before continuing"
EOF
fi

echo "Reproduction complete."
