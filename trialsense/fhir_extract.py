"""FHIR Bundle -> flat patient features (with provenance for explanations).

Closed-world assumption (v1): a condition/medication that is not on the record
is treated as absent. Labs that are missing or stale are treated as UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .codes import (CONDITION_CODES, CONDITION_KEYWORDS, LAB_CODES,
                    MED_CODES, MED_KEYWORDS)


@dataclass
class Features:
    pid: str
    age: int | None
    sex: str | None
    conditions: dict[str, date | None] = field(default_factory=dict)   # key -> onset
    labs: dict[str, tuple[float, date, str]] = field(default_factory=dict)  # key -> (value, date, resource id)
    meds: dict[str, date | None] = field(default_factory=dict)         # key -> start


def _d(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None


def _codings(cc: dict) -> list[tuple[str, str]]:
    return [(c.get("code", ""), (c.get("display") or "").lower()) for c in cc.get("coding", [])]


def _match(codings, code_map, kw_map):
    for key in code_map:
        code = code_map[key][0]
        if any(c == code for c, _ in codings):
            return key
    for key, kws in kw_map.items():
        if any(k in disp for _, disp in codings for k in kws):
            return key
    return None


def extract_features(bundle: dict, today: date | None = None) -> Features:
    today = today or date.today()
    f = Features(pid="?", age=None, sex=None)
    for e in bundle.get("entry", []):
        r = e["resource"]
        t = r["resourceType"]
        if t == "Patient":
            f.pid, f.sex = r["id"], r.get("gender")
            b = _d(r.get("birthDate"))
            if b:
                f.age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        elif t == "Condition":
            if r.get("clinicalStatus", {}).get("coding", [{}])[0].get("code") not in (None, "active"):
                continue
            key = _match(_codings(r.get("code", {})), CONDITION_CODES, CONDITION_KEYWORDS)
            if key:
                f.conditions[key] = _d(r.get("onsetDateTime"))
        elif t == "Observation":
            lab = None
            codings = _codings(r.get("code", {}))
            for k, (code, _, _) in LAB_CODES.items():
                if any(c == code for c, _ in codings):
                    lab = k
            vq = r.get("valueQuantity")
            when = _d(r.get("effectiveDateTime"))
            if lab and vq and when:
                prev = f.labs.get(lab)
                if prev is None or when > prev[1]:
                    f.labs[lab] = (float(vq["value"]), when, r.get("id", ""))
        elif t == "MedicationRequest":
            if r.get("status") != "active":
                continue
            key = _match(_codings(r.get("medicationCodeableConcept", {})), MED_CODES, MED_KEYWORDS)
            if key:
                f.meds[key] = _d(r.get("authoredOn"))
    return f
