import os
import uuid
import yaml
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process, LLM
from src.mcp_server import geocode_location, get_weather, get_country_data

# ---------------------------------------------------------
# 1. Corporate TLS / Fail-safe imports
# ---------------------------------------------------------
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass  # Optional: only needed if behind corporate MITM proxies

# ---------------------------------------------------------
# 2. Thread Grouping & Tracing Setup
# ---------------------------------------------------------
# Mint one UUID per process so all queries in one REPL/Streamlit session
# collapse into the same trace thread in the LangSmith UI.
_SESSION_ID = str(uuid.uuid4())

# Set tracing dynamically based on the custom env variable
if os.environ.get("LANGSMITH_TRACING", "").lower() == "true":
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

from langsmith import traceable, Client
from langsmith.run_helpers import get_current_run_tree

# ---------------------------------------------------------
# Pydantic Structured Output Model
# ---------------------------------------------------------
# Create a explicit sub-model for demographics to enforce exact keys
class CountryDemographics(BaseModel):
    capital: str = Field(description="The capital city of the country.")
    population: int = Field(description="The total population of the country as an integer.")
    currencies: list[str] = Field(description="List of currency names used in the country.")

class IntelligenceBriefing(BaseModel):
    """Strict JSON schema for the final LLM output to eliminate token waste."""
    location_found: bool = Field(description="True if the location and country were successfully identified.")
    weather_summary: str = Field(description="A highly concise summary of the 7-day weather trend (max 2 sentences).")
    demographic_stats: CountryDemographics = Field(description="Strictly typed demographic statistics of the country.")
    raw_forecast: list = Field(description="The exact 7-day min/max forecast array returned by the weather tool.")

def load_yaml(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

# ---------------------------------------------------------
# Outcome Enrichment & Feedback Hook
# ---------------------------------------------------------
def _annotate_run(run_id: str, query: str, briefing: IntelligenceBriefing):
    """
    Pushes outcome metadata, custom tags, and feedback scores onto the root run.
    Wrapped in a try/except to act as a fail-safe.
    """
    if os.environ.get("LANGSMITH_TRACING", "").lower() != "true":
        return
        
    try:
        client = Client()
        
        # 1. Dynamic Tags based on the data retrieved
        new_tags = ["crewai_workflow"]
        if briefing.location_found:
            new_tags.append(f"region:{briefing.demographic_stats.get('reg', 'Unknown')}")
            new_tags.append("status:success")
        else:
            new_tags.append("status:not_found")
            
        # 2. Add Run Metadata (Diffable across models)
        extra_metadata = {
            "session_id": _SESSION_ID,
            "location_input": query,
            "briefing_outcome_stats": briefing.demographic_stats
        }

        # 3. Update the Root Run in LangSmith
        client.update_run(
            run_id=run_id,
            tags=new_tags,
            extra={"metadata": extra_metadata}
        )
        
        # 4. Feedback Score (Chartable in LangSmith UI)
        # Score 1 if the agent successfully utilized tools to resolve the query.
        score = 1 if briefing.location_found else 0
        client.create_feedback(
            run_id=run_id,
            key="location_resolved",
            score=score,
            comment="Data retrieved successfully" if score == 1 else "Failed to resolve location context"
        )
        
    except Exception as e:
        print(f"Warning: Failed to annotate LangSmith trace: {e}")


# ---------------------------------------------------------
# CrewAI Orchestration
# ---------------------------------------------------------
@traceable(run_type="chain", name="Intelligence_Agent_Workflow")
def run_research_crew(user_query: str) -> IntelligenceBriefing:
    """Executes the CrewAI workflow and handles telemetry."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_yaml(os.path.join(base_dir, 'config.yaml'))
    prompts = load_yaml(os.path.join(base_dir, 'prompts.yaml'))

    llm_config = config.get('llm', {})
    model_name = f"{llm_config.get('provider', 'gemini')}/{llm_config.get('model', 'gemini-2.5-flash')}"
    
    # 1. Base Metadata Injection for this Trace
    # This attaches the environment context immediately to the trace before LLMs run.
    run_tree = get_current_run_tree()
    if run_tree:
        if "metadata" not in run_tree.extra:
            run_tree.extra["metadata"] = {}
        run_tree.extra["metadata"].update({
            "framework": "crewai",
            "model_name": model_name,
            "temperature": llm_config.get('temperature', 0.1)
        })

    # 2. Configure Model
    my_llm = LLM(
        model=model_name,
        temperature=llm_config.get('temperature', 0.1),
        max_tokens=llm_config.get('max_tokens', 1024),
        api_key=os.environ.get("GEMINI_API_KEY")
    )

    # 3. Assemble Crew
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

    task_config = prompts['tasks']['research_query_task']
    research_task = Task(
        description=task_config['description'],
        expected_output=task_config['expected_output'],
        agent=analyst_agent,
        output_pydantic=IntelligenceBriefing 
    )

    crew = Crew(
        agents=[analyst_agent],
        tasks=[research_task],
        process=Process.sequential,
        verbose=True
    )

    # 4. Kickoff Workflow
    crew_output = crew.kickoff(inputs={'user_query': user_query})
    briefing = crew_output.pydantic
    
    # 5. Outcome Enrichment
    # Once the run completes, we update the trace with the final result data
    if run_tree:
        _annotate_run(run_tree.id, user_query, briefing)
        
    return briefing