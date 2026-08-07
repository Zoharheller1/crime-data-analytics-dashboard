import duckdb

# =========================
# CONFIG
# =========================
DUCKLAKE_FILE = "full_data.ducklake"          # my big lake
SQLITE_GOLD_FILE = "gold.db"                  # the small "GOLD" db to submit
SAMPLE_ROWS = 500                             # representative rows per GOLD table



# =========================
# CONNECT + LOAD EXTENSIONS
# =========================
con = duckdb.connect()
con.execute("INSTALL ducklake;")
con.execute("LOAD ducklake;")
con.execute(f"ATTACH 'ducklake:{DUCKLAKE_FILE}' AS lake;")
con.execute("USE lake;")

con.execute("INSTALL sqlite;")
con.execute("LOAD sqlite;")
con.execute(f"ATTACH '{SQLITE_GOLD_FILE}' AS gold (TYPE SQLITE);")

# =========================
# 0) Clean view for "real crimes" rows only
# =========================
con.execute("""
CREATE OR REPLACE VIEW crimes_only AS
SELECT *
FROM crimes
WHERE "Crime ID" IS NOT NULL
  AND "Crime type" IS NOT NULL;
""")

# =========================
# =========================
# Helpers
# =========================
def sql_quote(value: str) -> str:
    """Quote a string for SQL single-quoted literal safely."""
    return "'" + value.replace("'", "''") + "'"

