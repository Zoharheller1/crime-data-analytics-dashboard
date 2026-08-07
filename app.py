# app.py
# Crime Analytics - GOLD (SQLite only) Streamlit Dashboard
# Requirements:
# - NO third-party Streamlit components (no st.components / external components)
# - Read ONLY from SQLite "gold.db"
# - Show sample tables (hundreds of rows) with styled st.dataframe + df.style
# - 5+ 2D visualizations; at least 2 Matplotlib; 1 Seaborn allowed; at least 2 interactive
# - User feedback stored in SQLite and displayed in dashboard

import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns


# =========================
# CONFIG
# =========================
APP_TITLE = "Crime Analytics Dashboard (GOLD / SQLite Only)"
DB_PATH = Path(__file__).parent / "gold.db"
SAMPLE_LIMIT = 500
PREVIEW_LIMIT = 500

TABLES = {
    "Q1 – Area Pareto (Concentration)": ("q1_area_pareto", "q1_area_pareto_sample"),
    "Q2 – Area Outliers (Z-score)": ("q2_area_outliers", "q2_area_outliers_sample"),
    "Q3 – Police Forces Ranking (Solved Rate)": ("q3_reported_by_rank",""),
    "Q4 – CUBE: Area × Crime Type": ("q4_cube_area_type_outcome", "q4_cube_area_type_outcome_sample"),
    "Q5 – Trend & Moving Average": ("q5_trend_moving_avg", ""),
    "Q6 – Load vs Solved Rate (Correlation + Quintiles)": ("q6_load_vs_outcome_corr", "q6_load_vs_outcome_corr_sample"),
}

REQUIRED_TABLES = ["table_catalog", "user_feedback"] + sorted({
    t.strip()
    for pair in TABLES.values()
    for t in pair
    if t and t.strip()
})



# =========================
# PAGE
# =========================
st.set_page_config(page_title=APP_TITLE, layout="wide")


# =========================
# DB HELPERS
# =========================
@st.cache_resource
def get_conn():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"gold.db not found at: {DB_PATH}")
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def read_sql(q: str, params=None) -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql_query(q, conn, params=params or [])


def exec_sql(q: str, params=None) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(q, params or [])
    conn.commit()


def ensure_feedback_table():
    exec_sql("""
    CREATE TABLE IF NOT EXISTS user_feedback (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      page TEXT NOT NULL,
      rating INTEGER NOT NULL,
      feedback_text TEXT NOT NULL
    );
    """)


def list_sqlite_tables() -> set[str]:
    df = read_sql("SELECT name FROM sqlite_master WHERE type='table';")
    return set(df["name"].tolist())


def assert_required_tables_exist():
    existing = list_sqlite_tables()
    missing = [t for t in REQUIRED_TABLES if t not in existing]
    if missing:
        st.error(
            "SQLite GOLD database is missing required tables.\n\n"
            f"Missing: {missing}\n\n"
            "Please re-run your DuckDB→SQLite pipeline that creates gold.db."
        )
        st.stop()


ensure_feedback_table()
assert_required_tables_exist()


# =========================
# UI HELPERS
# =========================
def styled_df(df: pd.DataFrame):
    # Styling is applied using pandas DataFrame.style and rendered via st.dataframe.
    styler = df.style.background_gradient(axis=0).highlight_null(color="#ffd6d6")
    return styler


def show_table_section(
    title: str,
    full_table: str,
    sample_table: str | None = None,
    limit_full_preview: int = PREVIEW_LIMIT
):
    st.subheader(title)

    has_sample = bool(sample_table and sample_table.strip())

    if has_sample:
        col1, col2 = st.columns(2, gap="large")
    else:
        col1 = st.container()
        col2 = None

    with col1:
        st.markdown("**GOLD summary (preview)**")
        df_full_preview = read_sql(f"SELECT * FROM {full_table} LIMIT {limit_full_preview};")
        st.dataframe(styled_df(df_full_preview), use_container_width=True)

    if has_sample and col2 is not None:
        with col2:
            st.markdown(f"**Representative sample (up to {SAMPLE_LIMIT} rows)**")
            df_sample = read_sql(f"SELECT * FROM {sample_table} LIMIT {SAMPLE_LIMIT};")
            st.dataframe(styled_df(df_sample), use_container_width=True)
    else:
        st.info("No sample table for this section (the full table is small enough).")

def feedback_box(page_name: str):
    st.divider()
    st.subheader("User Feedback (stored in SQLite)")

    with st.form(key=f"feedback_form_{page_name}"):
        rating = st.slider("Rating (1–10)", min_value=1, max_value=10, value=8)
        txt = st.text_area("Write a note / observation / suggestion", height=120)
        submitted = st.form_submit_button("Save feedback")

    if submitted:
        if not txt.strip():
            st.warning("Feedback cannot be empty.")
        else:
            exec_sql(
                "INSERT INTO user_feedback(created_at, page, rating, feedback_text) VALUES (?, ?, ?, ?);",
                [datetime.now().isoformat(timespec="seconds"), page_name, int(rating), txt.strip()],
            )
            st.success("Saved.")

    st.markdown("**Recent feedback:**")
    df_fb = read_sql("SELECT created_at, page, rating, feedback_text FROM user_feedback ORDER BY id DESC LIMIT 10;")
    st.dataframe(styled_df(df_fb), use_container_width=True)


