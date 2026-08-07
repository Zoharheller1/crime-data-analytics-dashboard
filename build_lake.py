"""
Build DuckLake data lake for the crime dataset.

Requirements:
    pip install duckdb numpy pandas

This script:
    1. Builds a FULL DuckLake on all the data (build_full_lake).
       -> This is for local work only, NOT for submission.
    2. Builds a SAMPLED DuckLake (build_sample_lake).
       -> This is the one you should zip and submit:
          - my_ducklake.ducklake
          - my_ducklake.ducklake.files/

All commands are executed from Python, as required by the assignment.
"""

import duckdb
from pathlib import Path

# ======== CONFIGURATION ========

# Root folder that contains subfolders like: 2024-05, 2024-04, 2023-12, ...
# Inside each such folder there are ~118 CSV files.
DATA_ROOT = Path(r"C:\Users\zohaa\Downloads\big data project")

# Names of the DuckLake files that will be created
FULL_DUCKLAKE_FILE = "full_data.ducklake"      # full lake (not submitted)
SAMPLE_DUCKLAKE_FILE = "my_ducklake.ducklake"  # sampled lake (for submission)

# File extension used by the dataset (CSV)
FILE_EXTENSION = "*.csv"

# Fraction of rows to keep in the sample lake (e.g. 0.01 = 1%)
SAMPLE_FRACTION = 0.01


# ======== HELPER FUNCTIONS ========

def init_ducklake(ducklake_filename: str, db_alias: str) -> duckdb.DuckDBPyConnection:
    """
    Initialize a DuckDB connection and attach a DuckLake database.

    Parameters
    ----------
    ducklake_filename : str
        File name of the DuckLake database (e.g. "my_ducklake.ducklake").
    db_alias : str
        Alias for the attached database (e.g. "full_lake" or "sample_lake").

    Returns
    -------
    duckdb.DuckDBPyConnection
        An active DuckDB connection using the attached DuckLake.
    """
    con = duckdb.connect()  # in-memory connection

    # Install and load the DuckLake extension
    con.execute("INSTALL ducklake;")
    con.execute("LOAD ducklake;")

    # Attach the DuckLake database. If it does not exist, it will be created.
    con.execute(f"ATTACH 'ducklake:{ducklake_filename}' AS {db_alias};")

    # Make the attached DuckLake the active database.
    con.execute(f"USE {db_alias};")

    return con


def load_csv_into_raw(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    temporary: bool = False
) -> None:
    """
    Load all CSV files from all month folders into a single table.

    If temporary=True, the table will be TEMPORARY (not persisted on disk),
    which is useful for the sampled DuckLake.

    The table will also contain a 'filename' column that stores the source file
    path for each row, which we later use to extract year and month.
    Files may have different schemas (street / outcomes / stop-and-search),
    so we use union_by_name = TRUE to align columns by name.
    We also disable strict_mode and enable null_padding to tolerate slightly
    malformed rows.
    """
    # Pattern like:  C:\\...\\big data project\\*\\*.csv
    pattern = str(DATA_ROOT / "*" / FILE_EXTENSION)

    temp_kw = "TEMPORARY" if temporary else ""

    con.execute(
        f"""
        CREATE OR REPLACE {temp_kw} TABLE {table_name} AS
        SELECT *
        FROM read_csv_auto(
            ?,
            HEADER = TRUE,
            FILENAME = TRUE,
            union_by_name = TRUE,
            strict_mode = FALSE,
            null_padding = TRUE
        );
        """,
        [pattern],
    )

    row_count = con.execute(
        f"SELECT COUNT(*) FROM {table_name};"
    ).fetchone()[0]
    print(f"{table_name} ({'TEMP' if temporary else 'PERSISTENT'}): loaded {row_count} rows.")


