"""Stage 6: tests for data preparation, loader, and retrieval API."""
import os
import sqlite3
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import loader  # noqa: E402
from normalize import canonical_disease, normalize_symptom  # noqa: E402
from store import (DiseaseNotFound, InvalidInput, KnowledgeStore,  # noqa: E402
                   StoreError, StoreUnavailable)

DATA_DIR = os.environ.get("CAREINDEX_DATA_DIR", "/mnt/user-data/uploads")


class DataPreparationTests(unittest.TestCase):
    def test_disease_corrections(self):
        self.assertEqual(canonical_disease("Dimorphic hemmorhoids(piles)"), "Dimorphic hemorrhoids (piles)")
        self.assertEqual(canonical_disease("Dimorphic hemorrhoids(piles)"), "Dimorphic hemorrhoids (piles)")
        self.assertEqual(canonical_disease("(vertigo) Paroymsal  Positional Vertigo"),
                         "(Vertigo) Paroxysmal Positional Vertigo")
        self.assertEqual(canonical_disease("hepatitis A"), "Hepatitis A")
        self.assertEqual(canonical_disease("AIDS"), "AIDS")

    def test_symptom_normalisation(self):
        cases = {
            "spotting_ urination": "spotting_urination",
            "dischromic _patches": "dischromic_patches",
            "foul_smell_of urine": "foul_smell_of_urine",
            "foul_smell_ofurine": "foul_smell_of_urine",
            "High Fever": "high_fever",
            "  itching ": "itching",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_symptom(raw), expected)


class BuiltDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="engine3_")
        cls.db_path = os.path.join(cls.tmp, "medical.db")
        cls.report = loader.build(DATA_DIR, cls.db_path)
        cls.store = KnowledgeStore(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        for name in os.listdir(cls.tmp):
            os.remove(os.path.join(cls.tmp, name))
        os.rmdir(cls.tmp)

    def sql(self, query, params=()):
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()

    # ---- loader and data quality ----
    def test_counts(self):
        self.assertEqual(self.report.diseases, 41)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM DISEASE")[0][0], 41)
        self.assertEqual(self.report.rejected, [])

    def test_symptom_names_are_clean(self):
        bad = self.sql("SELECT symptom_name FROM SYMPTOM WHERE symptom_name LIKE '% %' "
                       "OR symptom_name LIKE '%\\_\\_%' ESCAPE '\\' OR symptom_name LIKE '\\_%' ESCAPE '\\' "
                       "OR symptom_name LIKE '%\\_' ESCAPE '\\'")
        self.assertEqual(bad, [])

    def test_foreign_keys_valid(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            conn.close()

    def test_every_disease_has_symptoms(self):
        orphans = self.sql("SELECT name FROM DISEASE d WHERE NOT EXISTS "
                           "(SELECT 1 FROM DISEASE_SYMPTOM ds WHERE ds.disease_id = d.disease_id)")
        self.assertEqual(orphans, [])

    def test_severity_typo_fixed(self):
        self.assertEqual(self.sql("SELECT COUNT(*) FROM SYMPTOM WHERE symptom_name = 'foul_smell_of_urine' AND weight IS NOT NULL")[0][0], 1)

    def test_weights_valid_and_missing_reported(self):
        self.assertEqual(self.sql("SELECT COUNT(*) FROM SYMPTOM WHERE weight IS NOT NULL AND (weight < 1 OR weight > 7)")[0][0], 0)
        missing = self.sql("SELECT COUNT(*) FROM SYMPTOM WHERE weight IS NULL")[0][0]
        self.assertEqual(missing, self.report.symptoms_without_weight)

    def test_descriptions_precautions_and_diet_complete(self):
        self.assertEqual(self.report.diseases_without_description, 0)
        self.assertEqual(self.report.diseases_without_precautions, 0)
        self.assertEqual(self.report.diseases_without_diet, 0)
        self.assertEqual(self.report.diet_entries_marked_draft, 41)

    # ---- retrieval API ----
    def test_get_disease_and_missing(self):
        malaria = self.store.get_disease_by_name("malaria")
        self.assertEqual(malaria["name"], "Malaria")
        with self.assertRaises(DiseaseNotFound):
            self.store.get_disease(999999)

    def test_invalid_ids_rejected(self):
        for bad in ["1; DROP TABLE DISEASE", True, 0, -3, None]:
            with self.subTest(bad=bad), self.assertRaises(InvalidInput):
                self.store.get_disease(bad)

    def test_guidance_and_details(self):
        malaria = self.store.get_disease_by_name("Malaria")
        details = self.store.get_disease_details(malaria["disease_id"])
        self.assertIn("keep mosquitos out", details["precautions"])
        self.assertTrue(details["diet_guidance"])
        self.assertIn("consult a doctor", details["disclaimer"].lower())
        self.assertTrue(details["symptoms"])

    def test_autocomplete_prefix_first(self):
        names = [s["symptom_name"] for s in self.store.find_symptoms("fev")]
        self.assertIn("high_fever", names)
        self.assertEqual(self.store.find_symptoms("   "), [])

    def test_resolve_symptoms(self):
        result = self.store.resolve_symptoms(["High Fever", "zzz not real", "high_fever"])
        self.assertEqual([m["symptom_name"] for m in result["matched"]], ["high_fever"])
        self.assertEqual(result["unknown"], ["zzz not real"])

    def test_sql_injection_is_inert(self):
        self.assertEqual(self.store.find_symptoms("'; DROP TABLE SYMPTOM; --"), [])
        self.assertTrue(self.store.list_symptoms())

    def test_store_is_read_only(self):
        conn = self.store._connect()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("DELETE FROM SYMPTOM")
        finally:
            conn.close()

    def test_missing_database(self):
        with self.assertRaises(StoreUnavailable):
            KnowledgeStore(os.path.join(self.tmp, "nope.db"))


class FailedLoadTests(unittest.TestCase):
    def test_failed_load_keeps_existing_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "medical.db")
            loader.build(DATA_DIR, out)
            empty = os.path.join(tmp, "empty_data")
            os.mkdir(empty)
            with self.assertRaises(FileNotFoundError):
                loader.build(empty, out)
            self.assertFalse(os.path.exists(out + ".tmp"))
            store = KnowledgeStore(out)
            self.assertEqual(len(store.get_disease_summaries([1])), 1)
            self.assertEqual(len(store.list_symptoms()), 131)


if __name__ == "__main__":
    unittest.main(verbosity=2)
