"""
scoring.py - Punctaj ponderat in stil broker, cu profile diferite.

Diferenta fata de scorul simplu (media egala a tuturor indicatorilor):
 - fiecare CATEGORIE are o pondere (ex. profitabilitate 30%, tehnic 10%)
 - in interiorul categoriei, indicatorii-cheie au greutate mai mare (stele 1-3)
 - se calculeaza intai scorul fiecarei categorii, apoi media ponderata pe categorii

Profilul schimba ponderile pe categorii (termen lung vs trader vs echilibrat).
"""

VERDICT_POINTS = {"BUY": 1.0, "NEUTRU": 0.5, "RISC": 0.0}

# Ponderea categoriilor (in %) pentru fiecare profil de investitor
PROFILES = {
    "Echilibrat": {
        "Evaluare": 20, "Profitabilitate": 30, "Sanatate financiara": 25,
        "Crestere": 15, "Tehnic": 10,
    },
    "Investitor pe termen lung": {
        "Evaluare": 22, "Profitabilitate": 30, "Sanatate financiara": 28,
        "Crestere": 15, "Tehnic": 5,
    },
    "Trader (tehnic)": {
        "Evaluare": 15, "Profitabilitate": 12, "Sanatate financiara": 8,
        "Crestere": 10, "Tehnic": 55,
    },
}

# Importanta fiecarui indicator in interiorul categoriei (1-3 stele = greutate)
INDICATOR_STARS = {
    # Evaluare
    "P/E (trailing)": 3, "EV/EBITDA": 3, "PEG": 2, "P/B (Price/Book)": 2,
    "Dividend Yield": 2, "Forward P/E": 2, "P/S (Price/Sales)": 1,
    "EV/Sales": 1, "Payout Ratio": 1,
    # Profitabilitate
    "ROE (Return on Equity)": 3, "Marja neta (Net Margin)": 3,
    "ROA (Return on Assets)": 2, "Marja operationala": 2,
    "Marja bruta (Gross Margin)": 1, "Marja EBITDA": 1,
    # Sanatate financiara
    "Net Debt / EBITDA": 3, "Debt/Equity": 3, "Free Cash Flow": 3,
    "Current Ratio": 2, "Quick Ratio": 2,
    # Crestere
    "Crestere profit (EPS YoY)": 3, "Crestere venituri (YoY)": 2,
    # Tehnic
    "Structura HH/HL": 2, "Medii mobile (SMA50/200)": 2, "RSI (14)": 1,
    "Beta": 1, "Pozitie in interval 52 sapt.": 1,
}


def score_to_verdict(score):
    if score is None:
        return "N/A"
    if score >= 65:
        return "BUY"
    if score >= 40:
        return "NEUTRU"
    return "RISC"


def compute_weighted_score(indicators, profile_key):
    """
    indicators: lista de dict cu 'group', 'name', 'verdict'.
    Returneaza (scor 0-100 sau None, verdict, detalii_pe_categorii).
    """
    cat_weights = PROFILES[profile_key]

    # Grupeaza punctele pe categorie, folosind stelele ca greutate interna
    by_group = {}
    for ind in indicators:
        pts = VERDICT_POINTS.get(ind["verdict"])
        if pts is None:  # N/A - exclus
            continue
        star = INDICATOR_STARS.get(ind["name"], 1)
        by_group.setdefault(ind["group"], []).append((star, pts))

    # Scorul fiecarei categorii (0..1)
    cat_scores = {}
    for group, items in by_group.items():
        den = sum(s for s, _ in items)
        if den > 0:
            cat_scores[group] = sum(s * p for s, p in items) / den

    # Media ponderata pe categorii (doar categoriile prezente)
    num = sum(cat_weights.get(g, 0) * cs for g, cs in cat_scores.items())
    den = sum(cat_weights.get(g, 0) for g in cat_scores)
    score = round(num / den * 100, 1) if den > 0 else None

    return score, score_to_verdict(score), {g: round(s * 100, 1) for g, s in cat_scores.items()}


def all_profiles_scores(indicators):
    """Returneaza {profil: (scor, verdict)} pentru toate profilele."""
    out = {}
    for p in PROFILES:
        s, v, _ = compute_weighted_score(indicators, p)
        out[p] = (s, v)
    return out