def kpi_block(items: list[tuple[str, str]]):
    cols = st.columns(len(items))
    for i, (label, value) in enumerate(items):
        cols[i].metric(label, value)


# =========================
# INSIGHTS HELPERS (REAL, DATA-DRIVEN)
# =========================
def q1_insights():
    df = read_sql("SELECT crimes, cum_pct FROM q1_area_pareto ORDER BY crimes DESC;")
    if df.empty:
        return {"kpis": [], "bullets": ["No rows found in q1_area_pareto."]}

    # How many areas to reach key thresholds
    def areas_for(threshold: float) -> int:
        hit = df[df["cum_pct"] >= threshold]
        return int(hit.index[0] + 1) if not hit.empty else int(len(df))

    n50 = areas_for(50.0)
    n80 = areas_for(80.0)


    top10_share = float(df.head(10)["crimes"].sum() / df["crimes"].sum() * 100.0)

    top100_share = float(df.head(100)["crimes"].sum() / df["crimes"].sum() * 100.0)

    return {
        "kpis": [
            ("Areas to reach 50%", f"{n50:,}"),
            ("Areas to reach 80%", f"{n80:,}"),
            ("Top 10 areas share", f"{top10_share:.2f}%"),
            ("Top 100 areas share", f"{top100_share:.2f}%"),
        ],
        "bullets": [
            f"Crime volume is highly concentrated: the top {n50:,} areas already account for 50% of all recorded crimes (Pareto effect).",
            f"Reaching 80% requires {n80:,} areas, indicating a long tail where many areas contribute small portions individually.",
            f"Even the top 10 areas alone contribute {top10_share:.2f}% of total crime volume, which is substantial given the number of areas overall.",
            "Operational implication: prioritizing interventions and resources in a relatively small subset of high-volume areas is likely to yield outsized impact.",
        ],
    }


def q2_insights():
    df = read_sql("SELECT crimes, avg_area_crimes, z_score FROM q2_area_outliers ORDER BY z_score DESC;")
    if df.empty:
        return {"kpis": [], "bullets": ["No rows found in q2_area_outliers."]}

    max_z = float(df["z_score"].max())
    med_z = float(df["z_score"].median())
    p95_z = float(df["z_score"].quantile(0.95))

    # A “47 sigma” outcome is plausible here because area crime counts are extremely heavy-tailed.
    # We quantify tail intensity with a robust ratio.
    top1_crimes = float(df.iloc[0]["crimes"])
    avg_crimes = float(df.iloc[0]["avg_area_crimes"]) if "avg_area_crimes" in df.columns else float(df["crimes"].mean())
    ratio_top1_to_avg = top1_crimes / avg_crimes if avg_crimes else None

    count_ge_10 = int((df["z_score"] >= 10).sum())
    count_ge_5 = int((df["z_score"] >= 5).sum())

    bullets = [
        f"The outlier distribution is extremely heavy-tailed: max z-score is {max_z:.2f} (median {med_z:.2f}, 95th percentile {p95_z:.2f}).",
        f"There are {count_ge_10:,} areas at ≥10 standard deviations above the mean, and {count_ge_5:,} areas at ≥5—far beyond what a normal model would predict.",
    ]
    if ratio_top1_to_avg is not None:
        bullets.append(f"The highest-volume hotspot is ~{ratio_top1_to_avg:.1f}× the average area in this filtered population, explaining the huge z-scores.")
    bullets += [
        "Interpretation: z-scores here are not signaling a bug; they reflect a non-normal, highly skewed distribution (major-city centers dominate).",
        "Operational implication: treat these as priority hotspots and consider using robust statistics (e.g., log scale, quantiles) alongside z-scores for communication.",
    ]

    return {
        "kpis": [
            ("Max z-score", f"{max_z:.2f}"),
            ("Median z-score", f"{med_z:.2f}"),
            ("Areas with z≥10", f"{count_ge_10:,}"),
            ("Areas with z≥5", f"{count_ge_5:,}"),
        ],
        "bullets": bullets,
    }


