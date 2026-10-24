# Submission checklist (HESS)

Status as of 2026-10-24. Items marked **author** need decisions or accounts only the author has.

## Manuscript
- [x] Complete draft answering RQ1–RQ3 (`paper/main.tex`, `main.pdf`; HESS layout 14 pages)
- [x] Every number generated from `reports/` (`paper/numbers.tex`, `paper/tables/`)
- [x] Eight figures at 174 mm width, vector PDF (`paper/figures/`)
- [x] 38 references, 37 DOIs checked against OpenAlex
- [x] Internal review against leakage, baselines, uncertainty, claims ([docs/12](../../docs/12-internal-review.md))
- [ ] **author** Name as it should appear, affiliation, ORCID, author contributions
- [ ] **author** Read the full text and the limitations; adjust anything you would not defend
- [x] HESS version in the Copernicus class: `python paper/make_hess.py` → `paper/hess/main_hess.pdf` (generated from `main.tex`; class files downloaded, not committed)
- [ ] Code and data availability statement with the Zenodo DOI (after the archive exists)
- [ ] **author** Suggested referees in the cover letter

## Release (step 6.3)
- [x] One-command reproduction with reference checks (`scripts/reproduce.sh`)
- [x] Pinned environment (`requirements-research.txt`)
- [x] `CITATION.cff`
- [x] Local tag `v1.0.0-rc1` on branch `research/p1`
- [ ] **author** Choose a licence (code and outputs)
- [ ] **author** Confirm redistribution terms of the Kaggle compilation of CGWB data (data card)
- [ ] **author** Merge `research/p1`, push to GitHub, create the release
- [ ] **author** Enable the GitHub–Zenodo integration (or upload manually) to mint the DOI

## Preprint and submission (step 6.4)
- [ ] **author** Post the preprint (ESSOAr or EarthArXiv)
- [ ] **author** Submit through the HESS portal with `paper/submission/cover-letter.md`
- [ ] Fallback venue if rejected: *Journal of Hydrology: Regional Studies*
