# QA Agent: Multi-API Agentic App with CrewAI

## Overview
This project is an agentic application built using the CrewAI framework and Google Gemini 2.5 Flash model. The agent leverages three public APIs as tools:
- **Open-Meteo** (Weather Forecast)
- **Nominatim** (OpenStreetMap Geocoding)
- **REST Countries** (Country Demographics)

The agent can answer complex, multi-step questions by combining data from these APIs, providing users with intelligence briefings on demographic, geographic, and meteorological data.

---

## Features
- **Agentic Reasoning:** Uses CrewAI to chain API calls and synthesize answers.
- **Flexible Question Handling:** Supports a wide range of user queries, including those requiring data from multiple APIs.
- **Modular Design:** Each API is implemented as a tool, making it easy to extend or modify.
- **Prompt Engineering:** Custom prompts and system instructions for optimal agent behavior.

---

## Project Structure
```
qa_agent/
├── agent.py         # Agent logic and implementation
├── config.yaml      # Configuration (API endpoints, keys, etc.)
├── mcp_server.py    # Tool definitions for the 3 APIs
├── prompts.py       # Prompts, system instructions, etc.
├── main.py          # Entrypoint for running the app
└── test_api/
    ├── nominatium.py
    ├── open_meteo.py
    └── rest_countries.py
```

---

## Setup Instructions
1. **Clone the Repository**
   ```sh
   git clone <repo-url>
   cd qa_agent
   ```
2. **Create a Virtual Environment**
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install Dependencies**
   ```sh
   pip install -r requirements.txt
   ```
   (Make sure to include CrewAI, requests, and any other dependencies in `requirements.txt`)

4. **Configure the App**
   - Edit `config.yaml` to set any required parameters (API endpoints, keys, etc.).

5. **Run the Application**
   ```sh
   python main.py
   ```

---

## Example Questions
Here are some example queries the agent can handle:
- "What is the weather in the capital of France?"
- "Which country is the Colosseum in, and what is its population?"
- "Compare the weather in the capitals of Canada and Australia."
- "What currency is used in Brazil, and what is the current weather in its capital?"

See the `conversation_context.txt` for more sample questions.

---

## API Tools
- **Open-Meteo:** Provides weather forecasts and current conditions for any location.
- **Nominatim:** Geocodes place names and landmarks to coordinates, and vice versa.
- **REST Countries:** Supplies country-level demographic and geographic data.

---

## Customization
- Add new tools by extending `mcp_server.py`.
- Modify agent behavior and prompts in `agent.py` and `prompts.py`.
- Update configuration in `config.yaml`.

---

## Troubleshooting
- **SSL Errors:** If you encounter SSL certificate errors, update your CA certificates or use `pip install certifi`.
- **CrewAI Telemetry:** Telemetry can be disabled in your code or via environment variables if you encounter related errors.
- **API Changes:** If an API changes its response format, update the corresponding tool implementation.

---

## License
MIT License (or specify your license here)

---

## Credits
- [Open-Meteo](https://open-meteo.com/)
- [Nominatim](https://nominatim.org/)
- [REST Countries](https://restcountries.com/)
- [CrewAI](https://crewai.com/)
- [Google Gemini](https://ai.google/discover/gemini/)
