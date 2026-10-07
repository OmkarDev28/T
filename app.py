"""TrialSense v1 UI.   Run:  streamlit run app.py"""
from collections import Counter
from datetime import date

import pandas as pd
import streamlit as st

from trialsense.fhir_extract import extract_features
from trialsense.matcher import match_trial, rank_patients, rank_trials
from trialsense.synthetic import generate_patients
from trialsense.trials import demo_trials, fetch_ctgov

ICON = {"pass": "✅", "fail": "❌", "unknown": "❓"}
TODAY = date.today()

st.set_page_config(page_title="TrialSense", page_icon="🩺", layout="wide")
st.title("🩺 TrialSense")
st.caption("Explainable hybrid AI for clinical-trial pre-screening · synthetic FHIR patients · "
           "T2DM case study · research prototype")


@st.cache_resource
def patients(n, seed):
    return [extract_features(b, TODAY) for b in generate_patients(n, seed, TODAY)]


@st.cache_resource
def live(query, n):
    return fetch_ctgov(query, n)


with st.sidebar:
    st.header("Data")
    n = st.slider("Synthetic patients", 50, 1000, 200, 50)
    seed = st.number_input("Seed", value=42, step=1)
    src = st.radio("Trial source", ["Demo trials", "Live ClinicalTrials.gov"])
    if src == "Live ClinicalTrials.gov":
        q = st.text_input("Condition", "type 2 diabetes")
        k = st.slider("Max trials", 5, 50, 20)
        try:
            trials = live(q, k)
        except Exception as e:
            st.error(f"Fetch failed ({e}); using demo trials.")
            trials = demo_trials()
    else:
        trials = demo_trials()

pts = patients(n, int(seed))
tab1, tab2, tab3 = st.tabs(["Patient → trials", "Trial → cohort", "Criteria parser"])

with tab1:
    pid = st.selectbox("Patient", [p.pid for p in pts])
    p = next(x for x in pts if x.pid == pid)
    c = st.columns(5)
    c[0].metric("Age", p.age); c[1].metric("Sex", p.sex)
    for i, lab in enumerate(["hba1c", "bmi", "egfr"]):
        v = p.labs.get(lab)
        c[2 + i].metric(lab.upper() if lab != "egfr" else "eGFR", f"{v[0]}" if v else "—",
                        help=str(v[1]) if v else "missing")
    st.write("**Conditions:**", ", ".join(p.conditions) or "none",
             " · **Active meds:**", ", ".join(p.meds) or "none")
    ranked = rank_trials(trials, p, TODAY)
    st.dataframe(pd.DataFrame([{"Trial": m.trial.id, "Title": m.trial.title, "Status": m.status,
                                "Criteria passed": f"{m.score:.0%}", "Blockers": len(m.blockers),
                                "Needs review": len(m.unknowns)} for m in ranked]),
                 use_container_width=True, hide_index=True)
    for m in ranked:
        with st.expander(f"{m.trial.id} — {m.status} — {m.trial.title}"):
            st.dataframe(pd.DataFrame([{"": ICON[r.outcome], "Type": r.criterion.ctype,
                                        "Criterion": r.criterion.text, "Evidence": r.evidence}
                                       for r in m.results]),
                         use_container_width=True, hide_index=True)

with tab2:
    ALL = ["Likely eligible", "Needs review", "Ineligible"]
    view = st.radio("View", ["Single trial", "Top patients for every trial"], horizontal=True)
    f1, f2, f3 = st.columns(3)
    top_n = f1.slider("Top N patients", 5, 100, 10)
    statuses = set(f2.multiselect("Status", ALL, default=ALL[:2]))
    min_score = f3.slider("Min criteria passed (%)", 0, 100, 0) / 100

    def rows(trial):
        out = []
        for rank, (q, m) in enumerate(rank_patients(trial, pts, TODAY, statuses, min_score, top_n), 1):
            out.append({"Rank": rank, "Patient": q.pid, "Age": q.age, "Sex": q.sex, "Status": m.status,
                        "Criteria passed": f"{m.score:.0%}", "Unknowns": len(m.unknowns),
                        "Blockers": len(m.blockers),
                        "Missing / failing": "; ".join(
                            [f"? {r.criterion.text}" for r in m.unknowns] +
                            [f"x {r.criterion.text}" for r in m.blockers])[:200]})
        return pd.DataFrame(out)

    if view == "Single trial":
        tid = st.selectbox("Trial", [t.id for t in trials], format_func=lambda i: next(
            f"{t.id} — {t.title}" for t in trials if t.id == i))
        t = next(x for x in trials if x.id == tid)
        ms = [match_trial(t, q, TODAY) for q in pts]
        cnt = Counter(m.status for m in ms)
        for col, s in zip(st.columns(3), ALL):
            col.metric(s, cnt.get(s, 0))
        df = rows(t)
        st.subheader(f"Best patients for {t.id}")
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False), f"{t.id}_top_patients.csv")
        why = Counter(r.criterion.text for m in ms for r in m.blockers)
        if why:
            st.subheader("What screens patients out?")
            st.bar_chart(pd.Series(why).sort_values(ascending=False))
    else:
        for t in trials:
            df = rows(t)
            n_ok = sum(match_trial(t, q, TODAY).status == "Likely eligible" for q in pts)
            st.subheader(f"{t.id} — {t.title}")
            st.caption(f"{n_ok} likely-eligible patients out of {len(pts)}")
            st.dataframe(df, use_container_width=True, hide_index=True)

with tab3:
    allc = [(t.id, c) for t in trials for c in t.criteria]
    parsed = sum(c.spec is not None for _, c in allc)
    st.metric("Rule-parse coverage", f"{parsed / max(1, len(allc)):.0%}", f"{parsed}/{len(allc)} criteria")
    only_un = st.checkbox("Show only unparsed criteria")
    st.dataframe(pd.DataFrame([{"Trial": i, "Type": c.ctype, "Criterion": c.text,
                                "Parsed spec": str(c.spec) if c.spec else "— (manual review)"}
                               for i, c in allc if not (only_un and c.spec)]),
                 use_container_width=True, hide_index=True)
