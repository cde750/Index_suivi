import yfinance as yf
import streamlit as st
import pandas as pd
from datetime import datetime

# Récupérer les dividendes annuels pour une action
def get_annual_dividends(ticker_symbol, start_year=2023):
    ticker = yf.Ticker(ticker_symbol)
    dividends = ticker.dividends

    # Afficher les dividendes bruts pour vérifier leur structure
    st.write(f"Dividendes bruts pour {ticker_symbol} :")
    st.write(dividends)

    if not dividends.empty:
        # Convertir l'index en dates si nécessaire
        dividends.index = pd.to_datetime(dividends.index)

        # Créer un DataFrame avec les dates comme une colonne, puis extraire l'année
        dividends_df = dividends.to_frame(name='Dividends')
        dividends_df['Year'] = dividends_df.index.year

        # Regrouper par année et sommer les dividendes
        dividends_by_year = dividends_df.groupby('Year')['Dividends'].sum().reset_index()

        # Filtrer pour les années >= start_year
        dividends_by_year = dividends_by_year[dividends_by_year['Year'] >= start_year]

        # S'assurer que l'année est correctement formatée
        dividends_by_year['Year'] = dividends_by_year['Year'].astype(str)  # Convertir en chaîne pour l'affichage

        # Renommer la colonne 'Dividends' par le symbole du ticker
        dividends_by_year.rename(columns={'Dividends': ticker_symbol}, inplace=True)

        # Affichage pour vérifier les dividendes regroupés
        st.write(f"Dividendes annuels regroupés pour {ticker_symbol} :", dividends_by_year)
      
        return dividends_by_year

    st.write(f"Aucun dividende pour {ticker_symbol}")
    return pd.DataFrame(columns=['Year', ticker_symbol])

# Interface Streamlit
st.title("Récupération des Dividendes Annuels")
st.subheader("Dividendes pour plusieurs actions")

# Charger les tickers à partir du fichier actions_list.txt
with open("actions_list.txt", "r") as file:
    tickers = [line.strip() for line in file if line.strip()]

# Année actuelle
current_year = datetime.now().year

# Récupérer et afficher les dividendes annuels pour chaque ticker
all_dividends = {}
for ticker in tickers:
    st.subheader(f"Dividendes pour {ticker}")
    dividends_by_year = get_annual_dividends(ticker, start_year=2023)
    all_dividends[ticker] = dividends_by_year

# Optionnel : afficher tous les dividendes récupérés
st.write("Données des dividendes pour toutes les actions :", all_dividends)
