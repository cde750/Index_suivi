"""
Application Streamlit - Stratégie Momentum S&P 500
Version 3 : correction du biais du survivant + test de contrôle aléatoire.
Lancer avec : streamlit run momentum.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import requests
import re
from io import StringIO
from datetime import datetime

# ---------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------
st.set_page_config(page_title="Momentum S&P 500", layout="wide", page_icon="📈")
st.title("📈 Backtest Stratégie Momentum — S&P 500")

# ---------------------------------------------------------------
# Sidebar : paramètres
# ---------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Paramètres")

    start_date = st.date_input("Date de début", value=pd.to_datetime("2015-01-01"))
    end_date = st.date_input("Date de fin", value=pd.to_datetime("today"))

    st.subheader("Univers")
    use_historical = st.checkbox(
        "🔬 Corriger le biais du survivant",
        value=True,
        help="Reconstitue la composition historique du S&P 500 à partir "
             "de l'historique des changements (Wikipedia)."
    )
    include_delisted = st.checkbox(
        "Inclure les titres sortis de l'indice",
        value=True,
        disabled=not use_historical,
        help="Tente de télécharger les données des sociétés retirées. "
             "Beaucoup n'ont plus de données disponibles."
    )
    max_tickers = st.slider("Nb max de tickers téléchargés", 50, 1000, 600,
                            help="Réduire pour un test rapide")

    st.subheader("Signal momentum")
    lookback = st.slider("Période de lookback (mois)", 3, 12, 12)
    skip = st.slider("Mois exclus (skip récent)", 0, 3, 1)

    st.subheader("Portefeuille")
    n_stocks = st.slider("Nombre de titres détenus", 5, 100, 30, step=5)
    buffer_mult = st.slider(
        "Zone tampon (× N)", 1.0, 2.5, 1.0, step=0.1,
        help="1.0 = pas de tampon. 1.5 = on ne vend qu'au-delà du rang 1.5×N."
    )
    rebal_freq = st.selectbox("Fréquence de rebalancement",
                              ["Mensuel", "Trimestriel"], index=0)
    weighting = st.selectbox("Pondération", ["Égale", "Proportionnelle au momentum"])

    st.subheader("Coûts")
    cost_bps = st.slider("Coûts de transaction (bps par trade)", 0, 50, 10)

    st.subheader("🎲 Test de contrôle")
    run_random = st.checkbox(
        "Comparer à une sélection aléatoire",
        value=True,
        help="Rejoue la même mécanique avec des titres tirés au hasard. "
             "Si les résultats sont proches, le signal momentum n'apporte rien."
    )
    n_sims = st.slider("Nombre de simulations", 10, 200, 50, step=10,
                       disabled=not run_random)

    run = st.button("🚀 Lancer le backtest", type="primary",
                    use_container_width=True)

# ---------------------------------------------------------------
# Récupération de l'univers
# ---------------------------------------------------------------
@st.cache_data(ttl=86400)
def get_sp500_data():
    """Récupère la composition actuelle ET l'historique des changements."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))

    # --- Table 0 : composition actuelle ---
    current = tables[0].copy()
    current["Symbol"] = current["Symbol"].str.replace(".", "-", regex=False)
    tickers_now = current["Symbol"].tolist()
    sectors = dict(zip(current["Symbol"], current["GICS Sector"]))
    names = dict(zip(current["Symbol"], current["Security"]))

    # --- Table 1 : historique des changements ---
    changes = tables[1].copy()
    # Les colonnes sont en MultiIndex : (Date, Date), (Added, Ticker), etc.
    changes.columns = ["_".join(str(c) for c in col).strip()
                       if isinstance(col, tuple) else str(col)
                       for col in changes.columns]

    def find_col(pattern):
        for c in changes.columns:
            if re.search(pattern, c, re.IGNORECASE):
                return c
        return None

    col_date = find_col(r"date")
    col_added = find_col(r"added.*ticker|ticker.*added")
    col_removed = find_col(r"removed.*ticker|ticker.*removed")

    hist = pd.DataFrame({
        "date": pd.to_datetime(changes[col_date], errors="coerce"),
        "added": changes[col_added].astype(str).str.replace(".", "-", regex=False),
        "removed": changes[col_removed].astype(str).str.replace(".", "-", regex=False),
    }).dropna(subset=["date"])

    # Nettoyage des cellules vides
    for c in ["added", "removed"]:
        hist[c] = hist[c].replace(["nan", "", "—", "-"], np.nan)

    hist = hist.sort_values("date").reset_index(drop=True)
    return tickers_now, sectors, names, hist


