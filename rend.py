import streamlit as st
from dividend import get_dividends  # Assurez-vous que get_dividends est défini dans dividend.py
from datetime import datetime

# Charger les valeurs d'action depuis le fichier
def load_action_values(file_path="action_values.txt"):
    action_values = {}
    try:
        with open(file_path, "r") as file:
            for line in file:
                if ":" in line:
                    ticker, value = line.strip().split(":")
                    action_values[ticker] = float(value)  # Convertir en float pour les calculs
    except FileNotFoundError:
        print("Erreur : Le fichier action_values.txt est introuvable.")
    
    return action_values

# Récupérer les dividendes et les valeurs d'action
all_dividends = get_dividends()
action_values = load_action_values("action_values.txt")

# Définir l'année de référence dynamique (N-1)
reference_year = str(datetime.now().year - 1)

# Nouveau dictionnaire pour stocker les résultats
dividendes_ratio = {}

# Calculer le ratio dividende / valeur d'action pour chaque ticker
for ticker, dividends_df in all_dividends.items():
    if not dividends_df.empty and ticker in action_values:
        # Filtrer pour obtenir uniquement l'année de référence N-1
        dividendes_n_1 = dividends_df[dividends_df['Year'] == reference_year]
        
        if not dividendes_n_1.empty:
            dividende_value = dividendes_n_1[ticker].values[0]  # Extraire le dividende de l'année N-1
            action_value = action_values[ticker]  # Récupérer la valeur de l'action
            ratio = (dividende_value / action_value) * 100  # Calculer le ratio en pourcentage
            dividendes_ratio[ticker] = round(ratio, 2)  # Arrondir à deux décimales pour plus de lisibilité

# Afficher les résultats dans Streamlit
st.write(f"Ratio Dividende {reference_year} / Valeur de l'Action pour chaque Ticker (en %):", dividendes_ratio)
