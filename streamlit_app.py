import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go

# Fonction pour charger les tickers d'ETF à partir d'un fichier
def load_etf_list(file_path):
    try:
        with open(file_path, 'r') as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return []

# Fonction pour sauvegarder les tickers d'ETF dans un fichier
def save_etf_list(file_path, etfs):
    with open(file_path, 'w') as f:
        f.write("\n".join(etfs))

# Définir le chemin du fichier contenant la liste des ETFs
ETF_FILE = 'etf_list.txt'

# Charger la liste des ETFs depuis le fichier
etfs = load_etf_list(ETF_FILE)

# ETFs avec une étoile (ajouter une étoile verte au titre du graphique)
starred_etfs = ["SP5.PA", "UST.PA", "MGT.PA", "WLD.PA"]

# Titre de l'application
st.title("Suivi des ETFs avec Yahoo Finance")

# Créer deux onglets dans l'interface Streamlit
tab1, tab2 = st.tabs(["Graphiques en chandeliers", "Courbes différentielles"])

# Premier onglet : Graphiques en chandeliers pour chaque ETF
with tab1:
    st.subheader("Graphiques en chandeliers pour chaque ETF")

    # Utilisation de st.text_area pour entrer les tickers, avec la liste actuelle comme valeur par défaut
    tickers_input = st.text_area(
        'Entrez les tickers des ETFs (un par ligne) :',
        value="\n".join(etfs)  # Charger la liste dans le text_area
    )

    # Conversion de la chaîne de tickers en une liste
    selected_etfs = [ticker.strip() for ticker in tickers_input.splitlines() if ticker.strip()]

    # Sauvegarder les tickers mis à jour dans le fichier lors du clic sur le bouton
    if st.button('Enregistrer la liste d\'ETFs'):
        save_etf_list(ETF_FILE, selected_etfs)
        st.success("La liste des ETFs a été sauvegardée.")

    # Période : choix entre 2 ans ou 5 ans (par défaut 5 ans)
    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,  # 5 ans sélectionné par défaut
        key="period_chandeliers"  # Ajout d'une clé unique
    )

    # Conversion de la sélection en format acceptable pour yfinance
    period = "2y" if selected_period == '2 ans' else "5y"

    # Option pour activer la moyenne mobile simple (SMA), activée par défaut
    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True)

    # Si SMA activée, choix du nombre de périodes pour la moyenne mobile
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30)

    # Boucle sur les ETFs sélectionnés
    for ticker in selected_etfs:
        # Ajout de l'étoile verte pour les ETFs dans la liste starred_etfs
        title_prefix = "⭐ " if ticker in starred_etfs else ""

        # Création du titre avec ou sans étoile
        title = f"{title_prefix}Cours de l'ETF {ticker} - {selected_period} d'historique"

        st.subheader(title)

        # Récupération des données de l'ETF
        etf_data = yf.download(ticker, period=period)

        # Vérification et conversion de l'index en DatetimeIndex si nécessaire
        if not isinstance(etf_data.index, pd.DatetimeIndex):
            etf_data.index = pd.to_datetime(etf_data.index)

        # Résample les données pour obtenir un échantillonnage hebdomadaire (W = Weekly)
        etf_data_weekly = etf_data.resample('W').agg({'Open': 'first', 
                                                      'High': 'max',
                                                      'Low': 'min', 
                                                      'Close': 'last',
                                                      'Volume': 'sum'})

        # Création du graphique en chandeliers avec Plotly
        fig = go.Figure(data=[go.Candlestick(x=etf_data_weekly.index,
                                             open=etf_data_weekly['Open'],
                                             high=etf_data_weekly['High'],
                                             low=etf_data_weekly['Low'],
                                             close=etf_data_weekly['Close'],
                                             name=f'{ticker}')])

        # Si l'option de la SMA est activée, calculer et ajouter la SMA au graphique
        if show_sma:
            etf_data_weekly['SMA'] = etf_data_weekly['Close'].rolling(window=sma_period).mean()

            fig.add_trace(go.Scatter(
                x=etf_data_weekly.index,
                y=etf_data_weekly['SMA'],
                mode='lines',
                name=f'SMA {sma_period} périodes',
                line=dict(color='yellow', width=2)
            ))

        fig.update_layout(
            title=title,
            xaxis_title='Date',
            yaxis_title='Prix (€)',
            xaxis_rangeslider_visible=False  # Cacher le range slider pour des chandeliers
        )

        # Affichage du graphique dans Streamlit
        st.plotly_chart(fig)

        # Option pour afficher le tableau de données
        if st.checkbox(f'Afficher les données sous forme de tableau pour {ticker}', key=f'table_{ticker}'):
            st.subheader(f'Tableau des données hebdomadaires pour {ticker}')
            st.write(etf_data_weekly[['Open', 'High', 'Low', 'Close']].head())

