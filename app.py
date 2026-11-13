import streamlit as st
import pandas as pd
import numpy as np
import json
import os

# Oldal konfiguráció
st.set_page_config(page_title="DALY & ICER Hatásmérő Auditor", layout="wide")

st.title("📊 DALY, ICER & PPP Egészségügyi Közgazdaságtani Auditor")
st.markdown("Hivatások, gyülekezetek, civil szervezetek és adományozói portfóliók összehasonlítása egyetlen közös valután (Shapley-, ICER- és PPP-szűrővel).")

# --- 1. BEÉPÍTETT ADATBÁZISOK ÉS BÁZISÉRTÉKEK ---

PPP_GDP_DB = {
    "Magyarország (16,12M Ft)": 16121000,
    "Fejlődő országok átlaga (1,15M Ft)": 1151500,
    "Bissau-Guinea (964e Ft)": 963970,
    "Kongói DK (651e Ft)": 651420,
    "Ukrajna / Kárpátalja (4,85M Ft)": 4850000,
    "EU-átlag (19,5M Ft)": 19500000
}

SECTOR_PRESETS = {
    "Egyéni / AI által kitöltött": {"overhead": 10, "shapley": 70, "subst": 20, "horizon": 5, "daly_per_cap": 0.15},
    "Fejlődő világbeli alapellátás (pl. Vitamin Angels, AMF)": {"overhead": 10, "shapley": 85, "subst": 5, "horizon": 6, "daly_per_cap": 0.263},
    "Hazai felesleg-aktiválás (pl. Élelmiszerbank)": {"overhead": 12, "shapley": 65, "subst": 15, "horizon": 2, "daly_per_cap": 0.085},
    "Hazai állami egészségügyi munkakör (Orvos / Ápoló)": {"overhead": 20, "shapley": 25, "subst": 80, "horizon": 10, "daly_per_cap": 0.12},
    "Hazai gyülekezeti / szociális szolgálat": {"overhead": 45, "shapley": 60, "subst": 50, "horizon": 5, "daly_per_cap": 0.05},
    "Klímavédelem (CO2 mentesítés - 1 főre/tonnára vetítve)": {"overhead": 10, "shapley": 90, "subst": 10, "horizon": 30, "daly_per_cap": 0.00024}
}

# A dokumentumodból rögzített referencia portfólió és bázisok
BASELINES = [
    {"Név": "BÁZIS: Átlagos magyar klinikai orvos", "Ráfordítás (Ft)": 35000000, "Korrigált DALY": 8.0, "GiveWell DALY": 6.0, "PPP GDP (Ft)": 16121000},
    {"Név": "BÁZIS: Magyar csúcssebész", "Ráfordítás (Ft)": 62000000, "Korrigált DALY": 35.0, "GiveWell DALY": 25.0, "PPP GDP (Ft)": 16121000},
    {"Név": "PORTFÓLIÓ: 1. Vitamin Angels", "Ráfordítás (Ft)": 270000, "Korrigált DALY": 190.0, "GiveWell DALY": 157.5, "PPP GDP (Ft)": 1151500},
    {"Név": "PORTFÓLIÓ: 2. Against Malaria Found.", "Ráfordítás (Ft)": 320000, "Korrigált DALY": 77.5, "GiveWell DALY": 38.5, "PPP GDP (Ft)": 651420},
    {"Név": "PORTFÓLIÓ: 3. Betel Iskola (Bissau)", "Ráfordítás (Ft)": 120000, "Korrigált DALY": 22.0, "GiveWell DALY": 12.5, "PPP GDP (Ft)": 963970},
    {"Név": "PORTFÓLIÓ: 4. Magyar Élelmiszerbank", "Ráfordítás (Ft)": 600000, "Korrigált DALY": 16.0, "GiveWell DALY": 8.0, "PPP GDP (Ft)": 16121000},
]

