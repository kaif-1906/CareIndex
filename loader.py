"""Stage 4: clean the CareIndex files and load them into SQLite.

Usage:
    python loader.py --data-dir /path/to/kaggle/files --out medical.db

The database is built in a temporary file and published with os.replace, so a
failed load never overwrites a working database (use case UC5: existing data unchanged).
Invalid records are reported and excluded, never silently invented.
"""
import argparse
import csv
import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field

from normalize import canonical_disease, display_symptom, normalize_symptom

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "schema.sql")
DEFAULT_DIET = os.path.join(HERE, "data", "diet_guidance_DRAFT.csv")
MAX_PRECAUTIONS = 4
WEIGHT_RANGE = (1, 7)


@dataclass
class LoadReport:
    diseases: int = 0
    symptoms: int = 0
    disease_symptom_links: int = 0
    duplicate_rows_skipped: int = 0
    symptoms_without_weight: int = 0
    diseases_without_description: int = 0
    diseases_without_precautions: int = 0
    diseases_without_diet: int = 0
    diet_entries_marked_draft: int = 0
    rejected: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _read_rows(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"required file missing: {path}")
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.reader(f))
    except UnicodeDecodeError:
        with open(path, newline="", encoding="latin-1") as f:
            return list(csv.reader(f))


def _parse_dataset(path, report):
    """Return {disease: [normalised symptoms]} from the wide Kaggle layout."""
    diseases = {}
    seen = set()
    for line_no, row in enumerate(_read_rows(path)[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        name = canonical_disease(row[0]) if row else ""
        if not name:
            report.rejected.append({"file": "dataset.csv", "line": line_no, "reason": "missing disease name"})
            continue
        symptoms = []
        for cell in row[1:]:
            if cell.strip():
                s = normalize_symptom(cell)
                if s and s not in symptoms:
                    symptoms.append(s)
        if not symptoms:
            report.rejected.append({"file": "dataset.csv", "line": line_no, "reason": f"no symptoms for {name}"})
            continue
        key = (name, frozenset(symptoms))
        if key in seen:
            report.duplicate_rows_skipped += 1
            continue
        seen.add(key)
        known = diseases.setdefault(name, [])
        for s in symptoms:
            if s not in known:
                known.append(s)
    return diseases


def _parse_weights(path, report):
    weights = {}
    for line_no, row in enumerate(_read_rows(path)[1:], start=2):
        if len(row) < 2 or not row[0].strip():
            continue
        s = normalize_symptom(row[0])
        try:
            w = int(row[1].strip())
        except ValueError:
            report.rejected.append({"file": os.path.basename(path), "line": line_no, "reason": "weight is not an integer"})
            continue
        if not WEIGHT_RANGE[0] <= w <= WEIGHT_RANGE[1]:
            report.rejected.append({"file": os.path.basename(path), "line": line_no,
                                    "reason": f"weight {w} outside {WEIGHT_RANGE}"})
            continue
        weights[s] = w
    return weights


def _parse_by_disease(path, report):
    """Return {disease: [non-empty cell values after the name]} for one-row-per-disease files."""
    out = {}
    for line_no, row in enumerate(_read_rows(path)[1:], start=2):
        if not row or not row[0].strip():
            continue
        name = canonical_disease(row[0])
        values = [c.strip() for c in row[1:] if c.strip()]
        if name in out:
            report.warnings.append(f"{os.path.basename(path)} line {line_no}: duplicate entry for {name}; first kept")
            continue
        out[name] = values
    return out


def build(data_dir, out_path, diet_path=DEFAULT_DIET):
    report = LoadReport()
    diseases = _parse_dataset(os.path.join(data_dir, "dataset.csv"), report)
    if not diseases:
        raise ValueError("dataset.csv produced no valid diseases; existing database left unchanged")
    weights = _parse_weights(os.path.join(data_dir, "Symptom-severity.csv"), report)
    descriptions = _parse_by_disease(os.path.join(data_dir, "symptom_Description.csv"), report)
    precautions = _parse_by_disease(os.path.join(data_dir, "symptom_precaution.csv"), report)
    diet = _parse_by_disease(diet_path, report)

    all_symptoms = sorted({s for syms in diseases.values() for s in syms})
    unused = sorted(set(weights) - set(all_symptoms))
    if unused:
        report.warnings.append(f"severity file lists symptoms not in dataset (ignored): {unused}")
    for name in sorted((set(descriptions) | set(precautions) | set(diet)) - set(diseases)):
        report.warnings.append(f"entry for '{name}' is not in dataset.csv (ignored)")

    tmp = out_path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    conn = sqlite3.connect(tmp)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
        with conn:  # one transaction: all rows or none
            symptom_ids = {}
            for s in all_symptoms:
                w = weights.get(s)
                if w is None:
                    report.symptoms_without_weight += 1
                cur = conn.execute(
                    "INSERT INTO SYMPTOM (symptom_name, display_name, weight) VALUES (?, ?, ?)",
                    (s, display_symptom(s), w))
                symptom_ids[s] = cur.lastrowid
                report.symptoms += 1

            for name in sorted(diseases):
                desc_vals = descriptions.get(name, [])
                desc = desc_vals[0] if desc_vals else ""
                if not desc:
                    report.diseases_without_description += 1
                cur = conn.execute("INSERT INTO DISEASE (name, description) VALUES (?, ?)", (name, desc))
                disease_id = cur.lastrowid
                report.diseases += 1

                for s in diseases[name]:
                    conn.execute("INSERT INTO DISEASE_SYMPTOM (disease_id, symptom_id) VALUES (?, ?)",
                                 (disease_id, symptom_ids[s]))
                    report.disease_symptom_links += 1

                prec = precautions.get(name, [])
                if len(prec) > MAX_PRECAUTIONS:
                    report.warnings.append(f"{name}: {len(prec)} precautions, keeping first {MAX_PRECAUTIONS}")
                prec = (prec + [None] * MAX_PRECAUTIONS)[:MAX_PRECAUTIONS]
                if prec[0] is None:
                    report.diseases_without_precautions += 1

                diet_vals = diet.get(name, [])
                diet_text = diet_vals[0] if diet_vals else None
                if diet_text is None:
                    report.diseases_without_diet += 1
                if len(diet_vals) > 1 and "DRAFT" in diet_vals[1].upper():
                    report.diet_entries_marked_draft += 1

                conn.execute(
                    "INSERT INTO GUIDANCE (disease_id, precaution_1, precaution_2, precaution_3, precaution_4, diet_guidance) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (disease_id, *prec, diet_text))
        conn.close()
        os.replace(tmp, out_path)  # atomic publish
    except Exception:
        conn.close()
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return report


def main():
    ap = argparse.ArgumentParser(description="Load CareIndex disease data into SQLite.")
    ap.add_argument("--data-dir", required=True, help="folder with dataset.csv, Symptom-severity.csv, etc.")
    ap.add_argument("--out", default=os.path.join(HERE, "medical.db"))
    ap.add_argument("--diet", default=DEFAULT_DIET)
    args = ap.parse_args()
    report = build(args.data_dir, args.out, args.diet)
    print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    main()
