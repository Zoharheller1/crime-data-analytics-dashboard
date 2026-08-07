"""
Stage C – Basic information about the data lake.

This script connects to an existing DuckLake (full or sample),
runs only SQL queries (no pandas logic), and writes a Markdown
file with basic information about the dataset.

Requirements:
    pip install duckdb

Usage:
    - By default the script works on the FULL lake.
    - To run on the SAMPLE lake (for the grader), change USE_SAMPLE = True.
"""

import duckdb
from pathlib import Path

# ========= CONFIGURATION =========

# DuckLake files created in the previous step
FULL_DUCKLAKE_FILE = "full_data.ducklake"      # big, not submitted
SAMPLE_DUCKLAKE_FILE = "my_ducklake.ducklake"  # small sample, submitted

# Logical table names inside each lake
FULL_TABLE_NAME = "crimes"          # created in build_full_lake()
SAMPLE_TABLE_NAME = "crimes_sample" # created in build_sample_lake()

# Choose which lake to analyze:
#   False -> run on full_data.ducklake (for your own analysis)
#   True  -> run on my_ducklake.ducklake (for the grader)
USE_SAMPLE = True

# Output Markdown file
MARKDOWN_OUTPUT = "dataset_overview_stage3.md"


# ========= DUCKDB / DUCKLAKE HELPERS =========

def connect_ducklake(ducklake_filename: str, db_alias: str = "lake") -> duckdb.DuckDBPyConnection:
    """
    Connect to DuckDB and attach a DuckLake database.

    Parameters
    ----------
    ducklake_filename : str
        DuckLake file name, e.g. 'full_data.ducklake'.
    db_alias : str
        Alias used inside DuckDB (default: 'lake').

    Returns
    -------
    duckdb.DuckDBPyConnection
        Active connection with the DuckLake attached and in USE.
    """
    con = duckdb.connect()  # in-memory connection

    # Install & load DuckLake extension
    con.execute("INSTALL ducklake;")
    con.execute("LOAD ducklake;")

    # Attach the DuckLake file
    con.execute(f"ATTACH 'ducklake:{ducklake_filename}' AS {db_alias};")
    con.execute(f"USE {db_alias};")

    return con


def describe_table(con: duckdb.DuckDBPyConnection, table_name: str):
    """
    Return DuckDB DESCRIBE output as a DataFrame.
    (Only uses SQL DESCRIBE; no pandas logic in the queries themselves.)
    """
    return con.execute(f"DESCRIBE {table_name};").fetchdf()

