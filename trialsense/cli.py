"""Quick terminal demo:  python -m trialsense.cli --patient 3 [--live]"""
import argparse
from collections import Counter
from datetime import date

from .fhir_extract import extract_features
from .matcher import rank_trials
from .synthetic import generate_patients
from .trials import demo_trials, fetch_ctgov

ICON = {"pass": "[+]", "fail": "[x]", "unknown": "[?]"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--patient", type=int, default=0)
    ap.add_argument("--live", action="store_true", help="fetch real trials from ClinicalTrials.gov")
    a = ap.parse_args()

    today = date.today()
    pts = [extract_features(b, today) for b in generate_patients(a.n, a.seed, today)]
    trials = fetch_ctgov() if a.live else demo_trials()
    allc = [c for t in trials for c in t.criteria]
    parsed = sum(c.spec is not None for c in allc)
    print(f"{len(trials)} trials, {len(allc)} criteria, rule-parse coverage {parsed/len(allc):.0%}\n")

    p = pts[a.patient]
    print(f"Patient {p.pid}: age {p.age}, {p.sex}, conditions={list(p.conditions)}, "
          f"labs={ {k: v[0] for k, v in p.labs.items()} }, meds={list(p.meds)}\n")
    for m in rank_trials(trials, p, today)[:5]:
        print(f"{m.status:16s} {m.score:4.0%}  {m.trial.id}  {m.trial.title}")
        for r in m.results:
            print(f"     {ICON[r.outcome]} {r.criterion.ctype[:3]}: {r.criterion.text[:60]:60s} | {r.evidence}")
        print()

    print("Cohort summary (status counts per trial):")
    for t in trials:
        c = Counter(m.status for m in (rank_trials([t], q, today)[0] for q in pts))
        print(f"  {t.id}: {dict(c)}")


if __name__ == "__main__":
    main()
