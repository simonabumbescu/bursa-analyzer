"""
app.py - Interfata Streamlit pentru analizorul de actiuni BVB.
Ruleaza cu:  streamlit run app.py

ATENTIE: Instrument educational. NU constituie consultanta financiara
sau recomandare de investitie. Datele pot avea intarzieri sau erori.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bvb_tickers import BVB_COMPANIES
from analyzer import (
    analyze_company,
    VERDICT_BUY, VERDICT_NEUTRU, VERDICT_RISC, VERDICT_NA,
)

st.set_page_config(page_title="Analizor Actiuni BVB", page_icon="📈", layout="wide")

VERDICT_COLORS = {
    VERDICT_BUY: "#16a34a",
    VERDICT_NEUTRU: "#d97706",
    VERDICT_RISC: "#dc2626",
    VERDICT_NA: "#9ca3af",
}
VERDICT_EMOJI = {
    VERDICT_BUY: "🟢 BUY",
    VERDICT_NEUTRU: "🟡 NEUTRU",
    VERDICT_RISC: "🔴 RISC",
    VERDICT_NA: "⚪ N/A",
}


def fmt_value(value, fmt):
    if value is None:
        return "—"
    if fmt == "text":
        return str(value)
    if isinstance(value, str):
        return value
    if fmt == "RON":
        return f"{value:,.0f}"
    if fmt == "%":
        return f"{value:.2f}%"
    if fmt == "x":
        return f"{value:.2f}x"
    return f"{value:,.2f}"


def fmt_big(value):
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    for unit, div in [("mld", 1e9), ("mil", 1e6), ("k", 1e3)]:
        if abs(v) >= div:
            return f"{v/div:,.2f} {unit}"
    return f"{v:,.2f}"


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
st.sidebar.title("📈 Analizor BVB")
st.sidebar.caption("Date live via Yahoo Finance")

mode = st.sidebar.radio("Mod", ["Analiza o firma", "Clasament toate firmele"])

st.sidebar.markdown("---")
st.sidebar.warning(
    "⚠️ Instrument **educational**. Nu este consultanta financiara. "
    "Verifica datele independent inainte de orice decizie."
)


# ---------------------------------------------------------------------------
# MOD 1: ANALIZA O FIRMA
# ---------------------------------------------------------------------------
if mode == "Analiza o firma":
    company = st.sidebar.selectbox("Alege firma", list(BVB_COMPANIES.keys()))
    ticker = BVB_COMPANIES[company]

    st.title(f"Analiza: {company}")
    st.caption(f"Ticker Yahoo: `{ticker}`")

    with st.spinner("Aduc datele live..."):
        data = analyze_company(ticker)

    raw = data["raw"]
    cur = raw.get("Moneda", "RON")

    # --- Verdict global ---
    gv = data["global_verdict"]
    gs = data["global_score"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Verdict global", VERDICT_EMOJI[gv])
    c2.metric("Scor (0-100)", f"{gs}" if gs is not None else "—")
    c3.metric("Pret curent", f"{raw.get('Pret curent'):,.2f} {cur}" if raw.get('Pret curent') else "—")
    c4.metric("Market Cap", f"{fmt_big(raw.get('Market Cap'))} {cur}")

    # --- Date brute cheie (profit, EBITDA) ---
    st.subheader("📊 Date financiare cheie")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Profit net (TTM)", f"{fmt_big(raw.get('Profit net (TTM)'))} {cur}")
    d2.metric("EBITDA", f"{fmt_big(raw.get('EBITDA'))} {cur}")
    d3.metric("Venituri (TTM)", f"{fmt_big(raw.get('Venituri (TTM)'))} {cur}")
    d4.metric("Volum mediu", fmt_big(raw.get('Volum mediu')))

    # --- Grafic pret cu swing points HH/HL ---
    hist = data.get("hist")
    if hist is not None and not hist.empty:
        st.subheader("📈 Evolutie pret (1 an) si structura HH/HL")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"],
                                 mode="lines", name="Pret inchidere",
                                 line=dict(color="#2563eb")))
        trend = data.get("trend", {})

        # Linii orizontale: SL / TP / Suport / Rezistenta
        tp_plan = data.get("trade_plan", {})
        x0, x1 = hist.index[0], hist.index[-1]
        levels = [
            ("take_profit", "🟩 Take Profit", "#16a34a", "solid"),
            ("resistance", "Rezistenta (HH)", "#9333ea", "dot"),
            ("support", "Suport (HL)", "#0891b2", "dot"),
            ("stop_loss", "🟥 Stop Loss", "#dc2626", "solid"),
        ]
        for key, label, color, dash in levels:
            val = tp_plan.get(key)
            if val:
                fig.add_hline(y=val, line=dict(color=color, width=1.5, dash=dash),
                              annotation_text=f"{label}: {val}",
                              annotation_position="right",
                              annotation_font_color=color)
        # Zona ideala de intrare (banda verde transparenta)
        ez = tp_plan.get("entry_zone")
        if ez:
            fig.add_hrect(y0=ez[0], y1=ez[1], line_width=0,
                          fillcolor="#16a34a", opacity=0.12,
                          annotation_text="Zona intrare", annotation_position="left")

        fig.update_layout(margin=dict(r=120))
        st.plotly_chart(fig, use_container_width=True)
        st.info(f"**Structura trend (HH/HL):** {trend.get('structure', 'N/A')}  ·  "
                f"Ultimele maxime: {trend.get('last_highs', '—')}  ·  "
                f"Ultimele minime: {trend.get('last_lows', '—')}")

    # --- Randament pe perioade (inclusiv 6 ani) ---
    returns = data.get("returns", [])
    if returns:
        st.subheader("💰 Randament istoric (pret)")
        rrows = []
        for r in returns:
            rrows.append({
                "Perioada": r["perioada"],
                "Randament total": f"{r['total']:+.1f}%" if r.get("total") is not None else "indisponibil",
                "Randament anualizat": f"{r['anual']:+.1f}%/an" if r.get("anual") is not None else "—",
            })
        rdf = pd.DataFrame(rrows)
        st.dataframe(rdf, use_container_width=True, hide_index=True)
        r6 = next((r for r in returns if r["perioada"] == "6 ani" and r.get("disponibil")), None)
        if r6:
            st.success(f"📅 **Randament pe 6 ani: {r6['total']:+.1f}%** "
                       f"({r6['anual']:+.1f}%/an in medie)")
        else:
            st.caption("Istoric de 6 ani indisponibil pentru aceasta firma (listare mai recenta).")

    # --- Plan de tranzactie: intrare HH/HL, TP, SL ---
    tp_plan = data.get("trade_plan", {})
    if tp_plan:
        st.subheader("🎯 Moment de intrare & praguri TP/SL (pe baza HH/HL)")
        if tp_plan.get("atentionare"):
            st.error(tp_plan["atentionare"])

        st.markdown(f"**Semnal de intrare:** {tp_plan.get('entry_signal', 'N/A')}")
        ez = tp_plan.get("entry_zone")
        if ez:
            st.markdown(f"**Zona ideala de intrare:** {ez[0]} – {ez[1]} {cur}")

        t1, t2, t3, t4 = st.columns(4)
        t1.metric("🟥 Stop Loss (SL)",
                  f"{tp_plan['stop_loss']} {cur}" if tp_plan.get("stop_loss") else "—")
        t2.metric("🟩 Take Profit (TP)",
                  f"{tp_plan['take_profit']} {cur}" if tp_plan.get("take_profit") else "—")
        t3.metric("Suport (HL)",
                  f"{tp_plan['support']} {cur}" if tp_plan.get("support") else "—")
        t4.metric("Rezistenta (HH)",
                  f"{tp_plan['resistance']} {cur}" if tp_plan.get("resistance") else "—")
        if tp_plan.get("risc_reward"):
            st.caption(f"Raport risc/recompensa estimat: **{tp_plan['risc_reward']}**  ·  "
                       f"SL = sub ultimul Higher Low − ATR  ·  TP = la raport ~1:2 fata de risc.")
        st.caption("⚠️ Niveluri orientative, calculate mecanic din swing points si volatilitate (ATR). "
                   "Nu sunt recomandari de tranzactionare.")

    # --- Tabel indicatori, grupati ---
    st.subheader("🔍 Toti indicatorii, pe rand")

    groups = {}
    for ind in data["indicators"]:
        groups.setdefault(ind["group"], []).append(ind)

    for group_name, inds in groups.items():
        st.markdown(f"### {group_name}")
        rows = []
        for ind in inds:
            rows.append({
                "Indicator": ind["name"],
                "Valoare": fmt_value(ind["value"], ind["fmt"]),
                "Interval de referinta": ind["ref"],
                "Verdict": VERDICT_EMOJI[ind["verdict"]],
            })
        df = pd.DataFrame(rows)

        def color_verdict(val):
            for v, label in VERDICT_EMOJI.items():
                if val == label:
                    return f"color: {VERDICT_COLORS[v]}; font-weight: 600;"
            return ""

        styler = df.style
        styler = (styler.map if hasattr(styler, "map") else styler.applymap)(
            color_verdict, subset=["Verdict"])
        st.dataframe(
            styler,
            use_container_width=True, hide_index=True,
        )

    # --- Sumar numaratoare ---
    st.subheader("✅ Sumar verdicte")
    counts = {VERDICT_BUY: 0, VERDICT_NEUTRU: 0, VERDICT_RISC: 0, VERDICT_NA: 0}
    for ind in data["indicators"]:
        counts[ind["verdict"]] += 1
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("🟢 BUY", counts[VERDICT_BUY])
    s2.metric("🟡 NEUTRU", counts[VERDICT_NEUTRU])
    s3.metric("🔴 RISC", counts[VERDICT_RISC])
    s4.metric("⚪ N/A", counts[VERDICT_NA])


# ---------------------------------------------------------------------------
# MOD 2: CLASAMENT TOATE FIRMELE
# ---------------------------------------------------------------------------
else:
    st.title("🏆 Clasament firme BVB")
    st.caption("Scor global calculat din toti indicatorii. Cu cat scorul e mai mare, cu atat profilul e mai favorabil.")

    if st.button("Genereaza clasamentul (dureaza ~1-2 min)"):
        rows = []
        progress = st.progress(0.0)
        names = list(BVB_COMPANIES.items())
        for i, (name, ticker) in enumerate(names):
            try:
                data = analyze_company(ticker)
                rows.append({
                    "Firma": name,
                    "Ticker": ticker,
                    "Scor": data["global_score"],
                    "Verdict": VERDICT_EMOJI[data["global_verdict"]],
                    "Pret": data["raw"].get("Pret curent"),
                    "Profit net": data["raw"].get("Profit net (TTM)"),
                    "EBITDA": data["raw"].get("EBITDA"),
                    "Trend HH/HL": data["trend"].get("structure"),
                })
            except Exception as e:
                rows.append({"Firma": name, "Ticker": ticker, "Scor": None,
                             "Verdict": "⚪ EROARE", "Pret": None,
                             "Profit net": None, "EBITDA": None,
                             "Trend HH/HL": str(e)[:40]})
            progress.progress((i + 1) / len(names))

        df = pd.DataFrame(rows)
        df = df.sort_values("Scor", ascending=False, na_position="last").reset_index(drop=True)
        df.index = df.index + 1
        df["Profit net"] = df["Profit net"].apply(fmt_big)
        df["EBITDA"] = df["EBITDA"].apply(fmt_big)
        df["Pret"] = df["Pret"].apply(lambda x: f"{x:,.2f}" if x else "—")

        st.dataframe(df, use_container_width=True)
        st.success("Clasament generat. Pozitia 1 = scor cel mai mare.")
    else:
        st.info("Apasa butonul pentru a calcula scorul tuturor firmelor si a genera clasamentul.")
