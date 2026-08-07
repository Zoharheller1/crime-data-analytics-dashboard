Big Data Project – Parts 4 & 5 



Students:

Zohar Heller – 208087965

Diana Korsunsky – 315075234

# NOTE:
# If the evaluator wants to generate the GOLD database from the SAMPLE DuckLake
# submitted in Part B, they should apply the following changes:
#
# Line 6:
#     DUCKLAKE_FILE = "my_ducklake.ducklake"
#
# Line 31:
#     Change:
#         FROM crimes
#     To:
#         FROM crimes_sample


Submitted Files

HOW_TO_RUN.txt

part4.py- python 

This code connects to the DuckLake database and retrieves 5 random example rows of valid crime records by joining crime details with their outcomes.

The purpose is to inspect and validate the data structure and ensure the data is suitable for building graphs and visualizations later in the project.

create the gold.py- 

This script builds a GOLD SQLite database from a large DuckLake dataset by running multiple analytical SQL queries on crime data.

It creates summarized and sampled tables (Pareto analysis, outliers, rankings, trends, correlations) that are ready for visualization and submission.

Finally, it documents all generated tables in a catalog (rows, columns, descriptions) to ensure clarity, reproducibility, and validation of the results.


gold.db

example_rows_stage4- the data for the graph of part 4

requirements.txt

app.py -
This Streamlit app loads only the pre-aggregated GOLD tables from gold.db (SQLite) and presents them as an interactive dashboard with styled table previews, KPIs, and multiple 2D visualizations.

It also includes a user feedback form stored back into SQLite, ensuring the dashboard is fully reproducible without any DuckDB access.

information about parts 4 and 5 .docs- 

all the required info
