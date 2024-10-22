import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go

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

# Cacher les données téléchargées
@st.cache_data(ttl=60*60*24)  # Cache pour 24 heures (ajustez la durée selon vos besoins)
def get_ticker_data(ticker, period):
    data = yf.download(ticker, period=period)
    if data.empty:
        return None
    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index)
    return data.resample('W').agg({'Close': 'last', 'Open': 'first', 'High': 'max', 'Low': 'min'})

@st.cache_data(ttl=60*60*24)  # Cache pour 24 heures
def get_ticker_close_data(ticker, period):
    data = yf.download(ticker, period=period)
    if data.empty:
        return None
    return data.resample('W').agg({'Close': 'last'})

# Fonction pour afficher les graphiques en chandelier avec des lignes horizontales
def display_candlestick(tickers, period, show_sma, sma_period, key_prefix):
    # Charger les valeurs des lignes horizontales
    action_values = load_action_values('action_values.txt')

    for ticker in tickers:
        st.subheader(f"Cours de {ticker} - {period} d'historique")

        # Récupérer les données à partir du cache
        data = get_ticker_data(ticker, period)
        if data is None:
            st.warning(f"Aucune donnée trouvée pour {ticker}.")
            continue

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

        # Ajouter une ligne horizontale si disponible
        if ticker in action_values:
            fig.add_shape(type="line",
                          x0=data.index.min(), x1=data.index.max(),
                          y0=action_values[ticker], y1=action_values[ticker],
                          line=dict(color="Red", width=2, dash="dash"))
            fig.add_trace(go.Scatter(
                x=[data.index.min()],
                y=[action_values[ticker]],
                text=[f"Seuil: {action_values[ticker]}"],
                mode="text",
                showlegend=False
            ))

        fig.update_layout(
            title=f"Cours de {ticker} - {period} d'historique",
            xaxis_title='Date',
            yaxis_title='Prix',
        )

        st.plotly_chart(fig)

# Fonction pour afficher les courbes différentielles
def display_differential_curves(tickers, ref_ticker, period, show_sma, sma_period, key_prefix):
    ref_data = get_ticker_close_data(ref_ticker, period)
    if ref_data is None:
        st.warning(f"Aucune donnée trouvée pour {ref_ticker}.")
        return

    for ticker in tickers:
        if ticker == ref_ticker:
            continue

        st.subheader(f"Différentiel entre {ticker} et {ref_ticker}")

        ticker_data = get_ticker_close_data(ticker, period)
        if ticker_data is None:
            st.warning(f"Aucune donnée trouvée pour {ticker}.")
            continue

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

        st.plotly_chart(fig)

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

    # Ajouter un radio pour choisir la source de l'action de référence
    ref_choice = st.radio(
        "Choisissez la référence pour la division :", 
        ('Entrer une action manuellement', '^FCHI', '^STOXX'), 
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

    # Affichage des courbes différentielles uniquement si une action de référence est sélectionnée ou entrée
    if action_ref:
        display_differential_curves(selected_actions, action_ref, period, show_sma_diff, sma_diff_period, key_prefix="actions_diff")
    else:
        st.warning("Veuillez entrer ou sélectionner une action de référence pour afficher les courbes différentielles.")



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
    devises_input = st.text_input("Entrez les symboles des devises séparés par des virgules", ','.join(selected_devises), key="devise_input")
    devises = [devise.strip() for devise in devises_input.split(",")]

    # Sauvegarder la liste des devises
    if st.button("Sauvegarder la liste des devises"):
        save_list('devises_list.txt', devises)

    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True, key="sma_devises")
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30, key="sma_period_devises")

    display_candlestick(devises, period, show_sma, sma_period, key_prefix="devises")


    # Onglet 6 : Recherche
with tab6:
    st.subheader("Graphique en chandelier des valeurs recherchées")

    # Charger la liste des valeurs recherchées
    selected_research = load_list('recherche.txt')

    selected_period = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_chandeliers_research"
    )
    period = "2y" if selected_period == '2 ans' else "5y"

    # Saisie des valeurs recherchées
    research_input = st.text_input("Entrez les symboles des valeurs recherchées séparés par des virgules", ','.join(selected_research), key="research_input")
    research_items = [item.strip() for item in research_input.split(",")]

    # Sauvegarder la liste des valeurs recherchées
    if st.button("Sauvegarder la liste des valeurs recherchées"):
        save_list('recherche.txt', research_items)

    show_sma = st.checkbox('Afficher la moyenne mobile simple (SMA)', value=True, key="sma_research")
    if show_sma:
        sma_period = st.slider('Choisissez le nombre de périodes pour la SMA', min_value=5, max_value=100, value=30, key="sma_period_research")

    display_candlestick(research_items, period, show_sma, sma_period, key_prefix="research")


# Onglet 7 : Recherche - Différentiels
with tab7:
    st.subheader("Courbes différentielles entre les éléments de Recherche")

    # Charger la liste des éléments de recherche
    selected_recherche = load_list('recherche.txt')

    # Ajouter un radio pour choisir la source de la référence
    ref_choice_recherche = st.radio(
        "Choisissez la référence pour la division :", 
        ('Entrer une action ou indice manuellement', '^FCHI', '^STOXX', '^SPX'), 
        key="ref_choice_recherche"
    )

    # Si l'utilisateur choisit d'entrer manuellement, afficher une zone de texte
    if ref_choice_recherche == 'Entrer une action ou indice manuellement':
        recherche_ref = st.text_input('Entrez l\'action ou l\'indice de référence pour la division', key="recherche_ref_diff")
    else:
        # Si l'utilisateur choisit ^FCHI ou ^STOXX, utiliser cette valeur
        recherche_ref = ref_choice_recherche

    selected_period_recherche = st.radio(
        "Choisissez la profondeur historique des données :",
        ('2 ans', '5 ans'),
        index=1,
        key="period_diff_recherche"
    )
    period_recherche = "2y" if selected_period_recherche == '2 ans' else "5y"

    show_sma_diff_recherche = st.checkbox('Afficher la moyenne mobile simple (SMA) pour les courbes différentielles', value=True, key="sma_diff_recherche")
    if show_sma_diff_recherche:
        sma_diff_period_recherche = st.slider('Choisissez le nombre de périodes pour la SMA des courbes différentielles', min_value=5, max_value=100, value=30, key="sma_diff_period_recherche")

    # Affichage des courbes différentielles uniquement si une référence est sélectionnée ou entrée
    if recherche_ref:
        display_differential_curves(selected_recherche, recherche_ref, period_recherche, show_sma_diff_recherche, sma_diff_period_recherche, key_prefix="recherche_diff")
    else:
        st.warning("Veuillez entrer ou sélectionner une référence pour afficher les courbes différentielles.")
