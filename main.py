import requests 
from google import genai
import os 
from dotenv import load_dotenv
import streamlit as st
from agent import BioinfoAgent
load_dotenv()
GOOGLE_API = os.getenv("GEMINI_API_KEY")

# initializing session state variables
if "data" not in st.session_state:
    st.session_state.data = None
if "identifier" not in st.session_state:
    st.session_state.identifier = ""

st.title("Welcome to your Genetic Variant AI Agent!")
st.write("Enter a gene ID or SNP (e.g., BRCA1, rs334)")

identifier = st.text_input("Gene ID or SNP", key="identifier")

if st.button("Summarize"):
    if not st.session_state.identifier:
        st.error("Please enter a gene ID or SNP.")
    else:
        agent = BioinfoAgent()

        with st.spinner("Fetching data..."):
            st.session_state.data = agent.run(
                query=st.session_state.identifier
            )
if st.session_state.data:
    data = st.session_state.data

    # split ai summary into collapsible subsections
    sections = data["ai_summary"].split("##")[1:]

    for sec in sections:
        lines = sec.strip().splitlines()
        header = lines[0].strip()
        content = "\n".join(lines[1:]).strip()
        
        with st.expander(f"{header}", expanded=True):
            st.markdown(f"<h2>{header}</h2>\n\n{content}", unsafe_allow_html=True)

    st.subheader("Sources and Databases")
    st.write(f"{', '.join(data['data_sources_used'])}")

    st.download_button(
        label="Download AI Summary",
        data=data["ai_summary"],
        file_name=f"{identifier}_summary.txt",
        mime="text/plain"
    )

