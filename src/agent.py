import os
import yaml
import litellm  # TRACING UPDATE: Importing litellm directly to inject callbacks
from typing import Optional, List
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process, LLM
from src.mcp_server import geocode_location, get_weather, get_country_data

# TRACING UPDATE: We import native tracing components to manage the run tree
from langsmith import Client, traceable
from langsmith.run_helpers import get_current_run_tree

# =====================================================================
# BLOCK 1: TELEMETRY FAIL-SAFES & LITELLM HOOKS
# =====================================================================
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass  # Optional requirement for corporate firewalls running SSL inspections

# Set tracing variables dynamically depending on the upstream env toggle.
if os.environ.get("LANGSMITH_TRACING", "").lower() == "true":
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

# TRACING UPDATE: Force CrewAI's underlying LiteLLM engine to blast LLM Input/Output
# directly to LangSmith. Because the @traceable context manager is active below,
# LangSmith will catch these and nest them into the "Single Unit" tree automatically.
litellm.success_callback = ["langsmith"]
litellm.failure_callback = ["langsmith"]

# =====================================================================
# BLOCK 2: NESTED PYDANTIC OUTPUT DATA SCHEMAS
# =====================================================================
# To prevent Gemini 2.5 Flash from hallucinating json object keys, we enforce 
# a deep, nested, strictly validated blueprint. 
# This shifts formatting computations away from the LLM directly to Streamlit.

class DailyForecast(BaseModel):
    """Strictly typed daily climate metrics to prevent key hallucination by the LLM."""
    d: str = Field(description="The date string.")
    hi: float = Field(description="The highest daily temperature.")
    lo: float = Field(description="The lowest daily temperature.")

class CountryDemographics(BaseModel):
    """Enforces static structured data formats for demographic payloads."""
    capital: Optional[str] = Field(default=None, description="The capital city of the targeted country.")
    population: Optional[int] = Field(default=None, description="Total population count rendered as a raw integer.")
    currencies: Optional[List[str]] = Field(default=None, description="Array list containing string indicators of legal currencies.")

class IntelligenceBriefing(BaseModel):
    """The master shape of the final agent object returned to the application."""
    location_found: bool = Field(description="Flag setting if the location context resolved cleanly.")
    response_summary: str = Field(description="The direct, natural language answer to the user's exact question (e.g., 'Japan uses the currency Yen').")
    display_weather: bool = Field(description="Set to True ONLY if the user explicitly requested weather, temperatures, forecasts, or climate details.")
    weather_summary: Optional[str] = Field(default=None, description="A highly concise summary of the 7 day climate movement if requested, otherwise None.")
    demographic_stats: Optional[CountryDemographics] = Field(default=None, description="Nested schema housing strictly-typed statistics if relevant, otherwise None.")
    raw_forecast: Optional[List[DailyForecast]] = Field(default=None, description="The strict array containing daily climate entries if requested, otherwise None.")

