import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
from dividend import get_dividends  # Fonction pour obtenir les dividendes par ticker
from rend import dividendes_ratio  # Importer le ratio dividendes/action

# Fonction mise en cache pour télécharger les données de yfinance
@st.cache_data
def fetch_data(ticker, period):
    try:
        # Télécharger les données depuis yfinance
        data = yf.download(ticker, period=period)
        return data
    except Exception as e:
        st.error(f"Erreur lors de la récupération des données pour {ticker} : {e}")
        return None

# Fonction pour charger la liste depuis un fichier
def load_list(filename):
    try:
        with open(filename, 'r') as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return []

# Fonction pour sauvegarder la liste dans un fichier
def save_list(filename, items):
    with open(filename, 'w') as f:
        for item in items:
            f.write(f"{item}\n")

# Fonction pour charger les valeurs des lignes horizontales à partir d'un fichier
def load_action_values(filename):
    try:
        with open(filename, 'r') as f:
            return {line.split(':')[0]: float(line.split(':')[1]) for line in f.readlines()}
    except FileNotFoundError:
        return {}

# Fonction pour afficher les graphiques en chandelier avec des lignes horizontales
def display_candlestick(tickers, period, show_sma, sma_period, key_prefix):
    # Charger les valeurs des lignes horizontales
    action_values = load_action_values('action_values.txt')

    # Listes pour définir les préfixes en fonction des tickers
    green_square_list = ['SP5.PA', 'UST.PA', 'MGT.PA', 'WLD.PA', 'JPNH.PA', 'SGQI.PA', 'CRP.PA', 'GC=F']
    red_square_list = ['FDJ.PA', 'ENGI.PA', 'ORA.PA', 'STLAP.PA', 'CS.PA', 'EN.PA', 'DG.PA', 'TTE.PA', 'GLE.PA', 'BNP.PA', 'TFI.PA','GTT.PA','NXI.PA']

    for ticker in tickers:
        # Préfixe pour chaque ticker
        unique_key = f"{key_prefix}_{ticker}"

        # Déterminer le préfixe d'icône en fonction des listes de couleurs
        if ticker in green_square_list:
            title_prefix = "🟩 "  # Carré vert
        elif ticker in red_square_list:
            title_prefix = "🟥 "  # Carré rouge
        else:
            title_prefix = ""

        # Récupérer le rendement pour le ticker, si disponible
        yield_percentage = dividendes_ratio.get(ticker, None)  # None si le rendement est introuvable

        # Titre principal sans rendement
        st.subheader(f"{title_prefix}Cours de {ticker} - {period} d'historique")

         # Afficher le rendement en sous-titre, avec mise en couleur conditionnelle
        if yield_percentage is not None:
            # Affiche en orange si le rendement dépasse 5 %
            color = "orange" if yield_percentage > 5 else "default"
            st.markdown(f"<span style='color:{color}; font-weight:bold;'>Rendement : {yield_percentage}%</span>", unsafe_allow_html=True)


        # Récupérer les données de cours pour le ticker
        data = fetch_data(ticker, period)
        
        if data is None or data.empty:
            st.warning(f"Aucune donnée trouvée pour {ticker}.")
            continue

        # Resample les données hebdomadaires
        data = data.resample('W').agg({'Close': 'last', 'Open': 'first', 'High': 'max', 'Low': 'min'})

        # Création du graphique en chandelier
        fig = go.Figure(data=[go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name=ticker
        )])

        # Ajouter la moyenne mobile simple si activée
        if show_sma:
            data['SMA'] = data['Close'].rolling(window=sma_period).mean()
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data['SMA'],
                mode='lines',
                name=f'SMA {sma_period} périodes',
                line=dict(color='yellow', width=2)
            ))

        # Ajouter la ligne horizontale si une valeur est spécifiée pour ce ticker
        if ticker in action_values:
            fig.add_shape(type="line",
                          x0=data.index.min(), x1=data.index.max(),
                          y0=action_values[ticker], y1=action_values[ticker],
                          line=dict(color="Red", width=2, dash="dash"),
                          name=f'Valeur seuil {ticker}')
            fig.add_trace(go.Scatter(
                x=[data.index.min()],
                y=[action_values[ticker]],
                text=[f"Seuil: {action_values[ticker]}"],
                mode="text",
                showlegend=False
            ))

        fig.update_layout(
            #title=f"{title_prefix}Cours de {ticker} - {period} d'historique",
            xaxis_title='Date',
            yaxis_title='Prix',
        )

        # Utilisation de `key=unique_key` pour rendre chaque chart unique
        st.plotly_chart(fig, key=unique_key)