@st.cache_data(ttl=86400)
def build_membership(tickers_now, hist, start, end, freq="ME"):
    """
    Reconstruit un masque booléen [date × ticker] = True si le titre
    était membre du S&P 500 à cette date.

    Méthode : on part de la composition actuelle et on remonte le temps
    en inversant chaque changement.
    """
    dates = pd.date_range(start=start, end=end, freq=freq)
    members = set(tickers_now)

    # On remonte du présent vers le passé
    membership_by_date = {}
    hist_desc = hist.sort_values("date", ascending=False)

    for d in reversed(dates):
        # Inverser tous les changements postérieurs à d
        changes_after = hist_desc[hist_desc["date"] > d]
        snapshot = set(tickers_now)
        for _, row in changes_after.iterrows():
            # Un titre ajouté après d n'était pas membre à d
            if pd.notna(row["added"]):
                snapshot.discard(row["added"])
            # Un titre retiré après d était membre à d
            if pd.notna(row["removed"]):
                snapshot.add(row["removed"])
        membership_by_date[d] = snapshot

    all_tickers = sorted(set().union(*membership_by_date.values()))
    mask = pd.DataFrame(False, index=dates, columns=all_tickers)
    for d, s in membership_by_date.items():
        mask.loc[d, list(s & set(all_tickers))] = True

    return mask


