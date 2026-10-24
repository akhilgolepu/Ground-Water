# Legacy pipeline (retired)

This folder keeps the original AquaSense pipeline (TFT forecaster, SHAP/VSN explanations, GA/PSO
pumping optimiser and FastAPI backend) for the audit trail only. **Its results are invalid**: the
preprocessing used `wellDepth` (each borehole's constant construction depth) as the target and
fabricated monthly timestamps, so every reported metric, explanation and "optimal" pumping quota
came from a constant. See [docs/01-project-audit.md](../docs/01-project-audit.md) for the full list
of defects.

Nothing outside this folder imports it. The research pipeline is in `src/research/`, and the
dashboard is a static site in `frontend/` that reads `frontend/public/data/`.

The code was moved here unchanged; import paths inside it still assume its old locations
(`src/...`, `backend/...`), so it will not run from here without edits.