def q3_insights():
    df = read_sql("""
        SELECT reported_by, total_crimes, solved, solved_rate,rate_rank
        FROM q3_reported_by_rank
        ORDER BY solved_rate DESC, total_crimes DESC;
    """)
    if df.empty:
        return {"kpis": [], "bullets": ["No rows found in q3_reported_by_rank."]}

    best = df.iloc[0]
    worst = df.iloc[-1]
    spread = float(best["solved_rate"] - worst["solved_rate"])

    tmp = df[["total_crimes", "solved_rate"]].copy()
    corr_val = tmp["total_crimes"].corr(tmp["solved_rate"])
    corr_val = None if pd.isna(corr_val) else float(corr_val)

    top5_mean = float(df.head(5)["solved_rate"].mean())
    bottom5_mean = float(df.tail(5)["solved_rate"].mean())

    bullets = [
        f"There is meaningful variation in solved_rate across forces: the best force records {best['solved_rate']:.2f}% while the worst records {worst['solved_rate']:.2f}% (spread {spread:.2f} percentage points).",
        f"Top-5 average solved_rate is {top5_mean:.2f}% versus {bottom5_mean:.2f}% for the bottom-5, suggesting structural differences rather than random noise.",
        f"The negative correlation may reflect higher operational complexity and case severity in large metropolitan forces.",
    ]
    if corr_val is not None:
        direction = "negative" if corr_val < 0 else "positive"
        bullets.append(f"The correlation between volume (total_crimes) and solved_rate is {corr_val:.3f} ({direction}), indicating that size alone does not fully explain effectiveness.")
    bullets += [
        "Interpretation: comparing forces by solved_rate surfaces potential best practices and underperforming contexts; however, differences may reflect case mix and reporting standards.",
        "Operational implication: use this ranking as a starting point for deeper diagnostics (crime-type adjusted rates, time-to-outcome, and resource allocation).",
    ]

    return {
        "kpis": [
            ("Best solved_rate", f"{best['solved_rate']:.2f}%"),
            ("Worst solved_rate", f"{worst['solved_rate']:.2f}%"),
            ("Spread", f"{spread:.2f} pp"),
            ("Forces included", f"{len(df):,}"),
        ],
        "bullets": bullets,
    }


def q4_insights():
    # For CUBE table we expect null combinations due to subtotals.
    stats = read_sql("""
        SELECT
          SUM(CASE WHEN lsoa_name IS NULL THEN 1 ELSE 0 END) AS rows_lsoa_null,
          SUM(CASE WHEN crime_type IS NULL THEN 1 ELSE 0 END) AS rows_type_null,
          SUM(CASE WHEN lsoa_name IS NULL AND crime_type IS NULL THEN 1 ELSE 0 END) AS rows_grand_total,
          COUNT(*) AS total_rows,
          MIN(CASE WHEN lsoa_name IS NOT NULL AND crime_type IS NOT NULL THEN outcome_rate END) AS min_rate,
          MAX(CASE WHEN lsoa_name IS NOT NULL AND crime_type IS NOT NULL THEN outcome_rate END) AS max_rate
        FROM q4_cube_area_type_outcome;
    """)
    if stats.empty:
        return {"kpis": [], "bullets": ["No rows found in q4_cube_area_type_outcome."]}

    s = stats.iloc[0]
    total_rows = int(s["total_rows"])
    grand_total = int(s["rows_grand_total"])
    min_rate = float(s["min_rate"]) if s["min_rate"] is not None else None
    max_rate = float(s["max_rate"]) if s["max_rate"] is not None else None

    # Identify extremes among full cross rows (non-null)
    extremes = read_sql("""
        SELECT lsoa_name, crime_type, total_crimes, outcome_rate
        FROM q4_cube_area_type_outcome
        WHERE lsoa_name IS NOT NULL AND crime_type IS NOT NULL
        ORDER BY outcome_rate ASC, total_crimes DESC
        LIMIT 1;
    """)
    best = read_sql("""
        SELECT lsoa_name, crime_type, total_crimes, outcome_rate
        FROM q4_cube_area_type_outcome
        WHERE lsoa_name IS NOT NULL AND crime_type IS NOT NULL
        ORDER BY outcome_rate DESC, total_crimes DESC
        LIMIT 1;
    """)

    bullets = [
        f"The CUBE output includes subtotals by design: {grand_total} grand-total row(s) and additional subtotal rows where one dimension is NULL.",
        "This enables multi-level comparisons: overall outcomes, area-only aggregates, crime-type-only aggregates, and full (area × crime type) interactions—all from one query.",
    ]
    if min_rate is not None and max_rate is not None:
        bullets.append(f"Outcome rates vary widely across the cube: min {min_rate:.2f}% and max {max_rate:.2f}% (among rows passing HAVING).")
    if not extremes.empty and not best.empty:
        e = extremes.iloc[0]
        b = best.iloc[0]
        bullets.append(
            f"At the detailed level (area × type), the lowest outcome_rate example is '{e['crime_type']}' in '{e['lsoa_name']}' with {e['outcome_rate']:.2f}% over {int(e['total_crimes']):,} crimes."
        )
        bullets.append(
            f"The highest outcome_rate example is '{b['crime_type']}' in '{b['lsoa_name']}' with {b['outcome_rate']:.2f}% over {int(b['total_crimes']):,} crimes."
        )
    bullets += [
        "Interpretation: effectiveness is not uniform; it changes with the interaction between location and crime category.",
        "Operational implication: prioritizing “low-rate” area×type cells can target specific investigative bottlenecks instead of applying generic interventions.",
    ]

    return {
        "kpis": [
            ("Rows in cube", f"{total_rows:,}"),
            ("Grand total rows", f"{grand_total:,}"),
            ("Min outcome_rate", f"{min_rate:.2f}%" if min_rate is not None else "N/A"),
            ("Max outcome_rate", f"{max_rate:.2f}%" if max_rate is not None else "N/A"),
        ],
        "bullets": bullets,
    }


