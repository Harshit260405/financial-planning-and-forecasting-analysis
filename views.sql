-- =============================================================================
-- FP&A Cost Center Dashboard - Widoki pomocnicze
-- =============================================================================
-- Zaklada, ze schema.sql zostal juz uruchomiony i tabele sa zaladowane danymi.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- VW_FACT_COSTS_ENRICHED
-- Zdenormalizowany widok faktow z pelnym kontekstem wymiarow - wygodny
-- do szybkich analiz ad-hoc bez pisania joinow za kazdym razem.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_fact_costs_enriched;
CREATE VIEW vw_fact_costs_enriched AS
SELECT
    f.fact_id,
    f.cost_center_id,
    cc.functional_area,
    cc.country_finance,
    cc.country_physical,
    cc.budget_owner,
    cc.stakeholder,
    cat.cost_type,
    cat.cost_group,
    cat.cost_category,
    f.project_id,
    proj.project_name,
    cl.client_id,
    cl.client_name,
    d.date,
    d.year,
    d.quarter,
    d.month_number,
    d.month_name,
    d.year_month,
    f.amount_budget,
    f.amount_actual,
    f.amount_forecast,
    f.amount_actual - f.amount_budget AS variance_abs,
    ROUND(
        (f.amount_actual - f.amount_budget) * 100.0 / NULLIF(f.amount_budget, 0), 2
    ) AS variance_pct
FROM fact_costs f
JOIN dim_cost_center cc ON cc.cost_center_id = f.cost_center_id
JOIN dim_category    cat ON cat.category_id   = f.category_id
JOIN dim_date        d   ON d.date_id          = f.date_id
LEFT JOIN dim_project proj ON proj.project_id  = f.project_id
LEFT JOIN dim_client  cl   ON cl.client_id     = proj.client_id;

-- -----------------------------------------------------------------------------
-- VW_VARIANCE_BY_COST_CENTER
-- Roczna wariancja budzetowa per centrum kosztow - typowy widok wyjsciowy
-- dla przegladu FP&A ("kto przekracza budzet").
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_variance_by_cost_center;
CREATE VIEW vw_variance_by_cost_center AS
SELECT
    cost_center_id,
    functional_area,
    year,
    SUM(amount_budget)  AS total_budget,
    SUM(amount_actual)  AS total_actual,
    SUM(amount_actual) - SUM(amount_budget) AS variance_abs,
    ROUND(
        (SUM(amount_actual) - SUM(amount_budget)) * 100.0 / NULLIF(SUM(amount_budget), 0), 2
    ) AS variance_pct
FROM vw_fact_costs_enriched
GROUP BY cost_center_id, functional_area, year;

-- -----------------------------------------------------------------------------
-- VW_MONTHLY_TREND_BY_COST_TYPE
-- Trend miesieczny kosztow rozbity na Labor / Non-Labor - do wykresu liniowego
-- na stronie glownej dashboardu.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_monthly_trend_by_cost_type;
CREATE VIEW vw_monthly_trend_by_cost_type AS
SELECT
    year_month,
    date,
    cost_type,
    SUM(amount_actual)   AS total_actual,
    SUM(amount_budget)   AS total_budget,
    SUM(amount_forecast) AS total_forecast
FROM vw_fact_costs_enriched
GROUP BY year_month, date, cost_type
ORDER BY date, cost_type;

-- -----------------------------------------------------------------------------
-- VW_TOP_VARIANCE_CATEGORIES
-- Kategorie kosztowe z najwieksza wariancja (co do wartosci bezwzglednej) -
-- pomocne przy szybkiej identyfikacji "gdzie szukac wyjasnien".
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_top_variance_categories;
CREATE VIEW vw_top_variance_categories AS
SELECT
    cost_type,
    cost_group,
    cost_category,
    year,
    SUM(amount_budget) AS total_budget,
    SUM(amount_actual) AS total_actual,
    SUM(amount_actual) - SUM(amount_budget) AS variance_abs,
    ROUND(
        (SUM(amount_actual) - SUM(amount_budget)) * 100.0 / NULLIF(SUM(amount_budget), 0), 2
    ) AS variance_pct
FROM vw_fact_costs_enriched
GROUP BY cost_type, cost_group, cost_category, year
ORDER BY ABS(SUM(amount_actual) - SUM(amount_budget)) DESC;

-- -----------------------------------------------------------------------------
-- VW_COST_BY_CLIENT
-- Koszty Non-Labor (billable) zagregowane per klient i projekt - typowy widok
-- dla agencji marketingowej: "ile wydajemy na obsluge danego klienta".
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_cost_by_client;
CREATE VIEW vw_cost_by_client AS
SELECT
    client_name,
    project_name,
    year,
    cost_group,
    cost_category,
    SUM(amount_budget) AS total_budget,
    SUM(amount_actual) AS total_actual,
    SUM(amount_actual) - SUM(amount_budget) AS variance_abs
FROM vw_fact_costs_enriched
WHERE client_name IS NOT NULL   -- wyklucza Labor Cost (nie ma przypisanego projektu)
GROUP BY client_name, project_name, year, cost_group, cost_category
ORDER BY total_actual DESC;

-- -----------------------------------------------------------------------------
-- VW_PROJECT_PROFITABILITY
-- Rentownosc per projekt: przychod vs koszt bezposredni (non-labor) tego
-- projektu. Marza = (Revenue - Direct Cost) / Revenue.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_project_profitability;
CREATE VIEW vw_project_profitability AS
SELECT
    r.project_id,
    p.project_name,
    p.client_id,
    cl.client_name,
    d.year,
    d.year_month,
    r.amount_revenue_actual,
    r.amount_revenue_budget,
    COALESCE(c.direct_cost_actual, 0) AS direct_cost_actual,
    COALESCE(c.direct_cost_budget, 0) AS direct_cost_budget,
    r.amount_revenue_actual - COALESCE(c.direct_cost_actual, 0) AS gross_margin_abs,
    ROUND(
        (r.amount_revenue_actual - COALESCE(c.direct_cost_actual, 0)) * 100.0
        / NULLIF(r.amount_revenue_actual, 0), 2
    ) AS gross_margin_pct
FROM fact_revenue r
JOIN dim_project p ON p.project_id = r.project_id
JOIN dim_client  cl ON cl.client_id = p.client_id
JOIN dim_date    d  ON d.date_id    = r.date_id
LEFT JOIN (
    SELECT project_id, date_id,
           SUM(amount_actual) AS direct_cost_actual,
           SUM(amount_budget) AS direct_cost_budget
    FROM fact_costs
    WHERE project_id IS NOT NULL
    GROUP BY project_id, date_id
) c ON c.project_id = r.project_id AND c.date_id = r.date_id;

-- -----------------------------------------------------------------------------
-- VW_CLIENT_PROFITABILITY
-- Rentownosc zagregowana na poziomie klienta i roku - widok dla dyrektora
-- ("ktore konta sa rentowne").
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_client_profitability;
CREATE VIEW vw_client_profitability AS
SELECT
    client_name,
    year,
    SUM(amount_revenue_actual)  AS total_revenue,
    SUM(direct_cost_actual)     AS total_direct_cost,
    SUM(amount_revenue_actual) - SUM(direct_cost_actual) AS gross_margin_abs,
    ROUND(
        (SUM(amount_revenue_actual) - SUM(direct_cost_actual)) * 100.0
        / NULLIF(SUM(amount_revenue_actual), 0), 2
    ) AS gross_margin_pct
FROM vw_project_profitability
GROUP BY client_name, year
ORDER BY total_revenue DESC;
