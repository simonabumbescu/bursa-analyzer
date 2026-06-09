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
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)

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
    for unit, div in [("mld", 1e9), ("mil", 1e6), ("k", 1e3)]:
        if abs(v) >= div:
            return f"{v/div:,.2f} {unit}"
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


def build_company_pdf(data, company_name):
    """Returneaza bytes PDF cu raportul complet al unei firme."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    ss = _styles()
    elems = []
    raw = data["raw"]
    cur = raw.get("Moneda", "RON")

    elems.append(Paragraph(f"Analiza: {company_name}", ss["TitleRo"]))
    elems.append(Paragraph(
        f"Ticker: {data['ticker']}  |  Generat: {datetime.now():%d.%m.%Y %H:%M}",
        ss["Small"]))
    elems.append(Spacer(1, 6))

    # --- Verdict global + date cheie ---
    gv = data["global_verdict"]
    gcolor = VERDICT_COLORS.get(gv, colors.grey)
    head = [
        ["Verdict global", gv, "Scor (0-100)", str(data.get("global_score", "-"))],
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
    elems.append(Paragraph(
        "Instrument educational. NU constituie consultanta financiara sau recomandare "
        "de investitie. Date via Yahoo Finance, pot avea intarzieri sau erori.",
        ss["Small"]))

    doc.build(elems)
    buf.seek(0)
    return buf.getvalue()


def build_ranking_pdf(rows):
    """
    rows: lista de dict cu cheile Firma, Ticker, Scor, Verdict, Pret,
    Profit net, EBITDA, Trend HH/HL (deja formatate ca string unde e cazul).
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    ss = _styles()
    elems = [Paragraph("Clasament firme BVB", ss["TitleRo"]),
             Paragraph(f"Generat: {datetime.now():%d.%m.%Y %H:%M}  |  "
                       f"Scor mai mare = profil mai favorabil", ss["Small"]),
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
        "Instrument educational. NU constituie consultanta financiara. Date via Yahoo Finance.",
        ss["Small"]))
    doc.build(elems)
    buf.seek(0)
    return buf.getvalue()
