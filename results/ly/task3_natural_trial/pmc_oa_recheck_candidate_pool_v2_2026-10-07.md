# PMC recheck candidate pool v2

- Date: 2026-10-07
- Candidate count: **4**
- Status: candidate pool with exact citation markers restored; not a completed new trial set.
- The earlier v1 copy was not suitable for blind review because its citing paragraphs contained only `[citation]` placeholders. This v2 package resolves the issue by matching each cited PMCID to a bibliography reference in the citing article XML and marking the exact cross-reference.
- All annotator labels, evidence statuses, reasons and adjudications remain blank.

## QA

- Exact `<CITED:...>` marker present in all 4 citing paragraphs: yes.
- Citing/cited license metadata and XML SHA-256: present. If the XML did not expose a license URL, the package retains the license URL from the source pool and records that provenance for follow-up verification.
- Candidate ID and cited DOI overlap with merged 30-row set: 0 / 0.
- Full train/dev/test, tuning and evaluation-set exclusion still requires the final manifests; the records are not yet counted as final eligible samples.

## Files for independent review

- `pmc_oa_recheck_chen_blind_annotation_v1_2026-10-07.csv` contains source fields only and blank `annotator_1_*` fields.
- `pmc_oa_recheck_ly_independent_annotation_v1_2026-10-07.csv` contains source fields only and blank `annotator_2_*` fields.

## Next action

Each annotator should fill a separate copy using the revised rules. Only after both copies return should the records be merged, disagreements adjudicated, and the new agreement measured. More unused natural candidates are still needed before claiming a substantial recheck sample or the final 30-row set.
