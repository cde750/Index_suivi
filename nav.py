# app.py (fichier principal à lancer)
import streamlit as st

page_a = st.Page("streamlit_app.py", title="Accueil", icon="🏠")
page_b = st.Page("momentum.py", title="SP 500", icon="🇺🇸")
page_c = st.Page("momentum_EU.py", title="Eurostoxx 50", icon="🇪🇺")
page_d = st.Page("Ey.py", title="Ey")

pg = st.navigation([page_a, page_b, page_c])
pg.run()
