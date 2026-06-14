"""
pdf_export.py - Genereaza PDF-uri din rezultatele analizei:
 - PDF per firma (toti indicatorii, randament, plan TP/SL)
 - PDF clasament (toate firmele)

Foloseste reportlab. Fara emoji/diacritice speciale in PDF (font standard).
"""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage,
)


def _render_chart_png(hist, trade_plan, company_name):
    """Randeaza graficul de pret (cu SL/TP/suport/rezistenta) ca PNG in memorie."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except Exception:
        return None
    if hist is None or getattr(hist, "empty", True):
        return None

    close = hist["Close"].dropna()
    if close.empty:
        return None

    fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=150)
    ax.plot(close.index, close.values, color="#2563eb", linewidth=1.3, label="Pret")

    tp = trade_plan or {}
    lines = [
        ("take_profit", "Take Profit", "#16a34a", "-"),
        ("resistance", "Rezistenta (HH)", "#9333ea", ":"),
        ("support", "Suport (HL)", "#0891b2", ":"),
        ("stop_loss", "Stop Loss", "#dc2626", "-"),
    ]
    for key, label, color, style in lines:
        val = tp.get(key)
        if val:
            ax.axhline(val, color=color, linewidth=1.1, linestyle=style,
                       label=f"{label}: {val}")
    ez = tp.get("entry_zone")
    if ez:
        ax.axhspan(ez[0], ez[1], color="#16a34a", alpha=0.12)

    ax.set_title(f"{company_name} - evolutie pret (1 an)", fontsize=9)
    ax.tick_params(labelsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.legend(fontsize=6, loc="best", framealpha=0.7)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()

    out = BytesIO()
    fig.savefig(out, format="png", bbox_inches="tight")
    plt.close(fig)
    out.seek(0)
    return out

VERDICT_COLORS = {
    "BUY": colors.HexColor("#16a34a"),
    "NEUTRU": colors.HexColor("#d97706"),
    "RISC": colors.HexColor("#dc2626"),
    "N/A": colors.HexColor("#9ca3af"),
}


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("TitleRo", parent=ss["Title"], fontSize=18,
                          textColor=colors.HexColor("#1e3a8a")))
    ss.add(ParagraphStyle("H2Ro", parent=ss["Heading2"], fontSize=12,
                          textColor=colors.HexColor("#1e40af"), spaceBefore=8))
    ss.add(ParagraphStyle("Small", parent=ss["Normal"], fontSize=8,
                          textColor=colors.grey))
    return ss


def _fmt_big(value):
    if value is None:
        return "-"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    for unit, div in [("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(v) >= div:
            return f"{v/div:,.2f}{unit}"
    return f"{v:,.2f}"


def _fmt_value(value, fmt):
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    if fmt == "text":
        return str(value)
    if fmt == "RON":
        return f"{value:,.0f}"
    if fmt == "%":
        return f"{value:.2f}%"
    if fmt == "x":
        return f"{value:.2f}x"
    return f"{value:,.2f}"


def build_company_pdf(data, company_name, profile=None, weighted_score=None,
                      weighted_verdict=None, cat_scores=None, all_profiles=None):
    """Returneaza bytes PDF cu raportul complet al unei firme.
    Daca se dau profile/weighted_*, foloseste scorul ponderat (stil broker)."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    ss = _styles()
    elems = []
    raw = data["raw"]
    cur = raw.get("Moneda", "RON")

    elems.append(Paragraph(f"Analiza: {company_name}", ss["TitleRo"]))
    subtitle = f"Ticker: {data['ticker']}  |  Generat: {datetime.now():%d.%m.%Y %H:%M}"
    if profile:
        subtitle += f"  |  Profil: {profile}"
    elems.append(Paragraph(subtitle, ss["Small"]))
    elems.append(Spacer(1, 6))

    # --- Verdict global + date cheie ---
    if weighted_verdict is not None:
        gv = weighted_verdict
        gscore = weighted_score
    else:
        gv = data["global_verdict"]
        gscore = data.get("global_score")
    gcolor = VERDICT_COLORS.get(gv, colors.grey)
    head = [
        ["Verdict global", gv, "Scor (0-100)", str(gscore if gscore is not None else "-")],
        ["Pret curent",
         f"{raw.get('Pret curent'):,.2f} {cur}" if raw.get('Pret curent') else "-",
         "Market Cap", f"{_fmt_big(raw.get('Market Cap'))} {cur}"],
        ["Profit net (TTM)", f"{_fmt_big(raw.get('Profit net (TTM)'))} {cur}",
         "EBITDA", f"{_fmt_big(raw.get('EBITDA'))} {cur}"],
        ["Venituri (TTM)", f"{_fmt_big(raw.get('Venituri (TTM)'))} {cur}",
         "Volum mediu", _fmt_big(raw.get('Volum mediu'))],
    ]
    t = Table(head, colWidths=[40*mm, 45*mm, 40*mm, 45*mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eff6ff")),
        ("BACKGROUND", (1, 0), (1, 0), gcolor),
        ("TEXTCOLOR", (1, 0), (1, 0), colors.white),
        ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 6))

    # --- Verdict pe toate profilele + scor pe categorii ---
    if all_profiles:
        elems.append(Paragraph("Verdict pe profile (stil broker)", ss["H2Ro"]))
        pdata = [["Profil", "Scor", "Verdict"]]
        prows = []
        for k, (pname, (psc, pv)) in enumerate(all_profiles.items(), start=1):
            pdata.append([pname, str(psc) if psc is not None else "-", pv])
            prows.append((k, pv))
        pt = Table(pdata, colWidths=[80*mm, 40*mm, 50*mm])
        pstyle = [
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ]
        for k, pv in prows:
            pstyle.append(("BACKGROUND", (2, k), (2, k), VERDICT_COLORS.get(pv, colors.grey)))
            pstyle.append(("TEXTCOLOR", (2, k), (2, k), colors.white))
            pstyle.append(("FONTNAME", (2, k), (2, k), "Helvetica-Bold"))
        pt.setStyle(TableStyle(pstyle))
        elems.append(pt)
        elems.append(Spacer(1, 6))

    if cat_scores:
        elems.append(Paragraph("Scor pe categorii", ss["H2Ro"]))
        cdata = [["Categorie", "Scor (0-100)"]]
        for g, sc in cat_scores.items():
            cdata.append([g, str(sc)])
        ctbl = Table(cdata, colWidths=[110*mm, 50*mm])
        ctbl.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        elems.append(ctbl)
    elems.append(Spacer(1, 8))

    # --- Grafic pret cu SL/TP ---
    chart = _render_chart_png(data.get("hist"), data.get("trade_plan"), company_name)
    if chart is not None:
        elems.append(Paragraph("Evolutie pret & niveluri TP/SL", ss["H2Ro"]))
        elems.append(RLImage(chart, width=170*mm, height=75*mm))
        elems.append(Spacer(1, 8))

    # --- Randament istoric ---
    returns = data.get("returns", [])
    if returns:
        elems.append(Paragraph("Randament istoric (pret)", ss["H2Ro"]))
        rdata = [["Perioada", "Randament total", "Randament anualizat"]]
        for r in returns:
            rdata.append([
                r["perioada"],
                f"{r['total']:+.1f}%" if r.get("total") is not None else "indisponibil",
                f"{r['anual']:+.1f}%/an" if r.get("anual") is not None else "-",
            ])
        rt = Table(rdata, colWidths=[40*mm, 60*mm, 60*mm])
        rt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        elems.append(rt)
        elems.append(Spacer(1, 8))

    # --- Plan de tranzactie ---
    tp = data.get("trade_plan", {})
    if tp:
        elems.append(Paragraph("Moment de intrare & praguri TP/SL (HH/HL)", ss["H2Ro"]))
        elems.append(Paragraph(f"<b>Semnal:</b> {tp.get('entry_signal', '-')}", ss["Normal"]))
        ez = tp.get("entry_zone")
        plan_rows = [
            ["Stop Loss", f"{tp.get('stop_loss', '-')} {cur}",
             "Take Profit", f"{tp.get('take_profit', '-')} {cur}"],
            ["Suport (HL)", f"{tp.get('support', '-')} {cur}",
             "Rezistenta (HH)", f"{tp.get('resistance', '-')} {cur}"],
            ["Zona intrare", f"{ez[0]} - {ez[1]} {cur}" if ez else "-",
             "Risc/Recompensa", tp.get("risc_reward", "-") or "-"],
        ]
        pt = Table(plan_rows, colWidths=[35*mm, 45*mm, 40*mm, 40*mm])
        pt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
            ("TEXTCOLOR", (1, 0), (1, 0), colors.HexColor("#dc2626")),
            ("TEXTCOLOR", (3, 0), (3, 0), colors.HexColor("#16a34a")),
            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ("FONTNAME", (3, 0), (3, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ]))
        elems.append(pt)
        if tp.get("atentionare"):
            elems.append(Spacer(1, 3))
            elems.append(Paragraph(tp["atentionare"].replace("⚠️", "ATENTIE:"),
                                   ParagraphStyle("warn", fontSize=9,
                                                  textColor=colors.HexColor("#b91c1c"))))
        elems.append(Spacer(1, 8))

    # --- Indicatori, grupati ---
    groups = {}
    for ind in data["indicators"]:
        groups.setdefault(ind["group"], []).append(ind)

    for group_name, inds in groups.items():
        elems.append(Paragraph(group_name, ss["H2Ro"]))
        idata = [["Indicator", "Valoare", "Interval de referinta", "Verdict"]]
        verdict_rows = []
        for k, ind in enumerate(inds, start=1):
            idata.append([
                ind["name"],
                _fmt_value(ind["value"], ind["fmt"]),
                ind["ref"],
                ind["verdict"],
            ])
            verdict_rows.append((k, ind["verdict"]))
        it = Table(idata, colWidths=[45*mm, 30*mm, 70*mm, 22*mm], repeatRows=1)
        style = [
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        for k, verdict in verdict_rows:
            style.append(("BACKGROUND", (3, k), (3, k), VERDICT_COLORS.get(verdict, colors.grey)))
            style.append(("TEXTCOLOR", (3, k), (3, k), colors.white))
            style.append(("FONTNAME", (3, k), (3, k), "Helvetica-Bold"))
        it.setStyle(TableStyle(style))
        elems.append(it)
        elems.append(Spacer(1, 5))

    elems.append(Spacer(1, 6))
    elems.append(Paragraph("Date via Yahoo Finance, pot avea intarzieri sau erori.",
                           ss["Small"]))

    doc.build(elems)
    buf.seek(0)
    return buf.getvalue()


def build_ranking_pdf(rows, profile=None):
    """
    rows: lista de dict cu cheile Firma, Ticker, Scor, Verdict, Pret,
    Profit net, EBITDA, Trend HH/HL (deja formatate ca string unde e cazul).
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    ss = _styles()
    sub = f"Generat: {datetime.now():%d.%m.%Y %H:%M}  |  Scor mai mare = mai favorabil"
    if profile:
        sub += f"  |  Profil: {profile}"
    elems = [Paragraph("Clasament firme BVB", ss["TitleRo"]),
             Paragraph(sub, ss["Small"]),
             Spacer(1, 8)]

    header = ["#", "Firma", "Scor", "Verdict", "Pret", "Profit net", "EBITDA", "Trend HH/HL"]
    tdata = [header]
    verdict_rows = []
    for i, r in enumerate(rows, start=1):
        verdict = (r.get("Verdict") or "").replace("BUY", "BUY").strip()
        v_clean = "BUY" if "BUY" in verdict else ("RISC" if "RISC" in verdict else
                  ("NEUTRU" if "NEUTRU" in verdict else "N/A"))
        tdata.append([
            str(i),
            r.get("Firma", "-"),
            str(r.get("Scor", "-")) if r.get("Scor") is not None else "-",
            v_clean,
            str(r.get("Pret", "-")),
            str(r.get("Profit net", "-")),
            str(r.get("EBITDA", "-")),
            (r.get("Trend HH/HL") or "-")[:22],
        ])
        verdict_rows.append((i, v_clean))

    t = Table(tdata, colWidths=[8*mm, 42*mm, 14*mm, 20*mm, 18*mm, 26*mm, 26*mm, 32*mm],
              repeatRows=1)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for i, verdict in verdict_rows:
        style.append(("BACKGROUND", (3, i), (3, i), VERDICT_COLORS.get(verdict, colors.grey)))
        style.append(("TEXTCOLOR", (3, i), (3, i), colors.white))
        style.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    elems.append(t)
    elems.append(Spacer(1, 8))
    elems.append(Paragraph(
        "Date via Yahoo Finance.",
        ss["Small"]))
    doc.build(elems)
    buf.seek(0)
    return buf.getvalue()


def build_etf_pdf(e, etf_name):
    """PDF raport ETF: scor ponderat, concentrare, fundamentale ponderate,
    sectoare, componente."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    ss = _styles()
    cell = ParagraphStyle("c2", parent=ss["Normal"], fontSize=8, leading=10)
    elems = []
    cur = e.get("currency", "RON")

    elems.append(Paragraph(f"Analiza ETF: {etf_name}", ss["TitleRo"]))
    elems.append(Paragraph(
        f"Ticker: {e['ticker']}  |  Indice: {e.get('index', '-')}  |  "
        f"Generat: {datetime.now():%d.%m.%Y %H:%M}", ss["Small"]))
    elems.append(Paragraph(e.get("descriere", ""), ss["Small"]))
    elems.append(Spacer(1, 6))

    gv = e["etf_verdict"]
    gcolor = VERDICT_COLORS.get(gv, colors.grey)
    head = [
        ["Verdict ETF", gv, "Scor ponderat", str(e.get("etf_score", "-"))],
        ["Pret curent", f"{e['price']:,.2f} {cur}" if e.get("price") else "-",
         "Nr. componente", str(e.get("n_holdings", "-"))],
        ["Top 10 pondere", f"{e['top10_weight']}%", "HHI concentrare", str(e["hhi"])],
    ]
    t = Table(head, colWidths=[38*mm, 45*mm, 40*mm, 45*mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eff6ff")),
        ("BACKGROUND", (1, 0), (1, 0), gcolor),
        ("TEXTCOLOR", (1, 0), (1, 0), colors.white),
        ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 4))
    elems.append(Paragraph(
        "Nota: ETF = cos de companii. Indicatorii fundamentali sunt MEDII PONDERATE "
        "dupa greutatea fiecarei firme in indice (look-through). Ponderi aproximative.",
        ss["Small"]))
    elems.append(Spacer(1, 8))

    # Fundamentale ponderate
    elems.append(Paragraph("Indicatori fundamentali (medii ponderate)", ss["H2Ro"]))
    wdata = [["Indicator (ponderat)", "Valoare"]]
    for name, (val, fmt) in e["weighted"].items():
        if val is None:
            sval = "-"
        elif fmt == "%":
            sval = f"{val:.2f}%"
        elif fmt == "x":
            sval = f"{val:.2f}x"
        else:
            sval = f"{val:.2f}"
        wdata.append([name, sval])
    wt = Table(wdata, colWidths=[120*mm, 40*mm])
    wt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    elems.append(wt)
    elems.append(Spacer(1, 8))

    # Alocare pe sectoare
    elems.append(Paragraph("Alocare pe sectoare", ss["H2Ro"]))
    sdata = [["Sector", "Pondere"]]
    for s, w in e["sector_alloc"].items():
        sdata.append([s, f"{w}%"])
    sst = Table(sdata, colWidths=[120*mm, 40*mm])
    sst.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    elems.append(sst)
    elems.append(Spacer(1, 8))

    # Componente
    elems.append(Paragraph("Componente (holdings) - pondere, verdict, contributie", ss["H2Ro"]))
    cdata = [["Firma", "Pondere", "Sector", "Scor", "Verdict", "Contrib."]]
    verdict_rows = []
    for k, c in enumerate(e["components"], start=1):
        score = c["score"]
        contrib = f"{c['weight'] * score / 100:.1f}" if score is not None else "-"
        cdata.append([c["name"][:28], f"{c['weight']:.1f}%", c["sector"][:20],
                      str(score) if score is not None else "-",
                      c["verdict"], contrib])
        verdict_rows.append((k, c["verdict"]))
    ct = Table(cdata, colWidths=[48*mm, 18*mm, 44*mm, 16*mm, 22*mm, 18*mm], repeatRows=1)
    cstyle = [
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("ALIGN", (4, 0), (4, -1), "CENTER"),
    ]
    for k, verdict in verdict_rows:
        cstyle.append(("BACKGROUND", (4, k), (4, k), VERDICT_COLORS.get(verdict, colors.grey)))
        cstyle.append(("TEXTCOLOR", (4, k), (4, k), colors.white))
        cstyle.append(("FONTNAME", (4, k), (4, k), "Helvetica-Bold"))
    ct.setStyle(TableStyle(cstyle))
    elems.append(ct)
    elems.append(Spacer(1, 8))
    elems.append(Paragraph(
        "Date via Yahoo Finance.",
        ss["Small"]))
    doc.build(elems)
    buf.seek(0)
    return buf.getvalue()


def build_daily_report_pdf(sections):
    """
    Raport zilnic: un PDF cu clasamentul pe mai multe profile.
    sections: lista de (profil, rows) - rows ca la build_ranking_pdf.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    ss = _styles()
    elems = [
        Paragraph("Clasament zilnic firme BVB", ss["TitleRo"]),
        Paragraph(f"Generat automat: {datetime.now():%d.%m.%Y %H:%M}  |  "
                  f"Clasament pe {len(sections)} profile de evaluare", ss["Small"]),
        Spacer(1, 8),
    ]

    for profile, rows in sections:
        elems.append(Paragraph(f"Profil: {profile}", ss["H2Ro"]))
        header = ["#", "Firma", "Scor", "Verdict", "Pret", "Profit net", "EBITDA"]
        tdata = [header]
        verdict_rows = []
        for i, r in enumerate(rows, start=1):
            verdict = (r.get("Verdict") or "")
            v_clean = ("BUY" if "BUY" in verdict else "RISC" if "RISC" in verdict
                       else "NEUTRU" if "NEUTRU" in verdict else "N/A")
            tdata.append([
                str(i), r.get("Firma", "-")[:30],
                str(r.get("Scor", "-")) if r.get("Scor") is not None else "-",
                v_clean, str(r.get("Pret", "-")),
                str(r.get("Profit net", "-")), str(r.get("EBITDA", "-")),
            ])
            verdict_rows.append((i, v_clean))
        t = Table(tdata, colWidths=[8*mm, 50*mm, 16*mm, 22*mm, 20*mm, 30*mm, 30*mm],
                  repeatRows=1)
        style = [
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ]
        for i, verdict in verdict_rows:
            style.append(("BACKGROUND", (3, i), (3, i), VERDICT_COLORS.get(verdict, colors.grey)))
            style.append(("TEXTCOLOR", (3, i), (3, i), colors.white))
            style.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))
        t.setStyle(TableStyle(style))
        elems.append(t)
        elems.append(Spacer(1, 10))

    elems.append(Paragraph("Date via Yahoo Finance.", ss["Small"]))
    doc.build(elems)
    buf.seek(0)
    return buf.getvalue()


# ===========================================================================
# GHID: ce inseamna indicatorii, intervale, influenta pe bursa
# ===========================================================================

# (Grup, [ (Indicator, Ce inseamna, Interval, Influenta pe bursa) ... ])
GLOSSARY = [
    ("A. EVALUARE (cat de scumpa e actiunea)", [
        ("P/E", "Cat platesti pentru 1 leu de profit anual al firmei.",
         "BUY <15 | NEUTRU 15-30 | RISC >30",
         "P/E mic = actiune ieftina fata de profit (atractiva). P/E mare = scumpa sau asteptari mari de crestere; risc de corectie daca profitul dezamageste."),
        ("Forward P/E", "P/E calculat pe profitul ESTIMAT pentru anul urmator.",
         "BUY <15 | NEUTRU 15-30 | RISC >30",
         "Arata cat de scumpa e fata de viitor. Mai mic decat P/E actual = profit asteptat in crestere."),
        ("PEG", "P/E raportat la ritmul de crestere a profitului.",
         "BUY <1 | NEUTRU 1-2 | RISC >2",
         "Sub 1 = cresterea justifica pretul (chilipir). Peste 2 = platesti prea mult pentru crestere."),
        ("P/B", "Pretul fata de valoarea contabila (averea neta) a firmei.",
         "BUY <1.5 | NEUTRU 1.5-4 | RISC >4",
         "Sub 1 = actiunea costa mai putin decat activele firmei. Tipic mic la banci."),
        ("P/S", "Pretul fata de cifra de afaceri (vanzari).",
         "BUY <2 | NEUTRU 2-6 | RISC >6",
         "Util la firme fara profit inca. Mic = vanzari multe la pret mic."),
        ("EV/EBITDA", "Valoarea totala a firmei fata de profitul operational brut.",
         "BUY <8 | NEUTRU 8-15 | RISC >15",
         "Cel mai folosit de analisti pentru comparatii intre firme; ignora datoriile si taxele. Mic = ieftina."),
        ("EV/Sales", "Valoarea totala a firmei fata de vanzari.",
         "BUY <2 | NEUTRU 2-6 | RISC >6",
         "Similar cu P/S dar tine cont si de datorii."),
        ("Dividend Yield", "Cat la suta din pret primesti inapoi ca dividend pe an.",
         "BUY >4% | NEUTRU 1-4% | RISC <1%",
         "Randament mare = venit pasiv bun; atrage investitori. Prea mare poate semnala pret cazut sau dividend nesustenabil."),
        ("Payout Ratio", "Cat din profit se distribuie ca dividend.",
         "BUY <60% | NEUTRU 60-100% | RISC >100%",
         "Peste 100% = firma plateste mai mult decat castiga (nesustenabil). Mic = loc de crestere a dividendului."),
    ]),
    ("B. PROFITABILITATE (cat de eficient face bani)", [
        ("Marja neta", "Cat profit ramane din fiecare 100 lei vanzari.",
         "BUY >10% | NEUTRU 2-10% | RISC <2%",
         "Marja mare = firma eficienta, rezistenta la scumpiri. Investitorii premiaza marjele mari."),
        ("Marja bruta", "Profitul dupa costul direct al produsului/serviciului.",
         "BUY >40% | NEUTRU 15-40% | RISC <15%",
         "Arata puterea de pret a firmei. Mare = avantaj competitiv."),
        ("Marja operationala", "Profitul din activitatea de baza (fara taxe/dobanzi).",
         "BUY >15% | NEUTRU 3-15% | RISC <3%",
         "Sanatatea operatiunii in sine. In crestere = afacere care se imbunatateste."),
        ("Marja EBITDA", "Profit operational brut ca % din vanzari.",
         "BUY >20% | NEUTRU 8-20% | RISC <8%",
         "Cea mai comparabila marja intre firme/sectoare diferite."),
        ("ROE", "Cat profit produce firma la capitalul actionarilor.",
         "BUY >15% | NEUTRU 5-15% | RISC <5%",
         "Indicatorul preferat al lui Buffett. ROE mare constant = firma de calitate."),
        ("ROA", "Cat profit produce firma din totalul activelor.",
         "BUY >7% | NEUTRU 2-7% | RISC <2%",
         "Arata eficienta folosirii activelor. Mic natural la banci/industrii grele."),
    ]),
    ("C. SANATATE FINANCIARA (cat de solida e)", [
        ("Debt/Equity", "Datorii fata de capitalul propriu (gradul de indatorare).",
         "BUY <0.5 | NEUTRU 0.5-2 | RISC >2",
         "Mare = firma indatorata, vulnerabila la dobanzi si crize. Mic = solida. (N/A la banci)"),
        ("Current Ratio", "Active curente fata de datorii pe termen scurt.",
         "BUY >1.5 | NEUTRU 1-1.5 | RISC <1",
         "Sub 1 = poate avea probleme sa-si plateasca facturile pe termen scurt. (N/A la banci)"),
        ("Quick Ratio", "Ca Current Ratio dar fara stocuri (test mai sever).",
         "BUY >1 | NEUTRU 0.5-1 | RISC <0.5",
         "Lichiditate imediata. Sub 0.5 = risc de cash. (N/A la banci)"),
        ("Net Debt/EBITDA", "Cati ani de profit operational trebuie ca sa achite datoria neta.",
         "BUY <1 | NEUTRU 1-3 | RISC >3",
         "Peste 3-4 = indatorare periculoasa. Bancile il urmaresc atent la imprumuturi."),
        ("Free Cash Flow", "Banii reali ramasi dupa investitii.",
         "BUY >0 | RISC <=0",
         "Pozitiv = firma genereaza numerar (poate da dividende, reduce datorii). Negativ repetat = arde bani."),
    ]),
    ("D. CRESTERE (cat de repede se dezvolta)", [
        ("Crestere venituri", "Cu cat au crescut vanzarile fata de anul trecut.",
         "BUY >10% | NEUTRU 0-10% | RISC <0%",
         "Crestere = firma se extinde; piata premiaza cresterea. Negativ = afacere in declin."),
        ("Crestere profit (EPS)", "Cu cat a crescut profitul pe actiune fata de anul trecut.",
         "BUY >10% | NEUTRU 0-10% | RISC <0%",
         "Motorul principal al pretului pe termen lung. Profit in crestere trage actiunea in sus."),
    ]),
    ("E. ANALIZA TEHNICA (pretul si trendul)", [
        ("Structura HH/HL", "Sir de maxime si minime tot mai sus (Higher High / Higher Low).",
         "BUY = HH+HL | RISC = LH+LL | NEUTRU = lateral",
         "HH+HL = trend ascendent sanatos (cumperi la minime tot mai sus). LH+LL = trend de scadere; eviti."),
        ("RSI (14)", "Indicator de momentum 0-100: supra-cumparat / supra-vandut.",
         "BUY <30 | NEUTRU 30-70 | RISC >70",
         "Sub 30 = vandut excesiv, posibil rebound. Peste 70 = cumparat excesiv, risc de corectie."),
        ("Medii mobile (SMA50/200)", "Pretul mediu pe 50 si 200 de zile.",
         "BUY = pret>SMA50>SMA200 | RISC = invers",
         "Pret peste medii = trend ascendent. 'Golden cross' (SMA50 trece peste SMA200) = semnal de cumparare clasic."),
        ("Beta", "Cat de mult se misca actiunea fata de piata.",
         "BUY <1 | NEUTRU 1-1.5 | RISC >1.5",
         "Sub 1 = mai stabila decat piata. Peste 1.5 = volatila (castiguri/pierderi amplificate)."),
        ("Pozitie in 52 sapt.", "Unde e pretul intre minimul si maximul ultimului an.",
         "BUY <40% | NEUTRU 40-85% | RISC >85%",
         "Aproape de minim = posibil ieftin. Aproape de maxim = risc sa fi intarziat / corectie."),
    ]),
]

# Termeni-cheie pentru plan de tranzactie
PLAN_TERMS = [
    ("Take Profit (TP)", "Pretul-tinta la care iei profitul si vinzi. Calculat la raport ~1:2 fata de risc."),
    ("Stop Loss (SL)", "Pretul la care iesi automat ca sa limitezi pierderea (sub suport - volatilitate ATR)."),
    ("Suport (HL)", "Nivel sub pret unde scaderea s-a oprit in trecut - 'podea'. Zona buna de cumparare."),
    ("Rezistenta (HH)", "Nivel peste pret unde cresterea s-a oprit in trecut - 'tavan'. Acolo se ia profit."),
    ("Zona de intrare", "Intervalul ideal de cumparare, langa suport, la un pullback."),
    ("Risc/Recompensa", "Cat risti vs. cat poti castiga. 1:2 = risti 1 ca sa castigi 2 (favorabil)."),
    ("EBITDA", "Profit inainte de dobanzi, taxe si amortizare - profitul operational 'pur'."),
    ("Market Cap", "Valoarea totala a firmei la bursa (pret x numar de actiuni)."),
]


def build_glossary_pdf():
    """PDF educational: ce inseamna indicatorii, intervale, influenta pe bursa."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    ss = _styles()
    cell = ParagraphStyle("cell", parent=ss["Normal"], fontSize=7.5, leading=9)
    cellb = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")
    elems = [
        Paragraph("Ghidul indicatorilor bursieri", ss["TitleRo"]),
        Paragraph("Ce inseamna fiecare indicator, ce interval e considerat bun, "
                  "si cum influenteaza pretul la bursa.", ss["Small"]),
        Spacer(1, 8),
    ]

    for group_name, items in GLOSSARY:
        elems.append(Paragraph(group_name, ss["H2Ro"]))
        rows = [[Paragraph("Indicator", cellb), Paragraph("Ce inseamna", cellb),
                 Paragraph("Interval", cellb), Paragraph("Influenta pe bursa", cellb)]]
        for name, mean, interval, infl in items:
            rows.append([Paragraph(f"<b>{name}</b>", cell), Paragraph(mean, cell),
                         Paragraph(interval, cell), Paragraph(infl, cell)])
        tbl = Table(rows, colWidths=[24*mm, 48*mm, 33*mm, 81*mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))
        elems.append(tbl)
        elems.append(Spacer(1, 7))

    # Termeni plan de tranzactie
    elems.append(Paragraph("F. TERMENI PLAN DE TRANZACTIE", ss["H2Ro"]))
    prows = [[Paragraph("Termen", cellb), Paragraph("Explicatie", cellb)]]
    for term, expl in PLAN_TERMS:
        prows.append([Paragraph(f"<b>{term}</b>", cell), Paragraph(expl, cell)])
    pt = Table(prows, colWidths=[40*mm, 146*mm], repeatRows=1)
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(pt)
    elems.append(Spacer(1, 8))

    elems.append(Paragraph(
        "Cum se citeste verdictul: VERDE (BUY) = valoare favorabila; GALBEN (NEUTRU) = "
        "acceptabil/de urmarit; ROSU (RISC) = semnal de atentie. Scorul global = media "
        "tuturor verdictelor (0-100): peste 65 favorabil, 40-65 neutru, sub 40 risc.",
        cell))
    elems.append(Spacer(1, 6))
    elems.append(Paragraph(
        "Important: niciun indicator nu se citeste singur - conteaza imaginea de ansamblu "
        "si sectorul firmei (ex. bancile au natural P/B mic si fara Current Ratio).",
        ss["Small"]))

    doc.build(elems)
    buf.seek(0)
    return buf.getvalue()
