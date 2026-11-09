# Digital Gardens vs. Wonder Valley — version-specific research-release candidate

This is the **current numerical research snapshot**, not a collection of superseded manuscripts. The parent archive also includes separately identified current Joule documents. It does **not** include `source_downloads.zip`, original BC Hydro XLS files, copied website graphics or older manuscript versions.

## Reproduction structure

The inner `02_PRIVATE_RESEARCH` directory name is preserved solely for path compatibility with the published V13/V14 Python scripts; the contents here are an intentionally clean research candidate rather than the earlier private master archive. The included `inputs/model_inputs.npz`, `inputs/grid_access.npz` and `inputs/weather_qc_hourly.csv.gz` permit rerunning the historical dispatch directly from frozen author-prepared numeric arrays. They do not reproduce all original provider download/quality-control steps from scratch.

Install the packages listed in `02_PRIVATE_RESEARCH/requirements.txt` (NumPy, Pandas, Numba, SciPy and Matplotlib as required). From the `02_RESEARCH_RELEASE_CANDIDATE` folder run:

```
python 02_PRIVATE_RESEARCH/code/test_model.py
python 02_PRIVATE_RESEARCH/comparative_analysis/NOV8_13/nov8_13_hourly_replay.py
python 02_PRIVATE_RESEARCH/comparative_analysis/NOV8_14/NOV8_14_recompute.py
python 02_PRIVATE_RESEARCH/comparative_analysis/NOV8_15/NOV8_15_VERIFY_BOUNDARIES.py
python 02_PRIVATE_RESEARCH/comparative_analysis/NOV8_16/NOV8_16_VERIFY_MATCHED_CREDITS.py
```

The V13 replay has 12 scenarios; V14 adds eight heat-delivery-coupled scenarios. The V16 arithmetic script checks 32 symmetrical-credit cases. Each simulated year has 8,760 hours; 29 February is omitted. Avoid inferring actual BC Hydro connection approval, CCS deployment, full lifecycle emissions or actual community-service participation from the calculations. Inputs are frozen processed evidence, not a universal open access representation of source documents.

See `SOURCE_RIGHTS_AND_ATTRIBUTION.md` for the corrected fact-versus-expression assessment, source credits and the source-specific outstanding checks. **No DOI has been issued for this candidate, and this archive has not been uploaded.**
