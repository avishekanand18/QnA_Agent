import requests

def test_open_meteo(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "hourly": "temperature_2m,windspeed_10m",
        "forecast_days": 3
    }
    
    print(f"--- Testing Open-Meteo API for coordinates ({lat}, {lon}) ---")
    try:
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status() # Raise error for bad responses (4xx, 5xx)
        data = response.json()
        
        # Extract and print high-level details
        current = data.get("current_weather", {})
        print(f"Success! Status Code: {response.status_code}")
        print(f"Current Temperature: {current.get('temperature')}°C")
        print(f"Current Wind Speed: {current.get('windspeed')} km/h")
        print(f"Timezone: {data.get('timezone')}")
        print(f"Data points fetched: {len(data['hourly']['time'])} hourly intervals.\n")
        
    except requests.exceptions.RequestException as e:
        print(f"API Request Failed: {e}\n")

# Test with coordinates (Example: Paris, France)
test_open_meteo(48.8566, 2.3522)