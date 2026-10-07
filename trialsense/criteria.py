"""Eligibility-criteria parsing: free text -> structured, machine-checkable specs.

Hybrid design:
  1. Deterministic rule/regex parser (auditable, no data leaves the machine).
  2. OPTIONAL LLM fallback for lines the rules cannot parse. It only ever sees
     public trial-criteria text (never patient data) and must return a spec
     from the same closed schema, which is validated before use.
Anything still unparsed becomes an 'unknown' (manual review) criterion.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

N = r"(\d+(?:\.\d+)?)"
UNIT = r"(?:%|kg/m2|kg/m²|ml/min\S*)?"

LAB_ALIASES = {
    "hba1c": r"hba1c|hemoglobin a1c|haemoglobin a1c|glycated hemoglobin|a1c",
    "bmi": r"bmi|body mass index",
    "egfr": r"egfr|estimated glomerular filtration rate",
}
ALLOWED_KINDS = {"age", "lab", "condition", "med"}
ALLOWED_LABS = set(LAB_ALIASES)
ALLOWED_CONDS = {"t2dm", "t1dm", "pregnancy", "mi"}
ALLOWED_MEDS = {"metformin", "insulin", "sglt2", "glp1"}


@dataclass
class Criterion:
    text: str
    ctype: str                 # "inclusion" | "exclusion"
    spec: dict | None = None   # None => could not be parsed
    parser: str = "none"       # "rule" | "llm" | "none"


# ---------- splitting raw ClinicalTrials.gov eligibility text ----------
def split_criteria(raw: str) -> list[tuple[str, str]]:
    out: list[list] = []
    ctype = "inclusion"
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^(inclusion|exclusion)\s+criteria\s*:?\s*$", s, re.I)
        if m:
            ctype = m.group(1).lower()
            continue
        if re.match(r"^([*\-•]|\d+[.)])\s+", s):
            out.append([ctype, re.sub(r"^([*\-•]|\d+[.)])\s+", "", s)])
        elif out and out[-1][0] == ctype:
            out[-1][1] += " " + s
        else:
            out.append([ctype, s])
    return [(c, t) for c, t in out]


# ---------- normalisation ----------
_REPL = [
    ("≥", ">="), ("≤", "<="), ("–", "-"), ("—", "-"),
    ("greater than or equal to", ">="), ("less than or equal to", "<="),
    ("at least", ">="), ("no less than", ">="), ("no more than", "<="),
    ("at most", "<="), ("greater than", ">"), ("more than", ">"),
    ("less than", "<"), ("above", ">"), ("below", "<"),
]


def normalise(text: str) -> str:
    t = text.lower()
    for a, b in _REPL:
        t = t.replace(a, b)
    return t


def _bounds_from(sub: str) -> dict | None:
    """Parse a range ('7.0% to 10.5%') or operators ('>= 7 and <= 10') at the start of `sub`."""
    m = re.search(rf"^[^0-9<>=]*?{N}\s*{UNIT}\s*(?:to|-|and)\s*{N}", sub)
    if m:
        return {"lo": float(m.group(1)), "hi": float(m.group(2)), "lo_incl": True, "hi_incl": True}
    b = {"lo": None, "hi": None, "lo_incl": True, "hi_incl": True}
    found = False
    for op, num in re.findall(rf"(>=|<=|>|<|=)\s*{N}", sub[:60]):
        v = float(num)
        found = True
        if op in (">=", ">", "="):
            b["lo"], b["lo_incl"] = v, op != ">"
        if op in ("<=", "<", "="):
            b["hi"], b["hi_incl"] = v, op != "<"
    return b if found else None


def _parse_age(t: str) -> dict | None:
    m = re.search(rf"\bage[d]?\b[^0-9<>=]*?{N}\s*(?:to|-|and)\s*{N}", t) or \
        re.search(rf"{N}\s*(?:to|-)\s*{N}\s*years", t)
    if m:
        return {"kind": "age", "lo": float(m.group(1)), "hi": float(m.group(2)),
                "lo_incl": True, "hi_incl": True}
    m = re.search(rf"{N}\s*years?(?: of age)?\s*(?:or older|and older|or above)", t)
    if m:
        return {"kind": "age", "lo": float(m.group(1)), "hi": None, "lo_incl": True, "hi_incl": True}
    if re.search(r"\bage\b|years", t):
        m = re.search(r"\bage\b[^0-9<>=]*(>=|<=|>|<)\s*" + N, t) or \
            re.search(rf"(>=|<=|>|<)\s*{N}\s*years", t)
        if m:
            b = _bounds_from(f"{m.group(1)} {m.group(2)}")
            if b:
                return {"kind": "age", **b}
    return None


def _months(t: str, pattern: str) -> float | None:
    m = re.search(pattern + rf"\s*(?:>=\s*)?{N}\s*(month|year)", t)
    if not m:
        return None
    v = float(m.group(1))
    return v * 12 if m.group(2) == "year" else v


def parse_rule(text: str) -> dict | None:
    t = normalise(text)
    spec = _parse_age(t)
    if spec:
        return spec
    for lab, aliases in LAB_ALIASES.items():
        m = re.search(rf"\b(?:{aliases})\b", t)
        if m:
            b = _bounds_from(t[m.end():])
            if b:
                return {"kind": "lab", "name": lab, **b}
    if "pregnan" in t or "breastfeeding" in t or "lactating" in t:
        return {"kind": "condition", "name": "pregnancy"}
    if "type 1 diabetes" in t:
        return {"kind": "condition", "name": "t1dm"}
    if "type 2 diabetes" in t:
        spec = {"kind": "condition", "name": "t2dm"}
        mm = _months(t, r"(?:for\s*)?>=")
        if mm:
            spec["min_months"] = mm
        return spec
    if "myocardial infarction" in t or "heart attack" in t:
        spec = {"kind": "condition", "name": "mi"}
        mm = _months(t, r"(?:within|in the (?:past|last)|last|past)")
        if mm:
            spec["within_months"] = mm
        return spec
    if "insulin" in t:
        return {"kind": "med", "name": "insulin"}
    if "metformin" in t:
        return {"kind": "med", "name": "metformin"}
    return None


# ---------- optional LLM fallback ----------
def validate_spec(s) -> dict | None:
    if not isinstance(s, dict) or s.get("kind") not in ALLOWED_KINDS:
        return None
    k = s["kind"]
    if k == "lab" and s.get("name") not in ALLOWED_LABS: return None
    if k == "condition" and s.get("name") not in ALLOWED_CONDS: return None
    if k == "med" and s.get("name") not in ALLOWED_MEDS: return None
    if k in ("age", "lab"):
        for key in ("lo", "hi"):
            if s.get(key) is not None and not isinstance(s[key], (int, float)):
                return None
        s.setdefault("lo", None); s.setdefault("hi", None)
        s.setdefault("lo_incl", True); s.setdefault("hi_incl", True)
        if s["lo"] is None and s["hi"] is None:
            return None
    return s


def llm_parse(text: str) -> dict | None:
    """Return a validated spec or None. Needs `pip install anthropic` + ANTHROPIC_API_KEY."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        prompt = (
            "Convert this clinical-trial eligibility criterion into ONE JSON object, or the word NONE if it "
            "cannot be expressed. Schema: {kind: age|lab|condition|med, name (lab: hba1c|bmi|egfr; condition: "
            "t2dm|t1dm|pregnancy|mi; med: metformin|insulin|sglt2|glp1), lo, hi, lo_incl, hi_incl, "
            "min_months, within_months}. The JSON describes the condition stated in the text (not whether it "
            "is inclusion/exclusion). Output JSON only.\n\nCriterion: " + text)
        msg = client.messages.create(
            model=os.environ.get("TRIALSENSE_LLM_MODEL", "claude-sonnet-5-5"),
            max_tokens=300, messages=[{"role": "user", "content": prompt}])
        out = msg.content[0].text.strip().strip("`")
        if out.upper().startswith("NONE"):
            return None
        return validate_spec(json.loads(out.removeprefix("json").strip()))
    except Exception:
        return None


def parse_trial_criteria(raw: str, use_llm: bool = False) -> list[Criterion]:
    crits = []
    for ctype, text in split_criteria(raw):
        spec, how = parse_rule(text), "rule"
        if spec is None and use_llm:
            spec, how = llm_parse(text), "llm"
        crits.append(Criterion(text, ctype, spec, how if spec else "none"))
    return crits