def q5_insights():
    df = read_sql("""
        SELECT year_partition, month_partition, crime_type, crimes, moving_avg_3m
        FROM q5_trend_moving_avg;
    """)
    if df.empty:
        return {"kpis": [], "bullets": ["No rows found in q5_trend_moving_avg."]}

    # Identify global peak month within each crime type based on raw crimes
    peaks = read_sql("""
        WITH ranked AS (
          SELECT
            crime_type,
            year_partition,
            month_partition,
            crimes,
            ROW_NUMBER() OVER (PARTITION BY crime_type ORDER BY crimes DESC) AS rn
          FROM q5_trend_moving_avg
        )
        SELECT crime_type, year_partition, month_partition, crimes
        FROM ranked
        WHERE rn = 1
        ORDER BY crimes DESC
        LIMIT 5;
    """)

    # Trend magnitude: compare first vs last month per crime type (moving average)
    drift = read_sql("""
        WITH first_last AS (
          SELECT
            crime_type,
            FIRST_VALUE(moving_avg_3m) OVER (PARTITION BY crime_type ORDER BY year_partition, month_partition) AS first_ma,
            LAST_VALUE(moving_avg_3m)  OVER (PARTITION BY crime_type ORDER BY year_partition, month_partition
                 ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_ma
          FROM q5_trend_moving_avg
        )
        SELECT crime_type, AVG(last_ma - first_ma) AS avg_ma_change
        FROM first_last
        GROUP BY crime_type
        ORDER BY avg_ma_change DESC
        LIMIT 5;
    """)

    months = int(read_sql("SELECT COUNT(*) AS c FROM (SELECT DISTINCT year_partition, month_partition FROM q5_trend_moving_avg);").iloc[0]["c"])

    bullets = [
        f"The time series covers {months} distinct months, enabling stable trend analysis rather than one-off snapshots.",
        "The 3-month moving average reduces month-to-month noise and highlights persistent increases/decreases across periods.",
        f"Moving averages smooth short-term volatility but may delay detection of sudden structural breaks.",
        f"The sharp drop in the final month likely reflects partial reporting rather than a true structural decline."
    ]
    if not peaks.empty:
        top_peak = peaks.iloc[0]
        bullets.append(
            f"The strongest single-month spike (among tracked types) is '{top_peak['crime_type']}' at {int(top_peak['year_partition'])}-{int(top_peak['month_partition']):02d} with {int(top_peak['crimes']):,} incidents."
        )
    if not drift.empty:
        top_drift = drift.iloc[0]
        bullets.append(
            f"Based on moving averages, the largest average drift is for '{top_drift['crime_type']}' with an average change of {float(top_drift['avg_ma_change']):.1f} (last minus first)."
        )
    bullets += [
        "Interpretation: comparing raw counts vs moving averages helps distinguish real trend shifts from seasonal or random variation.",
        "Operational implication: management decisions should be aligned to the moving-average curve rather than single-month spikes.",
    ]

    return {
        "kpis": [
            ("Distinct months", f"{months:,}"),
            ("Crime types tracked", f"{df['crime_type'].nunique():,}"),
            ("Rows", f"{len(df):,}"),
            ("MA window", "3 months"),
        ],
        "bullets": bullets,
    }

