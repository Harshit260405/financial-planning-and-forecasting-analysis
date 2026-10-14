"""
FP&A Cost Center Dashboard - Synthetic Data Generator
========================================================
Generuje spojny, realistyczny zbior danych na potrzeby modelu gwiazdy
(star schema) do analizy kosztow na poziomie centrum kosztow.

Wyjscie (CSV, gotowe do zaladowania do Power BI / SQLite):
    dim_cost_center.csv
    dim_category.csv
    dim_date.csv
    fact_costs.csv

Uruchomienie:
    python generate_data.py --n-cost-centers 25 --start 2024-01 --end 2025-12 --seed 42
"""

import argparse
import calendar
import itertools
import os
from datetime import date

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 1. SLOWNIKI / DANE REFERENCYJNE
# ---------------------------------------------------------------------------

FUNCTIONAL_AREAS = [
    "IT", "Sales", "Marketing", "HR", "Finance",
    "Operations", "R&D", "Supply Chain", "Customer Service", "Legal",
]

COUNTRIES = [
    "Poland", "Germany", "France", "United Kingdom", "United States",
    "Spain", "Italy", "Netherlands",
]

FIRST_NAMES = [
    "Anna", "Piotr", "Maria", "Jan", "Katarzyna", "Michal", "Agnieszka",
    "Tomasz", "Ewa", "Marek", "Sofia", "Lukas", "Emma", "Noah", "Olivia",
    "Liam", "Julia", "David", "Laura", "Marco",
]
LAST_NAMES = [
    "Kowalski", "Nowak", "Wisniewski", "Wojcik", "Kowalczyk", "Muller",
    "Schmidt", "Garcia", "Martinez", "Rossi", "Bianchi", "Smith", "Jones",
    "Dubois", "Bernard", "de Jong", "Bakker",
]

# ---------------------------------------------------------------------------
# KLIENCI I PROJEKTY (na potrzeby wariantu "agencja marketingowa")
# ---------------------------------------------------------------------------
# Nazwy klientow i (w wiekszosci) nazwy projektow pochodza z publicznego
# portfolio agencji SAMY (https://samy.com/es/work/) - uzyte wylacznie dla
# realizmu nazewnictwa. WAZNE: wszystkie kwoty finansowe w tym projekcie sa
# W 100% SYNTETYCZNE (losowo wygenerowane) i NIE reprezentuja rzeczywistych
# budzetow/kosztow tych marek. Tam gdzie w portfolio widniala tylko jedna
# kampania, dopisany zostal drugi, prawdopodobny tytul projektu (oznaczony
# ponizej), zeby kazdy klient mial min. 2 projekty - te dodatkowe tytuly sa
# fikcyjne i nie pochodza z materialow SAMY.
CLIENT_PROJECTS = {
    "The North Face": [
        "International Klein Blue", "Ultra-Trail du Mont-Blanc",
        "Transgrancanaria", "Festival de escalada",
    ],
    "KPN": [
        "Youtube Channel", "Social Media Growth Plan",  # 2. tytul - fikcyjny (filler)
    ],
    "Johnnie Walker": [
        "Keep Walking Valencia", "Global Influencer Program",  # filler
    ],
    "L'Oreal Paris": [
        "Big Deal Waterproof", "Revitalift Laser Eyebags", "Magic Retouch",
    ],
    "Krispy Kreme": [
        "Entering the Spanish Market", "Loyalty Program Launch",  # filler
    ],
    "Durex": [
        "We Are Sorry", "Pride Campaign",  # filler
    ],
    "The Mission Billion Initiative": [
        "Dis-Inspirational Quotes", "Awareness Drive",  # filler
    ],
    "Fazer": [
        "I'll Just Have One Piece", "Renovacion de marca con foco en social media",
    ],
    "Amazon Prime": [
        "The Roasted Academy", "Creator Collab Series",  # filler
    ],
    "Old Jamaica": [
        "Adios, Old Jamaica", "Heritage Campaign",  # filler
    ],
    "Helen AI Influencer": [
        "Educar aprovechando la innovacion", "Product Launch Series",  # filler
    ],
    "AUTUMNCRISP": [
        "Uvas que conquistan internet", "Harvest Season Push",  # filler
    ],
    "Blacklane": [
        "Vive la vida en Blacklane", "Airport Experience Campaign",  # filler
    ],
    "NYX": [
        "Butter Melt Blush", "Spring Color Launch",  # filler
    ],
    "INGUAT": [
        "Guatemala se globaliza", "Tourism Awareness Campaign",  # filler
    ],
    "Crocs": [
        "Conquistando el mundo con Hypebeast", "Summer Collab Drop",  # filler
    ],
    "PETA": [
        "Good Sh*t", "Awareness Series",  # filler
    ],
    "Kia Europe": [
        "El movimiento responsable", "EV Launch Campaign",  # filler
    ],
}

