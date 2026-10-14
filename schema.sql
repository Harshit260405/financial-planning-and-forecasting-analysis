-- =============================================================================
-- FP&A Cost Center Dashboard - Schemat bazy danych (star schema)
-- =============================================================================
-- Silnik docelowy: SQLite (lekki, bez serwera, latwy do dolaczenia do repo).
-- Skladnia jest w duzej mierze przenosna na PostgreSQL - patrz komentarze
-- przy typach specyficznych dla SQLite (AUTOINCREMENT, brak natywnego ENUM).
--
-- Kolejnosc tworzenia: wymiary najpierw, potem tabela faktow (FK).
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- DIM_CLIENT
-- Klient agencji (marka), dla ktorej realizowane sa projekty/kampanie.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_client;
CREATE TABLE dim_client (
    client_id       TEXT PRIMARY KEY,          -- np. "CL001"
    client_name     TEXT NOT NULL UNIQUE
);

-- -----------------------------------------------------------------------------
-- DIM_PROJECT
-- Projekt/kampania - snowflake do dim_client (kazdy projekt nalezy do
-- dokladnie jednego klienta, kazdy klient ma min. 2 projekty).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_project;
CREATE TABLE dim_project (
    project_id      TEXT PRIMARY KEY,          -- np. "PRJ0001"
    project_name    TEXT NOT NULL,
    client_id       TEXT NOT NULL REFERENCES dim_client (client_id)
);
CREATE INDEX idx_dim_project_client ON dim_project (client_id);

-- -----------------------------------------------------------------------------
-- DIM_COST_CENTER
-- Centrum kosztow - jednostka organizacyjna, na ktora ksiegowane sa koszty.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_cost_center;
CREATE TABLE dim_cost_center (
    cost_center_id      TEXT PRIMARY KEY,          -- np. "CC0001"
    functional_area      TEXT    NOT NULL,          -- IT, Sales, Marketing, HR, ...
    country_finance      TEXT    NOT NULL,          -- kraj rozliczeniowy (ksiegowy)
    country_physical     TEXT    NOT NULL,          -- kraj fizycznej lokalizacji
    budget_owner         TEXT    NOT NULL,          -- osoba odpowiedzialna za budzet
    stakeholder          TEXT    NOT NULL,          -- glowny interesariusz biznesowy
    size_factor           REAL    NOT NULL CHECK (size_factor > 0)  -- wspolczynnik skali CC
);

-- -----------------------------------------------------------------------------
-- DIM_CATEGORY
-- Hierarchia kosztow, 3 poziomy szczegolowosci:
--   cost_type    (poziom 1, najmniej szczegolowy): Labor Cost / Non-Labor Cost
--   cost_group   (poziom 2): Salary & Wages, Employee Cost, Professional Fees, IT Expenses
--   cost_category(poziom 3, lisc - na tym poziomie ksiegowane sa transakcje)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_category;
CREATE TABLE dim_category (
    category_id     INTEGER PRIMARY KEY,
    cost_type       TEXT    NOT NULL CHECK (cost_type IN ('Labor Cost', 'Non-Labor Cost')),
    cost_group      TEXT    NOT NULL,
    cost_category   TEXT    NOT NULL UNIQUE,
    base_share      REAL    NOT NULL CHECK (base_share > 0)
);

-- -----------------------------------------------------------------------------
-- DIM_DATE
-- Pelny kalendarz DZIENNY (jeden wiersz na kazdy dzien, bez luk) - wymog
-- Power BI dla tabeli oznaczonej jako "Date table". fact_costs (dane
-- miesieczne) laczy sie z wierszem, gdzie is_month_start = TRUE.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_id         INTEGER PRIMARY KEY,
    date            DATE    NOT NULL UNIQUE,
    year            INTEGER NOT NULL,
    quarter         TEXT    NOT NULL,                -- "Q1".."Q4"
    month_number    INTEGER NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    month_name      TEXT    NOT NULL,
    year_month      TEXT    NOT NULL,                -- "2024-01"
    fiscal_year     INTEGER NOT NULL,
    day_of_month    INTEGER NOT NULL,
    is_month_start  INTEGER NOT NULL CHECK (is_month_start IN (0, 1))  -- SQLite: brak typu BOOLEAN
);

-- -----------------------------------------------------------------------------
-- FACT_COSTS
-- Tabela faktow - miesieczne kwoty budget / actual / forecast per
-- centrum kosztow x kategoria x miesiac.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_costs;
CREATE TABLE fact_costs (
    fact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cost_center_id  TEXT    NOT NULL REFERENCES dim_cost_center (cost_center_id),
    category_id     INTEGER NOT NULL REFERENCES dim_category (category_id),
    date_id         INTEGER NOT NULL REFERENCES dim_date (date_id),
    project_id      TEXT    REFERENCES dim_project (project_id),  -- NULL dla Labor Cost (nie alokowane do projektu)
    amount_budget   REAL    NOT NULL CHECK (amount_budget >= 0),
    amount_actual   REAL    NOT NULL CHECK (amount_actual >= 0),
    amount_forecast REAL    NOT NULL CHECK (amount_forecast >= 0),

    UNIQUE (cost_center_id, category_id, date_id, project_id)
);

-- Indeksy pod typowe filtry / joiny w dashboardzie (drill-down po CC, kategorii, czasie)
CREATE INDEX idx_fact_costs_cost_center ON fact_costs (cost_center_id);
CREATE INDEX idx_fact_costs_category    ON fact_costs (category_id);
CREATE INDEX idx_fact_costs_date        ON fact_costs (date_id);
CREATE INDEX idx_fact_costs_project     ON fact_costs (project_id);

-- -----------------------------------------------------------------------------
-- FACT_REVENUE
-- Przychod na poziomie klient x projekt x miesiac. Sluzy do liczenia
-- rentownosci (Revenue - Direct Cost) per klient / projekt.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_revenue;
CREATE TABLE fact_revenue (
    revenue_id              INTEGER PRIMARY KEY,
    client_id                TEXT    NOT NULL REFERENCES dim_client (client_id),
    project_id                TEXT    NOT NULL REFERENCES dim_project (project_id),
    date_id                   INTEGER NOT NULL REFERENCES dim_date (date_id),
    amount_revenue_budget     REAL    NOT NULL CHECK (amount_revenue_budget >= 0),
    amount_revenue_actual     REAL    NOT NULL CHECK (amount_revenue_actual >= 0),
    amount_revenue_forecast   REAL    NOT NULL CHECK (amount_revenue_forecast >= 0),

    UNIQUE (project_id, date_id)
);

CREATE INDEX idx_fact_revenue_client  ON fact_revenue (client_id);
CREATE INDEX idx_fact_revenue_project ON fact_revenue (project_id);
CREATE INDEX idx_fact_revenue_date    ON fact_revenue (date_id);
