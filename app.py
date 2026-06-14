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
from bvb_etfs import BVB_ETFS
from analyzer import (
    analyze_company as _analyze_company,
    analyze_etf as _analyze_etf,
    VERDICT_BUY, VERDICT_NEUTRU, VERDICT_RISC, VERDICT_NA,
)
from pdf_export import (
    build_company_pdf, build_ranking_pdf, build_glossary_pdf, build_etf_pdf,
)
from scoring import (
    compute_weighted_score, all_profiles_scores, PROFILES, score_to_verdict,
)


@st.cache_data(ttl=300, show_spinner=False)
def analyze_etf(etf_name):
    return _analyze_etf(BVB_ETFS[etf_name])


@st.cache_data(ttl=120, show_spinner=False)
def analyze_company(ticker_symbol):
    """Cache scurt (2 min) ca datele sa fie cat mai proaspete fara a lovi Yahoo prea des."""
    return _analyze_company(ticker_symbol)

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
    # Notatie ca pe site-urile financiare: T (trilion), B (miliard), M (milion), K (mie)
    for unit, div in [("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(v) >= div:
            return f"{v/div:,.2f}{unit}"
    return f"{v:,.2f}"


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
st.sidebar.title("📈 Analizor BVB")
st.sidebar.caption("Date live via Yahoo Finance")

mode = st.sidebar.radio("Mod", ["Analiza o firma", "Analiza ETF", "Clasament toate firmele"])

if st.sidebar.button("🔄 Reimprospateaza date (live)"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("Datele se reincarca automat la 2 min. "
                   "Yahoo (gratuit) are intarziere de ~15 min.")

st.sidebar.markdown("---")
st.sidebar.download_button(
    "📘 Ghid indicatori (PDF)",
    data=build_glossary_pdf(),
    file_name="ghid_indicatori_bursa.pdf",
    mime="application/pdf",
    help="Explica ce inseamna fiecare indicator, intervalele si efectul pe bursa.",
)

st.sidebar.markdown("---")
with st.sidebar.expander("ℹ️ Notatie cifre (T/B/M/K)"):
    st.markdown(
        "- **T** = Trilion (1.000 miliarde)\n"
        "- **B** = Billion / Miliard\n"
        "- **M** = Million / Milion\n"
        "- **K** = Thousand / Mie\n\n"
        "Ex: market cap **41.39B RON** = 41,39 miliarde lei."
    )
    st.markdown("**Verdicte:** 🟢 BUY (favorabil) · 🟡 NEUTRU · 🔴 RISC")



# ---------------------------------------------------------------------------
# MOD 1: ANALIZA O FIRMA
# ---------------------------------------------------------------------------
if mode == "Analiza o firma":
    company = st.sidebar.selectbox("Alege firma", list(BVB_COMPANIES.keys()))
    ticker = BVB_COMPANIES[company]

    st.title(f"Analiza: {company}")
    st.caption(f"Ticker Yahoo: `{ticker}`")
    from bvb_tickers import COMPANY_DESC
    if COMPANY_DESC.get(ticker):
        st.info(f"💼 **Cu ce face bani:** {COMPANY_DESC[ticker]}")

    with st.spinner("Aduc datele live..."):
        data = analyze_company(ticker)

    raw = data["raw"]
    cur = raw.get("Moneda", "RON")

    # --- Profil de scoring (stil broker) ---
    profile = st.radio("Profil de evaluare (stil broker):", list(PROFILES.keys()),
                       horizontal=True,
                       help="Schimba ponderea categoriilor: termen lung = fundamentale, "
                            "trader = tehnic, echilibrat = mix.")
    gs, gv, cat_scores = compute_weighted_score(data["indicators"], profile)

    # --- Verdict global (ponderat dupa profil) ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Verdict ({profile.split()[0]})", VERDICT_EMOJI[gv])
    c2.metric("Scor ponderat (0-100)", f"{gs}" if gs is not None else "—")
    c3.metric("Pret curent", f"{raw.get('Pret curent'):,.2f} {cur}" if raw.get('Pret curent') else "—")
    c4.metric("Market Cap", f"{fmt_big(raw.get('Market Cap'))} {cur}")

    # --- Comparatie toate profilele + scoruri pe categorii ---
    allp = all_profiles_scores(data["indicators"])
    pc = st.columns(len(allp))
    for col, (pname, (psc, pv)) in zip(pc, allp.items()):
        col.metric(pname, VERDICT_EMOJI[pv].split()[0], f"{psc}" if psc else "—")
    with st.expander("🔬 Scor pe categorii (cum se compune)"):
        catrows = [{"Categorie": g, "Scor categorie (0-100)": sc,
                    "Pondere in profil": f"{PROFILES[profile].get(g, 0)}%"}
                   for g, sc in cat_scores.items()]
        st.dataframe(pd.DataFrame(catrows), use_container_width=True, hide_index=True)

    # --- Date brute cheie (profit, EBITDA) ---
    st.subheader("📊 Date financiare cheie")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Profit net (TTM)", f"{fmt_big(raw.get('Profit net (TTM)'))} {cur}")
    d2.metric("EBITDA", f"{fmt_big(raw.get('EBITDA'))} {cur}")
    d3.metric("Venituri (TTM)", f"{fmt_big(raw.get('Venituri (TTM)'))} {cur}")
    d4.metric("Volum mediu", fmt_big(raw.get('Volum mediu')))

    # --- Buton descarcare PDF firma (cu profilul ales) ---
    try:
        pdf_bytes = build_company_pdf(data, company,
                                      profile=profile, weighted_score=gs,
                                      weighted_verdict=gv, cat_scores=cat_scores,
                                      all_profiles=allp)
        st.download_button(
            "📄 Descarca raport PDF",
            data=pdf_bytes,
            file_name=f"raport_{ticker.replace('.', '_')}.pdf",
            mime="application/pdf",
        )
    except Exception as e:
        st.caption(f"PDF indisponibil momentan: {e}")

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
                    # fundal colorat (bine suportat de st.dataframe pe orice versiune)
                    text = "#ffffff" if v != VERDICT_NA else "#111111"
                    return (f"background-color: {VERDICT_COLORS[v]}; "
                            f"color: {text}; font-weight: 700;")
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
# MOD 2: ANALIZA ETF (look-through)
# ---------------------------------------------------------------------------
elif mode == "Analiza ETF":
    etf_name = st.sidebar.selectbox("Alege ETF-ul", list(BVB_ETFS.keys()))
    st.title(f"Analiza ETF: {etf_name}")
    edef = BVB_ETFS[etf_name]
    st.caption(f"Ticker: `{edef['ticker']}`  ·  Replica indicele **{edef['index']}**  ·  "
               f"{edef['descriere']}")

    with st.spinner("Analizez ETF-ul si toate componentele (poate dura ~1 min)..."):
        e = analyze_etf(etf_name)
    cur = e["currency"]

    is_bonds = e.get("type") == "obligatiuni" or e["n_holdings"] == 0

    # Verdict global ETF
    c1, c2, c3, c4 = st.columns(4)
    if is_bonds:
        c1.metric("Tip", "Obligatiuni")
        c2.metric("Pret curent", f"{e['price']:,.2f} {cur}" if e["price"] else "—")
        c3.metric("Volum mediu", f"{e['avg_volume']:,}" if e.get("avg_volume") else "—")
        c4.metric("Componente", "—")
    else:
        c1.metric("Verdict ETF", VERDICT_EMOJI[e["etf_verdict"]])
        c2.metric("Scor ponderat (0-100)", f"{e['etf_score']}" if e["etf_score"] else "—")
        c3.metric("Pret curent", f"{e['price']:,.2f} {cur}" if e["price"] else "—")
        c4.metric("Nr. componente", e["n_holdings"])

    if is_bonds:
        st.info("ℹ️ Acest ETF investeste in **obligatiuni de stat**, nu in actiuni. "
                "Analiza look-through pe companii nu se aplica - mai jos ai doar evolutia "
                "pretului si randamentul. Obligatiunile de stat sunt considerate "
                "investitii cu risc scazut.")
        if e["returns"]:
            st.subheader("💰 Randament")
            rrows = [{"Perioada": r["perioada"],
                      "Randament total": f"{r['total']:+.1f}%" if r.get("total") is not None else "—",
                      "Anualizat": f"{r['anual']:+.1f}%/an" if r.get("anual") is not None else "—"}
                     for r in e["returns"]]
            st.dataframe(pd.DataFrame(rrows), use_container_width=True, hide_index=True)
        hist = e.get("hist")
        if hist is not None and not hist.empty:
            st.subheader("📈 Evolutie pret (1 an)")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], mode="lines",
                                     line=dict(color="#2563eb"), name="Pret"))
            st.plotly_chart(fig, use_container_width=True)
        st.stop()
    else:
        st.info("ℹ️ ETF-ul nu se analizeaza ca o firma, ci ca un **cos** de companii. "
                "Indicatorii de mai jos sunt **medii ponderate** dupa greutatea fiecarei companii "
                "in indice (look-through). Ponderile sunt aproximative (indicele se recalculeaza trimestrial).")

    # Buton PDF ETF
    try:
        st.download_button("📄 Descarca raport ETF (PDF)",
                           data=build_etf_pdf(e, etf_name),
                           file_name=f"raport_etf_{edef['ticker'].replace('.', '_')}.pdf",
                           mime="application/pdf")
    except Exception as ex:
        st.caption(f"PDF indisponibil: {ex}")

    # Concentrare
    st.subheader("⚖️ Concentrare & diversificare")
    k1, k2, k3 = st.columns(3)
    k1.metric("Top 10 pondere", f"{e['top10_weight']}%",
              help="Cat din ETF e in primele 10 firme. Mare = concentrat (risc).")
    k2.metric("Indice concentrare (HHI)", f"{e['hhi']}",
              help="0 = foarte diversificat, 1 = o singura firma. Sub 0.15 e ok.")
    k3.metric("Verdict concentrare", VERDICT_EMOJI[e["conc_verdict"]])
    st.caption("Top 10 < 50% = bine diversificat (BUY) · 50-70% = NEUTRU · > 70% = concentrat (RISC)")

    # Fundamentale ponderate
    st.subheader("📊 Indicatori fundamentali (medii ponderate)")
    wrows = []
    for name, (val, fmt) in e["weighted"].items():
        if val is None:
            sval = "—"
        elif fmt == "%":
            sval = f"{val:.2f}%"
        elif fmt == "x":
            sval = f"{val:.2f}x"
        else:
            sval = f"{val:.2f}"
        wrows.append({"Indicator (ponderat)": name, "Valoare": sval})
    st.dataframe(pd.DataFrame(wrows), use_container_width=True, hide_index=True)

    # Randament
    if e["returns"]:
        st.subheader("💰 Randament ETF")
        rrows = [{"Perioada": r["perioada"],
                  "Randament total": f"{r['total']:+.1f}%" if r.get("total") is not None else "—",
                  "Anualizat": f"{r['anual']:+.1f}%/an" if r.get("anual") is not None else "—"}
                 for r in e["returns"]]
        st.dataframe(pd.DataFrame(rrows), use_container_width=True, hide_index=True)

    # Grafic pret
    hist = e.get("hist")
    if hist is not None and not hist.empty:
        st.subheader("📈 Evolutie pret ETF (1 an)")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], mode="lines",
                                 line=dict(color="#2563eb"), name="Pret"))
        tp = e.get("trade_plan", {})
        for key, color in [("take_profit", "#16a34a"), ("stop_loss", "#dc2626")]:
            if tp.get(key):
                fig.add_hline(y=tp[key], line=dict(color=color, width=1.2, dash="solid"))
        st.plotly_chart(fig, use_container_width=True)

    # Alocare pe sectoare
    st.subheader("🏭 Alocare pe sectoare")
    salloc = e["sector_alloc"]
    sfig = go.Figure(go.Bar(x=list(salloc.values()), y=list(salloc.keys()),
                            orientation="h", marker_color="#2563eb"))
    sfig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis_title="% din ETF")
    st.plotly_chart(sfig, use_container_width=True)
    if e["max_sector"] > 35:
        st.warning(f"⚠️ Concentrare sectoriala: cel mai mare sector = {e['max_sector']}% "
                   f"din ETF. Risc daca acel sector are probleme.")

    # Componente (holdings) cu ponderi, verdicte si contributie
    st.subheader("📋 Componente: procent + verdict + impact in ETF")
    st.caption("**Impact = pondere × calitate.** 'Contributie scor' = cate puncte aduce "
               "fiecare firma la scorul ETF-ului (pondere × scorul ei). "
               "Asa vezi care firme TRAG ETF-ul in sus si care il trag in jos.")

    crows = []
    for c in e["components"]:
        score = c["score"]
        contrib = round(c["weight"] * score / 100, 1) if score is not None else None
        # eticheta de impact: combina ponderea cu verdictul
        if c["weight"] >= 8 and c["verdict"] == VERDICT_RISC:
            impact = "⚠️ Risc major (pondere mare + risc)"
        elif c["weight"] >= 8 and c["verdict"] == VERDICT_BUY:
            impact = "💪 Motor principal (pondere mare + bun)"
        elif c["verdict"] == VERDICT_RISC:
            impact = "Risc minor (pondere mica)"
        elif c["verdict"] == VERDICT_BUY:
            impact = "Pozitiv (pondere mica)"
        else:
            impact = "Neutru"
        crows.append({
            "Firma": c["name"][:28],
            "Pondere": c["weight"],
            "Sector": c["sector"],
            "Scor firma": score if score is not None else None,
            "Verdict": VERDICT_EMOJI.get(c["verdict"], "—"),
            "Contributie scor": contrib,
            "Impact in ETF": impact,
        })
    cdf = pd.DataFrame(crows)

    def color_verdict_etf(val):
        for v, label in VERDICT_EMOJI.items():
            if val == label:
                text = "#ffffff" if v != VERDICT_NA else "#111111"
                return f"background-color: {VERDICT_COLORS[v]}; color: {text}; font-weight: 700;"
        return ""

    styler = cdf.style.format({"Pondere": "{:.1f}%", "Contributie scor": "{:.1f}"})
    styler = (styler.map if hasattr(styler, "map") else styler.applymap)(
        color_verdict_etf, subset=["Verdict"])
    # bara vizuala pe pondere
    try:
        styler = styler.bar(subset=["Pondere"], color="#93c5fd")
    except Exception:
        pass
    st.dataframe(styler, use_container_width=True, hide_index=True)

    # Insight: top motor si top risc
    valid = [c for c in e["components"] if c["score"] is not None]
    if valid:
        motoare = sorted([c for c in valid if c["verdict"] == VERDICT_BUY],
                         key=lambda c: c["weight"], reverse=True)[:3]
        riscuri = sorted([c for c in valid if c["verdict"] == VERDICT_RISC],
                         key=lambda c: c["weight"], reverse=True)[:3]
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**💪 Motoarele ETF-ului** (pondere mare + verdict bun):")
            if motoare:
                for c in motoare:
                    st.markdown(f"- {c['name'][:26]} — **{c['weight']:.1f}%** 🟢")
            else:
                st.caption("Nicio firma BUY semnificativa.")
        with col_b:
            st.markdown("**⚠️ Riscurile ETF-ului** (pondere mare + verdict risc):")
            if riscuri:
                for c in riscuri:
                    st.markdown(f"- {c['name'][:26]} — **{c['weight']:.1f}%** 🔴")
            else:
                st.caption("Niciun risc major ponderat.")


