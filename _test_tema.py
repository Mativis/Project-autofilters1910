import json

import streamlit as st

st.set_page_config(page_title="debug tema", layout="wide")

st.write("### Diagnóstico de tema")
st.json(
    {
        "context.theme.type": str(st.context.theme.type),
        "option theme.base": st.get_option("theme.base"),
        "option theme.backgroundColor": st.get_option("theme.backgroundColor"),
        "option theme.textColor": st.get_option("theme.textColor"),
        "option theme.secondaryBackgroundColor": st.get_option("theme.secondaryBackgroundColor"),
        "option theme.primaryColor": st.get_option("theme.primaryColor"),
    }
)
