import requests

def test_rest_countries(country_name):
    # Using the v3.1 endpoint filtering down to a specific country name
    url = f"https://restcountries.com/v3.1/name/{country_name}"
    
    print(f"--- Testing REST Countries API for country: '{country_name}' ---")
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        data = response.json()
        
        if data and isinstance(data, list):
            country = data[0]  # Grab the primary match
            print(country, "\n", "-"*50)  # Print raw JSON for debugging
            
            # Parse deep JSON safely
            official_name = country.get("name", {}).get("official", "N/A")
            capital = country.get("capital", ["N/A"])[0]
            population = country.get("population", 0)
            region = country.get("region", "N/A")
            
            # Currencies structure can be nested dynamically by code (e.g. {"EUR": {"name": "Euro"}})
            currencies_dict = country.get("currencies", {})
            curr_names = [info.get("name") for info in currencies_dict.values()]
            
            print(f"Success! Status Code: {response.status_code}")
            print(f"Official Name: {official_name}")
            print(f"Capital City: {capital}")
            print(f"Region: {region}")
            print(f"Population: {population:,}")
            print(f"Currencies Used: {', '.join(curr_names)}\n")
            
    except requests.exceptions.RequestException as e:
        print(f"API Request Failed: {e}\n")

# Test with a country name
test_rest_countries("Japan")