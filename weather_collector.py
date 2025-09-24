# weather_collector.py
import requests

class EthiopianWeatherForecast:
    def __init__(self, api_key):
        self.api_key = ""
        self.base_url = "http://api.weatherapi.com/v1"
        # Real Ethiopian locations with coordinates
        self.locations = {
            "Addis Ababa": {"lat": 9.005401, "lon": 38.763611},
            "Mekelle": {"lat": 13.4969, "lon": 39.4769},
            "Bahir Dar": {"lat": 11.5936, "lon": 37.3908},
            "Hawassa": {"lat": 7.05, "lon": 38.4667},
            "Dire Dawa": {"lat": 9.6, "lon": 41.8667},
            "Jijiga": {"lat": 9.35, "lon": 42.8},
            "Gambela": {"lat": 8.25, "lon": 34.5833},
            "Asosa": {"lat": 10.0667, "lon": 34.5333},
            "Semera": {"lat": 11.5, "lon": 41.5},
            "Jimma": {"lat": 7.6667, "lon": 36.8333},
            "Nekemte": {"lat": 9.0833, "lon": 36.55},
            "Bale Robe": {"lat": 7.1333, "lon": 40.0},
            "Shashemene": {"lat": 7.2, "lon": 38.6},
            "Dilla": {"lat": 6.4167, "lon": 38.3167},
            "Bonga": {"lat": 7.2667, "lon": 36.2333},
            "Arba Minch": {"lat": 6.0333, "lon": 37.55},
            "Hosaena": {"lat": 7.55, "lon": 37.85},
            "Debre Markos": {"lat": 10.3333, "lon": 37.7333},
            "Debre Birhan": {"lat": 9.6833, "lon": 39.5333},
            "Metu": {"lat": 8.3, "lon": 35.5833},
            "Adigrat": {"lat": 14.2833, "lon": 39.4667},
            "Goba": {"lat": 7.0167, "lon": 39.9833}
        }

    def get_location_coords(self, query):
        """Case-insensitive location matcher"""
        query = query.lower().strip()
        for name, coords in self.locations.items():
            if query in name.lower() or name.lower() in query:
                return name, coords
        # Default fallback
        return "Addis Ababa", self.locations["Addis Ababa"]

    def fetch_live_weather(self, lat, lon):
        """Fetch REAL 14-day forecast from WeatherAPI (online)"""
        try:
            url = f"{self.base_url}/forecast.json"
            params = {
                "key": self.api_key,
                "q": f"{lat},{lon}",
                "days": 14,  # Requires paid WeatherAPI plan
                "aqi": "no",
                "alerts": "no"
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Live weather fetch error: {e}")
            return None
