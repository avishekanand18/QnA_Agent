import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# =====================================================================
# BLOCK 1: ENVIRONMENTAL INGESTION & COLD START CONTROLS
# =====================================================================
# Environment variables must load before importing src.agent to ensure 
# CrewAI and the LangSmith client hooks activate with the correct settings.
load_dotenv()

from src.agent import run_research_crew

# Configure frontend dashboard parameters
st.set_page_config(
    page_title="Global Intelligence Portal",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Global Intelligence & Climate Portal")
st.caption("Enhanced UI Pipeline Featuring Double-Tier TTL Caching & Short-Term Context Memory Routing")

# =====================================================================
# BLOCK 2: APP-LEVEL APPLICATION TTL CACHING CONTAINER
# =====================================================================
# This cache acts as our primary defense mechanism. 
# If a query and its conversation context match an identical request seen 
# within 30 minutes, it skips the LLM and APIs entirely, costing 0 tokens.
@st.cache_data(ttl=1800, show_spinner=False)
def cached_research_crew_execution(query: str, formatted_history: str):
    """
    App-level caching proxy router.
    Locks operations down to exact query and memory argument signatures.
    """
    return run_research_crew(query, formatted_history)

# =====================================================================
# BLOCK 3: MODULAR USER INTERFACE RENDERING ENGINE
# =====================================================================
def render_briefing_dashboard(briefing):
    """
    Accepts an absolute typed Pydantic data contract object.
    Unpacks properties cleanly into functional Streamlit components.
    """
    if not briefing.location_found:
        st.error("The automated network agent was unable to find or resolve this specific query location context.")
        return
        
    st.success("Analysis executed successfully!")
    
    # Always present the direct, specific answer to the user's query
    st.info(briefing.response_summary)
    
    # Render Demographic Metrics only if the agent found them relevant and populated them
    if briefing.demographic_stats and (briefing.demographic_stats.capital or briefing.demographic_stats.population or briefing.demographic_stats.currencies):
        st.write("### 📊 Country Demographic Profiles")
        col1, col2, col3 = st.columns(3)
        stats = briefing.demographic_stats
        
        with col1:
            if stats.capital:
                st.metric("Identified Capital", stats.capital)
        with col2:
            if stats.population:
                st.metric("Total Population", f"{stats.population:,}")
        with col3:
            if stats.currencies:
                st.metric("Local Currencies", ", ".join(stats.currencies))
    
    # Render weather data and chart ONLY if the user explicitly requested weather details
    if briefing.display_weather:
        st.write("### 🌤️ Weather Metrics")
        if briefing.weather_summary:
            st.warning(briefing.weather_summary)
            
        if briefing.raw_forecast:
            st.subheader("🗓️ Real-Time 7-Day Temperature Variance Map")
            
            # Extract Pydantic objects into a list of raw dictionaries for Pandas
            forecast_data = [day.model_dump() for day in briefing.raw_forecast]
            
            # Ingest array items smoothly into a processing Pandas frame
            df = pd.DataFrame(forecast_data)
            df.rename(columns={"d": "Timeline Date", "hi": "Max Temp (°C)", "lo": "Min Temp (°C)"}, inplace=True)
            df.set_index("Timeline Date", inplace=True)
            
            # Push interactive vector graph directly onto user's web client view
            st.line_chart(df)

# =====================================================================
# BLOCK 4: CHAT SESSION MEMORY STATE INITIALIZATION
# =====================================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

# Continuously loop and draw message components if entries persist inside state history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        else:
            # Re-render the complete structured analytical layout for older items
            render_briefing_dashboard(message["content"])

# =====================================================================
# BLOCK 5: CONVERSATION CONTROL LOOP & LIVE EXECUTION TRACK
# =====================================================================
if user_input := st.chat_input("Query country records or climate profiles (e.g., 'What is the weather there?')"):
    
    # Immediately render user prompt onto frontend screen
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant"):
        with st.spinner("Executing agentic tools via tracking pipelines..."):
            try:
                # -----------------------------------------------------
                # SUB-SECTOR: SHORT-TERM CONTEXT CONVERSATION FORMATTER
                # -----------------------------------------------------
                # Introspect historical list structures to build a sliding context frame.
                # Captures the last user input and assistant response, compressing context weight.
                memory_string = ""
                if len(st.session_state.messages) > 2:
                    # Snip the previous question and answer exchange loop
                    past_exchange = st.session_state.messages[-3:-1]
                    
                    # Unpack the human-typed prompt text
                    prev_user = past_exchange[0]["content"]
                    # Unpack weather text summary from assistant object
                    prev_assistant = past_exchange[1]["content"].response_summary if hasattr(past_exchange[1]["content"], 'response_summary') else "Resolved"
                    
                    memory_string = f"Prior User Inquiry: '{prev_user}' -> Prior Assistant Discovery: '{prev_assistant}'"
                
                # Run the query through our caching proxy layer
                briefing_payload = cached_research_crew_execution(user_input, memory_string)
                
                # Push structural components straight onto user interface dashboard layout
                render_briefing_dashboard(briefing_payload)
                
                # Retain the raw Pydantic response object inside our session history trace
                st.session_state.messages.append({"role": "assistant", "content": briefing_payload})
                
            except Exception as e:
                st.error(f"A runtime pipeline execution interruption fault triggered: {str(e)}")