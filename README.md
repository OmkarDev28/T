# TrialSense v1

**Explainable Hybrid AI for Clinical-Trial Pre-Screening Using Public Trial Criteria and Synthetic FHIR Patient Records — a Type 2 Diabetes Mellitus Case Study**

## Quick start
```bash
pip install -r requirements.txt
python tests/test_core.py          # sanity tests (set PYTHONPATH=. if needed)
python -m trialsense.cli --patient 3
streamlit run app.py               # interactive UI
```

## Pipeline
```
ClinicalTrials.gov criteria text ─► split ─► rule parser ─► (optional LLM fallback, schema-validated) ─► structured specs
Synthetic FHIR R4 bundles (Synthea-style) ─► feature extraction (LOINC / SNOMED / RxNorm, with provenance)
                                   └──────────────► three-valued matcher ◄─────────────┘
                                                   pass / fail / unknown + evidence per criterion
```

* **Hybrid**: deterministic rules first (auditable); LLM only for unparsed *public* criteria text, output validated against a closed schema. No patient data ever leaves the machine.
* **Explainable**: each criterion → ✅ / ❌ / ❓ with the exact value + date that decided it.
* **Safe by design**: missing or >12-month-old labs → *unknown* (never silently pass/fail). Trial status: *Likely eligible* / *Needs review* / *Ineligible*.
* **Privacy**: only synthetic data. Real data would be processed locally; federated variant is a v2 item.

## Supported criteria (v1)
Age · HbA1c · BMI · eGFR (ranges / operators) · T2DM (with min duration) · T1DM · pregnancy/lactation · MI (with "within N months") · insulin · metformin.
Everything else → "needs manual review" (visible in the *Criteria parser* tab).

## Known limitations (state these in the paper)
* Closed-world assumption for conditions/meds (absent ⇒ not present).
* No temporal logic beyond "within / for at least N months"; no dose/"stable dose" handling; no AND/OR nesting inside a single bullet.
* Demo trials are illustrative, not real registrations. Use `--live` / sidebar option for real ones.
* Synthetic generator is simplistic (independent labs). Use real Synthea via `load_bundles_from_dir()`.
* No ground truth yet, so no accuracy numbers — only parse coverage and cohort counts.

## Roadmap to v2
1. Real Synthea T2DM cohort + curated gold labels (clinician-style annotation of ~100 live criteria).
2. Evaluate parser: precision/recall vs. gold; compare rules-only vs. rules+LLM.
3. Evaluate matcher: sensitivity/specificity against gold eligibility on synthetic cohort.
4. Richer criteria (comorbidities, medication washout, stable-dose, AND/OR), UMLS/SNOMED concept expansion.
5. Optional ML ranker (e.g. learning-to-rank on unknown-heavy trials), fairness checks across sex/age.
