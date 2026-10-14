"""
Laduje wygenerowane pliki CSV (data/raw) do bazy SQLite zgodnie ze schema.sql,
a nastepnie tworzy widoki z views.sql.

Uzycie:
    python sql/load_to_sqlite.py
"""
import os
import sqlite3

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
DB_PATH = os.path.join(BASE_DIR, "data", "fpa_cost.db")
SCHEMA_SQL = os.path.join(BASE_DIR, "sql", "schema.sql")
VIEWS_SQL = os.path.join(BASE_DIR, "sql", "views.sql")


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)

    with open(SCHEMA_SQL, "r") as f:
        conn.executescript(f.read())

    table_files = {
        "dim_cost_center": "dim_cost_center.csv",
        "dim_category": "dim_category.csv",
        "dim_date": "dim_date.csv",
        "dim_client": "dim_client.csv",
        "dim_project": "dim_project.csv",
    }
    for table, filename in table_files.items():
        df = pd.read_csv(os.path.join(RAW_DIR, filename))
        df.to_sql(table, conn, if_exists="append", index=False)

    # fact_costs ma kolumne autoincrement fact_id, wiec wstawiamy bez niej
    fact_df = pd.read_csv(os.path.join(RAW_DIR, "fact_costs.csv"))
    fact_df.to_sql("fact_costs", conn, if_exists="append", index=False)

    fact_rev_df = pd.read_csv(os.path.join(RAW_DIR, "fact_revenue.csv"))
    fact_rev_df.to_sql("fact_revenue", conn, if_exists="append", index=False)

    with open(VIEWS_SQL, "r") as f:
        conn.executescript(f.read())

    conn.commit()

    # szybka walidacja
    cur = conn.cursor()
    for table in ["dim_cost_center", "dim_category", "dim_date", "dim_client", "dim_project", "fact_costs", "fact_revenue"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table:<20} {cur.fetchone()[0]:>6} wierszy")

    print(f"\nBaza zapisana w: {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
