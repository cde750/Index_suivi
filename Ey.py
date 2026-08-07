"""
ocr_ey.py — Extraction OCR d'une capture de prévisions EY (format monospace).
Lancer :  streamlit run ocr_ey.py
Prérequis : pip install streamlit pandas pillow pytesseract
            + binaire Tesseract installé (voir sidebar de l'app)
"""

import io
import re
from datetime import datetime

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

st.set_page_config(page_title="OCR Prévisions EY", layout="wide")

OUTPUT_COLS = ["ArrDep", "CieOpe", "NumVol", "EscDep", "EscArr",
               "DateLocaleMvt", "NbPaxCNT", "NbPaxTOT"]

MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
          "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

# Ligne de date :  WE 05AUG26   (le F J Y de droite est ignoré)
RE_DATE = re.compile(r"^\s*[A-Z]{2}\s+(\d{2})\s*([A-Z]{3})\s*(\d{2})\b")

# Ligne de vol : EY 0032 CDGAUH 0 1005 388 OF 4 53 400
RE_VOL = re.compile(
    r"^\s*([A-Z0-9]{2})\s+(\d{3,4})\s+"      # cie + numéro
    r"([A-Z]{3})\s*([A-Z]{3})\s+"            # escales (collées ou non)
    r"\d+\s+"                                # étape / stops
    r"\d{3,4}\s+"                            # heure
    r"\S+"                                   # type avion
    r"(.*)$"                                 # reste : [OF] + chiffres classes
)


# ------------------------------------------------------------------
# OCR
# ------------------------------------------------------------------
def ocr_image(file, psm=6):
    """Retourne le texte brut OCR de l'image."""
    import pytesseract

    img = Image.open(file)
    img = ImageOps.grayscale(img)
    # Upscale x2 : nette amélioration sur les petites captures
    img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    # Binarisation simple
    img = img.point(lambda p: 255 if p > 150 else 0)

    config = f"--psm {psm} -c tessedit_char_whitelist=" \
             "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
    return pytesseract.image_to_string(img, config=config)


# ------------------------------------------------------------------
# PARSING
# ------------------------------------------------------------------
def parse_text(text):
    """Parse le texte OCR -> DataFrame au schéma OUTPUT_COLS."""
    rows = []
    rejets = []
    date_courante = None

    for ligne in text.splitlines():
        if not ligne.strip():
            continue

        m_date = RE_DATE.match(ligne)
        if m_date:
            jour, mois_txt, annee = m_date.groups()
            mois = MONTHS.get(mois_txt.upper())
            if mois:
                date_courante = datetime(2000 + int(annee), mois, int(jour))
            else:
                rejets.append((ligne, f"mois inconnu : {mois_txt}"))
            continue

        m_vol = RE_VOL.match(ligne)
        if not m_vol:
            rejets.append((ligne, "format non reconnu"))
            continue

        if date_courante is None:
            rejets.append((ligne, "aucune date en amont"))
            continue

        cie, num, esc_dep, esc_arr, reste = m_vol.groups()

        # Les nombres du reste = classes F / J / Y (OF ignoré par la whitelist)
        chiffres = [int(x) for x in re.findall(r"\b\d+\b", reste)]
        paxtot = sum(chiffres)

        rows.append({
            "ArrDep": "D" if esc_dep == "CDG" else "A",
            "CieOpe": cie,
            "NumVol": num.lstrip("0") or "0",
            "EscDep": esc_dep,
            "EscArr": esc_arr,
            "DateLocaleMvt": date_courante.strftime("%d/%m/%Y"),
            "NbPaxCNT": 0,
            "NbPaxTOT": paxtot,
            "_classes": " + ".join(map(str, chiffres)) if chiffres else "—",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=OUTPUT_COLS + ["_classes"])
    return df, rejets


# ------------------------------------------------------------------
# UI
# ------------------------------------------------------------------
st.title("OCR — Prévisions compagnie (capture PNG)")

with st.sidebar:
    st.header("Réglages")
    psm = st.selectbox(
        "Mode de segmentation Tesseract (PSM)",
        [6, 4, 11, 12],
        index=0,
        help="6 = bloc de texte uniforme (défaut, adapté ici). "
             "Essayer 4 ou 11 si le résultat est mauvais.",
    )
    st.divider()
    st.caption(
        "**Installation Tesseract**\n\n"
        "- Windows : [UB-Mannheim installer]"
        "(https://github.com/UB-Mannheim/tesseract/wiki)\n"
        "- macOS : `brew install tesseract`\n"
        "- Linux : `sudo apt install tesseract-ocr`"
    )

st.warning(
    "⚠️ **Relecture obligatoire.** L'OCR peut confondre des chiffres "
    "sans lever d'erreur. Vérifiez le tableau avant export.",
    icon="⚠️",
)

fichier = st.file_uploader("Capture d'écran (PNG / JPG)", type=["png", "jpg", "jpeg"])

if fichier:
    col_img, col_res = st.columns([1, 1])

    with col_img:
        st.subheader("Image source")
        st.image(fichier, use_container_width=True)

    try:
        texte = ocr_image(fichier, psm=psm)
    except ImportError:
        st.error("`pytesseract` n'est pas installé : `pip install pytesseract`")
        st.stop()
    except Exception as e:
        st.error(f"Erreur OCR : {e}\n\nLe binaire Tesseract est-il installé et dans le PATH ?")
        st.stop()

    with st.expander("Texte OCR brut (débogage)"):
        st.code(texte)

    df, rejets = parse_text(texte)

    with col_res:
        st.subheader("Données extraites")
        if df.empty:
            st.error("Aucune ligne exploitable. Vérifiez le texte brut ci-dessus.")
        else:
            st.caption(
                f"{len(df)} vol(s) — colonne `_classes` = détail du calcul de NbPaxTOT"
            )
            edited = st.data_editor(
                df,
                use_container_width=True,
                num_rows="dynamic",
                column_config={
                    "_classes": st.column_config.TextColumn(
                        "Détail classes", disabled=True, help="Somme = NbPaxTOT"
                    ),
                    "NbPaxTOT": st.column_config.NumberColumn("NbPaxTOT", min_value=0),
                    "NbPaxCNT": st.column_config.NumberColumn("NbPaxCNT", min_value=0),
                },
                key="editeur",
            )

    if rejets:
        with st.expander(f"⚠️ {len(rejets)} ligne(s) ignorée(s)"):
            st.dataframe(
                pd.DataFrame(rejets, columns=["Ligne OCR", "Motif"]),
                use_container_width=True,
            )

    if not df.empty:
        st.divider()
        final = edited[OUTPUT_COLS].copy()

        c1, c2, c3 = st.columns(3)
        c1.metric("Vols", len(final))
        c2.metric("Total PAX", int(final["NbPaxTOT"].sum()))
        c3.metric("Jours couverts", final["DateLocaleMvt"].nunique())

        buf = io.StringIO()
        final.to_csv(buf, index=False, sep=";")

        st.download_button(
            "📥 Télécharger le CSV",
            data=buf.getvalue().encode("utf-8-sig"),
            file_name=f"Previs_cies_{datetime.now():%d_%m_%Y}.csv",
            mime="text/csv",
            type="primary",
        )
else:
    st.info("Déposez une capture pour démarrer.")
