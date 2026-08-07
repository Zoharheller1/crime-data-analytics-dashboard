import duckdb

con = duckdb.connect()
con.execute("INSTALL ducklake;")
con.execute("LOAD ducklake;")
con.execute("ATTACH 'ducklake:full_data.ducklake' AS lake;")
con.execute("USE lake;")

query = """
WITH crimes_only AS (
    SELECT
        "Crime ID"      AS crime_id,
        "Crime type"    AS crime_type,
        "LSOA name"     AS lsoa_name,
        "Reported by"   AS reported_by,
        year_partition,
        month_partition
    FROM crimes
    WHERE "Crime ID" IS NOT NULL
      AND "Crime type" IS NOT NULL
      AND "LSOA name" IS NOT NULL
),
outcomes_only AS (
    SELECT
        "Crime ID"               AS crime_id,
        "Outcome type"           AS outcome_type,
        "Last outcome category"  AS last_outcome_category
    FROM crimes
    WHERE "Crime ID" IS NOT NULL
      AND "Outcome type" IS NOT NULL
)
SELECT
    c.crime_id,
    c.crime_type,
    c.lsoa_name,
    c.reported_by,
    o.outcome_type,
    o.last_outcome_category,
    c.year_partition,
    c.month_partition
FROM crimes_only c
JOIN outcomes_only o USING (crime_id)
ORDER BY  RANDOM() LIMIT 5;
"""

df = con.execute(query).fetchdf()
print(df)
df.to_csv("example_rows_stage4.csv", index=False)
print("Wrote example_rows_stage4.csv")
