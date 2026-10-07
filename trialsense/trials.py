"""Trial sources: bundled demo trials + live ClinicalTrials.gov API v2 fetch.

The DEMO trials are illustrative (written in ClinicalTrials.gov style) and are
NOT real registered studies - IDs are prefixed DEMO. Use fetch_ctgov() for real ones.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .criteria import Criterion, parse_trial_criteria


@dataclass
class Trial:
    id: str
    title: str
    raw_criteria: str
    source: str = "demo"
    criteria: list[Criterion] = field(default_factory=list)

    def __post_init__(self):
        if not self.criteria:
            self.criteria = parse_trial_criteria(self.raw_criteria)


DEMO = [
    ("DEMO-01", "Weekly GLP-1 RA add-on to metformin in adults with T2DM", """Inclusion Criteria:
* Diagnosis of type 2 diabetes mellitus for at least 6 months
* Age 18 to 75 years
* HbA1c between 7.5% and 10.5%
* BMI >= 27 kg/m2
* Currently treated with metformin

Exclusion Criteria:
* History of type 1 diabetes
* eGFR < 45 mL/min/1.73 m2
* Myocardial infarction within 6 months
* Pregnant or breastfeeding
* Use of insulin
* Personal history of medullary thyroid carcinoma"""),
    ("DEMO-02", "SGLT2 inhibitor in T2DM with moderate renal impairment", """Inclusion Criteria:
* Type 2 diabetes mellitus
* Age >= 18 years
* eGFR 30 to 60 mL/min/1.73 m2
* HbA1c 6.5% to 10.0%

Exclusion Criteria:
* Type 1 diabetes
* Pregnancy
* Myocardial infarction within 3 months
* History of recurrent genital mycotic infections"""),
    ("DEMO-03", "Closed-loop insulin delivery in insulin-treated T2DM", """Inclusion Criteria:
* Type 2 diabetes mellitus
* Age 21 to 70 years
* Currently using insulin
* HbA1c >= 8.0% and <= 12.0%

Exclusion Criteria:
* Pregnancy
* eGFR < 30 mL/min/1.73 m2
* Unable to use a smartphone"""),
    ("DEMO-04", "Intensive lifestyle programme in early, treatment-naive T2DM", """Inclusion Criteria:
* Type 2 diabetes mellitus
* Age 30 to 65 years
* BMI 30 to 45 kg/m2
* HbA1c 6.5% to 8.0%

Exclusion Criteria:
* Use of insulin
* Current metformin use
* Pregnancy
* Myocardial infarction within 12 months"""),
    ("DEMO-05", "Cardiovascular outcomes trial in T2DM after recent MI", """Inclusion Criteria:
* Type 2 diabetes mellitus
* Age 50 years or older
* Myocardial infarction within 12 months
* HbA1c >= 7.0%
* eGFR >= 30 mL/min/1.73 m2

Exclusion Criteria:
* Type 1 diabetes
* Pregnancy"""),
]


def demo_trials() -> list[Trial]:
    return [Trial(i, t, c, "demo") for i, t, c in DEMO]


def fetch_ctgov(query: str = "type 2 diabetes", n: int = 20, status: str = "RECRUITING") -> list[Trial]:
    """Pull recruiting trials from ClinicalTrials.gov API v2 (needs internet)."""
    params = urllib.parse.urlencode({
        "query.cond": query, "filter.overallStatus": status, "pageSize": n,
        "fields": "NCTId,BriefTitle,EligibilityCriteria"})
    url = f"https://clinicaltrials.gov/api/v2/studies?{params}"
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    trials = []
    for s in data.get("studies", []):
        p = s["protocolSection"]
        raw = p.get("eligibilityModule", {}).get("eligibilityCriteria")
        if raw:
            trials.append(Trial(p["identificationModule"]["nctId"],
                                p["identificationModule"]["briefTitle"], raw, "ctgov"))
    return trials
