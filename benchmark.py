"""Stage 6: indexed lookup vs LIKE scan (E3 KPI: 'indexed vs LIKE benchmark reported').

Usage:
    python benchmark.py --db medical.db --runs 300 [--synthetic] --out results.json

--synthetic also builds a larger random database (about 1M links) to show how
the two approaches scale, because the real dataset is too small to show a difference.
"""
import argparse
import json
import os
import random
import sqlite3
import statistics
import tempfile
import time

from loader import SCHEMA_PATH

TERM = "itching"
INDEXED_SQL = """SELECT d.disease_id FROM DISEASE_SYMPTOM ds
JOIN SYMPTOM s ON s.symptom_id = ds.symptom_id
JOIN DISEASE d ON d.disease_id = ds.disease_id
WHERE s.symptom_name = ?"""
SCAN_SQL = """SELECT d.disease_id FROM DISEASE_SYMPTOM ds
JOIN SYMPTOM s ON s.symptom_id = ds.symptom_id
JOIN DISEASE d ON d.disease_id = ds.disease_id
WHERE s.symptom_name LIKE ? ESCAPE '\\'"""


def _median_ms(conn, sql, params, runs):
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        conn.execute(sql, params).fetchall()
        samples.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(samples), 4)


def _plan(conn, sql, params):
    return [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()]


def benchmark(db_path, runs, label):
    conn = sqlite3.connect(db_path)
    try:
        n_links = conn.execute("SELECT COUNT(*) FROM DISEASE_SYMPTOM").fetchone()[0]
        indexed_params = (TERM,)
        scan_params = (f"%{TERM}%",)
        result = {
            "label": label,
            "database": os.path.basename(db_path),
            "disease_symptom_links": n_links,
            "term": TERM,
            "runs": runs,
            "indexed_lookup": {"median_ms": _median_ms(conn, INDEXED_SQL, indexed_params, runs),
                               "plan": _plan(conn, INDEXED_SQL, indexed_params)},
            "like_scan": {"median_ms": _median_ms(conn, SCAN_SQL, scan_params, runs),
                          "plan": _plan(conn, SCAN_SQL, scan_params)},
        }
        result["speedup"] = round(result["like_scan"]["median_ms"] / max(result["indexed_lookup"]["median_ms"], 1e-9), 1)
        return result
    finally:
        conn.close()


def build_synthetic(path, n_diseases=5000, n_symptoms=50000, n_links=1000000, seed=7):
    rnd = random.Random(seed)
    conn = sqlite3.connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    with conn:
        conn.executemany("INSERT INTO DISEASE (disease_id, name, description) VALUES (?, ?, '')",
                         [(i, f"synthetic disease {i}") for i in range(1, n_diseases + 1)])
        names = [TERM] + [f"synthetic_symptom_{i:06d}" for i in range(1, n_symptoms)]
        conn.executemany("INSERT INTO SYMPTOM (symptom_id, symptom_name, display_name) VALUES (?, ?, ?)",
                         [(i + 1, n, n) for i, n in enumerate(names)])
        conn.executemany("INSERT OR IGNORE INTO DISEASE_SYMPTOM (disease_id, symptom_id) VALUES (?, ?)",
                         ((rnd.randint(1, n_diseases), rnd.randint(1, n_symptoms)) for _ in range(n_links)))
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--runs", type=int, default=300)
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    results = [benchmark(args.db, args.runs, "real CareIndex dataset")]
    if args.synthetic:
        tmp = os.path.join(tempfile.mkdtemp(), "synthetic.db")
        build_synthetic(tmp)
        results.append(benchmark(tmp, max(20, args.runs // 10), "synthetic, about 1M links"))
        os.remove(tmp)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
