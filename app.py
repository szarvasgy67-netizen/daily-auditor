import streamlit as st
import pandas as pd
import numpy as np
import json

st.set_page_config(page_title="DALY & ICER Hatásmérő Auditor", layout="wide")

st.title("📊 DALY, ICER & PPP Egészségügyi Közgazdaságtani Auditor")
st.markdown("Hivatások, gyülekezetek, civil szervezetek és adományozói portfóliók összehasonlítása (Shapley-, ICER- és PPP-szűrővel).")

# --- 1. BEÉPÍTETT ADATBÁZISOK ÉS BÁZISÉRTÉKEK ---
PPP_GDP_DB = {
    "Magyarország (16,12M Ft)": 16121000,
    "USA (29,8M Ft)": 29800000,
    "Fejlődő országok átlaga (1,15M Ft)": 1151500,
    "Bissau-Guinea (964e Ft)": 963970,
    "Kongói DK (651e Ft)": 651420,
    "Ukrajna / Kárpátalja (4,85M Ft)": 4850000,
    "EU-átlag (19,5M Ft)": 19500000
}

SECTOR_PRESETS = {
    "Egyéni / AI által kitöltött": {"overhead": 15, "shapley": 70, "subst": 30, "horizon": 5, "daly_per_cap": 0.15},
    "Baptista Szeretetszolgálat (2025 teljes)": {"overhead": 22, "shapley": 40, "subst": 75, "horizon": 6, "daly_per_cap": 0.12},
    "Fejlődő világbeli alapellátás (pl. Vitamin Angels, AMF)": {"overhead": 10, "shapley": 85, "subst": 5, "horizon": 6, "daly_per_cap": 0.263},
    "Hazai felesleg-aktiválás (pl. Élelmiszerbank)": {"overhead": 12, "shapley": 75, "subst": 35, "horizon": 2, "daly_per_cap": 0.0853},
    "Hazai állami egészségügyi munkakör (Orvos / Ápoló)": {"overhead": 20, "shapley": 25, "subst": 80, "horizon": 10, "daly_per_cap": 0.02},
    "Hazai gyülekezeti / szociális szolgálat": {"overhead": 40, "shapley": 60, "subst": 50, "horizon": 5, "daly_per_cap": 0.05},
    "Klímavédelem (CO2 mentesítés - 1 tonnára vetítve)": {"overhead": 10, "shapley": 90, "subst": 10, "horizon": 30, "daly_per_cap": 0.00024}
}

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
        "name": "Magyar Élelmiszerbank (600e Ft)",
        "budget": 600000,
        "beneficiaries": 286,
        "daly_per_cap": 0.0853,
        "overhead": 12,
        "shapley": 75,
        "subst": 35,
        "horizon": 2,
        "country": "Magyarország (16,12M Ft)",
        "reasoning": "Írj be egy nevet a bal oldali Groq AI keresőbe, vagy válassz szektorsablont!"
    }

# --- 3. OLDALSÁV: GROQ AI ADATBÁNYÁSZ ÉS SABLONOK ---
with st.sidebar:
    st.header("⚡ 1. Automatikus Kitöltés (Groq AI)")
    groq_key = st.secrets.get("GROQ_API_KEY", "") or st.text_input("Groq API Kulcs (gsk_...)", type="password")
    search_query = st.text_input("Mit elemezzünk?", placeholder="pl. Máltai Szeretetszolgálat vagy magyar mentőápoló")
    
    if st.button("🔍 Adatok kikeresése AI-val"):
        if not groq_key:
            st.warning("Add meg a Groq kulcsot a Secrets-ben vagy fent!")
        elif not search_query:
            st.warning("Írd be a vizsgált szervezet, hivatás vagy projekt nevét!")
        else:
            try:
                from groq import Groq
                client = Groq(api_key=groq_key)
                prompt = f"""
                Te egy egészségügyi közgazdaságtani (WHO GBD, GiveWell, ICER, Shapley) szakértő vagy.
                Elemezd a következőt: "{search_query}".
                Adj vissza KIZÁRÓLAG egy érvényes JSON objektumot az alábbi kulcsokkal (magyarul, reális közgazdasági és pénzügyi adatokkal):
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
                    "reasoning": "Rövid, 2 mondatos szakmai indoklás a pénzügyi és DALY számokhoz."
                }}
                A 'country' értéke CSAK ezek közül egy lehet: {list(PPP_GDP_DB.keys())}.
                """
                with st.spinner("Groq AI elemzés folyamatban..."):
                    chat_completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="openai/gpt-oss-120b",
                        temperature=0.1,
                        response_format={"type": "json_object"}
                    )
                    parsed = json.loads(chat_completion.choices[0].message.content)
                    st.session_state.form_data.update(parsed)
                    st.rerun()
            except Exception as e:
                st.error(f"Hiba a Groq lekérdezés során: {e}")

    st.divider()
    st.header("📋 2. Gyors Szektorsablonok")
    selected_preset = st.selectbox("Válassz típust:", list(SECTOR_PRESETS.keys()))
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
    country_keys = list(PPP_GDP_DB.keys())
    default_idx = country_keys.index(st.session_state.form_data["country"]) if st.session_state.form_data["country"] in country_keys else 0
    country = st.selectbox("Célország / Régió (PPP GDP)", country_keys, index=default_idx)

