"""
analyzer.py - Logica de analiza a indicatorilor pentru o firma.
Aduce date live de pe Yahoo Finance (yfinance) si evalueaza fiecare indicator:
 - valoarea curenta
 - intervalul de referinta
 - verdict: BUY / NEUTRU / RISC
 - scor numeric pentru clasament

ATENTIE: instrument educational, NU consultanta financiara.
"""

import numpy as np
import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# Praguri de evaluare. Pentru fiecare indicator definim cum se traduce
# valoarea intr-un verdict. "higher_better" spune daca o valoare mare e buna.
# ---------------------------------------------------------------------------

VERDICT_BUY = "BUY"
VERDICT_NEUTRU = "NEUTRU"
VERDICT_RISC = "RISC"
VERDICT_NA = "N/A"

# scor pentru clasament
SCORE = {VERDICT_BUY: 1.0, VERDICT_NEUTRU: 0.5, VERDICT_RISC: 0.0, VERDICT_NA: None}


def _verdict_from_bands(value, good_max=None, bad_min=None,
                        good_min=None, bad_max=None, higher_better=False):
    """
    Decide verdictul pe baza unor benzi.
    Doua moduri:
      - higher_better=False (valoare mica = bine): folosim good_max / bad_min
      - higher_better=True  (valoare mare = bine): folosim good_min / bad_max
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return VERDICT_NA
    if not higher_better:
        if good_max is not None and value <= good_max:
            return VERDICT_BUY
        if bad_min is not None and value >= bad_min:
            return VERDICT_RISC
        return VERDICT_NEUTRU
    else:
        if good_min is not None and value >= good_min:
            return VERDICT_BUY
        if bad_max is not None and value <= bad_max:
            return VERDICT_RISC
        return VERDICT_NEUTRU


def _pct(value):
    """Inmulteste cu 100 daca valoarea pare a fi fractie (yfinance da margini ca 0.23)."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return value * 100.0


# ---------------------------------------------------------------------------
# Analiza tehnica: HH/HL si trend
# ---------------------------------------------------------------------------

def _swing_points(series, window=5):
    """Identifica swing highs si swing lows pe baza unei ferestre locale."""
    highs, lows = [], []
    vals = series.values
    n = len(vals)
    for i in range(window, n - window):
        seg = vals[i - window:i + window + 1]
        if vals[i] == seg.max():
            highs.append((i, vals[i]))
        if vals[i] == seg.min():
            lows.append((i, vals[i]))
    return highs, lows


def analyze_trend_hh_hl(hist):
    """
    Analizeaza structura HH/HL (Higher Highs / Higher Lows) pe pretul de inchidere.
    Returneaza un dict cu structura si verdict.
    """
    if hist is None or hist.empty or len(hist) < 30:
        return {"structure": "N/A", "verdict": VERDICT_NA, "detail": "Date insuficiente"}

    close = hist["Close"].dropna()
    highs, lows = _swing_points(close, window=5)

    last_highs = [v for _, v in highs[-3:]]
    last_lows = [v for _, v in lows[-3:]]

    hh = len(last_highs) >= 2 and all(
        last_highs[i] > last_highs[i - 1] for i in range(1, len(last_highs)))
    hl = len(last_lows) >= 2 and all(
        last_lows[i] > last_lows[i - 1] for i in range(1, len(last_lows)))
    lh = len(last_highs) >= 2 and all(
        last_highs[i] < last_highs[i - 1] for i in range(1, len(last_highs)))
    ll = len(last_lows) >= 2 and all(
        last_lows[i] < last_lows[i - 1] for i in range(1, len(last_lows)))

    if hh and hl:
        structure = "HH + HL (trend ascendent)"
        verdict = VERDICT_BUY
    elif lh and ll:
        structure = "LH + LL (trend descendent)"
        verdict = VERDICT_RISC
    elif hh or hl:
        structure = "Partial ascendent"
        verdict = VERDICT_NEUTRU
    elif lh or ll:
        structure = "Partial descendent"
        verdict = VERDICT_NEUTRU
    else:
        structure = "Lateral / neclar"
        verdict = VERDICT_NEUTRU

    return {
        "structure": structure,
        "verdict": verdict,
        "last_highs": [round(x, 2) for x in last_highs],
        "last_lows": [round(x, 2) for x in last_lows],
    }


