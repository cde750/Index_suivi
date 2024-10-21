import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import os

# Fonction pour afficher un graphique en chandelier avec éventuellement la SMA
def display_candlestick(tickers, period, show_sma, sma_period, key_prefix=""):
    for ticker in tickers:
        # Télécharger les données
        try:
            data = yf.download(ticker, period=period)
        except Exception as e:
            st.error(f"Erreur lors du téléchargement des données pour {ticker}: {e}")
            continue

        # Vérifier que des données existent
        if data.empty:
            st.warning(f"Aucune donnée disponible pour {ticker}.")
            continue

        # Créer le graphique en chandelier
        fig = go.Figure(data=[go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name=ticker
        )])

        # Ajouter la SMA si cochée
        if show_sma:
            data['SMA'] = data['Close'].rolling(window=sma_period).mean()
            fig.add_trace(go.Scatter(
                x=data.index, y=data['SMA'],
                mode='lines',
                name=f'SMA {sma_period}',
                line=dict(color='yellow')
            ))

        # Ajouter des préfixes pour les tickers spécifiques
        green_square_list = ['SP5.PA', 'UST.PA', 'MGT.PA', 'WLD.PA']
        red_square_list = ['TTE.PA', 'GLE.PA', 'BNP.PA']

        if ticker in green_square_list:
            title_prefix = "🟩 "  # Carré vert
        elif ticker in red_square_list:
            title_prefix = "🟥 "  # Carré rouge
        else:
            title_prefix = ""

        # Configurer le titre du graphique
        fig.update_layout(
            title=f"{title_prefix} Cours de l'ETF {ticker} - {period} d'historique",
            xaxis_title="Date",
            yaxis_title="Prix",
            xaxis_rangeslider_visible=False
        )

        st.plotly_chart(fig)

# Fonction pour afficher les courbes différentielles
def display_differential_curves(tickers, ref_ticker, period, show_sma, sma_period, key_prefix=""):
    ref_data = yf.download(ref_ticker, period=period)
    
    # Vérifier que les données de référence existent
    if ref_data.empty:
        st.warning(f"Aucune donnée disponible pour l'action de référence {ref_ticker}.")
        return

    ref_close = ref_data['Close']

    for ticker in tickers:
        try:
            data = yf.download(ticker, period=period)
        except Exception as e:
            st.error(f"Erreur lors du téléchargement des données pour {ticker}: {e}")
            continue

        if data.empty:
            st.warning(f"Aucune donnée disponible pour {ticker}.")
            continue

        # Calculer la courbe différentielle
        diff_curve = data['Close'] / ref_close

        # Créer le graphique
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data.index, y=diff_curve,
            mode='lines', name=f'{ticker} / {ref_ticker}'
        ))

        # Ajouter la SMA si cochée
        if show_sma:
            sma_diff = diff_curve.rolling(window=sma_period).mean()
            fig.add_trace(go.Scatter(
                x=data.index, y=sma_diff,
                mode='lines',
                name=f'SMA {sma_period}',
                line=dict(color='yellow')
            ))

        fig.update_layout(
            title=f"Courbe différentielle {ticker} / {ref_ticker} - {period} d'historique",
            xaxis_title="Date",
            yaxis_title="Ratio"
        )

        st.plotly_chart(fig)

