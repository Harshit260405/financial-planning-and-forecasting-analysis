# FP&A Cost Center & Client Profitability Dashboard

An end-to-end portfolio project for a fictional marketing agency: synthetic cost and revenue data → star/snowflake schema (SQL) → an interactive Power BI dashboard for cost control, client/project profitability, and media channel efficiency analysis.

![Power BI](https://img.shields.io/badge/Power%20BI-F2C811?style=flat&logo=powerbi&logoColor=black)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-SQLite-blue?style=flat&logo=sqlite&logoColor=white)
![DAX](https://img.shields.io/badge/DAX-Power%20BI-yellow?style=flat)

---

## ⚠️ Data disclaimer

Client and project names are taken from the public portfolio of marketing agency and are used **purely for naming realism**. **All financial figures (costs, revenue, margins) are 100% synthetic (randomly generated in Phyhon).**

---

## 🎥 Demo

![Dashboard demo](docs/demo.gif)

*The recording shows: selecting year/month, the MTD/YTD toggle, drill-down through the cost hierarchy, filtering by cost center/client/project, and channel-level analysis.*

> 📥 The `powerbi/cost_dashboard.pbix` file can be downloaded and opened in Power BI Desktop to explore the dashboard yourself.

---

## 📊 Business problem

The dashboard answers questions typical of an FP&A team and a marketing agency's leadership:

**Cost control (Cost Center view)**
- How does the current month (MTD) compare to the cumulative year-to-date (YTD) result?
- Where is the largest deviation from budget — which cost category, which department?

**Profitability (Client & Project view)**
- Which client is genuinely profitable, and which is running at a loss?
- Are all campaigns for the same client equally profitable?

**Channel efficiency (Channel view)**
- What share of media budget goes to TikTok, YouTube, Instagram?
- Which channel is getting more expensive fastest, year over year?
- Do different clients show clearly different channel preferences?

---

## 🏗️ Project architecture

```
Python (synthetic data generator)
        ↓
SQLite (star + snowflake schema: 5 dimensions, 2 fact tables)
        ↓
Power BI (relationships, hierarchies, DAX measures, 3 report pages)
```

### Data model

![Data model](docs/data_model.png)

**Dimensions:**
- **`dim_cost_center`** — cost center: ID, functional area, finance/physical country, budget owner, stakeholder
- **`dim_category`** — 3-level cost hierarchy: `cost_type` (Labor / Non-Labor) → `cost_group` (Salary & Wages, Employee Cost, Professional Fees, IT Expenses, **Channel Fees**) → `cost_category` (16 leaf items, including TikTok/YouTube/Instagram)
- **`dim_date`** — full daily calendar (no gaps, required for Power BI's "Mark as Date Table"), 24 months of data
- **`dim_client`** — 18 agency clients
- **`dim_project`** — projects/campaigns, snowflaked to `dim_client` (every client has at least 2 projects)

**Facts:**
- **`fact_costs`** — monthly `actual` / `budget` / `forecast` amounts per cost center × category × month, with an optional `project_id` (Non-Labor costs are split across 1-3 client projects; Labor Cost stays unassigned — salaries aren't billable 1:1 to a campaign)
- **`fact_revenue`** — revenue at the client × project × month grain; generated as direct cost × a client-specific margin, plus independent noise

**Realistic cost mix** (marketing agency, not a generic company): Labor ~50%, Channel Fees ~30%, Professional Fees ~12%, IT Expenses ~8%.

---

## 🖥️ Dashboard — 3 pages

**1. Cost Center view** — Executive Summary: KPI cards, an MTD/YTD table with drill-down through the cost hierarchy, a donut chart, top 5 cost centers by variance, and an org-structure filter panel

**2. Client view** — client profitability ranking (best performers / needs attention), margin per project, filterable by client/project

**3. Channel view** — spend share per channel (TikTok/YouTube/Instagram/Professional Fees), year-over-year channel cost efficiency, channel mix per client

**Shared mechanism across all pages:** an **MTD / YTD** toggle (disconnected table + `SWITCH`), synced across pages (`Sync slicers`), driving KPI cards, tables, and charts simultaneously.

---

## 🧮 Selected DAX patterns

The full measure list lives in the `.pbix` file. Two representative patterns:

**MTD/YTD toggle driving an entire page:**
```dax
Selected View = SELECTEDVALUE('View Selector'[View], "MTD")

Selected Actual =
SWITCH([Selected View], "MTD", [MTD Actual], "YTD", [YTD Actual])

YTD Actual =
CALCULATE(
    [Actual Costs],
    DATESYTD(dim_date[date]),
    REMOVEFILTERS(dim_date[month_name])
)
```

**Client profitability (Direct Cost excludes Labor Cost via a filter on `project_id`):**
```dax
Direct Cost Actual =
CALCULATE(SUM(fact_costs[amount_actual]), fact_costs[project_id] <> BLANK())

Selected Gross Margin % =
DIVIDE([Selected Revenue] - [Selected Direct Cost], [Selected Revenue])
```

---

## 🛠️ Tech stack

| Layer | Tool |
|---|---|
| Data generation | Python (pandas, numpy) |
| Database | SQLite (star/snowflake schema, SQL views) |
| Model / BI | Power BI Desktop (relationships, hierarchies, DAX, custom theme) |

---

## 📁 Repository structure

```
fpa-cost-center-dashboard/
├── README.md
├── data/
│   ├── raw/                          <- generated CSV files (7 tables)
│   ├── generator/
│   │   └── generate_data.py          <- synthetic data generator
│   └── fpa_cost.db                   <- ready-to-use SQLite database
├── sql/
│   ├── schema.sql                    <- DDL (star + snowflake schema)
│   ├── views.sql                     <- views (variance, profitability, trends)
│   └── load_to_sqlite.py             <- CSV -> SQLite loader
├── powerbi/
│   ├── cost_dashboard.pbix
│   └── marketing_agency_theme.json   <- custom color theme
└── docs/
    ├── data_model.png
    └── demo.gif
```

---

## 🚀 Reproducing the project locally

```bash
# 1.. Open powerbi/cost_dashboard.pbix in Power BI Desktop
#    (optional: import powerbi/marketing_agency_theme.json via View -> Themes -> Browse for themes)
```


---

## 💡 Key takeaways from the data

*Fill in after a final review of the dashboard, e.g.:*
- Which client has the highest and which has a negative margin in the latest month
- Which channel (TikTok/YouTube/Instagram) is growing in cost fastest year over year
- Whether channel mix differs meaningfully across clients

---

## 📬 Contact

markomajer90@gmail.com