# Fonction pour afficher les courbes différentielles
def display_differential_curves(tickers, ref_ticker, period, show_sma, sma_period, key_prefix):
    for ticker in tickers:
        if ticker == ref_ticker:
            continue

        unique_key = f"{key_prefix}_{ticker}_diff"

        st.subheader(f"Différentiel entre {ticker} et {ref_ticker}")

        # Récupérer les données en utilisant la fonction mise en cache
        ref_data = fetch_data(ref_ticker, period)
        ticker_data = fetch_data(ticker, period)
        
        if ref_data is None or ticker_data is None or ref_data.empty or ticker_data.empty:
            st.warning(f"Aucune donnée trouvée pour {ticker} ou {ref_ticker}.")
            continue

        # Resample des données en semaines 
        ref_data = ref_data.resample('W').agg({'Close': 'last'})
        ticker_data = ticker_data.resample('W').agg({'Close': 'last'})

        # Calcul du différentiel
        diff_data = ticker_data['Close'] / ref_data['Close']

        # Création du graphique différentiel
        fig = go.Figure(data=[go.Scatter(
            x=diff_data.index,
            y=diff_data,
            mode='lines',
            name=f'Différentiel {ticker}/{ref_ticker}'
        )])

        # Ajouter la moyenne mobile simple si activée
        if show_sma:
            diff_data_sma = diff_data.rolling(window=sma_period).mean()
            fig.add_trace(go.Scatter(
                x=diff_data.index,
                y=diff_data_sma,
                mode='lines',
                name=f'SMA {sma_period} périodes',
                line=dict(color='yellow', width=2)
            ))

        fig.update_layout(
            title=f"Différentiel entre {ticker} et {ref_ticker}",
            xaxis_title='Date',
            yaxis_title='Ratio',
        )

        # Utilisation de `key=unique_key` pour rendre chaque chart unique
        st.plotly_chart(fig, key=unique_key)


# Onglets
tab1, tab2, tab3, tab4, tab5 , tab6, tab7 = st.tabs(["Indices", "Indices - différentiels", "Actions", "Actions - différentiels", "Devises", "Recherche", "Recherche - différentiels"])

# Onglet 1 : Indices
with tab1:
    st.subheader("Graphique en chandelier des ETFs")

    # Charger la liste des ETFs
    selected_etfs = load_list('etf_list.txt')

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_chandeliers_etfs"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    # Saisie des ETFs
    etfs_input = st.text_input("Entrez les symboles des ETFs séparés par des virgules", ','.join(selected_etfs), key="etf_input")
    etfs = [etf.strip() for etf in etfs_input.split(",")]

    # Sauvegarder la liste des ETFs
    if st.button("Sauvegarder la liste des ETFs"):
        save_list('etf_list.txt', etfs)

    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True, key="sma_etfs")
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30, key="sma_period_etfs")

    display_candlestick(etfs, period, show_sma, sma_period, key_prefix="etfs")

# Onglet 2 : Indices - Courbes différentielles
with tab2:
    st.subheader("Courbes différentielles entre les ETFs")

    # Charger la liste des ETFs
    selected_etfs = load_list('etf_list.txt')

    # Choix de l'ETF de référence
    etf_ref = st.selectbox('Choisissez l\'ETF de référence pour la division', selected_etfs, index=0, key="etf_ref_diff")

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_diff_etfs"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    show_sma_diff = st.checkbox('Afficher la moyenne mobile simple (SMA) pour les courbes différentielles', value=True, key="sma_diff_etfs")
    if show_sma_diff:
        sma_diff_period = st.slider('Choisissez le nombre de périodes pour la SMA des courbes différentielles', min_value=5, max_value=100, value=30, key="sma_diff_period_etfs")

    display_differential_curves(selected_etfs, etf_ref, period, show_sma_diff, sma_diff_period, key_prefix="etf_diff")

