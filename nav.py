# app.py (fichier principal à lancer)
import streamlit as st

page_a = st.Page("streamlit_app.py", title="Accueil", icon="🏠")
page_b = st.Page("momentum.py", title="Analyse", icon="📊")
page_c = st.Page("momentum_EU.py", title="Analyse", icon="📊")

pg = st.navigation([page_a, page_b, page_c])
pg.run()
