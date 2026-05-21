import os
import uuid
import yaml
from typing import Optional, List
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process, LLM
from src.mcp_server import geocode_location, get_weather, get_country_data

# =====================================================================
# BLOCK 1: TELEMETRY & MITM PROXY FAIL-SAFES
# =====================================================================
# This block isolates security handshakes and session state.
# We mint a process-level string UUID so all user queries inside the same 
# browser session merge into a single cleanly structured Thread inside LangSmith.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass  # Optional requirement for corporate firewalls running SSL inspections

_SESSION_ID = str(uuid.uuid4())

# Set tracing variables dynamically depending on the upstream env toggle.
if os.environ.get("LANGSMITH_TRACING", "").lower() == "true":
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

# CRITICAL TRACING UPDATE (STEP 1):
# We import tracing_v2_enabled to deeply wrap the execution context,
# allowing LangChain to capture nested LLM and tool calls automatically.
from langchain_core.tracers.context import tracing_v2_enabled
from langsmith import Client

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
def _annotate_run(run_id: str, query: str, briefing: IntelligenceBriefing, run_tree_context):
    """
    Asynchronously patches metadata onto the root LangSmith run.
    Uses runtime introspection to extract telemetry attributes without blocking user flow.
    Evaluates agent efficiency based on tool usage vs required output.
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
            "session_id": _SESSION_ID,
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

        # -------------------------------------------------------------
        # STEP 4: AGENT EFFICIENCY SCORING (NEW)
        # -------------------------------------------------------------
        if run_tree_context and hasattr(run_tree_context, 'child_runs'):
            # Count how many times actual tools were invoked in the trace
            tool_calls = sum(1 for child in run_tree_context.child_runs if child.run_type == "tool")
            
            efficiency_score = 1.0
            efficiency_comment = "Agent routed tools perfectly."
            
            # Logic: If the user didn't ask for weather, but the agent called more than 1 tool
            # (which implies it needlessly called Geocode or Weather), penalize it.
            if not briefing.display_weather and tool_calls > 1:
                efficiency_score = 0.0
                efficiency_comment = f"Inefficient: User didn't request weather, but agent invoked {tool_calls} tools."
            
            # Logic: If the user DID ask for weather, it requires exactly 3 tools 
            # (Country -> Geocode -> Weather). If it used more, it hallucinated a loop.
            elif briefing.display_weather and tool_calls > 3:
                efficiency_score = 0.5
                efficiency_comment = f"Sub-optimal: Agent looped or hallucinated tools ({tool_calls} calls)."
                
            client.create_feedback(
                run_id=run_id,
                key="agent_tool_efficiency",
                score=efficiency_score,
                comment=efficiency_comment
            )
            
    except Exception as e:
        print(f"Telemetry Warning: Failed to ship LangSmith trace update: {e}")

# =====================================================================
# BLOCK 5: MAIN EXECUTION CONTAINER (THE CREW KICKOFF)
# =====================================================================
# Removed the @traceable decorator here. We now handle tracing explicitly 
# inside the function using the LangChain context manager.

def run_research_crew(user_query: str, chat_history: str = "") -> IntelligenceBriefing:
    """
    Accepts user prompts and short-term memory fragments.
    Configures and spawns an instance of the automated multi-tool research task.
    """
    # Locating path routes safely within the project setup directory tree
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_yaml(os.path.join(base_dir, 'config.yaml'))
    prompts = load_yaml(os.path.join(base_dir, 'prompts.yaml'))

    # Construct the foundational LiteLLM routing prefix for Google Gemini
    llm_config = config.get('llm', {})
    model_name = f"{llm_config.get('provider', 'gemini')}/{llm_config.get('model', 'gemini-2.5-flash')}"
    
    # Instantiate the LiteLLM execution class wrapper
    my_llm = LLM(
        model=model_name,
        temperature=llm_config.get('temperature', 0.1),
        max_tokens=llm_config.get('max_tokens', 1024),
        api_key=os.environ.get("GEMINI_API_KEY")
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

    # CRITICAL TRACING UPDATE (STEP 1):
    # We wrap the kickoff execution in the tracing_v2_enabled context.
    # This forces LangChain/CrewAI to capture every nested tool and LLM run 
    # under a single root trace named "Intelligence_Agent_Workflow".
    
    with tracing_v2_enabled(project_name=os.environ.get("LANGCHAIN_PROJECT", "default")) as cb:
        crew_output = crew.kickoff(inputs={
            'user_query': user_query,
            'chat_history': chat_history
        })
        
        # Extract the root run ID from the context callback to annotate it later
        if cb and cb.latest_run:
            root_run_id = cb.latest_run.id
        else:
            root_run_id = None
    
    # Retrieve the structured Pydantic class payload parsed directly by the orchestration architecture
    briefing = crew_output.pydantic
    
    # Perform outcome enrichment logic on the root run we just captured
    if root_run_id:
        # Pass the callback context (cb) so we can inspect the child runs
        _annotate_run(root_run_id, user_query, briefing, cb.latest_run)
        
    return briefing