# Hierarchia kosztow: Cost Type (poziom 1) -> Cost Group (poziom 2) -> Cost Category (poziom 3, leaf)
# base_monthly_share = orientacyjny udzial danej kategorii w miesiecznym koszcie centrum (przed szumem)
CATEGORY_TREE = {
    "Labor Cost": {
        "Salary & Wages": {
            "Salary": 1.00,
            "Fringe": 0.18,
            "Pension": 0.08,
            "Bonus": 0.10,
        },
        "Employee Cost": {
            "T&E": 0.06,
            "Auto Lease": 0.05,
            "Other Benefits": 0.04,
        },
    },
    "Non-Labor Cost": {
        "Professional Fees": {
            "Marketing Fees": 0.15,
            "Other Fees": 0.05,
            "Repairs": 0.03,
        },
        "IT Expenses": {
            "Licenses": 0.09,
            "IT Outsourcing": 0.12,
            "Other Licenses": 0.03,
        },
        "Channel Fees": {
            "TikTok": 0.08,
            "YouTube": 0.10,
            "Instagram": 0.12,
        },
    },
}


def build_category_dim():
    """Splaszcza CATEGORY_TREE do tabeli wymiarowej Dim_Category (13 wierszy lisci)."""
    rows = []
    cat_id = 1
    for cost_type, groups in CATEGORY_TREE.items():
        for cost_group, categories in groups.items():
            for cost_category, base_share in categories.items():
                rows.append({
                    "category_id": cat_id,
                    "cost_type": cost_type,          # poziom 1 - najmniej szczegolowy
                    "cost_group": cost_group,        # poziom 2
                    "cost_category": cost_category,  # poziom 3 - lisc, na tym poziomie ksiegowane sa koszty
                    "base_share": base_share,
                })
                cat_id += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. DIM_COST_CENTER
# ---------------------------------------------------------------------------

