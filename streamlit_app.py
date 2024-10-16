import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt


st.title("🎈 My new app")
st.write(
    "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
)
ticker = 'SP5.PA'  # Code pour Amundi SP5 sur Yahoo Finance
etf_data = yf.download(ticker, period="1y")
