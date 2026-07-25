import pandas as pd
import streamlit as st

st.set_page_config(page_title="PIF Prévis", page_icon="🛫", layout="centered", initial_sidebar_state="auto")


st.title('🛫 PIF Prévis') 
st.divider()

with st.sidebar.expander("Version"):
    st.sidebar.info("")
    



hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
