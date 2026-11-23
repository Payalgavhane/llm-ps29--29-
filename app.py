"""Streamlit front end for the Language Grammar Tutor.  Run: streamlit run app.py"""
import json
import os
from collections import Counter

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from grammar_tutor import (PROVIDERS, GrammarTutorError, correct_paragraph,
                           highlight, tally_categories)

load_dotenv()
st.set_page_config(page_title="Language Grammar Tutor", page_icon="📝", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = Counter()   # mistakes tallied across the session
if "text" not in st.session_state:
    st.session_state.text = ""

SAMPLES = {
    "Sample 1 - tenses & articles": "Yesterday I go to the market and buy a apple. She don't like it because it were too sour.",
    "Sample 2 - prepositions": "I am agree with you. We discussed about the project in the morning and arrived to the office at 9.",
    "Sample 3 - plurals & agreement": "My friends is coming to my house. They brings many gift and we eats together.",
    "Sample 4 - spelling & punctuation": "Its a beatiful day, but i dont have enough time to go outside becuase i must finish my homwork",
    "Sample 5 - word order": "Never I have seen such a big city. Where you are going tomorow? He asked me what was my name.",
}

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("⚙️ Settings")
    provider = st.selectbox("LLM provider", list(PROVIDERS))
    model = st.text_input("Model", PROVIDERS[provider]["model"])
    api_key = st.text_input(f"{provider} API key", type="password",
                            value=os.getenv(PROVIDERS[provider]["env"], ""),
                            help="Or put it in a .env file. Never commit it.")
    level = st.select_slider("Learner level", ["Beginner", "Intermediate", "Advanced"],
                             value="Intermediate")
    native = st.text_input("Native language (optional)", placeholder="e.g. Marathi, Hindi")
    st.divider()
    st.subheader("Try a sample")
    choice = st.selectbox("Sample inputs", ["-"] + list(SAMPLES))
    if st.button("Load sample") and choice != "-":
        st.session_state.text = SAMPLES[choice]
        st.rerun()
    if st.button("Reset mistake tracker"):
        st.session_state.history = Counter()

# ---------------- Main ----------------
st.title("📝 Language Grammar Tutor")
st.caption("Paste a paragraph. Get the corrected text, highlighted mistakes, and the "
           "grammar rule behind each one.")

paragraph = st.text_area("Your paragraph", key="text", height=170,
                         placeholder="Type or paste your English paragraph here...")

if st.button("✅ Check my grammar", type="primary"):
    try:
        with st.spinner("Checking..."):
            result = correct_paragraph(paragraph, provider, api_key, level, native, model or None)
        st.session_state.result = result
        st.session_state.original = paragraph
        st.session_state.history.update(tally_categories(result["errors"]))
    except GrammarTutorError as e:
        st.error(str(e))

result = st.session_state.get("result")
if result:
    original = st.session_state.original
    errors = result["errors"]

    if not errors:
        st.success("🎉 No mistakes found. Great job!")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Your text (mistakes in red)")
        st.markdown(highlight(original, [e["error"] for e in errors], "#fde2e2", "#9b1c1c"),
                    unsafe_allow_html=True)
    with c2:
        st.subheader("Corrected text (fixes in green)")
        st.markdown(highlight(result["corrected_text"], [e["correction"] for e in errors],
                              "#dcfce7", "#14532d"), unsafe_allow_html=True)

    if errors:
        st.subheader(f"Mistakes found: {len(errors)}")
        st.dataframe(pd.DataFrame(errors).rename(columns={
            "error": "Error", "correction": "Correction", "rule": "Rule", "category": "Category"}),
            width="stretch", hide_index=True)
    if result["tip"]:
        st.info(f"💡 Tip: {result['tip']}")

    with st.expander("Raw JSON output"):
        st.json(result)
    st.download_button("⬇️ Download JSON", json.dumps(result, indent=2, ensure_ascii=False),
                       "grammar_report.json", "application/json")

if st.session_state.history:
    st.divider()
    st.subheader("📊 Your repeated mistakes (this session)")
    st.bar_chart(pd.Series(st.session_state.history).sort_values(ascending=False))