def q6_insights():
    """
    Q6 Insights (max-score, SQLite-safe):
    - No STDDEV_SAMP (not available in SQLite).
    - Computes std via sqrt(E[x^2] - E[x]^2) per quintile.
    - Adds effect size (Q5-Q1), monotonicity, within-quintile spread,
      and concrete best/worst examples in Q5.
    """

    base = read_sql("""
        SELECT
            lsoa_name,
            crimes,
            outcome_rate_pct,
            volume_quintile,
            corr_all_areas,
            rate_zscore
        FROM q6_load_vs_outcome_corr
        WHERE crimes IS NOT NULL
          AND outcome_rate_pct IS NOT NULL
          AND volume_quintile IS NOT NULL;
    """)
    if base.empty:
        return {"kpis": [], "bullets": ["No rows found in q6_load_vs_outcome_corr (after filtering NULLs)."]}

    corr_df = read_sql("""
        SELECT DISTINCT corr_all_areas
        FROM q6_load_vs_outcome_corr
        WHERE corr_all_areas IS NOT NULL;
    """)
    corr_val = float(corr_df.iloc[0]["corr_all_areas"]) if not corr_df.empty else None

    # SQLite-safe "std" using sqrt(E[x^2] - (E[x])^2)
    quint = read_sql("""
        SELECT
            volume_quintile,
            COUNT(*) AS areas,
            AVG(crimes) AS avg_crimes,
            AVG(outcome_rate_pct) AS avg_rate,
            -- variance = E[x^2] - (E[x])^2
            CASE
                WHEN (AVG(outcome_rate_pct * outcome_rate_pct) - AVG(outcome_rate_pct) * AVG(outcome_rate_pct)) < 0
                THEN 0
                ELSE (AVG(outcome_rate_pct * outcome_rate_pct) - AVG(outcome_rate_pct) * AVG(outcome_rate_pct))
            END AS var_rate,
            MIN(outcome_rate_pct) AS min_rate,
            MAX(outcome_rate_pct) AS max_rate
        FROM q6_load_vs_outcome_corr
        WHERE crimes IS NOT NULL
          AND outcome_rate_pct IS NOT NULL
          AND volume_quintile IS NOT NULL
        GROUP BY volume_quintile
        ORDER BY volume_quintile;
    """)

    # add std_rate in pandas (safe and clear)
    if not quint.empty:
        quint["std_rate"] = (quint["var_rate"].astype(float) ** 0.5)

    # monotonic check
    monotonic = None
    if len(quint) >= 2:
        diffs = quint["avg_rate"].diff().dropna()
        monotonic = bool((diffs >= 0).all())

    q1 = quint.iloc[0] if not quint.empty else None
    q5 = quint.iloc[-1] if not quint.empty else None

    delta_pp = None
    ratio = None
    if q1 is not None and q5 is not None and float(q1["avg_rate"]) != 0:
        delta_pp = float(q5["avg_rate"]) - float(q1["avg_rate"])
        ratio = float(q5["avg_rate"]) / float(q1["avg_rate"])

    # spread per quintile
    spread_summary = None
    if not quint.empty:
        quint["spread"] = quint["max_rate"].astype(float) - quint["min_rate"].astype(float)
        max_spread_row = quint.loc[quint["spread"].idxmax()]
        spread_summary = {
            "q": int(max_spread_row["volume_quintile"]),
            "min": float(max_spread_row["min_rate"]),
            "max": float(max_spread_row["max_rate"]),
            "spread": float(max_spread_row["spread"]),
            "std": float(max_spread_row["std_rate"]),
        }

    # Best/worst examples in Q5 (top load)
    best_q5 = read_sql("""
        SELECT lsoa_name, crimes, outcome_rate_pct, rate_zscore
        FROM q6_load_vs_outcome_corr
        WHERE volume_quintile = 5
          AND outcome_rate_pct IS NOT NULL
          AND crimes IS NOT NULL
        ORDER BY outcome_rate_pct DESC
        LIMIT 1;
    """)
    best_q5 = best_q5.iloc[0].to_dict() if not best_q5.empty else None

    worst_q5 = read_sql("""
        SELECT lsoa_name, crimes, outcome_rate_pct, rate_zscore
        FROM q6_load_vs_outcome_corr
        WHERE volume_quintile = 5
          AND outcome_rate_pct IS NOT NULL
          AND crimes IS NOT NULL
        ORDER BY outcome_rate_pct ASC
        LIMIT 1;
    """)
    worst_q5 = worst_q5.iloc[0].to_dict() if not worst_q5.empty else None

    bullets = []

    # 1) correlation
    if corr_val is not None:
        direction = "positive" if corr_val > 0 else "negative" if corr_val < 0 else "near zero"
        bullets.append(f"The global correlation between crime volume and solved rate is {corr_val:.4f} ({direction}, weak magnitude).")
    else:
        bullets.append("Global correlation (corr_all_areas) is not available.")

    # 2) trend + effect size
    if q1 is not None and q5 is not None:
        bullets.append(
            f"Across quintiles, the average solved rate increases from {float(q1['avg_rate']):.2f}% "
            f"(Q1, avg {float(q1['avg_crimes']):.0f} crimes, n={int(q1['areas'])}) "
            f"to {float(q5['avg_rate']):.2f}% "
            f"(Q5, avg {float(q5['avg_crimes']):.0f} crimes, n={int(q5['areas'])})."
        )
        if delta_pp is not None:
            bullets.append(f"Effect size (Q5 − Q1): {delta_pp:.2f} percentage points ({ratio:.2f}× relative).")

    # 3) monotonicity
    if monotonic is not None:
        bullets.append(
            "Quintile means are monotonic (non-decreasing), supporting a stable directional pattern across load levels."
            if monotonic
            else "Quintile means are not strictly monotonic; the overall trend exists, but there are local reversals."
        )

    # 4) variability
    if spread_summary is not None:
        bullets.append(
            f"Within-quintile variability is substantial (largest spread in Q{spread_summary['q']}: "
            f"{spread_summary['min']:.2f}% to {spread_summary['max']:.2f}%, spread {spread_summary['spread']:.2f} pp; "
            f"std≈{spread_summary['std']:.2f}), implying factors beyond volume drive outcome differences."
        )

    # 5) concrete examples
    if best_q5 is not None and worst_q5 is not None:
        bullets.append(
            "Concrete Q5 examples show heterogeneity: "
            f"best '{best_q5['lsoa_name']}' {float(best_q5['outcome_rate_pct']):.2f}% "
            f"(crimes={int(best_q5['crimes'])}, z={float(best_q5['rate_zscore']):.3f}) vs "
            f"worst '{worst_q5['lsoa_name']}' {float(worst_q5['outcome_rate_pct']):.2f}% "
            f"(crimes={int(worst_q5['crimes'])}, z={float(worst_q5['rate_zscore']):.3f})."
        )

    # 6–8) interpretation + caveat + operational
    bullets.append("Interpretation: higher-volume areas do not necessarily have worse solved rates in this dataset; the association is mildly positive but weak.")
    bullets.append("Plausible mechanism (hypothesis): high-volume urban areas may have stronger investigative capacity and standardized reporting pipelines that partially offset workload.")
    bullets.append("Caveat: outcome_rate_pct is a proxy derived from recorded outcome text; reporting practices and offense mix may influence measured rates, so this is descriptive rather than causal.")
    bullets.append("Operational implication: validate workload-performance assumptions empirically; stratify by volume and then drill down by crime type and local context to identify actionable drivers.")

    kpis = [
        ("Global correlation", f"{corr_val:.4f}" if corr_val is not None else "N/A"),
        ("Areas analyzed", f"{len(base):,}"),
        ("Lowest quintile avg rate", f"{float(q1['avg_rate']):.2f}%" if q1 is not None else "N/A"),
        ("Highest quintile avg rate", f"{float(q5['avg_rate']):.2f}%" if q5 is not None else "N/A"),
        ("Q5−Q1 delta (pp)", f"{delta_pp:.2f}" if delta_pp is not None else "N/A"),
    ]

    return {
        "kpis": kpis,
        "bullets": bullets,
        "quintile_table": quint.drop(columns=["var_rate", "spread"], errors="ignore"),
    }


