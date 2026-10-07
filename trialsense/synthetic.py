"""Synthetic FHIR R4 patient generator.

v1 stand-in for Synthea so the project runs with zero setup. Produces
Bundle resources (Patient, Condition, Observation, MedicationRequest) with
deliberate missing / stale data so the matcher has realistic 'unknown' cases.
Swap in real Synthea output (FHIR bundles) via load_bundles_from_dir().
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from .codes import (CONDITION_CODES, LAB_CODES, LOINC_SYS, MED_CODES,
                    RXNORM_SYS, SNOMED_SYS)


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def _cond(pid, key, onset: date):
    code, disp = CONDITION_CODES[key]
    return {"resourceType": "Condition", "id": f"{pid}-cond-{key}",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "code": {"coding": [{"system": SNOMED_SYS, "code": code, "display": disp}]},
            "subject": {"reference": f"Patient/{pid}"},
            "onsetDateTime": onset.isoformat()}


def _obs(pid, key, value, when: date):
    code, disp, unit = LAB_CODES[key]
    return {"resourceType": "Observation", "id": f"{pid}-obs-{key}", "status": "final",
            "code": {"coding": [{"system": LOINC_SYS, "code": code, "display": disp}]},
            "subject": {"reference": f"Patient/{pid}"},
            "effectiveDateTime": when.isoformat(),
            "valueQuantity": {"value": round(value, 1), "unit": unit}}


def _med(pid, key, start: date):
    code, disp = MED_CODES[key]
    return {"resourceType": "MedicationRequest", "id": f"{pid}-med-{key}", "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {"coding": [{"system": RXNORM_SYS, "code": code, "display": disp}]},
            "subject": {"reference": f"Patient/{pid}"},
            "authoredOn": start.isoformat()}


def make_patient(rng: random.Random, i: int, today: date) -> dict:
    pid = f"pt-{i:04d}"
    sex = rng.choice(["male", "female"])
    age = int(_clip(rng.gauss(58, 13), 18, 90))
    birth = today - timedelta(days=age * 365 + rng.randint(0, 364))
    res = [{"resourceType": "Patient", "id": pid, "gender": sex,
            "birthDate": birth.isoformat(), "name": [{"family": f"Synthetic{i}"}]}]

    r = rng.random()
    dx = "t2dm" if r < 0.85 else ("t1dm" if r < 0.90 else None)
    if dx:
        years = rng.uniform(0.2, 15)
        res.append(_cond(pid, dx, today - timedelta(days=int(years * 365))))

    hba1c = _clip(rng.gauss(8.0, 1.5), 5.0, 14) if dx else _clip(rng.gauss(5.4, 0.3), 4.5, 6.4)
    labs = {"hba1c": hba1c,
            "bmi": _clip(rng.gauss(31, 6), 17, 55),
            "egfr": _clip(rng.gauss(78, 24), 8, 120)}
    for key, val in labs.items():
        if rng.random() > 0.10:  # 10% missing
            res.append(_obs(pid, key, val, today - timedelta(days=rng.randint(5, 520))))

    meds = []
    if dx == "t2dm":
        if rng.random() < 0.75: meds.append("metformin")
        if rng.random() < 0.25: meds.append("sglt2")
        if rng.random() < 0.15: meds.append("glp1")
        if rng.random() < 0.20: meds.append("insulin")
    elif dx == "t1dm":
        meds.append("insulin")
    for m in meds:
        res.append(_med(pid, m, today - timedelta(days=rng.randint(30, 2000))))

    if sex == "female" and age < 45 and rng.random() < 0.05:
        res.append(_cond(pid, "pregnancy", today - timedelta(days=rng.randint(20, 200))))
    if rng.random() < 0.07:
        res.append(_cond(pid, "mi", today - timedelta(days=rng.randint(30, 1800))))

    return {"resourceType": "Bundle", "type": "collection",
            "entry": [{"resource": r} for r in res]}


def generate_patients(n: int = 200, seed: int = 42, today: date | None = None) -> list[dict]:
    today = today or date.today()
    rng = random.Random(seed)
    return [make_patient(rng, i, today) for i in range(n)]


def load_bundles_from_dir(path: str) -> list[dict]:
    """Load real Synthea FHIR output (one Bundle JSON per patient)."""
    out = []
    for p in sorted(Path(path).glob("*.json")):
        b = json.loads(p.read_text())
        if b.get("resourceType") == "Bundle":
            out.append(b)
    return out
