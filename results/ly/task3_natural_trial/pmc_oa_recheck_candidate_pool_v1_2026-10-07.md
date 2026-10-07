# PMC recheck candidate pool v1

- Date: 2026-10-07
- Source pool: `.repo_upload/data/interim/pmc_oa_candidate_pool_ly_v1_2026-10-03.json`
- Candidate count: **4**
- Purpose: provide a clean, label-free starting pool for the revised rules after the 30-row overall agreement threshold was not met.
- All annotator labels, evidence statuses, reasons and adjudications are blank in this package.
- This is a candidate pool, not a completed new pilot set. It cannot by itself establish the 0.80/0.65 thresholds.

## Overlap check against merged 30-row set

| candidate_id | cited DOI | ID overlap | cited DOI overlap | status |
|---|---|---:|---:|---|
| `PMC-OA-11720600` | `10.1186/s12889-025-21307-4` | no | no | `blind_review_pending` |
| `PMC-OA-9893927` | `10.3389/fpsyg.2022.1044261` | no | no | `blind_review_pending` |
| `PMC-OA-5589427` | `10.1187/cbe.16-08-0253` | no | no | `blind_review_pending` |
| `PMC-OA-7264990` | `10.3389/fpsyg.2020.00876` | no | no | `blind_review_pending` |

## Required next action

Use the revised rules in `pmc30_annotation_rule_revision_v1_2026-10-07.md`. The two annotators must fill separate blind copies with the three-class label, evidence status, stable locator and reason. Merge and adjudicate only after both copies are returned.

The current pool has four unused candidates. More candidates should be retrieved before claiming a substantive recheck sample or the final 30-row natural set.