@st.cache_data(ttl=86400, show_spinner=False)
def download_prices(tickers, start, end):
    """Télécharge les prix ajustés. Robuste aux tickers invalides."""
    data = yf.download(list(tickers), start=start, end=end,
                       auto_adjust=True, progress=False, threads=True)
    if "Close" not in data:
        return pd.DataFrame()
    prices = data["Close"]
    if isinstance(prices, pd.Series):
        prices = prices.to_frame()
    # On garde tout ticker ayant au moins 60 jours de données
    prices = prices.dropna(axis=1, thresh=60)
    prices = prices.ffill(limit=5)
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
def run_backtest(prices, lookback, skip, n_stocks, rebal_freq, weighting,
                 cost_bps, membership=None, buffer_mult=1.0,
                 selection="momentum", seed=None):
    """
    Backtest momentum avec :
      - filtre d'appartenance historique à l'indice (membership)
      - zone tampon pour réduire le turnover
      - mode 'random' pour le test de contrôle

    selection : 'momentum' ou 'random'
    """
    rng = np.random.default_rng(seed)
    monthly = prices.resample("ME").last()
    momentum = monthly.shift(skip) / monthly.shift(lookback) - 1

    step = 1 if rebal_freq == "Mensuel" else 3
    rebal_dates = momentum.index[lookback::step]

    portfolio_rets = []
    weights_history = {}
    ranks_history = {}
    turnover_list = []
    prev_weights = pd.Series(dtype=float)
    n_buffer = int(np.ceil(n_stocks * buffer_mult))

    for i, date in enumerate(rebal_dates):
        signal = momentum.loc[date].dropna()

        # --- Filtre 1 : historique complet sur le lookback ---
        valid = monthly.loc[:date].tail(lookback + 1).dropna(axis=1).columns
        signal = signal[signal.index.isin(valid)]

        # --- Filtre 2 : appartenance à l'indice à cette date ---
        if membership is not None:
            idx = membership.index[membership.index <= date]
            if len(idx) == 0:
                continue
            in_index = membership.loc[idx[-1]]
            eligible = in_index[in_index].index
            signal = signal[signal.index.isin(eligible)]

        if len(signal) < n_stocks:
            continue

        # --- Sélection ---
        if selection == "random":
            chosen = rng.choice(signal.index, size=n_stocks, replace=False)
            top = signal.loc[chosen]
            ranks = pd.Series(np.arange(1, len(signal) + 1),
                              index=signal.sort_values(ascending=False).index)
        else:
            ranks = pd.Series(np.arange(1, len(signal) + 1),
                              index=signal.sort_values(ascending=False).index)
            if buffer_mult > 1.0 and len(prev_weights) > 0:
                held = [t for t in prev_weights.index if t in ranks.index]
                keep = [t for t in held if ranks[t] <= n_buffer]
                n_new = n_stocks - len(keep)
                if n_new > 0:
                    cands = [t for t in ranks.index if t not in keep][:n_new]
                    selected = keep + cands
                else:
                    selected = sorted(keep, key=lambda t: ranks[t])[:n_stocks]
                top = signal.loc[selected]
            else:
                top = signal.nlargest(n_stocks)

        ranks_history[date] = {"ranks": ranks, "signal": signal}

        # --- Pondération ---
        if weighting == "Égale":
            w = pd.Series(1 / len(top), index=top.index)
        else:
            pos = top - top.min() + 1e-6
            w = pos / pos.sum()

        weights_history[date] = w

        # --- Turnover et coûts ---
        all_idx = w.index.union(prev_weights.index)
        turnover = (w.reindex(all_idx, fill_value=0)
                    - prev_weights.reindex(all_idx, fill_value=0)).abs().sum() / 2
        turnover_list.append(turnover)
        cost = turnover * 2 * cost_bps / 10000
        prev_weights = w

        # --- Rendements jusqu'au prochain rebalancement ---
        next_date = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else prices.index[-1]
        px = prices.loc[date:next_date, w.index].ffill().dropna(axis=0, how="any")
        if len(px) < 2:
            continue

        period = px.pct_change().iloc[1:]
        cum = (1 + period).cumprod()
        port_val = (cum * w).sum(axis=1)
        port_rets = port_val.pct_change()
        port_rets.iloc[0] = port_val.iloc[0] - 1
        port_rets.iloc[0] -= cost
        portfolio_rets.append(port_rets)

    if not portfolio_rets:
        return None, None, None, None

    strat_rets = pd.concat(portfolio_rets)
    strat_rets = strat_rets[~strat_rets.index.duplicated(keep="first")]
    return strat_rets, weights_history, ranks_history, np.mean(turnover_list)


def compute_metrics(rets, freq=252):
    cum = (1 + rets).cumprod()
    n_years = len(rets) / freq
    cagr = cum.iloc[-1] ** (1 / n_years) - 1
    vol = rets.std() * np.sqrt(freq)
    sharpe = (rets.mean() * freq) / vol if vol > 0 else np.nan
    dd = cum / cum.cummax() - 1
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan
    return {
        "CAGR": cagr, "Volatilité": vol, "Sharpe": sharpe,
        "Max Drawdown": max_dd, "Calmar": calmar,
        "Perf totale": cum.iloc[-1] - 1,
    }, cum, dd


def fmt_metrics(m):
    return {
        "CAGR": f"{m['CAGR']:.2%}", "Volatilité": f"{m['Volatilité']:.2%}",
        "Sharpe": f"{m['Sharpe']:.2f}", "Max Drawdown": f"{m['Max Drawdown']:.2%}",
        "Calmar": f"{m['Calmar']:.2f}", "Perf totale": f"{m['Perf totale']:.2%}",
    }


# ---------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------
if not run:
    st.info("👈 Configurez les paramètres dans la barre latérale puis "
            "cliquez sur **Lancer le backtest**.")
    st.stop()

# --- 1. Univers ---
with st.spinner("📥 Récupération de la composition S&P 500..."):
    tickers_now, sectors, names, hist_changes = get_sp500_data()

