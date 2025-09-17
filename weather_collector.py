import requests
import json
import datetime
import time

class EthiopianWeatherForecast:
    def __init__(self):
        # API configuration for WeatherAPI.com
        self.api_key = "7add9cf5aa00418a91161932251709"  # Replace with your actual API key
        self.base_url = "http://api.weatherapi.com/v1"
        
        # Ethiopian agricultural regions with coordinates
        self.locations = {
            # Capitals
            "Addis Ababa": {"lat": 9.005401, "lon": 38.763611},
            "Mekelle": {"lat": 13.4969, "lon": 39.4769},
            "Bahir Dar": {"lat": 11.5936, "lon": 37.3908},
            "Hawassa": {"lat": 7.05, "lon": 38.4667},
            "Dire Dawa": {"lat": 9.6, "lon": 41.8667},
            "Jijiga": {"lat": 9.35, "lon": 42.8},
            "Gambela": {"lat": 8.25, "lon": 34.5833},
            "Asosa": {"lat": 10.0667, "lon": 34.5333},
            "Semera": {"lat": 11.5, "lon": 41.5},
            # Agricultural Hotspots
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
        
        self.forecast_data = []
        self.failed_locations = []
    
    def fetch_forecast_data(self, location, lat, lon):
        """Fetch forecast data using WeatherAPI.com"""
        try:
            # WeatherAPI.com uses q parameter with "lat,lon" format
            q = f"{lat},{lon}"
            days = 7  # Get 7-day forecast
            
            url = f"{self.base_url}/forecast.json?key={self.api_key}&q={q}&days={days}&aqi=no&alerts=no"
            
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            return data
        except Exception as e:
            print(f"Error fetching forecast for {location}: {str(e)}")
            return None
    
    def process_forecast_data(self, location, data):
        """Process forecast data for storage"""
        forecast_info = {
            'location': location,
            'timestamp': datetime.datetime.now().isoformat(),
            'current': {},
            'forecast': []
        }
        
        # Current weather
        if 'current' in data:
            current = data['current']
            forecast_info['current'] = {
                'temperature': current.get('temp_c', 'N/A'),
                'humidity': current.get('humidity', 'N/A'),
                'weather': current.get('condition', {}).get('text', 'N/A'),
                'wind_speed': current.get('wind_kph', 'N/A'),
                'timestamp': current.get('last_updated', 'N/A')
            }
        
        # Forecast data
        if 'forecast' in data and 'forecastday' in data['forecast']:
            for day in data['forecast']['forecastday']:
                day_data = {
                    'date': day.get('date', 'N/A'),
                    'temp_min': day.get('day', {}).get('mintemp_c', 'N/A'),
                    'temp_max': day.get('day', {}).get('maxtemp_c', 'N/A'),
                    'weather': day.get('day', {}).get('condition', {}).get('text', 'N/A'),
                    'precipitation': day.get('day', {}).get('daily_chance_of_rain', 0),
                    'wind_speed': day.get('day', {}).get('maxwind_kph', 'N/A'),
                }
                forecast_info['forecast'].append(day_data)
        
        return forecast_info
    
    def fetch_all_forecasts(self):
        """Fetch weather data for all locations"""
        self.forecast_data = []
        self.failed_locations = []
        total_locations = len(self.locations)
        
        print(f"Fetching weather forecasts for {total_locations} locations...")
        
        for i, (location, coords) in enumerate(self.locations.items(), 1):
            print(f"[{i}/{total_locations}] Fetching forecast for {location}...", end=" ")
            
            data = self.fetch_forecast_data(location, coords['lat'], coords['lon'])
            
            if data is not None:
                forecast_info = self.process_forecast_data(location, data)
                self.forecast_data.append(forecast_info)
                print(f"Success")
            else:
                self.failed_locations.append(location)
                print("Failed")
            
            # Add a small delay to avoid hitting API rate limits
            time.sleep(1)
        
        print()
        success_count = len(self.forecast_data)
        failed_count = len(self.failed_locations)
        print(f"Forecast fetching completed. {success_count} locations succeeded, {failed_count} locations failed.")
        
        if failed_count > 0:
            print("Failed locations:", ", ".join(self.failed_locations))
    
    def save_to_data_txt(self):
        """Save the collected data to data.txt in a readable format"""
        if not self.forecast_data:
            print("No data to save. Please fetch data first.")
            return False
        
        try:
            with open('data.txt', 'w') as file:
                file.write("Ethiopian Weather Forecast Data\n")
                file.write("=" * 50 + "\n\n")
                file.write(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for forecast in self.forecast_data:
                    file.write(f"Location: {forecast['location']}\n")
                    file.write(f"Current Temperature: {forecast['current']['temperature']}°C\n")
                    file.write(f"Current Conditions: {forecast['current']['weather']}\n")
                    file.write(f"Humidity: {forecast['current']['humidity']}%\n")
                    file.write(f"Wind Speed: {forecast['current']['wind_speed']} km/h\n")
                    
                    file.write("\n7-Day Forecast:\n")
                    for day in forecast['forecast']:
                        file.write(f"  {day['date']}: {day['temp_min']}°C - {day['temp_max']}°C, ")
                        file.write(f"{day['weather']}, Precip: {day['precipitation']}%\n")
                    
                    file.write("\n" + "-" * 40 + "\n\n")
            
            print("Data successfully saved to data.txt")
            return True
        except Exception as e:
            print(f"Error saving data to file: {str(e)}")
            return False

def main():
    """Main function to run the data collection"""
    print("Starting Ethiopian Weather Data Collection...")
    
    # Initialize the weather collector
    collector = EthiopianWeatherForecast()
    
    # Fetch all forecast data
    collector.fetch_all_forecasts()
    
    # Save the data to data.txt
    collector.save_to_data_txt()
    
    print("Data collection completed!")

if __name__ == "__main__":
    main()
