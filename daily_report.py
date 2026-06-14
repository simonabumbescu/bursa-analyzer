"""
daily_report.py - Genereaza clasamentul BVB pe toate 3 profilele intr-un PDF
si il trimite pe email. Conceput pentru rulare automata (GitHub Actions / cron).

Configurare prin variabile de mediu (GitHub Secrets):
  SMTP_USER  - adresa Gmail care trimite (ex: contul.tau@gmail.com)
  SMTP_PASS  - App Password Gmail (16 caractere, NU parola normala)
  MAIL_TO    - adresa destinatar (poate fi aceeasi sau alta)
  MAIL_SUBJECT (optional) - subiectul emailului
"""

import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage

# Orele (in ora Romaniei) la care vrem sa trimitem raportul
ORE_TRIMITERE = {9, 19}


def ora_romaniei():
    """Returneaza (ora, este_zi_lucratoare) in fusul orar al Romaniei."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Europe/Bucharest"))
    except Exception:
        now = datetime.utcnow()  # fallback: UTC
    return now.hour, now.weekday() < 5  # weekday: 0=luni ... 4=vineri


def trebuie_sa_trimit():
    """Trimite doar la orele dorite, in zile lucratoare. Rularea manuala trimite mereu."""
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        return True  # buton "Run workflow" - test, trimite oricum
    ora, e_lucratoare = ora_romaniei()
    return e_lucratoare and ora in ORE_TRIMITERE

from bvb_tickers import BVB_COMPANIES
from analyzer import analyze_company
from scoring import compute_weighted_score, PROFILES, VERDICT_POINTS
from pdf_export import build_daily_report_pdf, _fmt_big


VERDICT_LABEL = {"BUY": "BUY", "NEUTRU": "NEUTRU", "RISC": "RISC", "N/A": "N/A"}


def build_sections():
    """Analizeaza toate firmele si construieste clasamentul pentru fiecare profil."""
    print("Analizez firmele...")
    analyzed = {}
    for name, ticker in BVB_COMPANIES.items():
        try:
            analyzed[name] = analyze_company(ticker)
            print(f"  OK {ticker}")
        except Exception as ex:
            print(f"  EROARE {ticker}: {ex}")

    sections = []
    for profile in PROFILES:
        rows = []
        for name, data in analyzed.items():
            sc, vd, _ = compute_weighted_score(data["indicators"], profile)
            rows.append({
                "Firma": name,
                "Scor": sc,
                "Verdict": vd,
                "Pret": f"{data['raw'].get('Pret curent'):,.2f}" if data["raw"].get("Pret curent") else "-",
                "Profit net": _fmt_big(data["raw"].get("Profit net (TTM)")),
                "EBITDA": _fmt_big(data["raw"].get("EBITDA")),
            })
        rows.sort(key=lambda r: (r["Scor"] is None, -(r["Scor"] or 0)))
        sections.append((profile, rows))
    return sections


def send_email(pdf_bytes):
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    mail_to = os.environ.get("MAIL_TO") or user
    subject = os.environ.get("MAIL_SUBJECT") or "Bursa de azi"

    if not user or not password:
        raise SystemExit("Lipsesc SMTP_USER / SMTP_PASS (seteaza-le ca secrets).")

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = mail_to
    msg["Subject"] = subject
    msg.set_content(
        "Salut,\n\nIn atasament gasesti clasamentul zilnic al firmelor de la BVB, "
        "pe toate cele 3 profile de evaluare (Echilibrat, Investitor pe termen lung, Trader).\n\n"
        f"Generat automat la {datetime.now():%d.%m.%Y %H:%M}.\n\n"
        "Date via Yahoo Finance."
    )
    fname = f"clasament_bvb_{datetime.now():%Y%m%d}.pdf"
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=fname)

    print(f"Trimit email catre {mail_to}...")
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls(context=ctx)
        server.login(user, password)
        server.send_message(msg)
    print("Email trimis cu succes.")


def main():
    if not trebuie_sa_trimit():
        ora, e_lucratoare = ora_romaniei()
        print(f"Nu trimit acum (ora Romaniei={ora}, zi lucratoare={e_lucratoare}). "
              f"Trimit doar la orele {sorted(ORE_TRIMITERE)} luni-vineri.")
        return
    sections = build_sections()
    pdf = build_daily_report_pdf(sections)
    print(f"PDF generat: {len(pdf)} bytes")
    send_email(pdf)


if __name__ == "__main__":
    main()