def build_cost_center_dim(n_cost_centers: int, rng: np.random.Generator):
    rows = []
    for i in range(1, n_cost_centers + 1):
        functional_area = rng.choice(FUNCTIONAL_AREAS)
        country_finance = rng.choice(COUNTRIES)
        # w wiekszosci przypadkow country_physical = country_finance,
        # ale czasem centrum jest fizycznie gdzie indziej (np. shared service center)
        country_physical = country_finance if rng.random() > 0.15 else rng.choice(COUNTRIES)

        budget_owner = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        stakeholder = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"

        rows.append({
            "cost_center_id": f"CC{i:04d}",
            "functional_area": functional_area,
            "country_finance": country_finance,
            "country_physical": country_physical,
            "budget_owner": budget_owner,
            "stakeholder": stakeholder,
            # baza wielkosci centrum kosztow - wplywa na skale kwot (male / srednie / duze CC)
            "size_factor": rng.choice([0.6, 1.0, 1.0, 1.6, 2.4], p=[0.15, 0.35, 0.25, 0.15, 0.10]),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2b. DIM_CLIENT / DIM_PROJECT (snowflake: projekt -> klient)
# ---------------------------------------------------------------------------

def build_client_dim():
    rows = []
    for i, client_name in enumerate(CLIENT_PROJECTS.keys(), start=1):
        rows.append({
            "client_id": f"CL{i:03d}",
            "client_name": client_name,
        })
    return pd.DataFrame(rows)


def build_project_dim(clients: pd.DataFrame):
    client_id_map = dict(zip(clients["client_name"], clients["client_id"]))
    rows = []
    proj_num = 1
    for client_name, project_names in CLIENT_PROJECTS.items():
        for project_name in project_names:
            rows.append({
                "project_id": f"PRJ{proj_num:04d}",
                "project_name": project_name,
                "client_id": client_id_map[client_name],
            })
            proj_num += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. DIM_DATE
# ---------------------------------------------------------------------------

def build_date_dim(start: str, end: str):
    """
    Buduje PELNY kalendarz dzienny (jeden wiersz na kazdy dzien, bez luk).

    Wazne: Power BI wymaga, zeby tabela oznaczona jako "Date table" nie miala
    luk w kolumnie daty - jeden wiersz na miesiac (np. tylko 2024-01-01,
    2024-02-01, ...) zostanie odrzucony, bo brakuje dni 02-28 stycznia itd.
    Dlatego generujemy dzienna siatke od pierwszego do ostatniego dnia zakresu,
    a fact_costs (dane miesieczne) laczy sie z pierwszym dniem kazdego miesiaca.
    """
    start_period = pd.Period(start, freq="M")
    end_period = pd.Period(end, freq="M")
    all_days = pd.date_range(start_period.start_time, end_period.end_time, freq="D")

    rows = []
    for i, ts in enumerate(all_days, start=1):
        p = ts.to_period("M")
        rows.append({
            "date_id": i,
            "date": ts.date(),
            "year": ts.year,
            "quarter": f"Q{ts.quarter}",
            "month_number": ts.month,
            "month_name": calendar.month_name[ts.month],
            "year_month": str(p),               # np. "2024-01"
            "fiscal_year": ts.year,              # zakladamy fiscal year = calendar year (mozna zmienic)
            "day_of_month": ts.day,
            "is_month_start": ts.day == 1,       # do latwego filtrowania / joinowania faktow miesiecznych
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. FACT_COSTS
# ---------------------------------------------------------------------------

def seasonality_factor(cost_category: str, month: int) -> float:
    """Zwraca mnoznik sezonowy dla danej kategorii i miesiaca (1-12)."""
    # Bonus wyplacany gl. w grudniu i marcu (roczne premie)
    if cost_category == "Bonus":
        return {12: 3.5, 3: 2.5}.get(month, 0.5)
    # T&E wyzsze wiosna/jesienia (sezon konferencji), nizsze latem/zima
    if cost_category == "T&E":
        return {6: 1.4, 7: 0.5, 8: 0.5, 9: 1.4, 10: 1.3, 12: 0.6}.get(month, 1.0)
    # Licencje IT - odnowienia gl. w styczniu
    if cost_category in ("Licenses", "Other Licenses"):
        return 2.2 if month == 1 else 0.9
    # Marketing - kampanie wiosenne i przedswiateczne (Q4)
    if cost_category == "Marketing Fees":
        return {11: 1.5, 12: 1.3, 4: 1.2, 5: 1.2}.get(month, 0.85)
    # Repairs - wiecej latem (przegledy/konserwacje)
    if cost_category == "Repairs":
        return {6: 1.3, 7: 1.4, 8: 1.3}.get(month, 0.9)
    # Channel fees (media placowe) - silny wzrost w Q4 (kampanie swiateczne) i wrzesniu (back-to-school)
    if cost_category in ("TikTok", "YouTube", "Instagram"):
        return {11: 1.6, 12: 1.7, 9: 1.3}.get(month, 0.85)
    return 1.0


def build_fact_costs(cost_centers: pd.DataFrame, categories: pd.DataFrame,
                      dates: pd.DataFrame, projects: pd.DataFrame,
                      rng: np.random.Generator):
    rows = []
    project_ids = projects["project_id"].tolist()

    # kazda kategoria ma swoja bazowa kwote miesieczna (przed size_factor i sezonowoscia)
    # kazda kategoria ma swoja bazowa kwote miesieczna (przed size_factor i sezonowoscia)
    # WARTOSCI PRZESKALOWANE pod realistyczny rozklad kosztow agencji marketingowej:
    # Labor Cost ~50%, Channel Fees ~30%, Professional Fees ~12%, IT Expenses ~8%
    # (patrz komentarz w README / historia zmian - pierwotne wartosci odzwierciedlaly
    # generyczna firme, nie agencje, dla ktorej media spend jest kluczowa pozycja)
    base_amount_map = {
        "Salary": 4050, "Fringe": 710, "Pension": 330, "Bonus": 455,
        "T&E": 255, "Auto Lease": 230, "Other Benefits": 150,
        "Marketing Fees": 6025, "Other Fees": 2010, "Repairs": 1255,
        "Licenses": 2490, "IT Outsourcing": 3380, "Other Licenses": 890,
        "TikTok": 6320, "YouTube": 7675, "Instagram": 9030,
    }

    # trend roczny per cost_type - np. IT rosnie szybciej niz przecietny koszt
    annual_growth_map = {
        "Salary": 0.045, "Fringe": 0.045, "Pension": 0.03, "Bonus": 0.02,
        "T&E": 0.02, "Auto Lease": 0.01, "Other Benefits": 0.02,
        "Marketing Fees": 0.03, "Other Fees": 0.02, "Repairs": 0.02,
        "Licenses": 0.08, "IT Outsourcing": 0.09, "Other Licenses": 0.06,
        "TikTok": 0.14, "YouTube": 0.10, "Instagram": 0.11,
    }

    # fact_costs jest na poziomie miesiecznym, wiec do kazdego miesiaca przypisujemy
    # date_id odpowiadajacy PIERWSZEMU dniowi tego miesiaca w dziennym kalendarzu
    month_grain = dates[dates["is_month_start"]].sort_values("date").reset_index(drop=True)
    first_year = month_grain["year"].min()

    for _, cc in cost_centers.iterrows():
        # kazde centrum ma losowa "kondycje budzetowa" - tendencje do przekraczania/oszczedzania
        cc_bias = rng.normal(loc=0.0, scale=0.06)  # np. +6% = centrum systematycznie przekracza budzet

        for _, cat in categories.iterrows():
            base_amount = base_amount_map[cat["cost_category"]] * cat["base_share"] * cc["size_factor"]
            growth = annual_growth_map[cat["cost_category"]]
            is_non_labor = cat["cost_type"] == "Non-Labor Cost"

            for _, d in month_grain.iterrows():
                years_elapsed = d["year"] - first_year
                trend_factor = (1 + growth) ** years_elapsed
                season = seasonality_factor(cat["cost_category"], d["month_number"])

                budget = base_amount * trend_factor * season
                # szum losowy +/- 8% na actual wzgledem budgetu, plus systematyczny bias centrum
                noise = rng.normal(loc=cc_bias, scale=0.08)
                actual = max(budget * (1 + noise), 0)

                # forecast = srednia wazona miedzy budget a actual z niepewnoscia (typowy FP&A rolling forecast)
                forecast_noise = rng.normal(loc=0.0, scale=0.05)
                forecast = max((0.5 * budget + 0.5 * actual) * (1 + forecast_noise), 0)

                if not is_non_labor:
                    # Labor Cost (wynagrodzenia) nie sa alokowane do konkretnego projektu klienta
                    rows.append({
                        "cost_center_id": cc["cost_center_id"],
                        "category_id": cat["category_id"],
                        "date_id": d["date_id"],
                        "project_id": None,
                        "amount_budget": round(budget, 2),
                        "amount_actual": round(actual, 2),
                        "amount_forecast": round(forecast, 2),
                    })
                else:
                    # Non-Labor Cost: rozbijamy kwote miesieczna na 1-3 losowo wybrane
                    # projekty klientow (wazone udzialy), zeby zasymulowac ksiegowanie
                    # kosztow "billable" na konkretne kampanie
                    n_splits = rng.choice([1, 2, 3], p=[0.6, 0.3, 0.1])
                    chosen_projects = rng.choice(project_ids, size=n_splits, replace=False)
                    weights = rng.dirichlet(np.ones(n_splits))

                    for proj_id, w in zip(chosen_projects, weights):
                        rows.append({
                            "cost_center_id": cc["cost_center_id"],
                            "category_id": cat["category_id"],
                            "date_id": d["date_id"],
                            "project_id": proj_id,
                            "amount_budget": round(budget * w, 2),
                            "amount_actual": round(actual * w, 2),
                            "amount_forecast": round(forecast * w, 2),
                        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4b. FACT_REVENUE
# ---------------------------------------------------------------------------

def build_fact_revenue(fact_costs: pd.DataFrame, dim_project: pd.DataFrame,
                        rng: np.random.Generator):
    """
    Buduje tabele faktow przychodowych na poziomie klient x projekt x miesiac.

    Logika: przychod wywodzi sie z kosztu bezposredniego (Non-Labor) danego
    projektu w danym miesiacu, pomnozonego przez marze charakterystyczna dla
    klienta (rozne konta maja rozna rentownosc - bardzo realistyczne w
    agencjach), plus niezalezny szum, zeby przychod nie byl idealnie
    skorelowany z kosztem (w rzeczywistosci sprzedaz/fakturowanie nie
    podaza 1:1 za kosztem w danym miesiacu).
    """
    # agregujemy koszt bezposredni (non-labor) per projekt x miesiac
    project_costs = (
        fact_costs[fact_costs["project_id"].notna()]
        .groupby(["project_id", "date_id"], as_index=False)
        .agg(cost_budget=("amount_budget", "sum"), cost_actual=("amount_actual", "sum"))
    )

    project_costs = project_costs.merge(
        dim_project[["project_id", "client_id"]], on="project_id", how="left"
    )

    # kazdy klient ma swoja bazowa marze - stala w czasie, ale rozna miedzy klientami
    client_ids = dim_project["client_id"].unique()
    client_margin = {
        cid: float(np.clip(rng.normal(loc=0.30, scale=0.09), 0.12, 0.55))
        for cid in client_ids
    }

    rows = []
    revenue_id = 1
    for _, r in project_costs.iterrows():
        margin = client_margin[r["client_id"]]
        revenue_budget = r["cost_budget"] * (1 + margin)

        # szum niezalezny od odchylenia kosztu - symuluje realia fakturowania
        revenue_noise = rng.normal(loc=0.0, scale=0.10)
        revenue_actual = max(revenue_budget * (1 + revenue_noise), 0)

        forecast_noise = rng.normal(loc=0.0, scale=0.06)
        revenue_forecast = max((0.5 * revenue_budget + 0.5 * revenue_actual) * (1 + forecast_noise), 0)

        rows.append({
            "revenue_id": revenue_id,
            "client_id": r["client_id"],
            "project_id": r["project_id"],
            "date_id": r["date_id"],
            "amount_revenue_budget": round(revenue_budget, 2),
            "amount_revenue_actual": round(revenue_actual, 2),
            "amount_revenue_forecast": round(revenue_forecast, 2),
        })
        revenue_id += 1

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5. MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generator danych FP&A Cost Center Dashboard")
    parser.add_argument("--n-cost-centers", type=int, default=25)
    parser.add_argument("--start", type=str, default="2024-01")
    parser.add_argument("--end", type=str, default="2025-12")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=os.path.join(os.path.dirname(__file__), "..", "raw"))
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    os.makedirs(args.out, exist_ok=True)

    dim_category = build_category_dim()
    dim_cost_center = build_cost_center_dim(args.n_cost_centers, rng)
    dim_date = build_date_dim(args.start, args.end)
    dim_client = build_client_dim()
    dim_project = build_project_dim(dim_client)
    fact_costs = build_fact_costs(dim_cost_center, dim_category, dim_date, dim_project, rng)
    fact_revenue = build_fact_revenue(fact_costs, dim_project, rng)

    dim_category.to_csv(os.path.join(args.out, "dim_category.csv"), index=False)
    dim_cost_center.to_csv(os.path.join(args.out, "dim_cost_center.csv"), index=False)
    dim_date.to_csv(os.path.join(args.out, "dim_date.csv"), index=False)
    dim_client.to_csv(os.path.join(args.out, "dim_client.csv"), index=False)
    dim_project.to_csv(os.path.join(args.out, "dim_project.csv"), index=False)
    fact_costs.to_csv(os.path.join(args.out, "fact_costs.csv"), index=False)
    fact_revenue.to_csv(os.path.join(args.out, "fact_revenue.csv"), index=False)

    print(f"Cost centers : {len(dim_cost_center):>6}")
    print(f"Categories   : {len(dim_category):>6}")
    print(f"Months       : {len(dim_date):>6}")
    print(f"Clients      : {len(dim_client):>6}")
    print(f"Projects     : {len(dim_project):>6}")
    print(f"Fact rows    : {len(fact_costs):>6}")
    print(f"Revenue rows : {len(fact_revenue):>6}")
    print(f"Zapisano do  : {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
