import requests
import json
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

# CRITICAL TRACING UPDATE (STEP 2): 
# Import the traceable decorator to explicitly tag internal tool executions
from langsmith import traceable

# =====================================================================
# BLOCK 1: PYDANTIC SCHEMA DEFINITIONS FOR ACCURATE LLM INPUT ROUTING
# =====================================================================
# These schemas tell the LLM exactly what arguments are expected.
# Comprehensive descriptions prevent the agent from accidentally pushing 
# string parameters into numeric floats.

class GeocodeInput(BaseModel):
    query: str = Field(..., description="String query location to resolve (e.g. 'Rome, Italy').")

class WeatherInput(BaseModel):
    latitude: float = Field(..., description="Numerical floating latitude point data.")
    longitude: float = Field(..., description="Numerical floating longitude point data.")

class CountryInput(BaseModel):
    country_name: str = Field(..., description="Full clean spelling indicator of country entity name.")

# =====================================================================
# BLOCK 2: GEOCODING LOCATION UTILITY (TOOL-CACHED ON)
# =====================================================================
class GeocodeLocationTool(BaseTool):
    name: str = "geocode_location"
    description: str = "Converts physical addresses or landmarks into precise lat/lon points. Execute first for weather requests."
    args_schema: type[BaseModel] = GeocodeInput
    cache: bool = True  # Turning on Tool Caching avoids slamming public API limits
    
    # TRACING UPDATE: explicitly tag this tool in the trace tree
    @traceable(run_type="tool", name="Geocode_Nominatim_API", tags=["nominatim", "geocoding"])
    def _run(self, query: str) -> str:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "limit": 1}
        headers = {"User-Agent": "CrewAIAgent_TestingApp/1.0"}
        
        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if data:
                result = data[0]
                # Keep return keys minimal to lower input context token weight
                return json.dumps({
                    "lat": float(result.get('lat')),
                    "lon": float(result.get('lon')),
                    "name": result.get('display_name')
                })
            return json.dumps({"err": "Location context not found."})
                
        except requests.exceptions.RequestException as e:
            return json.dumps({"err": f"Network exception: {str(e)}"})

# =====================================================================
# BLOCK 3: 7-DAY DAILY WEATHER UTILITY (TOOL-CACHED OFF)
# =====================================================================
class GetWeatherTool(BaseTool):
    name: str = "get_weather"
    description: str = "Pulls the full 7-day high/low temperature metrics map. Requires exact numerical floats."
    args_schema: type[BaseModel] = WeatherInput
    cache: bool = False  # Left off so weather returns are always real-time if a call reaches this layer
    
    # TRACING UPDATE: explicitly tag this tool in the trace tree
    @traceable(run_type="tool", name="Weather_OpenMeteo_API", tags=["open-meteo", "climate"])
    def _run(self, latitude: float, longitude: float) -> str:
        url = "https://api.open-meteo.com/v1/forecast"
        # Requesting daily aggregated intervals instead of raw 168-hour slots dramatically minimizes token usage
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": 7
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            daily = data.get("daily", {})
            forecast_array = []
            
            # Zip multiple data lists down into a tightly packed sequence map
            if daily and "time" in daily:
                for i in range(len(daily["time"])):
                    forecast_array.append({
                        "d": daily["time"][i],               # Date 
                        "hi": daily["temperature_2m_max"][i], # High Temp
                        "lo": daily["temperature_2m_min"][i]  # Low Temp
                    })
                    
            return json.dumps({
                "tz": data.get("timezone"),
                "f": forecast_array 
            })
                
        except requests.exceptions.RequestException as e:
            return json.dumps({"err": f"Climate backend unreachable: {str(e)}"})

# =====================================================================
# BLOCK 4: DEMOGRAPHIC ENGINE (TOOL-CACHED ON)
# =====================================================================
class GetCountryDataTool(BaseTool):
    name: str = "get_country_data"
    description: str = "Queries geographic demographic records including capitals, population, and currencies."
    args_schema: type[BaseModel] = CountryInput
    cache: bool = True  # Retaining demographic values locally stops duplicated API queries
    
    # TRACING UPDATE: explicitly tag this tool in the trace tree
    @traceable(run_type="tool", name="Demographics_RESTCountries_API", tags=["rest-countries", "demographics"])
    def _run(self, country_name: str) -> str:
        url = f"https://restcountries.com/v3.1/name/{country_name}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list):
                country = data[0]
                currency_identities = [info.get("name") for info in country.get("currencies", {}).values()]
                
                # Compress return parameters to keep the context payload clean
                return json.dumps({
                    "nm": country.get("name", {}).get("official", "N/A"),
                    "cap": country.get("capital", ["N/A"])[0],
                    "reg": country.get("region", "N/A"),
                    "pop": country.get("population", 0),
                    "cur": currency_identities
                })
            return json.dumps({"err": "Payload data format anomaly resolved."})
                
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                return json.dumps({"err": "Target country profile missing."})
            return json.dumps({"err": f"HTTP Fault: {str(e)}"})
        except requests.exceptions.RequestException as e:
            return json.dumps({"err": f"Network transmission error: {str(e)}"})

# =====================================================================
# BLOCK 5: INITIALIZE & INSTANTIATE UTILITY OBJECTS FOR MODULE IMPORTS
# =====================================================================
geocode_location = GeocodeLocationTool()
get_weather = GetWeatherTool()
get_country_data = GetCountryDataTool()