# Onglet 3 : Actions
with tab3:
    st.subheader("Graphique en chandelier des Actions")

    # Charger la liste des Actions
    selected_actions = load_list('actions_list.txt')

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_chandeliers_actions"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    # Saisie des Actions
    actions_input = st.text_input("Entrez les symboles des Actions séparés par des virgules", ','.join(selected_actions), key="actions_input")
    actions = [action.strip() for action in actions_input.split(",")]

    # Sauvegarder la liste des Actions
    if st.button("Sauvegarder la liste des Actions"):
        save_list('actions_list.txt', actions)

    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True, key="sma_actions")
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30, key="sma_period_actions")

    display_candlestick(actions, period, show_sma, sma_period, key_prefix="actions")

# Onglet 4 : Actions - Courbes différentielles
with tab4:
    st.subheader("Courbes différentielles entre les Actions")

    # Charger la liste des Actions
    selected_actions = load_list('actions_list.txt')

     # Ajouter un radio pour choisir la source de l'action de référence
    ref_choice = st.radio(
        "Choisissez la référence pour la division :", 
        ('^FCHI','^STOXX50E', '^SPX','Entrer une action manuellement'), 
        key="ref_choice"
    )

    # Si l'utilisateur choisit d'entrer une action manuellement, afficher une zone de texte
    if ref_choice == 'Entrer une action manuellement':
        action_ref = st.text_input('Entrez l\'action de référence pour la division', key="action_ref_diff")
    else:
        # Si l'utilisateur choisit ^FCHI ou ^STOXX, utiliser cette valeur
        action_ref = ref_choice

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

    display_differential_curves(selected_actions, action_ref, period, show_sma_diff, sma_diff_period, key_prefix="action_diff")

# Onglet 5 : Devises
with tab5:
    st.subheader("Graphique en chandelier des Devises")

    # Charger la liste des Devises
    selected_devises = load_list('devises_list.txt')

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_chandeliers_devises"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    # Saisie des Devises
    devises_input = st.text_input("Entrez les symboles des Devises séparés par des virgules", ','.join(selected_devises), key="devises_input")
    devises = [devise.strip() for devise in devises_input.split(",")]

    # Sauvegarder la liste des Devises
    if st.button("Sauvegarder la liste des Devises"):
        save_list('devises_list.txt', devises)

    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True, key="sma_devises")
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30, key="sma_period_devises")

    display_candlestick(devises, period, show_sma, sma_period, key_prefix="devises")

# Onglet 6 : Recherche
with tab6:
    st.subheader("Graphique en chandelier pour Recherche")

    # Charger la liste des symboles
    selected_recherche = load_list('recherche_list.txt')

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_chandeliers_recherche"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    # Saisie des symboles
    recherche_input = st.text_input("Entrez les symboles séparés par des virgules", ','.join(selected_recherche), key="recherche_input")
    recherche = [symb.strip() for symb in recherche_input.split(",")]

    # Sauvegarder la liste des symboles
    if st.button("Sauvegarder la liste des symboles pour Recherche"):
        save_list('recherche_list.txt', recherche)

    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True, key="sma_recherche")
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30, key="sma_period_recherche")

    display_candlestick(recherche, period, show_sma, sma_period, key_prefix="recherche")

# Onglet 7 : Recherche - Courbes différentielles
with tab7:
    st.subheader("Courbes différentielles pour Recherche")

    # Charger la liste des symboles
    selected_recherche = load_list('recherche_list.txt')

    # Ajouter un radio pour choisir la source de la référence
    ref_choice_recherche = st.radio(
        "Choisissez la référence pour la division :", 
        ('^FCHI', '^STOXX50E', '^SPX','Entrer une action ou indice manuellement'), 
        key="ref_choice_recherche"
    )

    # Si l'utilisateur choisit d'entrer manuellement, afficher une zone de texte
    if ref_choice_recherche == 'Entrer une action ou indice manuellement':
        recherche_ref = st.text_input('Entrez l\'action ou l\'indice de référence pour la division', key="recherche_ref_diff")
    else:
        # Si l'utilisateur choisit ^FCHI ou ^STOXX, utiliser cette valeur
        recherche_ref = ref_choice_recherche

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_diff_recherche"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    show_sma_diff = st.checkbox('Afficher la moyenne mobile simple (SMA) pour les courbes différentielles', value=True, key="sma_diff_recherche")
    if show_sma_diff:
        sma_diff_period = st.slider('Choisissez le nombre de périodes pour la SMA des courbes différentielles', min_value=5, max_value=100, value=30, key="sma_diff_period_recherche")

    display_differential_curves(selected_recherche, recherche_ref, period, show_sma_diff, sma_diff_period, key_prefix="recherche_diff")