# Fonction pour charger une liste à partir d'un fichier texte
def load_list(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return [line.strip() for line in f.readlines()]
    else:
        st.warning(f"Le fichier {filename} est introuvable.")
        return []

# Fonction pour sauvegarder une liste dans un fichier texte
def save_list(filename, items):
    with open(filename, 'w') as f:
        f.writelines([item + '\n' for item in items])

# Définition des onglets
st.title("Suivi des ETF, Actions et Devises")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Indices", "Indices - différentiels", "Actions", "Actions - différentiels", "Devises"])

# Onglet 1 : Indices
with tab1:
    st.subheader("Graphique en chandelier des Indices")

    # Charger la liste des ETF
    selected_etfs = load_list('etf_list.txt')

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_chandeliers_etf"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    # Saisie des ETF
    etfs_input = st.text_input("Entrez les symboles des ETF séparés par des virgules", ','.join(selected_etfs), key="etf_input")
    etfs = [etf.strip() for etf in etfs_input.split(",")]

    # Sauvegarder la liste des ETF
    if st.button("Sauvegarder la liste des ETF"):
        save_list('etf_list.txt', etfs)

    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True, key="sma_etf")
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30, key="sma_period_etf")

    display_candlestick(etfs, period, show_sma, sma_period, key_prefix="etfs")

# Onglet 2 : Indices - Courbes différentielles
with tab2:
    st.subheader("Courbes différentielles entre les Indices")

    # Charger la liste des ETF
    selected_etfs = load_list('etf_list.txt')

    # Choisir l'ETF de référence
    etf_ref = st.selectbox('Choisissez l\'ETF de référence pour la division', selected_etfs, key="etf_ref_diff")

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_diff_etf"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    show_sma_diff = st.checkbox('Afficher la moyenne mobile simple (SMA) pour les courbes différentielles', value=True, key="sma_diff_etf")
    if show_sma_diff:
        sma_diff_period = st.slider('Choisissez le nombre de périodes pour la SMA des courbes différentielles', min_value=5, max_value=100, value=30, key="sma_diff_period_etf")

    display_differential_curves(selected_etfs, etf_ref, period, show_sma_diff, sma_diff_period, key_prefix="etfs_diff")

# Onglet 3 : Actions
with tab3:
    st.subheader("Graphique en chandelier des Actions")

    # Charger la liste des actions
    selected_actions = load_list('action_list.txt')

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_chandeliers_actions"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    # Saisie des actions
    actions_input = st.text_input("Entrez les symboles des actions séparés par des virgules", ','.join(selected_actions), key="action_input")
    actions = [action.strip() for action in actions_input.split(",")]

    # Sauvegarder la liste des actions
    if st.button("Sauvegarder la liste des actions"):
        save_list('action_list.txt', actions)

    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True, key="sma_actions")
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30, key="sma_period_actions")

    display_candlestick(actions, period, show_sma, sma_period, key_prefix="actions")

# Onglet 4 : Actions - Courbes différentielles
with tab4:
    st.subheader("Courbes différentielles entre les Actions")

    # Charger la liste des actions
    selected_actions = load_list('action_list.txt')

    # Saisie libre de l'action de référence
    action_ref = st.text_input('Entrez l\'action de référence pour la division', key="action_ref_diff")

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_diff_actions"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    show_sma_diff = st.checkbox('Afficher la moyenne mobile simple (SMA) pour les courbes différentielles', value=True, key="sma_diff_actions")
    if show_sma_diff:
        sma_diff_period = st.slider('Choisissez le nombre de périodes pour la SMA des courbes différentielles', min_value=5, max_value=100, value=30, key="sma_diff_period_actions")

    display_differential_curves(selected_actions, action_ref, period, show_sma_diff, sma_diff_period, key_prefix="actions_diff")

# Onglet 5 : Devises
with tab5:
    st.subheader("Graphique en chandelier des Devises")

    # Charger la liste des devises
    selected_devises = load_list('devises_list.txt')

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_chandeliers_devises"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    # Saisie des devises
    devises_input = st.text_input("Entrez les symboles des devises séparés par des virgules", ','.join(selected_devises), key="devises_input")
    devises = [devise.strip() for devise in devises_input.split(",")]

    # Sauvegarder la liste des devises
    if st.button("Sauvegarder la liste des devises"):
        save_list('devises_list.txt', devises)

    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True, key="sma_devises")
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30, key="sma_period_devises")

    display_candlestick(devises, period, show_sma, sma_period, key_prefix="devises")