def cols_count_in_duckdb(tbl: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM pragma_table_info('{tbl}')").fetchone()[0]

def insert_catalog_sqlite(sqlite_table_name: str, description: str):
    rows_count = con.execute(f"SELECT COUNT(*) FROM {sqlite_table_name};").fetchone()[0]
    cols_count = con.execute(f"SELECT COUNT(*) FROM pragma_table_info('{sqlite_table_name}');").fetchone()[0]
    con.execute(
        "INSERT INTO gold.table_catalog VALUES (?, ?, ?, ?)",
        [sqlite_table_name, int(rows_count), int(cols_count), description]
    )


# =========================
# 1) DEFINE QUERIES (DuckDB tables) + DESCRIPTIONS
# =========================
queries = {
    "q1_area_pareto": {
        "desc": "Pareto by area (LSOA): crimes count + % of total + cumulative %",
        "sql": r"""
WITH area_counts AS (
  SELECT
    "LSOA name" AS lsoa_name,
    COUNT(*) AS crimes
  FROM crimes_only
  WHERE "LSOA name" IS NOT NULL
  GROUP BY "LSOA name"
  HAVING COUNT(*) >= 100
),
ranked AS (
  SELECT
    lsoa_name,
    crimes,
    100.0 * crimes / SUM(crimes) OVER () AS pct_of_total,
    
      100.0 * SUM(crimes) OVER (ORDER BY crimes DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
      / SUM(crimes) OVER () AS cum_pct
  FROM area_counts
)
SELECT *
FROM ranked
ORDER BY crimes DESC;
"""
    },

    "q2_area_outliers": {
        "desc": "Areas above average crimes (z-score) to detect hotspots statistically",
        "sql": r"""
WITH area_counts AS (
  SELECT
    "LSOA name" AS lsoa_name,
    COUNT(*) AS crimes
  FROM crimes_only
  WHERE "LSOA name" IS NOT NULL
  GROUP BY "LSOA name"
  HAVING COUNT(*) >= 100
)
SELECT
  lsoa_name,
  crimes,
  ROUND(AVG(crimes) OVER (), 2) AS avg_area_crimes,
  ROUND((crimes - AVG(crimes) OVER ()) / NULLIF(STDDEV_SAMP(crimes) OVER (), 0), 2) AS z_score
FROM area_counts
QUALIFY crimes > AVG(crimes) OVER ()
ORDER BY z_score DESC, crimes DESC;
"""
    },

    "q3_reported_by_rank": {
        "desc": "Ranking police forces by outcome rate (Outcome type NOT NULL) with window rank",
        "sql": r"""
        WITH by_force AS (
  SELECT
    "Reported by" AS reported_by,
    COUNT(*) AS total_crimes,

    SUM(
      CASE
        WHEN "Last outcome category" ILIKE '%charged%'
        OR "Last outcome category" ILIKE '%caution%'
        OR "Last outcome category" ILIKE '%penalty%'
        OR "Last outcome category" ILIKE '%warning%'
        OR "Last outcome category" ILIKE '%summons%'
        OR "Last outcome category" ILIKE '%court%'
        THEN 1 ELSE 0
      END
    ) AS solved,
    ROUND(
      100.0 * SUM(
        CASE
          WHEN "Last outcome category" ILIKE '%charged%'
        OR "Last outcome category" ILIKE '%caution%'
        OR "Last outcome category" ILIKE '%penalty%'
        OR "Last outcome category" ILIKE '%warning%'
        OR "Last outcome category" ILIKE '%summons%'
        OR "Last outcome category" ILIKE '%court%'
          THEN 1 ELSE 0
        END
      ) / COUNT(*),
      2
    ) AS solved_rate
  FROM crimes_only
  WHERE "Reported by" IS NOT NULL
  GROUP BY "Reported by"
  HAVING COUNT(*) >= 1000

)
SELECT
  reported_by,
  total_crimes,
  solved,
  solved_rate,
  RANK() OVER (ORDER BY solved_rate DESC, total_crimes DESC) AS rate_rank
FROM by_force
ORDER BY rate_rank;


"""
    },

    "q4_cube_area_type_outcome": {
        "desc": "CUBE over (LSOA, Crime type): totals + outcome rate for subtotals and cross-cut analysis",
        "sql": r"""
SELECT
  "LSOA name" AS lsoa_name,
  "Crime type" AS crime_type,
  COUNT(*) AS total_crimes,

  -- Meaningful outcomes (proxy for investigative success / legal action)
  SUM(
    CASE
      WHEN "Last outcome category" ILIKE '%charged%'
        OR "Last outcome category" ILIKE '%caution%'
        OR "Last outcome category" ILIKE '%penalty%'
        OR "Last outcome category" ILIKE '%warning%'
        OR "Last outcome category" ILIKE '%summons%'
        OR "Last outcome category" ILIKE '%court%'
      THEN 1 ELSE 0
    END
  ) AS has_outcome,

  ROUND(
    100.0 * SUM(
      CASE
        WHEN "Last outcome category" ILIKE '%charged%'
          OR "Last outcome category" ILIKE '%caution%'
          OR "Last outcome category" ILIKE '%penalty%'
          OR "Last outcome category" ILIKE '%warning%'
          OR "Last outcome category" ILIKE '%summons%'
          OR "Last outcome category" ILIKE '%court%'
        THEN 1 ELSE 0
      END
    ) / COUNT(*),
    2
  ) AS outcome_rate

FROM crimes_only
WHERE "LSOA name" IS NOT NULL
  AND "Crime type" IS NOT NULL

GROUP BY CUBE ("LSOA name", "Crime type")
HAVING COUNT(*) >= 200

ORDER BY
  CASE WHEN lsoa_name IS NULL THEN 1 ELSE 0 END,
  CASE WHEN crime_type IS NULL THEN 1 ELSE 0 END,
  outcome_rate DESC,
  total_crimes DESC;

"""
    },

    "q5_trend_moving_avg": {
        "desc": "Monthly trend by crime type + 3-month moving average (window PARTITION)",
        "sql": r"""
WITH monthly AS (
  SELECT
    year_partition,
    month_partition,
    "Crime type" AS crime_type,
    COUNT(*) AS crimes
  FROM crimes_only
  GROUP BY year_partition, month_partition, crime_type
  HAVING COUNT(*) >= 50
),
trend AS (
  SELECT
    *,
    AVG(crimes) OVER (
      PARTITION BY crime_type
      ORDER BY year_partition, month_partition
      ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS moving_avg_3m
  FROM monthly
)
SELECT *
FROM trend
ORDER BY crime_type, year_partition, month_partition;
"""
    },

    "q6_load_vs_outcome_corr": {
        "desc": "Does higher crime load correlate with lower outcome rate? (CORR + NTILE)",
        "sql": r"""WITH per_area AS (
  SELECT
    "LSOA name" AS lsoa_name,
    COUNT(*) AS crimes,
    SUM(
      CASE
          WHEN "Last outcome category" ILIKE '%charged%'
          OR "Last outcome category" ILIKE '%caution%'
          OR "Last outcome category" ILIKE '%penalty%'
          OR "Last outcome category" ILIKE '%warning%'
          OR "Last outcome category" ILIKE '%summons%'
          OR "Last outcome category" ILIKE '%court%'
        THEN 1 ELSE 0
      END
    ) AS solved,
    1.0 * SUM(
      CASE
          WHEN "Last outcome category" ILIKE '%charged%'
          OR "Last outcome category" ILIKE '%caution%'
          OR "Last outcome category" ILIKE '%penalty%'
          OR "Last outcome category" ILIKE '%warning%'
          OR "Last outcome category" ILIKE '%summons%'
          OR "Last outcome category" ILIKE '%court%'
        THEN 1 ELSE 0
      END
    ) / COUNT(*) AS outcome_rate
  FROM crimes_only
  WHERE "LSOA name" IS NOT NULL
  GROUP BY "LSOA name"
  HAVING COUNT(*) >= 200
),
with_quintile AS (
  SELECT
    *,
    NTILE(5) OVER (ORDER BY crimes) AS volume_quintile
  FROM per_area
),
quintile_stats AS (
  SELECT
    volume_quintile,
    COUNT(*) AS areas_in_quintile,
    AVG(crimes) AS avg_crimes_in_quintile,
    AVG(outcome_rate) AS avg_rate_in_quintile,
    MIN(outcome_rate) AS min_rate_in_quintile,
    MAX(outcome_rate) AS max_rate_in_quintile,
    CORR(crimes, outcome_rate) AS corr_within_quintile
  FROM with_quintile
  GROUP BY volume_quintile
),
global_stats AS (
  SELECT
    AVG(outcome_rate) AS global_avg_rate,
    STDDEV_SAMP(outcome_rate) AS global_std_rate,
    CORR(crimes, outcome_rate) AS corr_all_areas
  FROM per_area
)
SELECT
  w.lsoa_name,
  w.crimes,
  ROUND(100.0 * w.outcome_rate, 2) AS outcome_rate_pct,
  w.volume_quintile,

  ROUND(q.corr_within_quintile, 4) AS corr_within_quintile,
  ROUND(g.corr_all_areas, 4) AS corr_all_areas,

  q.areas_in_quintile,
  ROUND(q.avg_crimes_in_quintile, 1) AS avg_crimes_in_quintile,
  ROUND(100.0 * q.avg_rate_in_quintile, 2) AS avg_rate_in_quintile_pct,
  ROUND(100.0 * q.min_rate_in_quintile, 2) AS min_rate_in_quintile_pct,
  ROUND(100.0 * q.max_rate_in_quintile, 2) AS max_rate_in_quintile_pct,

  CASE
    WHEN g.global_std_rate IS NULL OR g.global_std_rate = 0 THEN NULL
    ELSE ROUND((w.outcome_rate - g.global_avg_rate) / g.global_std_rate, 3)
  END AS rate_zscore

FROM with_quintile w
JOIN quintile_stats q USING (volume_quintile)
CROSS JOIN global_stats g
ORDER BY w.crimes DESC;

"""
    },
}

# =========================
# 2) RUN QUERIES -> create DuckDB (lake) summary tables
# =========================
for name, item in queries.items():
    con.execute(f"CREATE OR REPLACE TABLE {name} AS {item['sql']}")
    rows = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    print(f"[DuckDB] Built {name}: {rows} rows")
# =========================
# 3) COPY TO SQLITE (GOLD) + representative samples + catalog
# =========================
con.execute("""
CREATE TABLE IF NOT EXISTS gold.table_catalog (
  table_name TEXT,
  rows_count INTEGER,
  cols_count INTEGER,
  description TEXT
);
""")
con.execute("DELETE FROM gold.table_catalog;")

for name, item in queries.items():
    # full summary into SQLite
    con.execute(f"CREATE OR REPLACE TABLE gold.{name} AS SELECT * FROM {name};")
    insert_catalog_sqlite(f"gold.{name}", item["desc"])

    # create sample ONLY if the full table is bigger than SAMPLE_ROWS
    rows_full = con.execute(f"SELECT COUNT(*) FROM {name};").fetchone()[0]

    if rows_full > SAMPLE_ROWS:
        if name == "q1_area_pareto":
            con.execute(
                f"CREATE OR REPLACE TABLE gold.{name}_sample AS "
                f"SELECT lsoa_name, crimes, pct_of_total "
                f"FROM {name} ORDER BY random() LIMIT {SAMPLE_ROWS};"
            )
        else:
            con.execute(
                f"CREATE OR REPLACE TABLE gold.{name}_sample AS "
                f"SELECT * FROM {name} ORDER BY random() LIMIT {SAMPLE_ROWS};"
            )

        insert_catalog_sqlite(
            f"gold.{name}_sample",
            f"Representative sample (~{SAMPLE_ROWS}) from {name}"
        )



# =========================
# 4) PRINT: catalog (tables + rows/cols + description) for submission
# =========================
print("\n===== GOLD TABLES CATALOG (for submission) =====")
catalog_df = con.execute("""
SELECT table_name, rows_count, cols_count, description
FROM gold.table_catalog
ORDER BY table_name;
""").fetchdf()
print(catalog_df.to_string(index=False))

print("\n===== SQLITE TABLE NAMES (raw) =====")
tables_df = con.execute("""
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_catalog = 'gold'
  AND table_schema = 'main'
ORDER BY table_name;
""").fetchdf()
print(tables_df.to_string(index=False))



# =========================
# 5) CHECKPOINT + CLOSE
# =========================
con.execute("CHECKPOINT;")
con.close()
print("\nDone.")


