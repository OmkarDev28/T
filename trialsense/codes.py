"""Shared terminology maps (SNOMED CT / LOINC / RxNorm) used by generator and extractor."""

SNOMED_SYS = "http://snomed.info/sct"
LOINC_SYS = "http://loinc.org"
RXNORM_SYS = "http://www.nlm.nih.gov/research/umls/rxnorm"

# key -> (code, display)
CONDITION_CODES = {
    "t2dm": ("44054006", "Diabetes mellitus type 2"),
    "t1dm": ("46635009", "Diabetes mellitus type 1"),
    "pregnancy": ("77386006", "Pregnant"),
    "mi": ("22298006", "Myocardial infarction"),
}
CONDITION_KEYWORDS = {
    "t2dm": ["type 2 diabetes", "diabetes mellitus type 2"],
    "t1dm": ["type 1 diabetes", "diabetes mellitus type 1"],
    "pregnancy": ["pregnan"],
    "mi": ["myocardial infarction", "heart attack"],
}

# key -> (code, display, unit)
LAB_CODES = {
    "hba1c": ("4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood", "%"),
    "egfr": ("33914-3", "Glomerular filtration rate/1.73 sq M.predicted", "mL/min/1.73m2"),
    "bmi": ("39156-5", "Body mass index (BMI) [Ratio]", "kg/m2"),
}
LAB_LABEL = {"hba1c": "HbA1c", "egfr": "eGFR", "bmi": "BMI"}

# key -> (code, display)
MED_CODES = {
    "metformin": ("6809", "Metformin"),
    "insulin": ("5856", "Insulin human"),
    "sglt2": ("1545653", "Empagliflozin"),
    "glp1": ("1991302", "Semaglutide"),
}
MED_KEYWORDS = {
    "metformin": ["metformin"],
    "insulin": ["insulin"],
    "sglt2": ["empagliflozin", "dapagliflozin", "canagliflozin"],
    "glp1": ["semaglutide", "liraglutide", "dulaglutide"],
}
CONDITION_LABEL = {
    "t2dm": "type 2 diabetes",
    "t1dm": "type 1 diabetes",
    "pregnancy": "pregnancy",
    "mi": "myocardial infarction",
}