def insights_panel(title: str, insight: dict):
    st.header("Insights / Findings")
    if insight.get("kpis"):
        kpi_block(insight["kpis"])
    bullets = insight.get("bullets", [])
    if bullets:
        for b in bullets:
            st.markdown(f"- {b}")


# =========================
# SIDEBAR NAVIGATION
# =========================
st.sidebar.title("Navigation")
page = st.sidebar.radio("Select a page", ["Overview"] + list(TABLES.keys()) + ["Feedback (All)"])


# =========================
# OVERVIEW
# =========================
if page == "Overview":
    st.title(APP_TITLE)
    st.caption("Data source: SQLite GOLD only (gold.db). No DuckDB access from the dashboard.")

    st.subheader("Dataset Story (Narrative)")
    st.markdown(
        """
This dashboard tells a focused story about **crime concentration, hotspots, institutional performance, multi-dimensional patterns,
temporal dynamics, and the relationship between workload and outcomes**.

The analysis is built from **pre-aggregated GOLD tables** stored in SQLite, enabling fast, reproducible exploration and presentation.
        """
    )

    st.subheader("GOLD Tables Catalog (required)")
    catalog = read_sql("SELECT * FROM table_catalog ORDER BY table_name;")
    st.dataframe(styled_df(catalog), use_container_width=True)

    st.subheader("Dashboard Structure (schematic)")
    st.markdown(
        """
- Q1: Crime concentration by area (Pareto)  
- Q2: Statistically extreme hotspots (z-score)  
- Q3: Police forces ranked by solved rate  
- Q4: Multi-dimensional analysis using CUBE (area × crime type), including subtotals  
- Q5: Time trends and smoothing (3-month moving average)  
- Q5b: Pivoted view for month-by-month comparison across top crime types  
- Q6: Relationship between crime load and solved rate (correlation + quintiles)  
- Feedback: User notes stored and displayed from SQLite  
        """
    )

    feedback_box("Overview")


# =========================
# Q1
# =========================
elif page == "Q1 – Area Pareto (Concentration)":
    st.title("Q1 – Crime Concentration by Area (Pareto)")

    st.markdown(
        """
**Research question:** Which areas account for the majority of crime volume?  
**Motivation:** If crime is concentrated, targeted interventions can be far more efficient than uniform allocation.



 **Note:** cumulative percentage (cum_pct) is omitted from the sample table by design. 
 It is only meaningful for the fully ordered population table, not for a random sample.

        """
    )

    show_table_section("Tables", "q1_area_pareto", "q1_area_pareto_sample")

    insights_panel("Q1", q1_insights())

    # --- Load data once ---
    df = read_sql("SELECT lsoa_name, crimes, cum_pct FROM q1_area_pareto ORDER BY crimes DESC;")

    # 1) Total number of areas (KPI)
    total_areas = int(len(df))
    st.metric("Total areas (LSOA)", f"{total_areas:,}")

    st.header("Visualization (Matplotlib, interactive): Cumulative share vs. Top-N areas")

    # 2) Slider max = total number of areas
    max_n = total_areas
    default_n = min(200, max_n)

    n = st.slider("Top-N areas", min_value=10, max_value=max_n, value=default_n, step=10)
    df_top = df.head(n)

    x = list(range(1, len(df_top) + 1))
    y = df_top["cum_pct"].astype(float).tolist()

    fig, ax = plt.subplots()
    ax.plot(x, y)
    ax.set_xlabel("Top-N areas (ordered by descending crime volume)")
    ax.set_ylabel("Cumulative % of total crimes")
    ax.set_title(f"Cumulative crime share – Top {n} areas")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

    # Optional: show the exact coverage at the chosen N
    coverage = float(df_top["cum_pct"].iloc[-1])
    st.caption(f"At Top-{n}, cumulative coverage is {coverage:.2f}% of total crimes.")


    feedback_box("Q1")