# --- 2. SESSION STATE INICIALIZÁLÁS ---
if "form_data" not in st.session_state:
    st.session_state.form_data = {
        "name": "Teszt Projekt (pl. Baptista Szeretetszolgálat)",
        "budget": 1000000,
        "beneficiaries": 200,
        "daly_per_cap": 0.15,
        "overhead": 15,
        "shapley": 70,
        "subst": 30,
        "horizon": 5,
        "country": "Magyarország (16,12M Ft)",
        "reasoning": "Válassz egy szektorsablont, töltsd ki kézzel, vagy használd az AI adatbányászt!"
    }

# --- 3. OLDALSÁV: AI ADATBÁNYÁSZ ÉS SABLONOK ---
with st.sidebar:
    st.header("🤖 1. Automatikus Kitöltés (AI)")
    api_key = st.text_input("Gemini API Kulcs (opcionális)", type="password", help="Ha megadsz egy ingyenes Google AI Studio kulcsot, a rendszer név alapján magától kikeresi az adatokat.")
    search_query = st.text_input("Mit elemezzünk?", placeholder="pl. Baptista Szeretetszolgálat hajléktalanellátás")
    
    if st.button("🔍 Adatok kikeresése AI-val"):
        if not api_key:
            st.warning("Kérlek, adj meg egy Gemini API kulcsot az automatikus kereséshez, vagy használj szektorsablont lentebb!")
        elif not search_query:
            st.warning("Írd be a vizsgált szervezet, hivatás vagy projekt nevét!")
        else:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-2.5-flash")
                prompt = f"""
                Te egy egészségügyi közgazdaságtani (WHO GBD, GiveWell, ICER, Shapley) szakértő vagy.
                Elemezd a következőt: "{search_query}".
                Adj vissza KIZÁRÓLAG egy érvényes JSON objektumot az alábbi kulcsokkal (magyarul, reális közgazdasági becslésekkel):
                {{
                    "name": "A vizsgált entitás pontos neve",
                    "budget": 1000000,
                    "beneficiaries": 100,
                    "daly_per_cap": 0.15,
                    "overhead": 20,
                    "shapley": 60,
                    "subst": 50,
                    "horizon": 5,
                    "country": "Magyarország (16,12M Ft)",
                    "reasoning": "Rövid, 2 mondatos szakmai indoklás a számokhoz."
                }}
                A 'country' értéke CSAK ezek közül egy lehet: {list(PPP_GDP_DB.keys())}.
                A 'budget' legyen egy tipikus éves ráfordítás vagy adományegység Ft-ban.
                """
                with st.spinner("AI elemzés és szakirodalmi paraméterezés folyamatban..."):
                    response = model.generate_content(prompt)
                    clean_json = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                    parsed = json.loads(clean_json)
                    st.session_state.form_data.update(parsed)
                    st.success("Adatok betöltve a kalkulátorba!")
            except Exception as e:
                st.error(f"Hiba az AI lekérdezés során: {e}")

    st.divider()
    st.header("📋 2. Gyors Szektorsablonok")
    selected_preset = st.selectbox("Válassz típust (API kulcs nélkül is):", list(SECTOR_PRESETS.keys()))
    if st.button("Sablon alkalmazása"):
        p = SECTOR_PRESETS[selected_preset]
        st.session_state.form_data["overhead"] = p["overhead"]
        st.session_state.form_data["shapley"] = p["shapley"]
        st.session_state.form_data["subst"] = p["subst"]
        st.session_state.form_data["horizon"] = p["horizon"]
        st.session_state.form_data["daly_per_cap"] = p["daly_per_cap"]
        st.rerun()

# --- 4. FŐ FELÜLET: BEMENETI PARAMÉTEREK ---
st.info(f"💡 **Módszertani megjegyzés:** {st.session_state.form_data['reasoning']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Alapadatok")
    name = st.text_input("Projekt / Hivatás / Szervezet neve", value=st.session_state.form_data["name"])
    budget = st.number_input("Éves ráfordítás / Adomány (Ft)", min_value=1000, value=int(st.session_state.form_data["budget"]), step=50000)
    beneficiaries = st.number_input("Érintettek száma (fő / év)", min_value=1, value=int(st.session_state.form_data["beneficiaries"]), step=10)
    country = st.selectbox("Célország / Régió (PPP GDP)", list(PPP_GDP_DB.keys()), index=list(PPP_GDP_DB.keys()).index(st.session_state.form_data["country"]))