def get_column_count(con: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """
    Return the number of columns in the table (pure SQL).
    """
    return con.execute(
        f"SELECT COUNT(*) FROM pragma_table_info('{table_name}');"
    ).fetchone()[0]



# ========= SQL QUERIES FOR BASIC INFO =========

def get_total_rows(con: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """
    Return total number of rows in the table (pure SQL).
    """
    return con.execute(f"SELECT COUNT(*) FROM {table_name};").fetchone()[0]


def get_null_counts(con: duckdb.DuckDBPyConnection, table_name: str, column_names) -> dict:
    """
    For each column, count how many NULL values it has (using SQL only).

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
    table_name : str
    column_names : list[str]

    Returns
    -------
    dict[str, int]
        Mapping column -> number of NULL values.
    """
    null_counts = {}

    for col in column_names:
        # Column names may contain spaces, so we always quote them
        sql = f'SELECT COUNT(*) - COUNT("{col}") AS nulls FROM {table_name};'
        nulls = con.execute(sql).fetchone()[0]
        null_counts[col] = nulls

    return null_counts


def get_file_stats(con: duckdb.DuckDBPyConnection, table_name: str):
    """
    Use the 'filename' column to understand how many original CSV files
    were loaded into the lake and show a few examples.

    Returns
    -------
    num_files : int
    sample_files : list[str]
    """
    num_files = con.execute(
        f"SELECT COUNT(DISTINCT filename) FROM {table_name};"
    ).fetchone()[0]

    # Show up to 20 file names as examples
    df_files = con.execute(
        f"""
        SELECT DISTINCT filename
        FROM {table_name}
        ORDER BY filename
        LIMIT 20;
        """
    ).fetchdf()

    sample_files = df_files["filename"].tolist()
    return num_files, sample_files


def get_date_range(con: duckdb.DuckDBPyConnection, table_name: str, column_names):
    """
    If year_partition / month_partition columns exist, compute basic range.
    Otherwise return (None, None, None, None).
    """
    has_year = "year_partition" in column_names
    has_month = "month_partition" in column_names

    year_min = year_max = None
    month_min = month_max = None

    if has_year:
        year_min, year_max = con.execute(
            f"SELECT MIN(year_partition), MAX(year_partition) FROM {table_name};"
        ).fetchone()

    if has_month:
        month_min, month_max = con.execute(
            f"SELECT MIN(month_partition), MAX(month_partition) FROM {table_name};"
        ).fetchone()

    return (year_min, year_max, month_min, month_max)


def get_rows_per_year(con: duckdb.DuckDBPyConnection, table_name: str, column_names):
    """
    Return number of rows per year_partition, if the column exists.
    Otherwise return None.
    """
    if "year_partition" not in column_names:
        return None

    df = con.execute(
        f"""
        SELECT year_partition AS year,
               COUNT(*)        AS row_count
        FROM {table_name}
        GROUP BY year_partition
        ORDER BY year_partition;
        """
    ).fetchdf()

    return df


def get_top_value_counts(con: duckdb.DuckDBPyConnection, table_name: str, column: str, limit: int = 10):
    """
    Return top N values for a given column, ordered by row count (SQL only).

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
    table_name : str
    column : str
        Column name as it appears in the table (may contain spaces).
    limit : int
        Max number of distinct values to return.

    Returns
    -------
    DataFrame with columns: value, row_count
    """
    # Quote the column name because it may contain spaces
    sql = f'''
        SELECT "{column}" AS value,
               COUNT(*)   AS row_count
        FROM {table_name}
        GROUP BY "{column}"
        ORDER BY row_count DESC
        LIMIT {limit};
    '''
    return con.execute(sql).fetchdf()


# ========= MARKDOWN GENERATION =========

def build_markdown(
    ducklake_file: str,
    table_name: str,
    total_rows: int,
    num_files: int,
    num_columns: int,   # <-- add this
    sample_files,
    cols_df,
    null_counts: dict,
    date_range,
    rows_per_year_df,
    top_crime_types_df,
    top_outcome_types_df,
) -> str:

    """
    Build the Markdown content summarizing the dataset.

    All numeric results come from SQL queries executed in DuckDB.
    """
    year_min, year_max, month_min, month_max = date_range

    lines = []

    # Title and basic info
    lines.append("# Crime dataset – basic overview")
    lines.append("")
    lines.append(f"- **DuckLake file**: `{ducklake_file}`")
    lines.append(f"- **Logical table**: `{table_name}`")
    lines.append(f"- **Total rows**: {total_rows}")
    lines.append(f"- **Number of columns**: {num_columns}")
    lines.append(f"- **Number of distinct source CSV files**: {num_files}")

    lines.append("")

    if year_min is not None:
        lines.append(f"- **Covered years (from filename)**: {year_min} – {year_max}")
    if month_min is not None:
        lines.append(f"- **Covered months (1–12, from filename)**: {month_min} – {month_max}")
    lines.append("")

    lines.append("## Dataset link")
    lines.append("")
    lines.append("https://www.kaggle.com/datasets/mexwell/uk-police-data/data")
    lines.append("")

    lines.append("Dataset size 7.63GB ")

    # Short textual description
    lines.append("## Dataset description")
    lines.append("")
    lines.append(
        "This data lake contains UK police crime data, police outcomes and "
        "stop-and-search records at street level. The files were downloaded "
        "from the official UK police open data portal and combined into a "
        "single DuckLake using DuckDB."
    )
    lines.append("")
    lines.append(
        "Each row typically represents either a recorded crime incident, a "
        "reported outcome for a crime, or a stop-and-search event. The "
        "source CSV file name is kept in the `filename` column."
    )
    lines.append("")

    # SQL section
    lines.append("## SQL queries used (basic examples)")
    lines.append("")
    lines.append("All analysis in this document was performed using DuckDB SQL only. Examples:")
    lines.append("")
    lines.append("```sql")
    lines.append("-- total number of rows")
    lines.append(f"SELECT COUNT(*) FROM {table_name};")
    lines.append("")
    lines.append("-- number of columns")
    lines.append(f"SELECT COUNT(*) FROM pragma_table_info('{table_name}');")
    lines.append("")

    lines.append("-- number of source files")
    lines.append(f"SELECT COUNT(DISTINCT filename) FROM {table_name};")
    lines.append("")
    lines.append("-- null count for a specific column, e.g. \"Crime ID\"")
    lines.append(f'SELECT COUNT(*) - COUNT("Crime ID") AS null_count')
    lines.append(f"FROM {table_name};")
    lines.append("")
    lines.append("-- rows per year (using year_partition)")
    lines.append(
        f"SELECT year_partition, COUNT(*) AS row_count "
        f"FROM {table_name} GROUP BY year_partition;"
    )
    lines.append("```")
    lines.append("")

    # Example filenames
    lines.append("## Example source files")
    lines.append("")
    lines.append("First 20 distinct `filename` values found in the lake:")
    lines.append("")
    for fn in sample_files:
        lines.append(f"- `{fn}`")
    lines.append("")

    # Rows per year
    if rows_per_year_df is not None and not rows_per_year_df.empty:
        lines.append("## Rows per year (year_partition)")
        lines.append("")
        lines.append("| Year | Row count |")
        lines.append("|------|-----------|")
        for _, row in rows_per_year_df.iterrows():
            lines.append(f"| {row['year']} | {row['row_count']} |")
        lines.append("")

    # Top crime types
    if top_crime_types_df is not None and not top_crime_types_df.empty:
        lines.append("## Top 10 crime types (by row count)")
        lines.append("")
        lines.append("| Crime type | Row count |")
        lines.append("|------------|-----------|")
        for _, row in top_crime_types_df.iterrows():
            value = row["value"] if row["value"] is not None else "(NULL)"
            lines.append(f"| {value} | {row['row_count']} |")
        lines.append("")

    # Top outcome types
    if top_outcome_types_df is not None and not top_outcome_types_df.empty:
        lines.append("## Top 10 outcome types (by row count)")
        lines.append("")
        lines.append("| Outcome type | Row count |")
        lines.append("|--------------|-----------|")
        for _, row in top_outcome_types_df.iterrows():
            value = row["value"] if row["value"] is not None else "(NULL)"
            lines.append(f"| {value} | {row['row_count']} |")
        lines.append("")

    # Column-level info
    lines.append("## Columns and basic statistics")
    lines.append("")
    lines.append(
        "The following table shows all columns in the logical table, their "
        "DuckDB data type, and how many NULL values each column contains "
        "in the full data lake."
    )
    lines.append("")
    lines.append("| Column | Type | Null values |")
    lines.append("|--------|------|-------------|")

    for _, row in cols_df.iterrows():
        col_name = row["column_name"]
        col_type = row["column_type"]
        nulls = null_counts.get(col_name, 0)
        lines.append(f"| {col_name} | {col_type} | {nulls} |")

    lines.append("")
    lines.append(
        "for each column (what it means, typical value ranges, etc.)."
    )

    return "\n".join(lines)


# ========= MAIN =========

def main():
    # Choose which lake and table to use
    if USE_SAMPLE:
        ducklake_file = SAMPLE_DUCKLAKE_FILE
        table_name = SAMPLE_TABLE_NAME
    else:
        ducklake_file = FULL_DUCKLAKE_FILE
        table_name = FULL_TABLE_NAME

    print(f"Connecting to DuckLake file: {ducklake_file}")
    print(f"Using logical table: {table_name}")

    con = connect_ducklake(ducklake_file, db_alias="lake")

    # 1) Basic schema information
    cols_df = describe_table(con, table_name)
    column_names = cols_df["column_name"].tolist()

    num_columns = get_column_count(con, table_name)
    print(f"Number of columns: {num_columns}")

    # 2) Total number of rows (SQL)
    total_rows = get_total_rows(con, table_name)
    print(f"Total rows: {total_rows}")

    # 3) NULL counts per column (SQL)
    null_counts = get_null_counts(con, table_name, column_names)

    # 4) Source file statistics (based on 'filename' column)
    num_files, sample_files = get_file_stats(con, table_name)
    print(f"Number of distinct source files (filename): {num_files}")

    # 5) Date range based on partition columns (if present)
    date_range = get_date_range(con, table_name, column_names)

    # 6) Rows per year (if partition column exists)
    rows_per_year_df = get_rows_per_year(con, table_name, column_names)

    # 7) Top 10 crime types (if column exists)
    top_crime_types_df = None
    if "Crime type" in column_names:
        top_crime_types_df = get_top_value_counts(
            con, table_name, column="Crime type", limit=10
        )

    # 8) Top 10 outcome types (if column exists)
    top_outcome_types_df = None
    if "Outcome type" in column_names:
        top_outcome_types_df = get_top_value_counts(
            con, table_name, column="Outcome type", limit=10
        )

    # 9) Build Markdown content
    markdown_text = build_markdown(
        ducklake_file=ducklake_file,
        table_name=table_name,
        total_rows=total_rows,
        num_files=num_files,
        num_columns=num_columns,
        sample_files=sample_files,
        cols_df=cols_df,
        null_counts=null_counts,
        date_range=date_range,
        rows_per_year_df=rows_per_year_df,
        top_crime_types_df=top_crime_types_df,
        top_outcome_types_df=top_outcome_types_df,
    )

    # 10) Write Markdown file
    output_path = Path(MARKDOWN_OUTPUT)
    output_path.write_text(markdown_text, encoding="utf-8")

    print(f"\nMarkdown written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