# =====================================================================
# BLOCK 3: CONFIGURATION FILE INGESTION UTILITY
# =====================================================================
def load_yaml(filepath: str) -> dict:
    """Safely loads file payloads into native Python dictionaries."""
    with open(filepath, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

# =====================================================================
# BLOCK 4: OUTCOME ENRICHMENT & LANGSMITH HOOK
# =====================================================================
def _annotate_run(run_id: str, query: str, briefing: IntelligenceBriefing, session_id: str):
    """
    Asynchronously patches metadata onto the root LangSmith run.
    Uses runtime introspection to extract telemetry attributes without blocking user flow.
    """
    if os.environ.get("LANGSMITH_TRACING", "").lower() != "true":
        return
        
    try:
        client = Client()
        
        # 1. Build tags programmatically
        runtime_tags = ["crewai_workflow"]
        if briefing.location_found:
            runtime_tags.append("status:success")
        else:
            runtime_tags.append("status:not_found")
            
        # 2. Structure metadata
        extra_metadata = {
            "session_id": session_id,
            "location_input": query,
            "display_weather_triggered": briefing.display_weather
        }

        # Issue network trace update
        client.update_run(
            run_id=run_id,
            tags=runtime_tags,
            extra={"metadata": extra_metadata}
        )
        
        # 3. Log General Resolution Score
        resolution_score = 1.0 if briefing.location_found else 0.0
        client.create_feedback(
            run_id=run_id,
            key="location_resolved",
            score=resolution_score,
            comment="Agent successfully resolved the query." if resolution_score == 1.0 else "Agent failed to resolve context."
        )
            
    except Exception as e:
        print(f"Telemetry Warning: Failed to ship LangSmith trace update: {e}")

# =====================================================================
# BLOCK 5: MAIN EXECUTION CONTAINER (THE CREW KICKOFF)
# =====================================================================
# TRACING UPDATE: We wrap the entire execution in @traceable. 
# This automatically creates a 'Single Unit' trace named "UI_Interaction_Flow"
# Every LLM node, agent step, and tool call will nest perfectly underneath this unit.
@traceable(name="UI_Interaction_Flow", run_type="chain")
def run_research_crew(user_query: str, chat_history: str = "", model_choice: str = "gemini", session_id: str = "default_session") -> IntelligenceBriefing:
    """
    Accepts user prompts, short-term memory fragments, and the requested model routing.
    Configures and spawns an instance of the automated multi-tool research task.
    """
    # Grab the active LangSmith Run Tree created by the @traceable decorator
    run_tree = get_current_run_tree()
    
    # Push the persistent session ID directly into the tree metadata.
    # This is the secret mechanism that populates the "Threads" tab in LangSmith.
    if run_tree:
        run_tree.add_metadata({"session_id": session_id})

    # Locating path routes safely within the project setup directory tree
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_yaml(os.path.join(base_dir, 'config.yaml'))
    prompts = load_yaml(os.path.join(base_dir, 'prompts.yaml'))

    llm_config = config.get('llm', {})
    
    # TRACING UPDATE: We reverted back to CrewAI's native `LLM` to satisfy Pydantic
    # strict validation. LiteLLM will handle the LangSmith traces behind the scenes.
    if model_choice.lower() == "groq":
        model_name = "groq/llama3-8b-8192" 
        active_api_key = os.environ.get("GROQ_API_KEY")
    else:
        model_name = f"{llm_config.get('provider', 'gemini')}/{llm_config.get('model', 'gemini-2.5-flash')}"
        active_api_key = os.environ.get("GEMINI_API_KEY")

    # Instantiate the native CrewAI execution class wrapper 
    my_llm = LLM(
        model=model_name,
        temperature=llm_config.get('temperature', 0.1),
        max_tokens=llm_config.get('max_tokens', 1024),
        api_key=active_api_key
    )

    # Initialize the core CrewAI intelligence agent entity
    agent_config = prompts['agents']['global_intelligence_analyst']
    analyst_agent = Agent(
        role=agent_config['role'],
        goal=agent_config['goal'],
        backstory=agent_config['backstory'],
        verbose=True, 
        allow_delegation=False,
        tools=[geocode_location, get_weather, get_country_data],
        llm=my_llm
    )

    # Instantiate the processing assignment task, locking output to the Pydantic structural blueprint
    task_config = prompts['tasks']['research_query_task']
    research_task = Task(
        description=task_config['description'],
        expected_output=task_config['expected_output'],
        agent=analyst_agent,
        output_pydantic=IntelligenceBriefing 
    )

    # Marshal runtime instances into a standard sequential execution thread
    crew = Crew(
        agents=[analyst_agent],
        tasks=[research_task],
        process=Process.sequential,
        verbose=True
    )

    # Kickoff the agent workflow natively. It will automatically attach to the active Run Tree.
    crew_output = crew.kickoff(inputs={
        'user_query': user_query,
        'chat_history': chat_history
    })
        
    # Retrieve the structured Pydantic class payload parsed directly by the orchestration architecture
    briefing = crew_output.pydantic
    
    # Perform outcome enrichment logic on the root run we just captured
    if run_tree:
        _annotate_run(str(run_tree.id), user_query, briefing, session_id)
        
    return briefing