def _atr(hist, period=14):
    """Average True Range - masura volatilitatii, pentru calcul SL/TP."""
    if hist is None or hist.empty or len(hist) < period + 1:
        return None
    high = hist["High"]
    low = hist["Low"]
    close = hist["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return float(atr) if not np.isnan(atr) else None


def compute_returns(ticker_obj, current_price):
    """
    Randamentul pretului pe mai multe orizonturi de timp (inclusiv 6 ani).
    Returneaza lista de dict: {perioada, randament_total_%, randament_anual_%}.
    """
    horizons = {"1 luna": "1mo", "6 luni": "6mo", "1 an": "1y",
                "3 ani": "3y", "5 ani": "5y", "6 ani": "6y"}
    years = {"1 luna": 1/12, "6 luni": 0.5, "1 an": 1,
             "3 ani": 3, "5 ani": 5, "6 ani": 6}
    out = []
    try:
        full = ticker_obj.history(period="max")
    except Exception:
        full = pd.DataFrame()
    if full is None or full.empty or current_price is None:
        return out
    close = full["Close"].dropna()
    last = close.iloc[-1]
    idx = close.index
    for label, _code in horizons.items():
        delta_days = int(years[label] * 365)
        target = idx[-1] - pd.Timedelta(days=delta_days)
        past = close[idx <= target]
        if past.empty:
            out.append({"perioada": label, "total": None, "anual": None,
                        "disponibil": False})
            continue
        start = past.iloc[-1]
        if start == 0:
            continue
        total = (last / start - 1) * 100
        yrs = years[label]
        annual = ((last / start) ** (1 / yrs) - 1) * 100 if yrs >= 1 else None
        out.append({"perioada": label, "total": round(total, 1),
                    "anual": round(annual, 1) if annual is not None else None,
                    "disponibil": True})
    return out


def compute_trade_plan(hist, trend, current_price):
    """
    Moment de intrare in functie de structura HH/HL + niveluri TP (take profit)
    si SL (stop loss) bazate pe swing points si ATR.
    Raport risc/recompensa tinta ~ 1:2.
    """
    plan = {"entry_signal": "N/A", "entry_zone": None, "support": None,
            "resistance": None, "stop_loss": None, "take_profit": None,
            "risc_reward": None, "atentionare": None}

    if hist is None or hist.empty or current_price is None:
        return plan

    close = hist["Close"].dropna()
    highs, lows = _swing_points(close, window=5)
    atr = _atr(hist) or (current_price * 0.03)

    # Suport REAL = cel mai apropiat swing low SUB pretul curent (nu micro-swingul recent).
    lows_below = [v for _, v in lows if v < current_price * 0.995]
    support = max(lows_below) if lows_below else round(close.min(), 4)
    # Rezistenta REALA = cel mai apropiat swing high PESTE pretul curent.
    highs_above = [v for _, v in highs if v > current_price * 1.005]
    resistance = min(highs_above) if highs_above else round(close.max(), 4)

    # Daca pretul e la maxime si nu exista rezistenta deasupra -> proiectam o tinta.
    if resistance <= current_price:
        resistance = current_price + 3 * atr

    plan["support"] = round(support, 2)
    plan["resistance"] = round(resistance, 2)

    verdict = trend.get("verdict")

    # --- Zona ideala de intrare: mereu calculata, in jurul suportului ---
    entry_low = support
    entry_high = support + atr
    plan["entry_zone"] = (round(float(entry_low), 2), round(float(entry_high), 2))

    # SL sub suport; TP la rezistenta (cu raport R/R real)
    sl = support - atr
    risk = current_price - sl
    tp_rr = current_price + 2 * risk          # tinta la raport 1:2
    tp = min(resistance, tp_rr) if resistance > current_price else tp_rr
    plan["stop_loss"] = round(sl, 2)
    plan["take_profit"] = round(tp, 2)
    if risk > 0:
        rr = (tp - current_price) / risk
        plan["risc_reward"] = f"1:{rr:.1f}"

    # --- Semnal de intrare in functie de structura + pozitia fata de zona ---
    in_zone = entry_low <= current_price <= entry_high * 1.02
    near_resist = current_price >= resistance * 0.98
    if verdict == VERDICT_RISC:
        plan["entry_signal"] = "EVITA - trend descendent (LH+LL). Fara intrare long."
    elif verdict == VERDICT_BUY:
        if in_zone:
            plan["entry_signal"] = "INTRARE BUNA - trend ascendent + pret la suport (Higher Low)."
        elif near_resist:
            plan["entry_signal"] = "ASTEAPTA pullback - trend bun, dar pretul e la rezistenta."
        else:
            plan["entry_signal"] = "INTRARE POSIBILA - trend ascendent, intra in zona verde la pullback."
    else:  # NEUTRU / lateral
        if in_zone:
            plan["entry_signal"] = "INTRARE SPECULATIVA - pret la suport, dar fara confirmare HH+HL."
        elif near_resist:
            plan["entry_signal"] = "ASTEAPTA - pret la rezistenta, fara confirmare de trend."
        else:
            plan["entry_signal"] = "ASTEAPTA pullback spre zona verde de intrare (suport)."

    # --- Atentionare prag TP/SL ---
    if plan["stop_loss"] and current_price:
        dist_sl = (current_price - plan["stop_loss"]) / current_price * 100
        if dist_sl < 3:
            plan["atentionare"] = (f"⚠️ ATENTIE: pretul e foarte aproape de Stop Loss "
                                   f"({dist_sl:.1f}% distanta) - risc de iesire in pierdere.")
    if plan["take_profit"] and current_price and not plan["atentionare"]:
        dist_tp = (plan["take_profit"] - current_price) / current_price * 100
        if dist_tp < 3:
            plan["atentionare"] = (f"⚠️ ATENTIE: pretul e aproape de Take Profit "
                                   f"({dist_tp:.1f}% distanta) - considera luarea profitului.")
    return plan


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.dropna().empty else None


def _sma(close, period):
    if len(close) < period:
        return None
    return close.rolling(period).mean().iloc[-1]


# ---------------------------------------------------------------------------
# Functia principala de analiza a unei firme
# ---------------------------------------------------------------------------

def _robust_info(tk, tries=3):
    """Yahoo limiteaza IP-urile de datacenter; reincercam de cateva ori."""
    import time
    for i in range(tries):
        try:
            info = tk.info or {}
            if info and (info.get("currentPrice") or info.get("regularMarketPrice")
                         or info.get("longName")):
                return info
        except Exception:
            pass
        time.sleep(1.2 * (i + 1))
    return {}


def _stmt_lookup(df, *labels):
    """Cauta o linie (dupa eticheta) in income_stmt/financials si ia valoarea cea mai recenta."""
    if df is None or getattr(df, "empty", True):
        return None
    for label in labels:
        if label in df.index:
            row = df.loc[label].dropna()
            if not row.empty:
                try:
                    return float(row.iloc[0])
                except (TypeError, ValueError):
                    return None
    return None


def analyze_company(ticker_symbol):
    """
    Returneaza un dict structurat cu toti indicatorii unei firme.
    """
    tk = yf.Ticker(ticker_symbol)
    info = _robust_info(tk)

    try:
        hist = tk.history(period="1y")
    except Exception:
        hist = pd.DataFrame()

    # Fallback pentru fundamentale (profit, EBITDA, venituri) cand info e gol/limitat,
    # folosind situatiile financiare (alt endpoint Yahoo, mai rar blocat).
    fin = None
    if not info.get("netIncomeToCommon") or not info.get("ebitda") or not info.get("totalRevenue"):
        try:
            fin = tk.income_stmt
        except Exception:
            fin = None
    fb_net = _stmt_lookup(fin, "Net Income", "Net Income Common Stockholders")
    fb_ebitda = _stmt_lookup(fin, "EBITDA", "Normalized EBITDA")
    fb_rev = _stmt_lookup(fin, "Total Revenue", "Operating Revenue")

    # Bilant + cashflow pentru fallback la sanatatea financiara
    try:
        bs = tk.balance_sheet
    except Exception:
        bs = None
    try:
        cf = tk.cashflow
    except Exception:
        cf = None
    bs_equity = _stmt_lookup(bs, "Stockholders Equity", "Total Equity Gross Minority Interest",
                             "Common Stock Equity")
    bs_total_debt = _stmt_lookup(bs, "Total Debt")
    bs_cur_assets = _stmt_lookup(bs, "Current Assets", "Total Current Assets")
    bs_cur_liab = _stmt_lookup(bs, "Current Liabilities", "Total Current Liabilities")
    bs_inventory = _stmt_lookup(bs, "Inventory")
    cf_fcf = _stmt_lookup(cf, "Free Cash Flow")
    cf_ocf = _stmt_lookup(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
    cf_capex = _stmt_lookup(cf, "Capital Expenditure")

    close = hist["Close"].dropna() if (hist is not None and not hist.empty) else pd.Series(dtype=float)

    indicators = []

    def add(name, group, value, fmt, verdict, ref):
        indicators.append({
            "name": name, "group": group, "value": value,
            "fmt": fmt, "verdict": verdict, "ref": ref,
        })

    # ---------------- A. EVALUARE / VALUATION ----------------
    pe = info.get("trailingPE")
    add("P/E (trailing)", "Evaluare", pe, "x",
        _verdict_from_bands(pe, good_max=15, bad_min=30),
        "BUY < 15 | NEUTRU 15-30 | RISC > 30")

    fpe = info.get("forwardPE")
    add("Forward P/E", "Evaluare", fpe, "x",
        _verdict_from_bands(fpe, good_max=15, bad_min=30),
        "BUY < 15 | NEUTRU 15-30 | RISC > 30")

    peg = info.get("pegRatio") or info.get("trailingPegRatio")
    add("PEG", "Evaluare", peg, "x",
        _verdict_from_bands(peg, good_max=1, bad_min=2),
        "BUY < 1 | NEUTRU 1-2 | RISC > 2")

    pb = info.get("priceToBook")
    add("P/B (Price/Book)", "Evaluare", pb, "x",
        _verdict_from_bands(pb, good_max=1.5, bad_min=4),
        "BUY < 1.5 | NEUTRU 1.5-4 | RISC > 4")

    ps = info.get("priceToSalesTrailing12Months")
    add("P/S (Price/Sales)", "Evaluare", ps, "x",
        _verdict_from_bands(ps, good_max=2, bad_min=6),
        "BUY < 2 | NEUTRU 2-6 | RISC > 6")

    ev_ebitda = info.get("enterpriseToEbitda")
    add("EV/EBITDA", "Evaluare", ev_ebitda, "x",
        _verdict_from_bands(ev_ebitda, good_max=8, bad_min=15),
        "BUY < 8 | NEUTRU 8-15 | RISC > 15")

    ev_rev = info.get("enterpriseToRevenue")
    add("EV/Sales", "Evaluare", ev_rev, "x",
        _verdict_from_bands(ev_rev, good_max=2, bad_min=6),
        "BUY < 2 | NEUTRU 2-6 | RISC > 6")

    dy = _pct(info.get("dividendYield")) if (info.get("dividendYield") or 0) < 1 else info.get("dividendYield")
    add("Dividend Yield", "Evaluare", dy, "%",
        _verdict_from_bands(dy, good_min=4, bad_max=1, higher_better=True),
        "BUY > 4% | NEUTRU 1-4% | RISC < 1%")

    payout = _pct(info.get("payoutRatio"))
    add("Payout Ratio", "Evaluare", payout, "%",
        _verdict_from_bands(payout, good_max=60, bad_min=100),
        "BUY < 60% | NEUTRU 60-100% | RISC > 100%")

    # ---------------- B. PROFITABILITATE ----------------
    net_margin = _pct(info.get("profitMargins"))
    add("Marja neta (Net Margin)", "Profitabilitate", net_margin, "%",
        _verdict_from_bands(net_margin, good_min=10, bad_max=2, higher_better=True),
        "BUY > 10% | NEUTRU 2-10% | RISC < 2%")

    gross_margin = _pct(info.get("grossMargins"))
    add("Marja bruta (Gross Margin)", "Profitabilitate", gross_margin, "%",
        _verdict_from_bands(gross_margin, good_min=40, bad_max=15, higher_better=True),
        "BUY > 40% | NEUTRU 15-40% | RISC < 15%")

    op_margin = _pct(info.get("operatingMargins"))
    add("Marja operationala", "Profitabilitate", op_margin, "%",
        _verdict_from_bands(op_margin, good_min=15, bad_max=3, higher_better=True),
        "BUY > 15% | NEUTRU 3-15% | RISC < 3%")

    ebitda_margin = _pct(info.get("ebitdaMargins"))
    add("Marja EBITDA", "Profitabilitate", ebitda_margin, "%",
        _verdict_from_bands(ebitda_margin, good_min=20, bad_max=8, higher_better=True),
        "BUY > 20% | NEUTRU 8-20% | RISC < 8%")

    roe = _pct(info.get("returnOnEquity"))
    add("ROE (Return on Equity)", "Profitabilitate", roe, "%",
        _verdict_from_bands(roe, good_min=15, bad_max=5, higher_better=True),
        "BUY > 15% | NEUTRU 5-15% | RISC < 5%")

    roa = _pct(info.get("returnOnAssets"))
    add("ROA (Return on Assets)", "Profitabilitate", roa, "%",
        _verdict_from_bands(roa, good_min=7, bad_max=2, higher_better=True),
        "BUY > 7% | NEUTRU 2-7% | RISC < 2%")

    # ---------------- C. SANATATE FINANCIARA ----------------
    # yfinance da debtToEquity ca PROCENT (ex 199.3 = 1.99x). Impartim mereu la 100.
    de = info.get("debtToEquity")
    if de is not None:
        de = de / 100.0
    # Fallback din bilant: Total Debt / Capital propriu
    if de is None and bs_total_debt and bs_equity:
        de = bs_total_debt / bs_equity if bs_equity != 0 else None
    add("Debt/Equity", "Sanatate financiara", de, "x",
        _verdict_from_bands(de, good_max=0.5, bad_min=2),
        "BUY < 0.5 | NEUTRU 0.5-2 | RISC > 2")

    current_ratio = info.get("currentRatio")
    if current_ratio is None and bs_cur_assets and bs_cur_liab:
        current_ratio = bs_cur_assets / bs_cur_liab if bs_cur_liab != 0 else None
    add("Current Ratio", "Sanatate financiara", current_ratio, "x",
        _verdict_from_bands(current_ratio, good_min=1.5, bad_max=1, higher_better=True),
        "BUY > 1.5 | NEUTRU 1-1.5 | RISC < 1 (N/A la banci)")

    quick_ratio = info.get("quickRatio")
    if quick_ratio is None and bs_cur_assets and bs_cur_liab:
        quick_assets = bs_cur_assets - (bs_inventory or 0)
        quick_ratio = quick_assets / bs_cur_liab if bs_cur_liab != 0 else None
    add("Quick Ratio", "Sanatate financiara", quick_ratio, "x",
        _verdict_from_bands(quick_ratio, good_min=1, bad_max=0.5, higher_better=True),
        "BUY > 1 | NEUTRU 0.5-1 | RISC < 0.5 (N/A la banci)")

    # Net Debt / EBITDA
    total_debt = info.get("totalDebt") or bs_total_debt
    cash = info.get("totalCash")
    ebitda = info.get("ebitda") or fb_ebitda
    nd_ebitda = None
    if total_debt is not None and ebitda and ebitda != 0:
        net_debt = total_debt - (cash or 0)
        nd_ebitda = net_debt / ebitda
    add("Net Debt / EBITDA", "Sanatate financiara", nd_ebitda, "x",
        _verdict_from_bands(nd_ebitda, good_max=1, bad_min=3),
        "BUY < 1 | NEUTRU 1-3 | RISC > 3")

    # Free Cash Flow: info -> cashflow FCF -> operating - capex
    fcf = info.get("freeCashflow")
    if fcf is None:
        fcf = cf_fcf
    if fcf is None and cf_ocf is not None:
        fcf = cf_ocf + (cf_capex or 0)  # capex e negativ in cashflow
    add("Free Cash Flow", "Sanatate financiara", fcf, "RON",
        VERDICT_BUY if (fcf or 0) > 0 else (VERDICT_RISC if fcf is not None else VERDICT_NA),
        "BUY > 0 | RISC <= 0")

    # ---------------- D. CRESTERE ----------------
    rev_growth = _pct(info.get("revenueGrowth"))
    add("Crestere venituri (YoY)", "Crestere", rev_growth, "%",
        _verdict_from_bands(rev_growth, good_min=10, bad_max=0, higher_better=True),
        "BUY > 10% | NEUTRU 0-10% | RISC < 0%")

    earnings_growth = _pct(info.get("earningsGrowth"))
    add("Crestere profit (EPS YoY)", "Crestere", earnings_growth, "%",
        _verdict_from_bands(earnings_growth, good_min=10, bad_max=0, higher_better=True),
        "BUY > 10% | NEUTRU 0-10% | RISC < 0%")

    # ---------------- E. ANALIZA TEHNICA ----------------
    # HH / HL
    trend = analyze_trend_hh_hl(hist)
    add("Structura HH/HL", "Tehnic", trend.get("structure"), "text",
        trend.get("verdict"),
        "BUY=HH+HL | RISC=LH+LL | NEUTRU=lateral")

    # RSI
    rsi = _rsi(close) if not close.empty else None
    rsi_verdict = VERDICT_NA
    if rsi is not None:
        if rsi < 30:
            rsi_verdict = VERDICT_BUY      # supra-vandut, posibil rebound
        elif rsi > 70:
            rsi_verdict = VERDICT_RISC     # supra-cumparat
        else:
            rsi_verdict = VERDICT_NEUTRU
    add("RSI (14)", "Tehnic", rsi, "",
        rsi_verdict, "BUY < 30 (supravandut) | NEUTRU 30-70 | RISC > 70 (supracumparat)")

    # Pret vs SMA50 / SMA200
    sma50 = _sma(close, 50) if not close.empty else None
    sma200 = _sma(close, 200) if not close.empty else None
    price = close.iloc[-1] if not close.empty else info.get("currentPrice")
    sma_verdict = VERDICT_NA
    sma_detail = "N/A"
    if price is not None and sma50 is not None and sma200 is not None:
        if price > sma50 > sma200:
            sma_verdict, sma_detail = VERDICT_BUY, "Pret > SMA50 > SMA200 (trend ascendent)"
        elif price < sma50 < sma200:
            sma_verdict, sma_detail = VERDICT_RISC, "Pret < SMA50 < SMA200 (trend descendent)"
        else:
            sma_verdict, sma_detail = VERDICT_NEUTRU, "Medii mobile mixte"
    add("Medii mobile (SMA50/200)", "Tehnic", sma_detail, "text",
        sma_verdict, "BUY=trend asc. | RISC=trend desc. | NEUTRU=mixt")

    # Beta
    beta = info.get("beta")
    add("Beta", "Tehnic", beta, "",
        _verdict_from_bands(beta, good_max=1, bad_min=1.5),
        "BUY < 1 (stabil) | NEUTRU 1-1.5 | RISC > 1.5 (volatil)")

    # Pozitia in intervalul 52w
    high52 = info.get("fiftyTwoWeekHigh")
    low52 = info.get("fiftyTwoWeekLow")
    pos52 = None
    if price and high52 and low52 and high52 != low52:
        pos52 = (price - low52) / (high52 - low52) * 100
    add("Pozitie in interval 52 sapt.", "Tehnic", pos52, "%",
        _verdict_from_bands(pos52, good_max=40, bad_min=85),
        "BUY < 40% (aproape de minim) | NEUTRU 40-85% | RISC > 85% (aproape de maxim)")

    # ---------------- F. DATE BRUTE / PIATA ----------------
    raw = {
        "Nume": info.get("longName") or info.get("shortName") or ticker_symbol,
        "Pret curent": price,
        "Moneda": info.get("currency", "RON"),
        "Market Cap": info.get("marketCap"),
        "Profit net (TTM)": info.get("netIncomeToCommon") or fb_net,
        "EBITDA": ebitda,
        "Venituri (TTM)": info.get("totalRevenue") or fb_rev,
        "52w High": high52,
        "52w Low": low52,
        "Volum mediu": info.get("averageVolume"),
        "Sector": info.get("sector"),
        "Variatie zi %": (round((close.iloc[-1] / close.iloc[-2] - 1) * 100, 2)
                          if len(close) >= 2 else None),
    }

    # ---------------- SCOR GLOBAL ----------------
    scores = [SCORE[i["verdict"]] for i in indicators if SCORE.get(i["verdict"]) is not None]
    global_score = round(sum(scores) / len(scores) * 100, 1) if scores else None

    if global_score is None:
        global_verdict = VERDICT_NA
    elif global_score >= 65:
        global_verdict = VERDICT_BUY
    elif global_score >= 40:
        global_verdict = VERDICT_NEUTRU
    else:
        global_verdict = VERDICT_RISC

    # ---------------- RANDAMENT MULTI-AN + PLAN TRANZACTIE ----------------
    returns = compute_returns(tk, price)
    trade_plan = compute_trade_plan(hist, trend, price)

    return {
        "ticker": ticker_symbol,
        "indicators": indicators,
        "raw": raw,
        "trend": trend,
        "global_score": global_score,
        "global_verdict": global_verdict,
        "hist": hist,
        "returns": returns,
        "trade_plan": trade_plan,
    }


# ===========================================================================
# ANALIZA ETF (look-through: media ponderata a componentelor + concentrare)
# ===========================================================================

def _hhi(weights):
    """Indice Herfindahl-Hirschman de concentrare (suma patratelor ponderilor in fractii)."""
    return sum((w / 100.0) ** 2 for w in weights)


def analyze_etf(etf_def):
    """
    etf_def: dict cu 'ticker', 'index', 'descriere', 'holdings' {ticker: pondere%}.
    Calculeaza:
     - analiza tehnica/pret a ETF-ului (din Yahoo)
     - look-through: indicatori fundamentali MEDII PONDERATI din componente
     - concentrare (top 10, HHI), alocare pe sectoare, verdict ponderat
    """
    from bvb_etfs import SECTORS

    ticker = etf_def["ticker"]
    holdings = etf_def.get("holdings") or {}
    etf_type = etf_def.get("type", "actiuni")

    # Normalizeaza ponderile la 100% (daca exista holdings)
    total_w = sum(holdings.values())
    weights = {t: (w / total_w * 100.0) for t, w in holdings.items()} if total_w > 0 else {}

    # --- Analiza pret/tehnica a ETF-ului in sine ---
    tk = yf.Ticker(ticker)
    info = _robust_info(tk)
    try:
        hist = tk.history(period="1y")
    except Exception:
        hist = pd.DataFrame()
    close = hist["Close"].dropna() if (hist is not None and not hist.empty) else pd.Series(dtype=float)
    price = close.iloc[-1] if not close.empty else info.get("currentPrice")
    trend = analyze_trend_hh_hl(hist)
    returns = compute_returns(tk, price)
    trade_plan = compute_trade_plan(hist, trend, price)

    etf_technical = []
    rsi = _rsi(close) if not close.empty else None
    rsi_v = VERDICT_NA
    if rsi is not None:
        rsi_v = VERDICT_BUY if rsi < 30 else (VERDICT_RISC if rsi > 70 else VERDICT_NEUTRU)
    etf_technical.append(("RSI (14)", round(rsi, 1) if rsi else None, rsi_v))
    etf_technical.append(("Structura HH/HL", trend.get("structure"), trend.get("verdict")))

    # --- Look-through: analizeaza fiecare componenta ---
    components = []
    for t, w in weights.items():
        try:
            d = analyze_company(t)
            ind_map = {i["name"]: i for i in d["indicators"]}
            components.append({
                "ticker": t,
                "weight": w,
                "name": d["raw"].get("Nume", t),
                "sector": SECTORS.get(t, "Altele"),
                "score": d["global_score"],
                "verdict": d["global_verdict"],
                "pe": _ind_val(ind_map, "P/E (trailing)"),
                "roe": _ind_val(ind_map, "ROE (Return on Equity)"),
                "net_margin": _ind_val(ind_map, "Marja neta (Net Margin)"),
                "div_yield": _ind_val(ind_map, "Dividend Yield"),
                "rev_growth": _ind_val(ind_map, "Crestere venituri (YoY)"),
                "de": _ind_val(ind_map, "Debt/Equity"),
            })
        except Exception:
            components.append({"ticker": t, "weight": w, "name": t,
                               "sector": SECTORS.get(t, "Altele"), "score": None,
                               "verdict": VERDICT_NA, "pe": None, "roe": None,
                               "net_margin": None, "div_yield": None,
                               "rev_growth": None, "de": None})

    # --- Medii ponderate (renormalizate pe componentele care au valoare) ---
    def wavg(key):
        num = den = 0.0
        for c in components:
            v = c.get(key)
            if v is not None:
                num += v * c["weight"]
                den += c["weight"]
        return (num / den) if den > 0 else None

    weighted = {
        "P/E ponderat": (wavg("pe"), "x"),
        "ROE ponderat": (wavg("roe"), "%"),
        "Marja neta ponderata": (wavg("net_margin"), "%"),
        "Dividend Yield ponderat": (wavg("div_yield"), "%"),
        "Crestere venituri ponderata": (wavg("rev_growth"), "%"),
        "Debt/Equity ponderat": (wavg("de"), "x"),
    }

    # --- Concentrare ---
    sorted_comp = sorted(components, key=lambda c: c["weight"], reverse=True)
    top10_weight = sum(c["weight"] for c in sorted_comp[:10])
    hhi = _hhi([c["weight"] for c in components])
    if top10_weight < 50:
        conc_verdict = VERDICT_BUY
    elif top10_weight < 70:
        conc_verdict = VERDICT_NEUTRU
    else:
        conc_verdict = VERDICT_RISC

    # --- Alocare pe sectoare ---
    sector_alloc = {}
    for c in components:
        sector_alloc[c["sector"]] = sector_alloc.get(c["sector"], 0.0) + c["weight"]
    sector_alloc = dict(sorted(sector_alloc.items(), key=lambda x: x[1], reverse=True))
    max_sector = max(sector_alloc.values()) if sector_alloc else 0

    # --- Scor global ponderat al ETF-ului (media scorurilor componentelor) ---
    num = den = 0.0
    for c in components:
        if c["score"] is not None:
            num += c["score"] * c["weight"]
            den += c["weight"]
    etf_score = round(num / den, 1) if den > 0 else None
    if etf_score is None:
        etf_verdict = VERDICT_NA
    elif etf_score >= 65:
        etf_verdict = VERDICT_BUY
    elif etf_score >= 40:
        etf_verdict = VERDICT_NEUTRU
    else:
        etf_verdict = VERDICT_RISC

    return {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "index": etf_def.get("index"),
        "type": etf_type,
        "descriere": etf_def.get("descriere"),
        "price": price,
        "currency": info.get("currency", "RON"),
        "avg_volume": info.get("averageVolume"),
        "hist": hist,
        "trend": trend,
        "returns": returns,
        "trade_plan": trade_plan,
        "etf_technical": etf_technical,
        "components": sorted_comp,
        "weighted": weighted,
        "top10_weight": round(top10_weight, 1),
        "hhi": round(hhi, 3),
        "conc_verdict": conc_verdict,
        "sector_alloc": {k: round(v, 1) for k, v in sector_alloc.items()},
        "max_sector": round(max_sector, 1),
        "etf_score": etf_score,
        "etf_verdict": etf_verdict,
        "n_holdings": len(components),
    }


def _ind_val(ind_map, name):
    ind = ind_map.get(name)
    if ind is None:
        return None
    v = ind.get("value")
    return v if isinstance(v, (int, float)) else None