# ---------------------------------------------------------------------------
# MOD 3: CLASAMENT TOATE FIRMELE
# ---------------------------------------------------------------------------
else:
    st.title("🏆 Clasament firme BVB")
    rank_profile = st.radio("Profil de evaluare (stil broker):", list(PROFILES.keys()),
                            horizontal=True,
                            help="Schimba ponderea categoriilor in scorul de clasament.")
    st.caption(f"Clasament dupa scorul ponderat ({rank_profile}). "
               "Pozitia 1 = cel mai favorabil profil.")

    if st.button("Genereaza clasamentul (dureaza ~1-2 min)"):
        rows = []
        progress = st.progress(0.0)
        names = list(BVB_COMPANIES.items())
        for i, (name, ticker) in enumerate(names):
            try:
                data = analyze_company(ticker)
                sc, vd, _ = compute_weighted_score(data["indicators"], rank_profile)
                rows.append({
                    "Firma": name,
                    "Ticker": ticker,
                    "Scor": sc,
                    "Verdict": VERDICT_EMOJI[vd],
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
        st.success(f"Clasament generat dupa profilul '{rank_profile}'. Pozitia 1 = scor cel mai mare.")

        # --- PDF clasament ---
        try:
            ranking_rows = df.to_dict("records")
            pdf_bytes = build_ranking_pdf(ranking_rows, profile=rank_profile)
            st.download_button(
                "📄 Descarca clasament PDF",
                data=pdf_bytes,
                file_name="clasament_bvb.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.caption(f"PDF clasament indisponibil: {e}")
    else:
        st.info("Alege profilul si apasa butonul pentru a genera clasamentul.")
