# Engine 03 - Medical Knowledge Store (CareIndex)

Owner: E3 (DBMS). Requirements covered: FR7, FR11, NFR5 (SQL parameterised, data validated at load), use cases UC3 and UC5.
Stack: Python 3.10+, SQLite (standard library only, no internet).

## Stage status

| Stage | Task | Status | Where |
|---|---|---|---|
| 1 | Define Engine 03 responsibilities | Done | This README, section "Responsibility" |
| 2 | Design the database schema | Done | schema.sql |
| 3 | Prepare the medical dataset | Done | normalize.py, data/cleaning_log.md, data/diet_guidance_DRAFT.csv |
| 4 | Implement the data loader | Done | loader.py |
| 5 | Implement database retrieval functions | Done | store.py |
| 6 | Test the database and retrieval functions | Done (18 tests pass; benchmark run) | tests/test_engine3.py, benchmark.py, results.json |
| 7 | Prepare the interface for integration | Done (API contract below); integration with E1/E4 pending team agreement | store.py docstring, section "Integration contract" |

## Responsibility

This engine is responsible for storing structured disease information (name, description, symptoms, precautions, diet guidance) in a relational SQLite schema, loading and validating it from the curated files, and returning exact records by disease ID.

In scope: schema, keys and indexes; data cleaning and validation at load; key-based lookups; the indexed vs LIKE benchmark.
Out of scope: ranking (E1), process management (E2), HTTP and UI (E4), any medical advice or diagnosis.

## Schema (Stage 2)

- DISEASE(disease_id PK, name UNIQUE, description)
- SYMPTOM(symptom_id PK, symptom_name UNIQUE canonical, display_name, weight 1-7)
- DISEASE_SYMPTOM(disease_id FK, symptom_id FK, PK(disease_id, symptom_id)), index on symptom_id
- GUIDANCE(disease_id PK FK, precaution_1..4, diet_guidance)

The Gate-0 deck listed "specialty" and "severity" on DISEASE. Neither is in the dataset, so they are not stored. Severity is stored per symptom (the dataset's weights). Specialty needs a decision from the team.

## Running

```
python3 loader.py --data-dir /mnt/user-data/uploads --out medical.db
python3 -m unittest discover -s tests -v
python3 benchmark.py --db medical.db --runs 300 --synthetic --out results.json
python3 store.py medical.db          # prints Malaria details as JSON
```

The loader writes to a temporary file and publishes it with os.replace, so a failed load never overwrites a working database.

## Integration contract (Stage 7)

Read-only, no caller-supplied SQL. Errors: DiseaseNotFound, InvalidInput, StoreUnavailable, StoreError (all subclass StoreError). Missing diet guidance is returned as null, never invented.

| Method | Used by | Returns |
|---|---|---|
| list_symptoms() | E4 (suggestions, checklist) | all symptoms with display names and weights |
| find_symptoms(query, limit) | E4 (typing suggestions, FR1) | prefix matches first, then substring matches |
| resolve_symptoms(terms) | E1 (FR2) | {matched: [...], unknown: [...]} |
| get_disease(id) / get_disease_by_name(name) | E1, E4 | one disease |
| get_disease_summaries(ids) | E1 (name the ranked IDs) | id and name for each ID |
| get_disease_symptoms(id) | E4 | symptoms for one disease |
| get_guidance(id) | E4 | precautions list and diet_guidance (or null) |
| get_disease_details(id) | E4 (UC3 details page) | disease, symptoms, precautions, diet, disclaimer |

Example: `get_disease_details(id)` returns the disclaimer "General information only. This is not a diagnosis or medical advice; consult a doctor."

## Open items for the team

1. **Diet guidance is a DRAFT.** Written by the team for this build; the guide (Dr Santosh P / Prof. Santosh Pattar) and the team should review it before the demo. It is marked "DRAFT" in the data file.
2. **Synonyms (FR2).** The dataset has no synonym list, so "high temperature" will not match "high_fever". Either add a synonym table or narrow FR2 to spelling and format normalisation.
3. **Specialty field** from the Gate-0 deck is not in the data. Decide whether to drop it from the deck or source it.
4. **Extra severity row** `prognosis` is ignored; confirm that is acceptable.
5. **Dataset size.** The dataset has 321 unique disease-symptom links, so the indexed-vs-LIKE difference is small in absolute time (see results.json). The synthetic run shows the scaling.
