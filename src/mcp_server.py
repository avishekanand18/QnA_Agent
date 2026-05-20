import requests
import json
from crewai.tools import tool

@tool
def geocode_location(query: str) -> str:
    """
    Geocodes a text query (like a city, landmark, or address) into latitude and longitude coordinates.
    
    Use this tool FIRST when you need to find the weather for a specific location but only have its name.
    
    Args:
        query (str): The name of the location to search for (e.g., "Eiffel Tower", "Tokyo, Japan").
        
    Returns:
        str: A JSON string containing the location's display name, latitude (lat), and longitude (lon).
             If the location is not found, it returns a JSON string with an error message.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }
    headers = {
        # Nominatim requires a distinct User-Agent
        "User-Agent": "CrewAIAgent_TestingApp/1.0" 
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, verify=False)
        response.raise_for_status()
        data = response.json()
        
        if data:
            result = data[0]
            return json.dumps({
                "success": True,
                "display_name": result.get('display_name'),
                "latitude": float(result.get('lat')),
                "longitude": float(result.get('lon')),
                "type": result.get('type')
            })
        else:
            return json.dumps({"success": False, "error": "Location not found."})
            
    except requests.exceptions.RequestException as e:
        return json.dumps({"success": False, "error": f"Geocoding API request failed: {str(e)}"})

@tool
def get_weather(latitude: float, longitude: float) -> str:
    """
    Fetches the current weather and a 3-day forecast for a specific set of coordinates.
    
    You MUST provide numerical latitude and longitude. If you only have a city name, 
    you must use the `geocode_location` tool first to get the coordinates.
    
    Args:
        latitude (float): The geographical latitude.
        longitude (float): The geographical longitude.
        
    Returns:
        str: A JSON string containing current temperature (in Celsius), current wind speed (km/h), 
             and a timezone indicator.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": "true",
        "hourly": "temperature_2m,windspeed_10m",
        "forecast_days": 3
    }
    
    try:
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current_weather", {})
        return json.dumps({
            "success": True,
            "current_temperature_celsius": current.get('temperature'),
            "current_windspeed_kmh": current.get('windspeed'),
            "timezone": data.get('timezone')
        })
            
    except requests.exceptions.RequestException as e:
        return json.dumps({"success": False, "error": f"Weather API request failed: {str(e)}"})

@tool
def get_country_data(country_name: str) -> str:
    """
    Retrieves demographic, geographic, and cultural data about a specific country.
    
    Use this tool when you need to know a country's capital, population, region, or official currency.
    
    Args:
        country_name (str): The common or official name of the country (e.g., "France", "Brazil").
        
    Returns:
        str: A JSON string containing the official name, capital city, region, population, 
             and a list of currencies used in the country.
    """
    url = f"https://restcountries.com/v3.1/name/{country_name}"
    
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        data = response.json()
        
        if data and isinstance(data, list):
            country = data[0]
            
            # Safe extraction of nested data
            currencies_dict = country.get("currencies", {})
            curr_names = [info.get("name") for info in currencies_dict.values()]
            
            return json.dumps({
                "success": True,
                "official_name": country.get("name", {}).get("official", "Unknown"),
                "capital": country.get("capital", ["Unknown"])[0],
                "region": country.get("region", "Unknown"),
                "population": country.get("population", 0),
                "currencies": curr_names
            })
        return json.dumps({"success": False, "error": "Unexpected data format received."})
            
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return json.dumps({"success": False, "error": "Country not found. Check the spelling."})
        return json.dumps({"success": False, "error": f"HTTP Error: {str(e)}"})
    except requests.exceptions.RequestException as e:
        return json.dumps({"success": False, "error": f"Country API request failed: {str(e)}"})