with col2:
    st.subheader("Klinikai & Terepi Szűrők")
    daly_per_cap = st.number_input("Bruttó DALY nyereség / fő", min_value=0.00001, max_value=50.0, value=float(st.session_state.form_data["daly_per_cap"]), format="%.5f")
    overhead = st.slider("Belső intézményi rezsi / súrlódás (%)", 0, 90, int(st.session_state.form_data["overhead"]))
    shapley = st.slider("Shapley-részesedés (%)", 5, 100, int(st.session_state.form_data["shapley"]))

with col3:
    st.subheader("GiveWell & Időbeli Szűrők")
    subst = st.slider("Helyettesíthetőség / Kiszorítás (%)", 0, 95, int(st.session_state.form_data["subst"]))
    horizon = st.slider("Hatás átlagos időtávja (év)", 1, 40, int(st.session_state.form_data["horizon"]))
    gw_strictness = st.slider("GiveWell konzervatív levonás (%)", 0, 50, 15)

# --- 5. PYTHON SZÁMÍTÁSI MOTOR ---
brutto_daly = beneficiaries * daly_per_cap
effective_factor = (1 - overhead / 100.0) * (shapley / 100.0)
korrigalt_daly = brutto_daly * effective_factor

discount_factor = 1 / ((1 + 0.03) ** horizon)
additionality_factor = (1 - subst / 100.0) * (1 - gw_strictness / 100.0)
givewell_daly = korrigalt_daly * discount_factor * additionality_factor

icer_korrigalt = budget / korrigalt_daly if korrigalt_daly > 0 else float('inf')
icer_givewell = budget / givewell_daly if givewell_daly > 0 else float('inf')

local_ppp_gdp = PPP_GDP_DB[country]
ppp_burden_pct = (icer_korrigalt / local_ppp_gdp) * 100

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
m6.metric("PPP-korrigált teher (GDP %)", f"{ppp_burden_pct:.2f}%", delta="WHO küszöb: < 100%")
m7.metric("Nyers hatékonyság (vs. Orvos)", f"{nyers_szorzo:.1f}x")
m8.metric("Valós PPP előny (vs. Orvos)", f"{ppp_szorzo:.1f}x")

# --- 7. ÖSSZEHASONLÍTÓ TÁBLÁZAT ---
st.subheader("⚖️ Összehasonlító Benchmarking (Bázisok + Portfólió + Vizsgált Projekt)")

all_rows = BASELINES + [{
    "Név": f"👉 VIZSGÁLT: {name}",
    "Ráfordítás (Ft)": budget,
    "Korrigált DALY": korrigalt_daly,
    "GiveWell DALY": givewell_daly,
    "PPP GDP (Ft)": local_ppp_gdp
}]

df_list = []
for r in all_rows:
    icer = r["Ráfordítás (Ft)"] / r["Korrigált DALY"] if r["Korrigált DALY"] > 0 else 0
    ppp_pct = (icer / r["PPP GDP (Ft)"]) * 100
    ppp_adv = 27.14 / ppp_pct if ppp_pct > 0 else 0
    df_list.append({
        "Szereplő / Program": r["Név"],
        "Ráfordítás (Ft)": f"{r['Ráfordítás (Ft)']:,.0f}".replace(",", " "),
        "Korrigált DALY": round(r["Korrigált DALY"], 2),
        "GiveWell Nettó DALY": round(r["GiveWell DALY"], 2),
"ICER (Ft / DALY)": f"{icer:,.0f}".replace(",", " "),
"PPP Teher (GDP %)": f"{ppp_pct:.2f}%",
"Valós PPP Előny (Orvos = 1x)": f"{ppp_adv:.1f}x"
})
df_res = pd.DataFrame(df_list)
st.dataframe(df_res, use_container_width=True, hide_index=True)
