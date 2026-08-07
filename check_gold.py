import duckdb


con = duckdb.connect()
con.execute("INSTALL ducklake;")
con.execute("LOAD ducklake;")
con.execute("ATTACH 'ducklake:full_data.ducklake' AS lake;")
con.execute("USE lake;")

df = con.execute("""
SELECT
  "Last outcome category",
  COUNT(*) AS cnt
FROM crimes_only
GROUP BY "Last outcome category"
ORDER BY cnt DESC;
""").df()

print(df)
