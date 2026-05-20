import os
import yaml
from crewai import Agent, Task, Crew, Process, LLM
from src.mcp_server import geocode_location, get_weather, get_country_data

def load_yaml(filepath: str) -> dict:
    """Helper function to load YAML configuration files."""
    with open(filepath, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def run_research_crew(user_query: str):
    """
    Initializes and executes the CrewAI orchestration for a given user query.
    """
    # 1. Load Configurations
    config = load_yaml('src/config.yaml')
    prompts = load_yaml('src/prompts.yaml')

    # 2. Configure the Gemini LLM
    llm_config = config.get('llm', {})
    # CrewAI uses litellm under the hood; the standard prefix for Gemini is 'gemini/'
    model_name = f"{llm_config.get('provider', 'gemini')}/{llm_config.get('model', 'gemini-2.5-flash')}"
    
    my_llm = LLM(
        model=model_name,
        temperature=llm_config.get('temperature', 0.1),
        api_key=os.environ.get("GEMINI_API_KEY")
    )

    # 3. Instantiate the Agent
    agent_config = prompts['agents']['global_intelligence_analyst']
    analyst_agent = Agent(
        role=agent_config['role'],
        goal=agent_config['goal'],
        backstory=agent_config['backstory'],
        verbose=True,  # Enables detailed logging of tool calls and thoughts in the console
        allow_delegation=False,
        tools=[geocode_location, get_weather, get_country_data],
        llm=my_llm
    )

    # 4. Instantiate the Task
    task_config = prompts['tasks']['research_query_task']
    research_task = Task(
        description=task_config['description'],
        expected_output=task_config['expected_output'],
        agent=analyst_agent
        # CrewAI automatically injects the inputs mapping into the {user_query} placeholder
    )

    # 5. Assemble and Kickoff the Crew
    crew = Crew(
        agents=[analyst_agent],
        tasks=[research_task],
        process=Process.sequential,
        verbose=True
    )

    # The inputs dictionary maps directly to the {user_query} variable in prompts.yaml
    result = crew.kickoff(inputs={'user_query': user_query})
    
    return result