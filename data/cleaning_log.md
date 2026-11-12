# Engine 03 - Data cleaning log (Stage 3)

Source: Kaggle "Disease Symptom Prediction" files as uploaded (dataset.csv, Symptom-severity.csv, symptom_Description.csv, symptom_precaution.csv).

| # | Issue found | Rule applied | Rows affected |
|---|---|---|---|
| 1 | Leading/trailing spaces in cells (e.g. " skin_rash") | Strip and normalise every symptom | ~36,000 cells |
| 2 | Symptom names with stray spaces: `dischromic _patches`, `spotting_ urination` | Join words with single underscore | 2 symptoms |
| 3 | Severity file typo `foul_smell_ofurine` | Correction map to `foul_smell_of_urine` | 1 weight row |
| 4 | Disease name typos: `Dimorphic hemmorhoids(piles)`, `(vertigo) Paroymsal Positional Vertigo`, `Peptic ulcer diseae`, `Osteoarthristis` | Correction map to the canonical spelling | 4 diseases |
| 5 | Inconsistent capitalisation: `hepatitis A` | Canonical `Hepatitis A` | 1 disease |
| 6 | Description file spells the disease `Dimorphic hemorrhoids(piles)` | Mapped through the same correction map | 1 entry |
| 7 | Identical disease/symptom-set rows repeated | Kept once (each row is a patient case; the union of symptoms per disease is stored) | 4,616 rows skipped |
| 8 | `prognosis` in the severity file is not a symptom in the dataset | Ignored, reported as a warning | 1 row |
| 9 | No diet guidance in any dataset file | Team-written general guidance in data/diet_guidance_DRAFT.csv, marked DRAFT | 41 diseases |
| 10 | Weight outside 1-7 or not an integer | Rejected and reported | 0 rows |

Result after cleaning: 41 diseases, 131 symptoms (all with a weight), 321 unique disease-symptom links, 0 rejected rows.
