"""Stage 5 and 7: read-only retrieval API for Engine 03 (Medical Knowledge Store).

Integration contract (for Engine 01 ranking and Engine 04 HTTP/JSON):
  * disease_id is the integer primary key; every method returns JSON-serialisable data.
  * Unknown disease            -> DiseaseNotFound
  * Bad input (e.g. id = "x")  -> InvalidInput
  * Database missing           -> StoreUnavailable
  * Other SQLite failure       -> StoreError
  The engine never invents content: a missing diet entry is returned as None.
  Every caller value is bound as a SQL parameter (NFR5).
"""
import sqlite3
from pathlib import Path

from normalize import normalize_symptom

DISCLAIMER = "General information only. This is not a diagnosis or medical advice; consult a doctor."
MAX_RESULTS = 50


class StoreError(Exception):
    pass


class StoreUnavailable(StoreError):
    pass


class DiseaseNotFound(StoreError):
    pass


class InvalidInput(StoreError):
    pass


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class KnowledgeStore:
    def __init__(self, db_path):
        path = Path(db_path).resolve()
        if not path.is_file():
            raise StoreUnavailable(f"database not found: {path}")
        self._uri = path.as_uri() + "?mode=ro"  # the store never writes

    def _connect(self):
        try:
            conn = sqlite3.connect(self._uri, uri=True)
        except sqlite3.Error as exc:
            raise StoreUnavailable(str(exc)) from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _fetch(self, sql, params=()):
        conn = self._connect()
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        except sqlite3.Error as exc:
            raise StoreError(f"query failed: {exc}") from exc
        finally:
            conn.close()

    @staticmethod
    def _disease_id(value):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise InvalidInput("disease_id must be a positive integer")
        return value

    # ---- symptoms -------------------------------------------------------
    def list_symptoms(self):
        return self._fetch(
            "SELECT symptom_id, symptom_name, display_name, weight FROM SYMPTOM ORDER BY display_name")

    def find_symptoms(self, query, limit=10):
        """Autocomplete for FR1: prefix matches first, then substring matches."""
        needle = normalize_symptom(query or "")
        if not needle:
            return []
        limit = max(1, min(int(limit), MAX_RESULTS))
        esc = _escape_like(needle)
        return self._fetch(
            "SELECT symptom_id, symptom_name, display_name FROM SYMPTOM "
            "WHERE symptom_name LIKE ? ESCAPE '\\' "
            "ORDER BY CASE WHEN symptom_name LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END, symptom_name "
            "LIMIT ?",
            (f"%{esc}%", f"{esc}%", limit))

    def resolve_symptoms(self, terms):
        """FR2: normalise user terms and map them to canonical symptoms via the UNIQUE index."""
        matched, unknown, seen = [], [], set()
        for term in terms or []:
            key = normalize_symptom(str(term))
            if not key or key in seen:
                continue
            seen.add(key)
            rows = self._fetch(
                "SELECT symptom_id, symptom_name, display_name FROM SYMPTOM WHERE symptom_name = ?", (key,))
            if rows:
                matched.append({"input": term, **rows[0]})
            else:
                unknown.append(term)
        return {"matched": matched, "unknown": unknown}

    # ---- diseases -------------------------------------------------------
    def get_disease(self, disease_id):
        did = self._disease_id(disease_id)
        rows = self._fetch("SELECT disease_id, name, description FROM DISEASE WHERE disease_id = ?", (did,))
        if not rows:
            raise DiseaseNotFound(f"no disease with id {did}")
        return rows[0]

    def get_disease_by_name(self, name):
        rows = self._fetch(
            "SELECT disease_id, name, description FROM DISEASE WHERE name = ? COLLATE NOCASE", (str(name).strip(),))
        if not rows:
            raise DiseaseNotFound(f"no disease named {name!r}")
        return rows[0]

    def get_disease_summaries(self, disease_ids):
        """Names for a list of ids, e.g. the ranked output of Engine 01."""
        ids = [self._disease_id(i) for i in disease_ids]
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        return self._fetch(
            f"SELECT disease_id, name FROM DISEASE WHERE disease_id IN ({placeholders})", ids)

    def get_disease_symptoms(self, disease_id):
        did = self._disease_id(disease_id)
        self.get_disease(did)
        return self._fetch(
            "SELECT s.symptom_id, s.symptom_name, s.display_name, s.weight "
            "FROM DISEASE_SYMPTOM ds JOIN SYMPTOM s ON s.symptom_id = ds.symptom_id "
            "WHERE ds.disease_id = ? ORDER BY s.weight DESC, s.symptom_name",
            (did,))

    def get_guidance(self, disease_id):
        did = self._disease_id(disease_id)
        self.get_disease(did)
        rows = self._fetch(
            "SELECT precaution_1, precaution_2, precaution_3, precaution_4, diet_guidance "
            "FROM GUIDANCE WHERE disease_id = ?", (did,))
        if not rows:
            return {"precautions": [], "diet_guidance": None}
        row = rows[0]
        precautions = [row[f"precaution_{i}"] for i in range(1, 5) if row[f"precaution_{i}"]]
        return {"precautions": precautions, "diet_guidance": row["diet_guidance"]}

    def get_disease_details(self, disease_id):
        """FR7 / UC3: everything the details page needs in one call."""
        disease = self.get_disease(disease_id)
        guidance = self.get_guidance(disease["disease_id"])
        return {
            "disease": disease,
            "symptoms": self.get_disease_symptoms(disease["disease_id"]),
            "precautions": guidance["precautions"],
            "diet_guidance": guidance["diet_guidance"],
            "diet_note": None if guidance["diet_guidance"] else "Diet guidance is not yet available for this disease.",
            "disclaimer": DISCLAIMER,
        }


if __name__ == "__main__":
    import json
    import os
    import sys

    db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "medical.db")
    store = KnowledgeStore(db)
    print(json.dumps(store.get_disease_details(store.get_disease_by_name("Malaria")["disease_id"]), indent=2))
