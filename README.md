# 📊 Crime Data Analytics Dashboard

A Big Data analytics project for exploring, transforming, and visualizing large-scale crime data.

The project processes crime records stored in DuckLake, builds a curated GOLD analytics layer, and presents the results through an interactive Streamlit dashboard.

The goal of the project is to transform raw crime data into meaningful analytical insights using SQL, Python, data aggregation, and interactive visualization.

---

## 🚀 Project Overview

The project follows a simple analytics pipeline:

```text
Raw Crime Data
      ↓
DuckLake Storage
      ↓
Data Validation & Exploration
      ↓
Analytical SQL Queries
      ↓
GOLD Analytics Layer
      ↓
SQLite Database
      ↓
Interactive Streamlit Dashboard

The system separates the raw data processing stage from the visualization layer.

The dashboard does not query the raw DuckLake data directly. Instead, it reads pre-aggregated analytical tables from the GOLD SQLite database, making the dashboard faster, reproducible, and easier to maintain.

🧠 Main Features
Large-scale crime data processing
SQL-based analytical queries
Crime and outcome data analysis
Data validation and random record inspection
Pre-aggregated GOLD analytics layer
Pareto analysis
Outlier detection
Rankings and comparisons
Time-based trend analysis
Correlation analysis
Interactive dashboard
KPI presentation
Dynamic visualizations
Styled data previews
User feedback form stored in SQLite
🛠️ Tech Stack
Python
SQL
DuckDB
DuckLake
SQLite
Streamlit
Pandas
Data Visualization
Big Data Analytics
📂 Project Structure
crime-data-analytics-dashboard/
│
├── app.py
├── build_lake.py
├── create_gold.py
├── check_gold.py
├── part4_analysis.py
├── stage3_basic_info.py
├── dataset_overview_stage3.md
├── gold.db
├── requirements.txt
├── HOW_TO_RUN.txt
├── README.md
└── .gitignore
🔍 Data Exploration

The project includes scripts for inspecting and validating the crime dataset before performing analytical processing.

part4_analysis.py

Connects to the DuckLake database and retrieves random examples of valid crime records.

Crime information is joined with outcome data in order to:

Validate the structure of the data
Verify that relevant fields contain usable information
Inspect relationships between crimes and outcomes
Prepare the dataset for later visualizations
🏗️ GOLD Analytics Layer
create_gold.py

Builds the analytical GOLD database from the DuckLake dataset.

The script executes multiple analytical SQL queries and generates summarized tables designed specifically for visualization and reporting.

The generated analytics include:

Pareto analysis
Outlier analysis
Rankings
Trends
Correlations
Aggregated crime statistics
Sampled analytical datasets

The results are stored in:

gold.db

The script also creates metadata describing the generated tables, including their structure, row counts, columns, and analytical purpose.

This makes the analytical layer easier to validate and reproduce.

📊 Interactive Dashboard
app.py

The dashboard is built using Streamlit.

It reads only the pre-aggregated tables stored in gold.db, instead of querying the raw DuckLake dataset directly.

The dashboard provides:

Interactive crime analytics
KPI cards
Analytical tables
Multiple 2D visualizations
Trend analysis
Rankings
Data previews
User feedback collection

The feedback submitted through the dashboard is stored directly in SQLite.

🗄️ Data Architecture

The project separates data processing into two main layers.

DuckLake Layer

Stores the original crime dataset and supports analytical SQL processing over large amounts of data.

GOLD Layer

Contains pre-computed analytical tables optimized for visualization.

This approach reduces repeated computation and allows the dashboard to operate independently from the original DuckLake database.

⚙️ Running the Project

Install the required dependencies:

pip install -r requirements.txt

Then run the Streamlit dashboard:

streamlit run app.py

For additional setup instructions, see:

HOW_TO_RUN.txt
🧪 Generating the GOLD Database

The project can generate the GOLD analytics database from a DuckLake dataset.

If using the sample DuckLake database, update the relevant configuration in create_gold.py so that the script reads from the sample data source and sample crime table.

The generated output is:

gold.db

which is then used by the Streamlit dashboard.

📈 Analytical Workflow

The project demonstrates an end-to-end Big Data analytics workflow:

Load and store crime data
Explore and validate the dataset
Execute analytical SQL queries
Aggregate and transform the data
Build a reusable GOLD analytics layer
Store analytical results in SQLite
Visualize insights using Streamlit
🎯 Project Goals

The project was designed to demonstrate practical experience with:

Big Data processing
SQL analytics
Data engineering workflows
Analytical database design
Data aggregation
Data visualization
Dashboard development
Python-based data applications
👥 Contributors

Developed collaboratively by:

Zohar Heller
Diana Korsunsky

as part of an academic Big Data project.

📫 Contact

Zohar Heller
Diana Korsunsky 

LinkedIn: linkedin.com/in/zohar-heller-4b24292b2

Email: zohaar010101@gmail.com