# Deuxième onglet : Courbes différentielles
with tab2:
    st.subheader("Courbes différentielles entre les ETFs")

    # Choix de l'ETF de référence
    etf_ref = st.selectbox('Choisissez l\'ETF de référence pour la division', selected_etfs, index=0)

    # Période : choix entre 2 ans ou 5 ans (par défaut 5 ans)
    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,  # 5 ans sélectionné par défaut
        key="period_diff"  # Ajout d'une clé unique
    )

    # Conversion de la sélection en format acceptable pour yfinance
    period = "2y" if selected_period == '2 ans' else "5y"

    # Option pour activer la moyenne mobile simple (SMA) pour les courbes différentielles, activée par défaut
    show_sma_diff = st.checkbox('Afficher la moyenne mobile simple (SMA) pour les courbes différentielles', value=True)

    # Si SMA activée, choix du nombre de périodes pour la SMA
    if show_sma_diff:
        sma_diff_period = st.slider('Choisissez le nombre de périodes pour la SMA des courbes différentielles', min_value=5, max_value=100, value=30)

    # Récupérer les données de l'ETF de référence
    etf_ref_data = yf.download(etf_ref, period=period)

    # Vérification et conversion de l'index en DatetimeIndex si nécessaire
    if not isinstance(etf_ref_data.index, pd.DatetimeIndex):
        etf_ref_data.index = pd.to_datetime(etf_ref_data.index)

    # Resample pour obtenir les prix hebdomadaires
    etf_ref_data = etf_ref_data.resample('W').agg({'Close': 'last'})

    # Boucle sur les ETFs pour créer des courbes différentielles
    for ticker in selected_etfs:
        if ticker != etf_ref:  # Ne pas comparer l'ETF de référence avec lui-même
            st.subheader(f"Courbe différentielle {ticker}/{etf_ref}")

            # Récupérer les données de l'ETF actuel
            etf_data = yf.download(ticker, period=period)

            # Vérification et conversion de l'index en DatetimeIndex si nécessaire
            if not isinstance(etf_data.index, pd.DatetimeIndex):
                etf_data.index = pd.to_datetime(etf_data.index)

            # Resample pour obtenir les prix hebdomadaires
            etf_data = etf_data.resample('W').agg({'Close': 'last'})

            # Calcul de la courbe différentielle (division des prix de clôture)
            differential = etf_data['Close'] / etf_ref_data['Close']

            # Création du graphique de la courbe différentielle
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=etf_data.index,
                y=differential,
                mode='lines',
                name=f'{ticker}/{etf_ref}',
                line=dict(width=2)
            ))

            # Si l'option de la SMA est activée, ajouter la SMA au graphique
            if show_sma_diff:
                differential_sma = differential.rolling(window=sma_diff_period).mean()

                fig.add_trace(go.Scatter(
                    x=etf_data.index,
                    y=differential_sma,
                    mode='lines',
                    name=f'SMA {sma_diff_period} périodes',
                    line=dict(color='yellow', width=2)
                ))

            fig.update_layout(
                title=f'Courbe différentielle {ticker}/{etf_ref}',
                xaxis_title='Date',
                yaxis_title=f'{ticker}/{etf_ref}',
            )

            # Affichage du graphique dans Streamlit
            st.plotly_chart(fig)

# Footer
st.write("Données fournies par Yahoo Finance")