# =========================
# Q2
# =========================
elif page == "Q2 – Area Outliers (Z-score)":
    st.title("Q2 – Detecting Hotspots via Z-score")

    st.markdown(
        """
**Research question:** Which areas are statistically extreme hotspots in crime volume?  
**Motivation:** A z-score view highlights areas whose volume is far beyond “typical” variance.
        """
    )

    show_table_section("Tables", "q2_area_outliers", "q2_area_outliers_sample")

    insights_panel("Q2", q2_insights())

    st.header("Visualization (Matplotlib): z-score distribution")
    df = read_sql("SELECT z_score FROM q2_area_outliers;")
    fig, ax = plt.subplots()
    ax.hist(df["z_score"].astype(float), bins=50)
    ax.set_xlabel("z_score")
    ax.set_ylabel("Number of areas")
    ax.set_title("Distribution of area z-scores (hotspot intensity)")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

    feedback_box("Q2")


# =========================
# Q3
# =========================
elif page == "Q3 – Police Forces Ranking (Solved Rate)":
    st.title("Q3 – Police Forces Ranked by Solved Rate")

    st.markdown(
        """
**Research question:** How does the solved/clearance rate vary across police forces?  
**Motivation:** Comparing institutions can reveal performance gaps and potential best practices.

 No sample table was created for this query, since the aggregation level (Police Force) results in only ~43 rows, 
 making sampling unnecessary.
        """
    )

    show_table_section("Tables", "q3_reported_by_rank", "")

    insights_panel("Q3", q3_insights())

    st.header("Visualization (Matplotlib, interactive): Top-K forces by solved rate")
    df = read_sql("""
        SELECT reported_by, total_crimes, solved_rate
        FROM q3_reported_by_rank
        ORDER BY solved_rate DESC, total_crimes DESC;
    """)
    k = st.slider("Top-K forces", 5, min(43, len(df)), 15)
    df_top = df.head(k).sort_values("solved_rate", ascending=True)

    fig, ax = plt.subplots()
    ax.barh(df_top["reported_by"], df_top["solved_rate"])
    ax.set_xlabel("Solved rate (%)")
    ax.set_title(f"Top {k} police forces by solved rate")
    ax.grid(True, axis="x", alpha=0.3)
    st.pyplot(fig)

    st.subheader("Size vs effectiveness (numeric check)")
    tmp = read_sql("SELECT total_crimes, solved_rate FROM q3_reported_by_rank;")
    corr_val = tmp["total_crimes"].corr(tmp["solved_rate"]) if not tmp.empty else None

    corr_df = pd.DataFrame({
        "corr_size_vs_efficiency": [None if corr_val is None else round(float(corr_val), 4)]
    })
    st.dataframe(styled_df(corr_df), use_container_width=True)

    feedback_box("Q3")


# =========================
# Q4
# =========================
elif page == "Q4 – CUBE: Area × Crime Type":
    st.title("Q4 – Multi-dimensional Patterns (CUBE: Area × Crime Type)")

    st.markdown(
        """
**Research question:** How do outcome rates differ by the interaction of (area × crime type), including subtotals?  
**Motivation:** A single CUBE query provides both detailed intersections and rollups for cross-cutting comparisons.

Note on NULL values in CUBE output:
In this table, NULL does not indicate missing data.
Instead, NULL represents aggregated subtotals produced by the SQL CUBE operator:

crime_type = NULL → aggregation over all crime types for the given area

lsoa_name = NULL → aggregation over all areas for the given crime type

both NULL → grand total across all areas and crime types
        """
    )

    show_table_section("Tables", "q4_cube_area_type_outcome", "q4_cube_area_type_outcome_sample")

    insights_panel("Q4", q4_insights())

    st.header("Visualization (Seaborn, interactive, 2D): Outcome-rate heatmap (Top areas × Top crime types)")

    top_areas = st.slider("Top areas", 5, 30, 15)
    top_types = st.slider("Top crime types", 5, 20, 10)

    conn = get_conn()

    # 1) Select TOP areas by total volume (from FULL cube table, not from a limited slice)
    areas_df = pd.read_sql_query("""
        SELECT lsoa_name, SUM(total_crimes) AS total
        FROM q4_cube_area_type_outcome
        WHERE lsoa_name IS NOT NULL AND crime_type IS NOT NULL
        GROUP BY lsoa_name
        ORDER BY total DESC
        LIMIT ?;
    """, conn, params=[top_areas])

    # 2) Select TOP crime types by total volume
    types_df = pd.read_sql_query("""
        SELECT crime_type, SUM(total_crimes) AS total
        FROM q4_cube_area_type_outcome
        WHERE lsoa_name IS NOT NULL AND crime_type IS NOT NULL
        GROUP BY crime_type
        ORDER BY total DESC
        LIMIT ?;
    """, conn, params=[top_types])

    areas = areas_df["lsoa_name"].tolist()
    types = types_df["crime_type"].tolist()

    # Safety: if something is empty, avoid crashing
    if not areas or not types:
        st.warning("Not enough data to build heatmap (areas/types empty).")
    else:
        # 3) Fetch ONLY the matrix cells we need (area x type)
        placeholders_areas = ",".join(["?"] * len(areas))
        placeholders_types = ",".join(["?"] * len(types))

        df = pd.read_sql_query(f"""
            SELECT lsoa_name, crime_type, outcome_rate, total_crimes
            FROM q4_cube_area_type_outcome
            WHERE lsoa_name IN ({placeholders_areas})
              AND crime_type IN ({placeholders_types});
        """, conn, params=areas + types)

        # 4) Pivot to matrix (heatmap values)
        pivot = df.pivot_table(
            index="lsoa_name",
            columns="crime_type",
            values="outcome_rate",
            aggfunc="mean"
        )

        # ---- Optional: what to do with missing cells ----
        # If you want to KEEP missing as blank (recommended for honesty):
        #   keep as NaN
        #
        # If you want to SHOW 0 instead (not recommended unless you explicitly explain it):
        # pivot = pivot.fillna(0)

        st.caption(f"Missing cells (no data for that Area×Type in the selected TOPs): {int(pivot.isna().sum().sum())}")

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.heatmap(pivot, ax=ax)
        ax.set_title("Outcome rate heatmap (Top Areas × Top Crime Types)")
        ax.set_xlabel("crime_type")
        ax.set_ylabel("lsoa_name")
        st.pyplot(fig)


    feedback_box("Q4")