def create_partitioned_enriched_table(
    con: duckdb.DuckDBPyConnection,
    source_table: str,
    target_table: str,
    where_clause: str = "TRUE"
) -> None:
    """
    Create a partitioned DuckLake table with extra year/month columns,
    and insert data from the source table.

    The filename pattern is expected to contain 'YYYY-MM', e.g.:
        2024-05-west-midlands-street.csv

    We create two integer columns:
        - year_partition
        - month_partition

    The function works in three steps:
        1. CREATE TABLE ... AS <SELECT ...> LIMIT 0      (schema only, no data)
        2. ALTER TABLE ... SET PARTITIONED BY (...)      (define partitioning)
        3. INSERT INTO ... <SELECT ... WHERE where_clause>
           (data is written in partitioned files)
    """
    base_select = f"""
        SELECT
            *,
            CAST(regexp_extract(filename, '([0-9]{{4}})-([0-9]{{2}})', 1) AS INTEGER) AS year_partition,
            CAST(regexp_extract(filename, '([0-9]{{4}})-([0-9]{{2}})', 2) AS INTEGER) AS month_partition
        FROM {source_table}
        WHERE {where_clause}
    """

    # 1) Create an empty table with the correct schema
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {target_table} AS
        {base_select}
        LIMIT 0;
        """
    )

    # 2) Set partitioning keys BEFORE inserting any data
    con.execute(
        f"""
        ALTER TABLE {target_table}
        SET PARTITIONED BY (year_partition, month_partition);
        """
    )
    print(f"{target_table}: partitioning configured (year_partition, month_partition).")

    # 3) Insert data (this will write partitioned Parquet files)
    con.execute(
        f"""
        INSERT INTO {target_table}
        {base_select};
        """
    )

    # Debug: show schema and row count
    print(f"{target_table}: schema")
    print(con.execute(f"DESCRIBE {target_table};").fetchdf())

    row_count = con.execute(
        f"SELECT COUNT(*) FROM {target_table};"
    ).fetchone()[0]
    print(f"{target_table}: inserted {row_count} rows.")


# ======== BUILD FUNCTIONS ========

def build_full_lake() -> None:
    """
    Build a FULL DuckLake over all the data.

    This may be large and is meant for local work only.
    You do NOT submit this DuckLake file.
    """
    con = init_ducklake(FULL_DUCKLAKE_FILE, "full_lake")

    # 1) Load all CSV files into a persistent raw table
    load_csv_into_raw(con, "crimes_raw", temporary=False)

    # 2) Create a partitioned enriched table with ALL rows
    create_partitioned_enriched_table(
        con=con,
        source_table="crimes_raw",
        target_table="crimes",
        where_clause="TRUE"  # no filter -> full data
    )

    # 3) Ensure everything is flushed and consistent
    con.execute("CHECKPOINT;")

    print(f"Full DuckLake created: {FULL_DUCKLAKE_FILE}")


def build_sample_lake() -> None:
    """
    Build a SAMPLED DuckLake for submission.

    This DuckLake will contain only a subset of the rows, but with
    the same columns and partitioning logic.
    """
    con = init_ducklake(SAMPLE_DUCKLAKE_FILE, "sample_lake")

    # 1) Load all CSV files into a TEMPORARY raw table (not persisted)
    load_csv_into_raw(con, "crimes_raw", temporary=True)

    # 2) Create a partitioned enriched table with a random sample of the rows
    create_partitioned_enriched_table(
        con=con,
        source_table="crimes_raw",
        target_table="crimes_sample",
        where_clause=f"random() < {SAMPLE_FRACTION}"
    )

    # 3) Flush everything to disk
    con.execute("CHECKPOINT;")

    print(f"Sample DuckLake created: {SAMPLE_DUCKLAKE_FILE}")
    print("This is the DuckLake that should be zipped and submitted.")


# ======== MAIN ENTRY POINT ========

if __name__ == "__main__":
    # Build the full lake locally (can be commented out if not needed):
    build_full_lake()

    # Build the sampled lake for submission:
    build_sample_lake()
