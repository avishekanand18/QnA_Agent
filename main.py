# main.py
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
from src.agent import run_research_crew

st.set_page_config(page_title="Global Intelligence Portal", page_icon="🌍", layout="wide")
st.title("🌍 Global Intelligence & Climate Portal")
st.caption("Driven by CrewAI, Gemini 2.5 Flash, and Strict Pydantic Data Contracts")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Helper function to prevent repeating UI code across history and live view
def render_briefing_ui(briefing):
    if not briefing.location_found:
        st.error("The requested location or intelligence context could not be resolved.")
        return
        
    st.success("Data synthesized successfully!")
    st.info(briefing.weather_summary)
    
    # Render Metrics using the clean Pydantic dot notation
    col1, col2, col3 = st.columns(3)
    stats = briefing.demographic_stats
    
    with col1:
        st.metric("Capital City", stats.capital)
    with col2:
        st.metric("Population", f"{stats.population:,}")
    with col3:
        st.metric("Currencies", ", ".join(stats.currencies))
    
    # Render Forecast Chart
    if briefing.raw_forecast:
        st.subheader("🗓️ 7-Day Temperature Trend")
        df = pd.DataFrame(briefing.raw_forecast)
        df.rename(columns={"d": "Date", "hi": "Max Temp (°C)", "lo": "Min Temp (°C)"}, inplace=True)
        df.set_index("Date", inplace=True)
        st.line_chart(df)

# 1. Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        else:
            render_briefing_ui(message["content"])

# 2. Handle New User Input
if user_input := st.chat_input("Ask a question..."):
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing query and chaining APIs..."):
            try:
                briefing = run_research_crew(user_input)
                render_briefing_ui(briefing)
                st.session_state.messages.append({"role": "assistant", "content": briefing})
            except Exception as e:
                st.error(f"An execution error occurred: {str(e)}")