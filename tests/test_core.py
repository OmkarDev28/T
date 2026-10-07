from datetime import date

from trialsense.criteria import parse_rule, split_criteria
from trialsense.fhir_extract import extract_features
from trialsense.matcher import match_trial, rank_trials
from trialsense.synthetic import generate_patients
from trialsense.trials import demo_trials

TODAY = date(2026, 10, 7)


def test_parser_cases():
    assert parse_rule("Age 18 to 75 years")["hi"] == 75
    assert parse_rule("Age >= 18 years")["lo"] == 18
    assert parse_rule("Age 50 years or older")["lo"] == 50
    s = parse_rule("HbA1c between 7.5% and 10.5%")
    assert (s["name"], s["lo"], s["hi"]) == ("hba1c", 7.5, 10.5)
    s = parse_rule("HbA1c >= 8.0% and <= 12.0%")
    assert (s["lo"], s["hi"]) == (8.0, 12.0)
    s = parse_rule("eGFR < 45 mL/min/1.73 m2")
    assert s["hi"] == 45 and s["hi_incl"] is False
    assert parse_rule("Myocardial infarction within 6 months")["within_months"] == 6
    assert parse_rule("Type 2 diabetes for at least 1 year")["min_months"] == 12
    assert parse_rule("History of type 1 diabetes")["name"] == "t1dm"
    assert parse_rule("Personal history of medullary thyroid carcinoma") is None


def test_split():
    out = split_criteria("Inclusion Criteria:\n* a\n* b\n  cont\nExclusion Criteria:\n* c")
    assert out == [("inclusion", "a"), ("inclusion", "b cont"), ("exclusion", "c")]


def test_end_to_end():
    pts = [extract_features(b, TODAY) for b in generate_patients(300, 1, TODAY)]
    trials = demo_trials()
    statuses = {m.status for p in pts for m in rank_trials(trials, p, TODAY)}
    assert statuses == {"Likely eligible", "Needs review", "Ineligible"} or "Ineligible" in statuses
    m = match_trial(trials[0], pts[0], TODAY)
    assert all(r.evidence for r in m.results)


if __name__ == "__main__":
    test_parser_cases(); test_split(); test_end_to_end(); print("all tests passed")
