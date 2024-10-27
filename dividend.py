# dividend.py

import yfinance as yf
import pandas as pd
from datetime import datetime

# Récupérer les dividendes annuels pour une action
def get_annual_dividends(ticker_symbol, start_year=2023):
    ticker = yf.Ticker(ticker_symbol)
    dividends = ticker.dividends

    if not dividends.empty:
        dividends.index = pd.to_datetime(dividends.index)
        dividends_df = dividends.to_frame(name='Dividends')
        dividends_df['Year'] = dividends_df.index.year
        dividends_by_year = dividends_df.groupby('Year')['Dividends'].sum().reset_index()
        dividends_by_year = dividends_by_year[dividends_by_year['Year'] >= start_year]
        dividends_by_year['Year'] = dividends_by_year['Year'].astype(str)
        dividends_by_year.rename(columns={'Dividends': ticker_symbol}, inplace=True)
        return dividends_by_year

    return pd.DataFrame(columns=['Year', ticker_symbol])

# Nouvelle fonction principale pour récupérer les dividendes pour tous les tickers
def get_dividends():
    all_dividends = {}
    try:
        with open("actions_list.txt", "r") as file:
            tickers = [line.strip() for line in file if line.strip()]

        for ticker in tickers:
            dividends_by_year = get_annual_dividends(ticker, start_year=2023)
            if not dividends_by_year.empty:
                all_dividends[ticker] = dividends_by_year
            else:
                all_dividends[ticker] = pd.DataFrame(columns=['Year', ticker])
    except FileNotFoundError:
        print("Erreur : Le fichier actions_list.txt est introuvable.")

    return all_dividends
