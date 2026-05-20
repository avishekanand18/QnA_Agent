import requests

def test_nominatim_search(query):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1
    }
    # Nominatim requires a distinct User-Agent to comply with usage policy
    headers = {
        "User-Agent": "test-bot"
    }
    
    print(f"--- Testing Nominatim Geocoding API for: '{query}' ---")
    try:
        response = requests.get(url, params=params, headers=headers, verify=False)
        response.raise_for_status()
        data = response.json()
        
        if data:
            result = data[0]
            print(f"Success! Status Code: {response.status_code}")
            print(f"Matched Name: {result.get('display_name')}")
            print(f"Latitude: {result.get('lat')}")
            print(f"Longitude: {result.get('lon')}")
            print(f"Type: {result.get('type')} ({result.get('addresstype')})\n")
        else:
            print("Request succeeded, but no location matches found.\n")
            
    except requests.exceptions.RequestException as e:
        print(f"API Request Failed: {e}\n")

# Test with a famous landmark
test_nominatim_search("Kolkata, India")