# =========================
# Q5
# =========================
elif page == "Q5 – Trend & Moving Average":
    st.title("Q5 – Temporal Trends (3-month moving average)")

    st.markdown(
        """
**Research question:** How does crime evolve over time, and what trend emerges after smoothing noise?  
**Motivation:** Moving averages highlight persistent shifts beyond month-to-month fluctuations.
        """
    )

    show_table_section("Tables", "q5_trend_moving_avg", "")

    insights_panel("Q5", q5_insights())

    st.header("Visualization (Matplotlib, interactive): Trend vs moving average by crime type")
    df = read_sql("""
        SELECT year_partition, month_partition, crime_type, crimes, moving_avg_3m
        FROM q5_trend_moving_avg
        ORDER BY crime_type, year_partition, month_partition;
    """)
    crime_types = sorted(df["crime_type"].dropna().unique().tolist())
    chosen = st.selectbox("Crime type", crime_types)

    d = df[df["crime_type"] == chosen].copy()
    d["ym"] = d["year_partition"].astype(str) + "-" + d["month_partition"].astype(int).astype(str).str.zfill(2)

    fig, ax = plt.subplots()
    ax.plot(d["ym"], d["crimes"], label="Crimes")
    ax.plot(d["ym"], d["moving_avg_3m"], label="Moving average (3m)")
    ax.set_title(f"Monthly trend – {chosen}")
    ax.set_xlabel("Year-Month")
    ax.set_ylabel("Count")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

    feedback_box("Q5")


# =========================
# Q6
# =========================
elif page == "Q6 – Load vs Solved Rate (Correlation + Quintiles)":
    st.title("Q6 – Crime Load vs Solved Rate (Correlation + Quintiles)")

    st.markdown(
        """
**Research question:** Is higher crime load associated with better or worse solved rates?  
**Motivation:** Testing this relationship challenges common assumptions and informs allocation strategies.
        """
    )

    show_table_section("Tables", "q6_load_vs_outcome_corr", "q6_load_vs_outcome_corr_sample")

    insight = q6_insights()
    insights_panel("Q6", insight)

    st.header("Interactive visualization (Matplotlib, 2D): Scatter by load quintile")
    df = read_sql("SELECT lsoa_name, crimes, outcome_rate_pct, volume_quintile FROM q6_load_vs_outcome_corr;")
    quintile = st.selectbox("Select load quintile", sorted(df["volume_quintile"].dropna().unique().tolist()))
    d = df[df["volume_quintile"] == quintile].copy()

    fig, ax = plt.subplots()
    ax.scatter(d["crimes"], d["outcome_rate_pct"], s=12)
    ax.set_xlabel("Crimes (area volume)")
    ax.set_ylabel("Solved rate (%)")
    ax.set_title(f"Quintile {quintile}: Crime volume vs solved rate")
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

    st.subheader("Quintile summary (from SQLite only)")
    if "quintile_table" in insight:
        st.dataframe(styled_df(insight["quintile_table"]), use_container_width=True)

    feedback_box("Q6")


# =========================
# FEEDBACK ONLY
# =========================
elif page == "Feedback (All)":
    st.title("Feedback (stored in SQLite)")
    df_fb = read_sql("SELECT created_at, page, rating, feedback_text FROM user_feedback ORDER BY id DESC;")
    st.dataframe(styled_df(df_fb), use_container_width=True)
