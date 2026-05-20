import requests
import json
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

# ---------------------------------------------------------
# Pydantic Input Schemas
# ---------------------------------------------------------
class GeocodeInput(BaseModel):
    query: str = Field(
        ..., 
        description="Name of the location to search (e.g., 'Tokyo, Japan'). Append country name for accuracy."
    )

class WeatherInput(BaseModel):
    latitude: float = Field(..., description="Numerical latitude of the location.")
    longitude: float = Field(..., description="Numerical longitude of the location.")

class CountryInput(BaseModel):
    country_name: str = Field(..., description="Common or official name of the country.")

# ---------------------------------------------------------
# Subclassed Strict Tools
# ---------------------------------------------------------
class GeocodeLocationTool(BaseTool):
    name: str = "geocode_location"
    description: str = "Finds latitude and longitude for a location name. Use this FIRST before checking weather."
    args_schema: type[BaseModel] = GeocodeInput
    
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
                return json.dumps({
                    "lat": float(result.get('lat')),
                    "lon": float(result.get('lon')),
                    "name": result.get('display_name')
                })
            return json.dumps({"err": "Not found"})
                
        except requests.exceptions.RequestException as e:
            return json.dumps({"err": str(e)})


class GetWeatherTool(BaseTool):
    name: str = "get_weather"
    description: str = "Fetches a 7-day weather forecast (min/max temperatures). MUST use numerical coordinates."
    args_schema: type[BaseModel] = WeatherInput
    
    def _run(self, latitude: float, longitude: float) -> str:
        url = "https://api.open-meteo.com/v1/forecast"
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
            forecast = []
            
            if daily and "time" in daily:
                for i in range(len(daily["time"])):
                    forecast.append({
                        "d": daily["time"][i],               
                        "hi": daily["temperature_2m_max"][i], 
                        "lo": daily["temperature_2m_min"][i]  
                    })
                    
            return json.dumps({
                "tz": data.get("timezone"),
                "f": forecast 
            })
                
        except requests.exceptions.RequestException as e:
            return json.dumps({"err": str(e)})


class GetCountryDataTool(BaseTool):
    name: str = "get_country_data"
    description: str = "Retrieves country demographics (capital, population, region, currencies)."
    args_schema: type[BaseModel] = CountryInput
    
    def _run(self, country_name: str) -> str:
        url = f"https://restcountries.com/v3.1/name/{country_name}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list):
                country = data[0]
                curr_names = [info.get("name") for info in country.get("currencies", {}).values()]
                
                return json.dumps({
                    "nm": country.get("name", {}).get("official", "N/A"),
                    "cap": country.get("capital", ["N/A"])[0],
                    "reg": country.get("region", "N/A"),
                    "pop": country.get("population", 0),
                    "cur": curr_names
                })
            return json.dumps({"err": "Bad format"})
                
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                return json.dumps({"err": "Not found"})
            return json.dumps({"err": str(e)})
        except requests.exceptions.RequestException as e:
            return json.dumps({"err": str(e)})

# Expose instances of the tools to be imported in agent.py
geocode_location = GeocodeLocationTool()
get_weather = GetWeatherTool()
get_country_data = GetCountryDataTool()