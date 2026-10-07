"""Explainable three-valued matcher: every verdict carries its evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .codes import CONDITION_LABEL, LAB_LABEL
from .criteria import Criterion
from .fhir_extract import Features
from .trials import Trial

STALE_DAYS = 365


def in_bounds(v: float, s: dict) -> bool:
    lo, hi = s.get("lo"), s.get("hi")
    if lo is not None and (v < lo or (v == lo and not s.get("lo_incl", True))): return False
    if hi is not None and (v > hi or (v == hi and not s.get("hi_incl", True))): return False
    return True


def evaluate_spec(spec: dict, f: Features, today: date) -> tuple[bool | None, str]:
    """Return (does the stated condition hold?, evidence). None = unknown."""
    k = spec["kind"]
    if k == "age":
        if f.age is None:
            return None, "age unavailable"
        return in_bounds(f.age, spec), f"age = {f.age}"
    if k == "lab":
        name = LAB_LABEL[spec["name"]]
        rec = f.labs.get(spec["name"])
        if rec is None:
            return None, f"no {name} result on file"
        val, d, _ = rec
        if (today - d).days > STALE_DAYS:
            return None, f"{name} = {val} ({d}) is older than 12 months"
        return in_bounds(val, spec), f"{name} = {val} ({d})"
    if k == "condition":
        key, label = spec["name"], CONDITION_LABEL[spec["name"]]
        if key not in f.conditions:
            return False, f"no active {label} on record"
        onset = f.conditions[key]
        for field_, op in (("min_months", "ge"), ("within_months", "le")):
            if spec.get(field_) is not None:
                if onset is None:
                    return None, f"{label} on record but onset date unknown"
                months = (today - onset).days / 30.44
                ok = months >= spec[field_] if op == "ge" else months <= spec[field_]
                return ok, f"{label} since {onset} ({months:.0f} months ago)"
        return True, f"{label} on record" + (f" since {onset}" if onset else "")
    if k == "med":
        has = spec["name"] in f.meds
        return has, f"{spec['name']} {'is' if has else 'not'} an active medication"
    return None, "unsupported criterion kind"


@dataclass
class CriterionResult:
    criterion: Criterion
    outcome: str     # "pass" | "fail" | "unknown"
    evidence: str


@dataclass
class TrialMatch:
    trial: Trial
    status: str      # "Likely eligible" | "Needs review" | "Ineligible"
    score: float
    results: list[CriterionResult]

    @property
    def blockers(self):
        return [r for r in self.results if r.outcome == "fail"]

    @property
    def unknowns(self):
        return [r for r in self.results if r.outcome == "unknown"]


STATUS_ORDER = {"Likely eligible": 0, "Needs review": 1, "Ineligible": 2}


def match_trial(trial: Trial, f: Features, today: date | None = None) -> TrialMatch:
    today = today or date.today()
    results = []
    for c in trial.criteria:
        if c.spec is None:
            results.append(CriterionResult(c, "unknown", "not auto-parsed - manual review"))
            continue
        verdict, ev = evaluate_spec(c.spec, f, today)
        if verdict is None:
            outcome = "unknown"
        elif c.ctype == "inclusion":
            outcome = "pass" if verdict else "fail"
        else:  # exclusion: condition holding => patient excluded
            outcome = "fail" if verdict else "pass"
        results.append(CriterionResult(c, outcome, ev))
    n = len(results) or 1
    passes = sum(r.outcome == "pass" for r in results)
    if any(r.outcome == "fail" for r in results):
        status = "Ineligible"
    elif any(r.outcome == "unknown" for r in results):
        status = "Needs review"
    else:
        status = "Likely eligible"
    return TrialMatch(trial, status, passes / n, results)


def rank_trials(trials: list[Trial], f: Features, today: date | None = None) -> list[TrialMatch]:
    ms = [match_trial(t, f, today) for t in trials]
    return sorted(ms, key=lambda m: (STATUS_ORDER[m.status], -m.score))


def rank_patients(trial: Trial, patients: list[Features], today: date | None = None,
                  statuses: set[str] | None = None, min_score: float = 0.0,
                  top_n: int | None = None) -> list[tuple[Features, TrialMatch]]:
    """Best-fit patients for ONE trial: status, then % criteria passed, then fewest unknowns."""
    pairs = [(p, match_trial(trial, p, today)) for p in patients]
    pairs = [(p, m) for p, m in pairs
             if (statuses is None or m.status in statuses) and m.score >= min_score]
    pairs.sort(key=lambda pm: (STATUS_ORDER[pm[1].status], -pm[1].score, len(pm[1].unknowns), pm[0].pid))
    return pairs[:top_n] if top_n else pairs
