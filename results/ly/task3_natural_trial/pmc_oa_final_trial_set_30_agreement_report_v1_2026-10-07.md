# PMC natural trial set (30 rows) agreement audit v1

- Audit date: 2026-10-07
- Source: `.repo_upload/results/ly/task3_natural_trial/pmc_oa_final_trial_set_30_v4_2026-10-05.csv`
- Scope: 30 merged natural PMC rows (20 V2 rows + 10 V3 rows).
- Integrity rule: raw annotator fields and adjudications were not changed. For the semantic agreement calculation only, `NOT-ACCURATE` is normalized to `NOT_ACCURATE`.

## Result

- Overall normalized label agreement: **23/30 = 0.7667**. The 0.80 threshold is **not met** (requires at least 24/30).
- Distortion binary agreement (`NOT_ACCURATE` vs other labels): **23/30 = 0.7667**. The 0.65 threshold is **met**.
- V2 subset: 18/20 = 0.9000.
- V3 subset: 5/10 = 0.5000.
- Literal-string agreement is 22/30 = 0.7333; the difference from normalized agreement is a formatting-only `NOT-ACCURATE`/`NOT_ACCURATE` discrepancy.

## Normalized semantic disagreements

- `PMC-OA-V2-05`: annotator_1=`ACCURATE`, annotator_2=`NOT_ACCURATE`, adjudicated=`NOT_ACCURATE`.
- `PMC-OA-V2-12`: annotator_1=`ACCURATE`, annotator_2=`NOT_ACCURATE`, adjudicated=`NOT_ACCURATE`.
- `PMC-OA-V3-02`: annotator_1=`NOT_ACCURATE`, annotator_2=`ACCURATE`, adjudicated=`ACCURATE`.
- `PMC-OA-V3-03`: annotator_1=`NOT_ACCURATE`, annotator_2=`ACCURATE`, adjudicated=`NOT_ACCURATE`.
- `PMC-OA-V3-04`: annotator_1=`NOT_ACCURATE`, annotator_2=`ACCURATE`, adjudicated=`NOT_ACCURATE`.
- `PMC-OA-V3-07`: annotator_1=`ACCURATE`, annotator_2=`NOT_ACCURATE`, adjudicated=`ACCURATE`.
- `PMC-OA-V3-08`: annotator_1=`NOT_ACCURATE`, annotator_2=`ACCURATE`, adjudicated=`ACCURATE`.

## Interpretation and next step

- This is an audit of the existing 30-row set, not a new model result and not a replacement for the raw annotation record.
- Because overall agreement is below 0.80, the trial-set acceptance condition is not passed. Keep the disagreements and adjudications, revise the decision rules against these cases, and obtain a new blind sample for confirmation.
- The distortion-class threshold is already met, but it does not override the unmet overall threshold.

Machine-readable metrics are stored beside this report in `pmc_oa_final_trial_set_30_agreement_metrics_v1_2026-10-07.json`.