buffer_start = pd.to_datetime(start_date) - pd.DateOffset(months=lookback + 2)
membership = None

if use_historical:
    with st.spinner("🔬 Reconstitution de la composition historique..."):
        membership = build_membership(tuple(tickers_now), hist_changes,
                                      buffer_start, end_date)
    universe = list(membership.columns)
    n_delisted = len([t for t in universe if t not in tickers_now])

    if not include_delisted:
        universe = [t for t in universe if t in tickers_now]
        membership = membership[[c for c in membership.columns if c in universe]]

    st.info(
        f"🔬 **Mode historique activé** — univers de {len(universe)} tickers, "
        f"dont {n_delisted} sortis de l'indice depuis {buffer_start.date()}. "
        f"{len(hist_changes)} changements de composition pris en compte."
    )
else:
    universe = tickers_now
    st.warning(
        "⚠️ **Biais du survivant actif** — l'univers est la composition "
        "actuelle appliquée rétroactivement. Les résultats sont optimistes."
    )

universe = universe[:max_tickers]

# --- 2. Prix ---
with st.spinner(f"📥 Téléchargement de {len(universe)} titres (1-3 min)..."):
    prices = download_prices(tuple(universe), buffer_start, end_date)
    spy = download_benchmark(start_date, end_date)

if prices.empty:
    st.error("Aucune donnée téléchargée.")
    st.stop()

avail = prices.shape[1]
missing = len(universe) - avail
st.success(
    f"✅ {avail} titres avec données exploitables"
    + (f" — {missing} tickers sans données (délistés/renommés)." if missing > 0 else ".")
)

if membership is not None:
    membership = membership[[c for c in membership.columns if c in prices.columns]]

# --- 3. Backtest momentum ---
with st.spinner("⚙️ Backtest momentum..."):
    strat_rets, weights_hist, ranks_hist, avg_turnover = run_backtest(
        prices, lookback, skip, n_stocks, rebal_freq, weighting, cost_bps,
        membership=membership, buffer_mult=buffer_mult, selection="momentum"
    )

if strat_rets is None:
    st.error("Pas assez de données pour ces paramètres.")
    st.stop()

strat_rets = strat_rets.loc[str(start_date):]
spy_rets = spy.pct_change().dropna()
common_idx = strat_rets.index.intersection(spy_rets.index)
strat_rets, spy_rets = strat_rets.loc[common_idx], spy_rets.loc[common_idx]

m_strat, cum_strat, dd_strat = compute_metrics(strat_rets)
m_spy, cum_spy, dd_spy = compute_metrics(spy_rets)

# --- 4. Test de contrôle aléatoire ---
random_results = None
if run_random:
    prog = st.progress(0.0, text="🎲 Simulations aléatoires...")
    sims = []
    for k in range(n_sims):
        r, _, _, _ = run_backtest(
            prices, lookback, skip, n_stocks, rebal_freq, weighting, cost_bps,
            membership=membership, buffer_mult=1.0,
            selection="random", seed=k
        )
        if r is not None:
            r = r.loc[str(start_date):].reindex(common_idx).fillna(0)
            sims.append(r)
        prog.progress((k + 1) / n_sims, text=f"🎲 Simulation {k+1}/{n_sims}")
    prog.empty()

    if sims:
        rand_df = pd.concat(sims, axis=1)
        rand_df.columns = [f"sim_{i}" for i in range(len(sims))]
        rand_metrics = pd.DataFrame(
            [compute_metrics(rand_df[c])[0] for c in rand_df.columns]
        )
        random_results = {"rets": rand_df, "metrics": rand_metrics}

# ===============================================================
# AFFICHAGE
# ===============================================================
st.header("📊 Résultats")

cols = st.columns(6)
for col, (name, val) in zip(cols, fmt_metrics(m_strat).items()):
    col.metric(name, val)
st.caption(f"Turnover moyen par rebalancement : {avg_turnover:.1%}")

