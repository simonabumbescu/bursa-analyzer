# ETF-uri listate la BVB + compozitia lor (look-through).
# Yahoo nu da holdings pentru ETF-urile BVB, asa ca definim manual componentele
# si ponderile aproximative, pe baza compozitiei indicelui urmarit.
#
# IMPORTANT: ponderile sunt APROXIMATIVE (indicele BET se recalculeaza trimestrial).
# Se normalizeaza automat la 100% in cod.

# Sector pe fiecare companie (pentru alocarea pe sectoare a ETF-ului)
SECTORS = {
    "TLV.RO": "Financiar-Banci",
    "BRD.RO": "Financiar-Banci",
    "BVB.RO": "Financiar-Bursa",
    "SNP.RO": "Energie-Petrol&Gaze",
    "SNG.RO": "Energie-Petrol&Gaze",
    "H2O.RO": "Utilitati-Energie",
    "SNN.RO": "Utilitati-Energie",
    "EL.RO": "Utilitati-Energie",
    "TGN.RO": "Utilitati-Gaze",
    "TEL.RO": "Utilitati-Electricitate",
    "COTE.RO": "Energie-Transport",
    "DIGI.RO": "Telecomunicatii",
    "M.RO": "Sanatate",
    "ATB.RO": "Sanatate-Farma",
    "TTS.RO": "Transport-Logistica",
    "ONE.RO": "Imobiliare",
    "TRP.RO": "Materiale-Constructii",
    "SFG.RO": "Consum-Restaurante",
    "AQ.RO": "Consum-Distributie",
    "WINE.RO": "Consum-Bauturi",
}

# Compozitia aproximativa a indicelui BET (ponderi in %, se normalizeaza in cod)
BET_CONSTITUENTS = {
    "TLV.RO": 19.0,
    "SNP.RO": 19.0,
    "H2O.RO": 15.0,
    "SNG.RO": 8.0,
    "BRD.RO": 6.5,
    "SNN.RO": 6.0,
    "DIGI.RO": 5.0,
    "TGN.RO": 3.0,
    "EL.RO": 3.0,
    "TEL.RO": 1.8,
    "M.RO": 2.0,
    "TTS.RO": 2.0,
    "ONE.RO": 2.0,
    "TRP.RO": 1.5,
    "SFG.RO": 1.5,
    "BVB.RO": 1.5,
    "AQ.RO": 1.5,
    "ATB.RO": 1.2,
    "COTE.RO": 1.0,
    "WINE.RO": 1.0,
}

# Compozitia aproximativa a unui ETF pe energie (sectorul energetic BVB)
ENERGY_CONSTITUENTS = {
    "SNP.RO": 25.0,   # OMV Petrom
    "H2O.RO": 20.0,   # Hidroelectrica
    "SNG.RO": 15.0,   # Romgaz
    "SNN.RO": 12.0,   # Nuclearelectrica
    "EL.RO": 8.0,     # Electrica
    "TGN.RO": 7.0,    # Transgaz
    "TEL.RO": 6.0,    # Transelectrica
    "PE.RO": 4.0,     # Premier Energy
    "COTE.RO": 3.0,   # Conpet
}

# ETF-urile BVB pe care le analizam.
# "ticker" = simbol Yahoo (pentru pret/tehnic), "holdings" = look-through.
# "type" = "actiuni" (look-through complet) sau "obligatiuni" (doar pret/tehnic).
BVB_ETFS = {
    "ETF BET Patria-Tradeville (TVBETETF)": {
        "ticker": "TVBETETF.RO",
        "index": "BET",
        "type": "actiuni",
        "descriere": "Replica indicele BET - cele mai lichide 20 companii de la BVB.",
        "holdings": BET_CONSTITUENTS,
    },
    "InterCapital BET-TR (ICBETNETF)": {
        "ticker": "ICBETNETF.RO",
        "index": "BET-TR",
        "type": "actiuni",
        "descriere": "Replica indicele BET-TR (BET cu dividende reinvestite).",
        "holdings": BET_CONSTITUENTS,
    },
    "BT Index Romania ETF BET-TR (BTBETRETF)": {
        "ticker": "BTBETRETF.RO",
        "index": "BET-TR",
        "type": "actiuni",
        "descriere": "ETF Banca Transilvania pe indicele BET-TR.",
        "holdings": BET_CONSTITUENTS,
    },
    "ETF Energie Patria-Tradeville (PTENGETF)": {
        "ticker": "PTENGETF.RO",
        "index": "Energie",
        "type": "actiuni",
        "descriere": "Primul ETF sectorial RO - companii din energie.",
        "holdings": ENERGY_CONSTITUENTS,
    },
    "InterCapital EUR Romania Govt Bond 5-10yr (ICGROETF)": {
        "ticker": "ICGROETF.RO",
        "index": "Obligatiuni de stat RO",
        "type": "obligatiuni",
        "descriere": "ETF pe obligatiuni de stat romanesti (5-10 ani). "
                     "Nu se aplica analiza look-through pe actiuni.",
        "holdings": {},
    },
}
