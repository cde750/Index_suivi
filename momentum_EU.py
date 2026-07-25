"""
Application Streamlit - Stratégie Momentum S&P 500
Signal 12-1 classique avec paramètres configurables.
Lancer avec : streamlit run momentum_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

# ---------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------
st.set_page_config(page_title="Momentum S&P 500", layout="wide", page_icon="📈")
st.title("📈 Backtest Stratégie Momentum — S&P 500")
st.caption(
    "⚠️ Univers = composition **actuelle** du S&P 500 → biais du survivant. "
    "Résultats à interpréter avec prudence. Usage éducatif uniquement."
)

# ---------------------------------------------------------------
# Sidebar : paramètres
# ---------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Paramètres")

    start_date = st.date_input("Date de début", value=pd.to_datetime("2015-01-01"))
    end_date = st.date_input("Date de fin", value=pd.to_datetime("today"))

    st.subheader("Signal momentum")
    lookback = st.slider("Période de lookback (mois)", 3, 12, 12)
    skip = st.slider("Mois exclus (skip récent)", 0, 3, 1)

    st.subheader("Portefeuille")
    n_stocks = st.slider("Nombre de titres détenus", 5, 100, 30, step=5)
    rebal_freq = st.selectbox("Fréquence de rebalancement",
                              ["Mensuel", "Trimestriel"], index=0)
    weighting = st.selectbox("Pondération", ["Égale", "Proportionnelle au momentum"])

    st.subheader("Coûts")
    cost_bps = st.slider("Coûts de transaction (bps par trade)", 0, 50, 10)

    st.subheader("Univers")
    max_tickers = st.slider("Nb max de tickers téléchargés", 50, 503, 503,
                            help="Réduire pour un test rapide")

    run = st.button("🚀 Lancer le backtest", type="primary", use_container_width=True)

# ---------------------------------------------------------------
# Fonctions données (mises en cache)
# ---------------------------------------------------------------
import requests
from io import StringIO

@st.cache_data
def get_sp500_tickers():
    """Récupère la liste des tickers S&P 500 depuis Wikipedia."""
    url = "https://en.wikipedia.org/wiki/EURO_STOXX_50"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # lève une erreur si problème
    
    table = pd.read_html(StringIO(response.text))[0]
    tickers = table["Ticker"].tolist()
    sectors = dict(zip(table["Ticker"],
                       table["GICS Sector"]))
    st.write(table)
    st.write(tickers)
    st.write(sectors)
    return tickers, sectors

@st.cache_data(ttl=86400, show_spinner=False)
def download_prices(tickers, start, end):
    """Télécharge les prix ajustés (dividendes inclus)."""
    data = yf.download(tickers, start=start, end=end,
                       auto_adjust=True, progress=False, threads=True)
    prices = data["Close"]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()
    # Nettoyage : retirer les colonnes trop incomplètes
    prices = prices.dropna(axis=1, thresh=int(len(prices) * 0.6))
    return prices


@st.cache_data(ttl=86400, show_spinner=False)
def download_benchmark(start, end):
    spy = yf.download("SPY", start=start, end=end,
                      auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]
    return spy


# ---------------------------------------------------------------
# Moteur de backtest
# ---------------------------------------------------------------
def run_backtest(prices, lookback, skip, n_stocks, rebal_freq,
                 weighting, cost_bps):
    """Backtest momentum avec rebalancement périodique."""
    monthly = prices.resample("ME").last()
    rets_monthly = monthly.pct_change()

    # Signal momentum : perf de t-lookback à t-skip
    momentum = monthly.shift(skip) / monthly.shift(lookback) - 1

    # Dates de rebalancement
    step = 1 if rebal_freq == "Mensuel" else 3
    rebal_dates = momentum.index[lookback::step]

    daily_rets = prices.pct_change()
    portfolio_rets = []
    weights_history = {}
    turnover_list = []
    prev_weights = pd.Series(dtype=float)

    for i, date in enumerate(rebal_dates):
        # --- Sélection des titres ---
        signal = momentum.loc[date].dropna()
        # Exiger un historique complet sur la période de lookback
        valid = monthly.loc[:date].tail(lookback + 1).dropna(axis=1).columns
        signal = signal[signal.index.isin(valid)]
        if len(signal) < n_stocks:
            continue
        top = signal.nlargest(n_stocks)

        # --- Pondération ---
        if weighting == "Égale":
            w = pd.Series(1 / n_stocks, index=top.index)
        else:
            pos = top - top.min() + 1e-6
            w = pos / pos.sum()

        weights_history[date] = w

        # --- Turnover et coûts ---
        all_idx = w.index.union(prev_weights.index)
        turnover = (w.reindex(all_idx, fill_value=0)
                    - prev_weights.reindex(all_idx, fill_value=0)).abs().sum() / 2
        turnover_list.append(turnover)
        cost = turnover * 2 * cost_bps / 10000  # achat + vente
        prev_weights = w

        # --- Rendements jusqu'au prochain rebalancement ---
        next_date = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else prices.index[-1]
        period = daily_rets.loc[date:next_date, w.index].iloc[1:]
        if period.empty:
            continue
        # Dérive des poids intra-période (buy & hold entre rebalancements)
        cum = (1 + period).cumprod()
        port_val = (cum * w).sum(axis=1)
        port_rets = port_val.pct_change()
        port_rets.iloc[0] = port_val.iloc[0] - 1
        port_rets.iloc[0] -= cost  # coûts appliqués au rebalancement
        portfolio_rets.append(port_rets)

    if not portfolio_rets:
        return None, None, None
    strat_rets = pd.concat(portfolio_rets)
    strat_rets = strat_rets[~strat_rets.index.duplicated(keep="first")]
    return strat_rets, weights_history, np.mean(turnover_list)


def compute_metrics(rets, freq=252):
    """Métriques de performance standard."""
    cum = (1 + rets).cumprod()
    n_years = len(rets) / freq
    cagr = cum.iloc[-1] ** (1 / n_years) - 1
    vol = rets.std() * np.sqrt(freq)
    sharpe = (rets.mean() * freq) / vol if vol > 0 else np.nan
    dd = cum / cum.cummax() - 1
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    return {
        "CAGR": f"{cagr:.2%}",
        "Volatilité": f"{vol:.2%}",
        "Sharpe": f"{sharpe:.2f}",
        "Max Drawdown": f"{max_dd:.2%}",
        "Calmar": f"{calmar:.2f}",
        "Perf totale": f"{cum.iloc[-1] - 1:.2%}",
    }, cum, dd


# ---------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------
if run:
    with st.spinner("📥 Récupération de la liste S&P 500..."):
        tickers, sectors = get_sp500_tickers()
        tickers = tickers[:max_tickers]

    # On télécharge avec une marge pour calculer le momentum dès le début
    buffer_start = pd.to_datetime(start_date) - pd.DateOffset(months=lookback + 2)

    with st.spinner(f"📥 Téléchargement des prix de {len(tickers)} titres "
                    "(peut prendre 1-2 min)..."):
        prices = download_prices(tuple(tickers), buffer_start, end_date)
        spy = download_benchmark(start_date, end_date)

    st.success(f"✅ {prices.shape[1]} titres avec données exploitables.")

    with st.spinner("⚙️ Backtest en cours..."):
        strat_rets, weights_hist, avg_turnover = run_backtest(
            prices, lookback, skip, n_stocks, rebal_freq, weighting, cost_bps
        )

    if strat_rets is None:
        st.error("Pas assez de données pour ces paramètres. "
                 "Élargissez la période ou réduisez le lookback.")
        st.stop()

    # Aligner sur la période demandée
    strat_rets = strat_rets.loc[str(start_date):]
    spy_rets = spy.pct_change().dropna()
    common_idx = strat_rets.index.intersection(spy_rets.index)
    strat_rets, spy_rets = strat_rets.loc[common_idx], spy_rets.loc[common_idx]

    metrics_strat, cum_strat, dd_strat = compute_metrics(strat_rets)
    metrics_spy, cum_spy, dd_spy = compute_metrics(spy_rets)

    # -----------------------------------------------------------
    # Affichage des résultats
    # -----------------------------------------------------------
    st.header("📊 Résultats")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    cols = [col1, col2, col3, col4, col5, col6]
    for col, (name, val) in zip(cols, metrics_strat.items()):
        col.metric(f"{name} (Stratégie)", val, delta=None)
    st.caption(f"Turnover moyen par rebalancement : {avg_turnover:.1%}")

    # --- Tableau comparatif ---
    comp = pd.DataFrame({"Momentum": metrics_strat, "SPY (Buy & Hold)": metrics_spy})
    st.dataframe(comp, use_container_width=True)

    # --- Courbe de performance ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cum_strat.index, y=cum_strat,
                             name="Stratégie Momentum", line=dict(width=2)))
    fig.add_trace(go.Scatter(x=cum_spy.index, y=cum_spy,
                             name="SPY", line=dict(width=2, dash="dash")))
    fig.update_layout(title="Performance cumulée (base 1)",
                      yaxis_type="log", height=500,
                      legend=dict(orientation="h", y=1.05))
    st.plotly_chart(fig, use_container_width=True)

    # --- Drawdown ---
    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(x=dd_strat.index, y=dd_strat, fill="tozeroy",
                                name="Momentum"))
    fig_dd.add_trace(go.Scatter(x=dd_spy.index, y=dd_spy,
                                name="SPY", line=dict(dash="dash")))
    fig_dd.update_layout(title="Drawdown", yaxis_tickformat=".0%", height=350)
    st.plotly_chart(fig_dd, use_container_width=True)

    # --- Rendements annuels ---
    yearly_strat = (1 + strat_rets).resample("YE").prod() - 1
    yearly_spy = (1 + spy_rets).resample("YE").prod() - 1
    yearly = pd.DataFrame({
        "Momentum": yearly_strat.values,
        "SPY": yearly_spy.reindex(yearly_strat.index).values
    }, index=yearly_strat.index.year)
    fig_yr = go.Figure()
    fig_yr.add_trace(go.Bar(x=yearly.index, y=yearly["Momentum"], name="Momentum"))
    fig_yr.add_trace(go.Bar(x=yearly.index, y=yearly["SPY"], name="SPY"))
    fig_yr.update_layout(title="Rendements annuels", yaxis_tickformat=".0%",
                         barmode="group", height=350)
    st.plotly_chart(fig_yr, use_container_width=True)

    # --- Portefeuille actuel ---
    st.header("🗂️ Dernier portefeuille sélectionné")
    last_date = max(weights_hist.keys())
    last_w = weights_hist[last_date].sort_values(ascending=False)
    df_port = pd.DataFrame({
        "Ticker": last_w.index,
        "Poids": last_w.values,
        "Secteur": [sectors.get(t, "N/A") for t in last_w.index],
    })
    st.caption(f"Rebalancement du {last_date.date()}")

    c1, c2 = st.columns([1, 1])
    with c1:
        st.dataframe(df_port.style.format({"Poids": "{:.2%}"}),
                     use_container_width=True, height=400)
    with c2:
        sector_w = df_port.groupby("Secteur")["Poids"].sum().sort_values()
        fig_sec = go.Figure(go.Bar(x=sector_w.values, y=sector_w.index,
                                   orientation="h"))
        fig_sec.update_layout(title="Exposition sectorielle",
                              xaxis_tickformat=".0%", height=400)
        st.plotly_chart(fig_sec, use_container_width=True)

    # --- Export ---
    st.download_button(
        "💾 Télécharger les rendements quotidiens (CSV)",
        strat_rets.to_csv().encode(),
        file_name="momentum_returns.csv",
        mime="text/csv",
    )
else:
    st.info("👈 Configurez les paramètres dans la barre latérale puis "
            "cliquez sur **Lancer le backtest**.")