# --- Tableau comparatif ---
comp_data = {"Momentum": fmt_metrics(m_strat), "SPY (Buy & Hold)": fmt_metrics(m_spy)}
if random_results is not None:
    med = random_results["metrics"].median()
    comp_data["Aléatoire (médiane)"] = {
        "CAGR": f"{med['CAGR']:.2%}", "Volatilité": f"{med['Volatilité']:.2%}",
        "Sharpe": f"{med['Sharpe']:.2f}", "Max Drawdown": f"{med['Max Drawdown']:.2%}",
        "Calmar": f"{med['Calmar']:.2f}", "Perf totale": f"{med['Perf totale']:.2%}",
    }
st.dataframe(pd.DataFrame(comp_data), use_container_width=True)

# ---------------------------------------------------------------
# TEST DE CONTRÔLE — section dédiée
# ---------------------------------------------------------------
if random_results is not None:
    st.header("🎲 Test de contrôle : le signal momentum apporte-t-il quelque chose ?")
    st.caption(
        f"{len(random_results['rets'].columns)} portefeuilles de {n_stocks} titres "
        "tirés au hasard dans le même univers, avec la même mécanique de "
        "rebalancement et les mêmes coûts."
    )

    rm = random_results["metrics"]
    cagr_rand = rm["CAGR"]
    sharpe_rand = rm["Sharpe"]

    pct_cagr = (cagr_rand < m_strat["CAGR"]).mean()
    pct_sharpe = (sharpe_rand < m_strat["Sharpe"]).mean()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("CAGR momentum", f"{m_strat['CAGR']:.2%}")
    k2.metric("CAGR aléatoire (médiane)", f"{cagr_rand.median():.2%}",
              delta=f"{m_strat['CAGR'] - cagr_rand.median():+.2%}")
    k3.metric("Percentile du momentum", f"{pct_cagr:.0%}",
              help="Part des portefeuilles aléatoires battus par le momentum.")
    k4.metric("Percentile (Sharpe)", f"{pct_sharpe:.0%}")

    # Verdict
    if pct_cagr >= 0.95:
        st.success(
            f"✅ **Le signal semble apporter de la valeur.** Le momentum bat "
            f"{pct_cagr:.0%} des portefeuilles aléatoires. L'écart de "
            f"{m_strat['CAGR'] - cagr_rand.median():.1%} de CAGR n'est "
            "probablement pas dû au hasard."
        )
    elif pct_cagr >= 0.75:
        st.warning(
            f"🟡 **Signal faible.** Le momentum bat {pct_cagr:.0%} des tirages "
            "aléatoires — c'est positif mais pas décisif. Une partie de la "
            "performance vient de l'univers, pas du signal."
        )
    else:
        st.error(
            f"🔴 **Le signal n'apporte rien de démontrable.** Le momentum ne bat "
            f"que {pct_cagr:.0%} des portefeuilles aléatoires. La performance "
            "observée provient essentiellement de l'univers et de la période, "
            "pas de la sélection momentum."
        )

    # Distribution des CAGR
    fig_dist = go.Figure()
    fig_dist.add_trace(go.Histogram(
        x=cagr_rand, nbinsx=25, name="Portefeuilles aléatoires",
        marker_color="lightsteelblue"
    ))
    fig_dist.add_vline(
        x=m_strat["CAGR"], line=dict(color="crimson", width=3),
        annotation_text=f"Momentum {m_strat['CAGR']:.1%}",
        annotation_position="top"
    )
    fig_dist.add_vline(
        x=m_spy["CAGR"], line=dict(color="grey", width=2, dash="dash"),
        annotation_text=f"SPY {m_spy['CAGR']:.1%}",
        annotation_position="bottom"
    )
    fig_dist.update_layout(
        title="Distribution du CAGR des portefeuilles aléatoires",
        xaxis_tickformat=".0%", height=380, showlegend=False
    )
    st.plotly_chart(fig_dist, use_container_width=True)

    # Faisceau de trajectoires
    fig_beam = go.Figure()
    rand_cum = (1 + random_results["rets"]).cumprod()
    for c in rand_cum.columns:
        fig_beam.add_trace(go.Scatter(
            x=rand_cum.index, y=rand_cum[c], mode="lines",
            line=dict(width=0.7, color="rgba(150,170,200,0.35)"),
            showlegend=False, hoverinfo="skip"
        ))
    fig_beam.add_trace(go.Scatter(
        x=rand_cum.index, y=rand_cum.median(axis=1), mode="lines",
        name="Médiane aléatoire", line=dict(color="steelblue", width=2, dash="dot")
    ))
    fig_beam.add_trace(go.Scatter(
        x=cum_strat.index, y=cum_strat, mode="lines",
        name="Momentum", line=dict(color="crimson", width=2.5)
    ))
    fig_beam.add_trace(go.Scatter(
        x=cum_spy.index, y=cum_spy, mode="lines",
        name="SPY", line=dict(color="black", width=2, dash="dash")
    ))
    fig_beam.update_layout(
        title="Momentum vs faisceau des portefeuilles aléatoires (échelle log)",
        yaxis_type="log", height=480,
        legend=dict(orientation="h", y=1.05)
    )
    st.plotly_chart(fig_beam, use_container_width=True)

    with st.expander("📋 Statistiques détaillées des simulations"):
        desc = rm.describe(percentiles=[.05, .25, .5, .75, .95]).T
        st.dataframe(
            desc.style.format({
                "mean": "{:.3f}", "std": "{:.3f}", "min": "{:.3f}",
                "5%": "{:.3f}", "25%": "{:.3f}", "50%": "{:.3f}",
                "75%": "{:.3f}", "95%": "{:.3f}", "max": "{:.3f}",
            }),
            use_container_width=True
        )