with col2:
    st.subheader("Klinikai & Terepi Szűrők")
    daly_per_cap = st.number_input("Bruttó DALY nyereség / fő", min_value=0.0001, max_value=50.0, value=float(st.session_state.form_data["daly_per_cap"]), format="%.4f")
    overhead = st.slider("Belső intézményi rezsi / súrlódás (%)", 0, 90, int(st.session_state.form_data["overhead"]), help="Mennyi megy el adminisztrációra, ingatlanra, veszteségre?")
    shapley = st.slider("Shapley-részesedés (%)", 5, 100, int(st.session_state.form_data["shapley"]), help="Az eredmény hány %-a a vizsgált szereplő érdeme (és nem a háttér-infrastruktúráé)?")

with col3:
    st.subheader("GiveWell & Időbeli Szűrők")
    subst = st.slider("Helyettesíthetőség / Kiszorítás (%)", 0, 95, int(st.session_state.form_data["subst"]), help="Ha kiesik, hány %-ban pótolja az állam vagy más szereplő?")
    horizon = st.slider("Hatás átlagos időtávja (év)", 1, 40, int(st.session_state.form_data["horizon"]), help="A 3%-os időbeli diszkontáláshoz (GiveWell nettó).")
    gw_strictness = st.slider("GiveWell konzervatív levonás (%)", 0, 50, 15, help="Szubjektív jóléti és bizonytalansági tételek levonása.")

# --- 5. PYTHON SZÁMÍTÁSI MOTOR (A 3 VALÓSÁG + ICER + PPP) ---

# 1. Valóság: Bruttó naptári maximum
brutto_daly = beneficiaries * daly_per_cap

# 2. Valóság: Terepi súrlódással és Shapley-megosztással korrigált naptári DALY
effective_factor = (1 - overhead / 100.0) * (shapley / 100.0)
korrigalt_daly = brutto_daly * effective_factor

# 3. Valóság: Szigorú GiveWell nettó (3%-os diszkontráta + helyettesíthetőség + konzervatív szűrő)
discount_factor = 1 / ((1 + 0.03) ** horizon)
additionality_factor = (1 - subst / 100.0) * (1 - gw_strictness / 100.0)
givewell_daly = korrigalt_daly * discount_factor * additionality_factor

# ICER számítás (Ft / DALY) - a Korrigált (2. Valóság) és a GiveWell (3. Valóság) alapon
icer_korrigalt = budget / korrigalt_daly if korrigalt_daly > 0 else float('inf')
icer_givewell = budget / givewell_daly if givewell_daly > 0 else float('inf')

# PPP korrekció (a helyi 1 főre jutó GDP %-ában)
local_ppp_gdp = PPP_GDP_DB[country]
ppp_burden_pct = (icer_korrigalt / local_ppp_gdp) * 100

# Összehasonlítás az átlagos magyar orvossal (Bázis: 4 375 000 Ft/DALY és 27,14% PPP)
nyers_szorzo = 4375000 / icer_korrigalt if icer_korrigalt > 0 else 0
ppp_szorzo = 27.14 / ppp_burden_pct if ppp_burden_pct > 0 else 0

# --- 6. EREDMÉNYEK MEGJELENÍTÉSE ---
st.divider()
st.header(f"📈 Eredmények: {name}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("1. Valóság (Bruttó DALY)", f"{brutto_daly:.2f} év")
m2.metric("2. Valóság (Korrigált DALY)", f"{korrigalt_daly:.2f} év")
m3.metric("3. Valóság (GiveWell Nettó)", f"{givewell_daly:.2f} év")
m4.metric("Nyers ICER (Korrigált)", f"{icer_korrigalt:,.0f} Ft/DALY".replace(",", " "))

m5, m6, m7, m8 = st.columns(4)
m5.metric("Szigorú GiveWell ICER", f"{icer_givewell:,.0f} Ft/DALY".replace(",", " "))
m6.metric("PPP-korrigált teher (GDP %)", f"{ppp_burden_pct:.2f}%", delta="WHO küszöb: < 100%", delta_color="normal")
