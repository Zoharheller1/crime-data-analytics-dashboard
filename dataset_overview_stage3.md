# Crime dataset – basic overview

- **DuckLake file**: `my_ducklake.ducklake`
- **Logical table**: `crimes_sample`
- **Total rows**: 339131
- **Number of columns**: 29
- **Number of distinct source CSV files**: 4454

- **Covered years (from filename)**: 2021 – 2024
- **Covered months (1–12, from filename)**: 1 – 12

## Dataset link

https://www.kaggle.com/datasets/mexwell/uk-police-data/data

Dataset size 7.63GB 
## Dataset description

This data lake contains UK police crime data, police outcomes and stop-and-search records at street level. The files were downloaded from the official UK police open data portal and combined into a single DuckLake using DuckDB.

Each row typically represents either a recorded crime incident, a reported outcome for a crime, or a stop-and-search event. The source CSV file name is kept in the `filename` column.

## SQL queries used (basic examples)

All analysis in this document was performed using DuckDB SQL only. Examples:

```sql
-- total number of rows
SELECT COUNT(*) FROM crimes_sample;

-- number of columns
SELECT COUNT(*) FROM pragma_table_info('crimes_sample');

-- number of source files
SELECT COUNT(DISTINCT filename) FROM crimes_sample;

-- null count for a specific column, e.g. "Crime ID"
SELECT COUNT(*) - COUNT("Crime ID") AS null_count
FROM crimes_sample;

-- rows per year (using year_partition)
SELECT year_partition, COUNT(*) AS row_count FROM crimes_sample GROUP BY year_partition;
```

## Example source files

First 20 distinct `filename` values found in the lake:

- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-avon-and-somerset-outcomes.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-avon-and-somerset-stop-and-search.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-avon-and-somerset-street.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-bedfordshire-outcomes.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-bedfordshire-stop-and-search.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-bedfordshire-street.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-btp-stop-and-search.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-btp-street.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cambridgeshire-outcomes.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cambridgeshire-stop-and-search.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cambridgeshire-street.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cheshire-outcomes.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cheshire-stop-and-search.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cheshire-street.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-city-of-london-street.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cleveland-outcomes.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cleveland-stop-and-search.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cleveland-street.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cumbria-outcomes.csv`
- `C:\Users\zohaa\Downloads\big data project\2021-06\2021-06-cumbria-stop-and-search.csv`

## Rows per year (year_partition)

| Year | Row count |
|------|-----------|
| 2021 | 61729 |
| 2022 | 115925 |
| 2023 | 119493 |
| 2024 | 41984 |

## Top 10 crime types (by row count)

| Crime type | Row count |
|------------|-----------|
| (NULL) | 155189 |
| Violence and sexual offences | 63817 |
| Anti-social behaviour | 30453 |
| Public order | 14990 |
| Criminal damage and arson | 14568 |
| Other theft | 14019 |
| Vehicle crime | 10795 |
| Shoplifting | 10441 |
| Burglary | 7657 |
| Drugs | 4979 |

## Top 10 outcome types (by row count)

| Outcome type | Row count |
|--------------|-----------|
| (NULL) | 198648 |
| Investigation complete; no suspect identified | 65818 |
| Unable to prosecute suspect | 52982 |
| Suspect charged | 10928 |
| Local resolution | 3910 |
| Action to be taken by another organisation | 1897 |
| Offender given a caution | 1602 |
| Further investigation is not in the public interest | 1322 |
| Further action is not in the public interest | 833 |
| Formal action is not in the public interest | 809 |

## Columns and basic statistics

The following table shows all columns in the logical table, their DuckDB data type, and how many NULL values each column contains in the full data lake.

| Column | Type | Null values |
|--------|------|-------------|
| Crime ID | VARCHAR | 47079 |
| Month | VARCHAR | 14706 |
| Reported by | VARCHAR | 14706 |
| Falls within | VARCHAR | 14706 |
| Longitude | DOUBLE | 7843 |
| Latitude | DOUBLE | 7843 |
| Location | VARCHAR | 14706 |
| LSOA code | VARCHAR | 23986 |
| LSOA name | VARCHAR | 23986 |
| Outcome type | VARCHAR | 198648 |
| Type | VARCHAR | 324425 |
| Date | TIMESTAMP WITH TIME ZONE | 324425 |
| Part of a policing operation | BOOLEAN | 330132 |
| Policing operation | VARCHAR | 339131 |
| Gender | VARCHAR | 325022 |
| Age range | VARCHAR | 326404 |
| Self-defined ethnicity | VARCHAR | 325373 |
| Officer-defined ethnicity | VARCHAR | 325519 |
| Legislation | VARCHAR | 324771 |
| Object of search | VARCHAR | 325325 |
| Outcome | VARCHAR | 324767 |
| Outcome linked to object of search | BOOLEAN | 333766 |
| Removal of more than just outer clothing | BOOLEAN | 331355 |
| Crime type | VARCHAR | 155189 |
| Last outcome category | VARCHAR | 189841 |
| Context | VARCHAR | 339131 |
| filename | VARCHAR | 0 |
| year_partition | INTEGER | 0 |
| month_partition | INTEGER | 0 |

for each column (what it means, typical value ranges, etc.).