# ---------------------------------------------------------------
# Graphiques standards
# ---------------------------------------------------------------
st.header("📈 Performance")

fig = go.Figure()
fig.add_trace(go.Scatter(x=cum_strat.index, y=cum_strat,
                         name="Stratégie Momentum", line=dict(width=2)))
fig.add_trace(go.Scatter(x=cum_spy.index, y=cum_spy,
                         name="SPY", line=dict(width=2, dash="dash")))
fig.update_layout(title="Performance cumulée (base 1)", yaxis_type="log",
                  height=500, legend=dict(orientation="h", y=1.05))
st.plotly_chart(fig, use_container_width=True)

fig_dd = go.Figure()
fig_dd.add_trace(go.Scatter(x=dd_strat.index, y=dd_strat, fill="tozeroy",
                            name="Momentum"))
fig_dd.add_trace(go.Scatter(x=dd_spy.index, y=dd_spy, name="SPY",
                            line=dict(dash="dash")))
fig_dd.update_layout(title="Drawdown", yaxis_tickformat=".0%", height=350)
st.plotly_chart(fig_dd, use_container_width=True)

yearly_strat = (1 + strat_rets).resample("YE").prod() - 1
yearly_spy = (1 + spy_rets).resample("YE").prod() - 1
yearly = pd.DataFrame({
    "Momentum": yearly_strat.values,
    "SPY": yearly_spy.reindex(yearly_strat.index).values
}, index=yearly_strat.index.year)
if random_results is not None:
    yr_rand = (1 + random_results["rets"]).resample("YE").prod() - 1
    yearly["Aléatoire (médiane)"] = yr_rand.median(axis=1).reindex(
        yearly_strat.index).values

fig_yr = go.Figure()
for c in yearly.columns:
    fig_yr.add_trace(go.Bar(x=yearly.index, y=yearly[c], name=c))
fig_yr.update_layout(title="Rendements annuels", yaxis_tickformat=".0%",
                     barmode="group", height=380)
st.plotly_chart(fig_yr, use_container_width=True)

