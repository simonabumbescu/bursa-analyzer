# 📈 Analizor Acțiuni BVB

Instrument **educațional** de analiză a acțiunilor listate la Bursa de Valori București (BVB),
cu date live de pe Yahoo Finance.

> ⚠️ **Disclaimer:** Acest proiect este pur educațional. NU constituie consultanță
> financiară sau recomandare de investiție. Verifică datele independent înainte de orice decizie.

## Funcționalități

- **27 de indicatori** grupați pe categorii: evaluare, profitabilitate, sănătate
  financiară, creștere, analiză tehnică.
- Fiecare indicator are valoare live, interval de referință și verdict
  🟢 BUY / 🟡 NEUTRU / 🔴 RISC.
- **Scor global 0-100** și clasament al tuturor firmelor.
- **Randament istoric** pe 1 lună → 6 ani (total + anualizat).
- **Structură HH/HL** (Higher Highs / Higher Lows) și **moment de intrare**.
- **Niveluri TP / SL**, suport/rezistență și zonă de intrare desenate pe grafic.
- Date financiare cheie: profit net, EBITDA, venituri, market cap.

## Instalare

```bash
pip install -r requirements.txt
```

## Rulare

```bash
streamlit run app.py
```

Se deschide la `http://localhost:8501`.

## Structură

| Fișier | Rol |
|---|---|
| `app.py` | Interfața Streamlit |
| `analyzer.py` | Logica indicatorilor, randament, plan de tranzacție |
| `bvb_tickers.py` | Lista firmelor BVB (ticker Yahoo) |
| `requirements.txt` | Dependențe |

## Sursa datelor

[Yahoo Finance](https://finance.yahoo.com) via biblioteca `yfinance`.
Firmele BVB folosesc sufixul `.RO` (ex: `TLV.RO`, `SNP.RO`).
Unele date fundamentale pot lipsi pentru anumite firme — sunt marcate ⚪ N/A.