# ---------------------------------------------------------------
# Ordres à passer
# ---------------------------------------------------------------
st.header("🗂️ Ordres à passer au prochain rebalancement")

dates_sorted = sorted(weights_hist.keys())
if len(dates_sorted) < 2:
    st.info("Pas assez de rebalancements pour comparer.")
else:
    d_new, d_old = dates_sorted[-1], dates_sorted[-2]
    w_new, w_old = weights_hist[d_new], weights_hist[d_old]
    ranks_new = ranks_hist[d_new]["ranks"]
    ranks_old = ranks_hist[d_old]["ranks"]
    signal_new = ranks_hist[d_new]["signal"]

    st.caption(f"Comparaison **{d_old.date()}** → **{d_new.date()}**")

    all_t = sorted(set(w_new.index) | set(w_old.index))
    rows = []
    for t in all_t:
        wn = w_new.get(t, 0.0)
        wo = w_old.get(t, 0.0)
        if wn > 0 and wo == 0:
            action = "🟢 ACHAT"
        elif wn == 0 and wo > 0:
            action = "🔴 VENTE"
        elif wn > wo + 1e-9:
            action = "🔵 RENFORCER"
        elif wn < wo - 1e-9:
            action = "🟠 ALLÉGER"
        else:
            action = "⚪ INCHANGÉ"
        rows.append({
            "Action": action, "Ticker": t,
            "Société": names.get(t, "—"), "Secteur": sectors.get(t, "—"),
            "Poids avant": wo, "Poids après": wn, "Δ Poids": wn - wo,
            "Rang avant": int(ranks_old[t]) if t in ranks_old.index else None,
            "Rang après": int(ranks_new[t]) if t in ranks_new.index else None,
            "Momentum": signal_new.get(t, np.nan),
        })
    df_ord = pd.DataFrame(rows)

    n_buy = (df_ord["Action"] == "🟢 ACHAT").sum()
    n_sell = (df_ord["Action"] == "🔴 VENTE").sum()
    n_keep = len(set(w_new.index) & set(w_old.index))
    turn = (w_new.reindex(all_t, fill_value=0)
            - w_old.reindex(all_t, fill_value=0)).abs().sum() / 2

    o1, o2, o3, o4 = st.columns(4)
    o1.metric("🟢 Entrées", n_buy)
    o2.metric("🔴 Sorties", n_sell)
    o3.metric("⚪ Maintenus", n_keep)
    o4.metric("Turnover", f"{turn:.1%}")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🟢 À acheter")
        buys = df_ord[df_ord["Action"] == "🟢 ACHAT"].sort_values("Rang après")
        st.dataframe(
            buys[["Ticker", "Société", "Poids après", "Rang après", "Momentum"]]
            .style.format({"Poids après": "{:.2%}", "Momentum": "{:.1%}"}),
            use_container_width=True, hide_index=True
        )
    with c2:
        st.subheader("🔴 À vendre")
        sells = df_ord[df_ord["Action"] == "🔴 VENTE"].sort_values("Rang avant")
        st.dataframe(
            sells[["Ticker", "Société", "Poids avant", "Rang avant", "Rang après"]]
            .style.format({"Poids avant": "{:.2%}"}),
            use_container_width=True, hide_index=True
        )

    with st.expander("📋 Détail complet des mouvements"):
        st.dataframe(
            df_ord.sort_values("Action").style.format({
                "Poids avant": "{:.2%}", "Poids après": "{:.2%}",
                "Δ Poids": "{:+.2%}", "Momentum": "{:.1%}",
            }),
            use_container_width=True, hide_index=True
        )

    st.download_button(
        "💾 Télécharger les ordres (CSV)",
        df_ord.to_csv(index=False).encode(),
        file_name=f"ordres_{d_old.date()}_{d_new.date()}.csv",
        mime="text/csv",
    )

st.download_button(
    "💾 Télécharger les rendements quotidiens (CSV)",
    strat_rets.to_csv().encode(),
    file_name="momentum_returns.csv",
    mime="text/csv",
)
