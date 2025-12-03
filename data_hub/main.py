import os
import requests
from sqlalchemy.orm import Session
from .models import get_db_session, DataSource, Dataset, AIModel
from .ingestion import DataIngestor, DataProcessor
from .api import APIHandler
from .analytics import DataAnalytics, DataVisualization
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

class RealWorldAIHub:
    def __init__(self, database_url: str = "sqlite:///data_hub.db"):
        self.db_session = get_db_session(database_url)
        self.ingestor = DataIngestor(self.db_session)
        self.processor = DataProcessor(self.db_session)
        self.analytics = DataAnalytics(self.db_session)
        self.visualization = DataVisualization(self.db_session)
        self.api_handler = APIHandler()  # Will use the same session

        # Predefined data sources for demonstration
        self._setup_default_sources()
    
    def _setup_default_sources(self):
        """Setup default data sources for the data hub"""
        # Weather API source
        try:
            weather_source = self.db_session.query(DataSource).filter(
                DataSource.name == "OpenWeatherMap"
            ).first()
            if not weather_source:
                weather_source = DataSource(
                    name="OpenWeatherMap",
                    description="Weather data API",
                    source_type="API",
                    connection_info={
                        "base_url": "http://api.openweathermap.org/data/2.5",
                        "requires_api_key": True
                    }
                )
                self.db_session.add(weather_source)
                self.db_session.commit()
        except Exception as e:
            print(f"Warning: Could not setup weather source: {e}")
        
        # News API source
        try:
            news_source = self.db_session.query(DataSource).filter(
                DataSource.name == "NewsAPI"
            ).first()
            if not news_source:
                news_source = DataSource(
                    name="NewsAPI",
                    description="News articles API",
                    source_type="API",
                    connection_info={
                        "base_url": "https://newsapi.org/v2",
                        "requires_api_key": True
                    }
                )
                self.db_session.add(news_source)
                self.db_session.commit()
        except Exception as e:
            print(f"Warning: Could not setup news source: {e}")
    
    def register_data_source(self, name: str, source_type: str, description: str = "", 
                           connection_info: dict = None) -> DataSource:
        """Register a new data source"""
        return self.ingestor.register_data_source(name, source_type, description, connection_info)
    
    def create_dataset(self, name: str, source_id: int, description: str = "", 
                      schema_info: dict = None) -> Dataset:
        """Create a new dataset"""
        return self.ingestor.create_dataset(name, source_id, description, schema_info)
    
    def ingest_from_api(self, source_id: int, dataset_id: int, endpoint: str, 
                       headers: dict = None, params: dict = None, 
                       data_field: str = None):
        """Ingest data from an API"""
        return self.ingestor.ingest_from_api(
            source_id, dataset_id, endpoint, headers, params, data_field
        )
    
    def ingest_from_file(self, source_id: int, dataset_id: int, file_path: str, 
                        file_format: str = "json"):
        """Ingest data from a file"""
        return self.ingestor.ingest_from_file(source_id, dataset_id, file_path, file_format)
    
    def run_statistical_analysis(self, dataset_id: int, analysis_params: Dict[str, Any] = None):
        """Run statistical analysis on a dataset"""
        return self.analytics.run_statistical_analysis(dataset_id, analysis_params)
    
    def run_trend_analysis(self, dataset_id: int, time_field: str, value_field: str):
        """Run trend analysis on a dataset"""
        return self.analytics.run_trend_analysis(dataset_id, time_field, value_field)
    
    def run_summary_analysis(self, dataset_id: int):
        """Run summary analysis on a dataset"""
        return self.analytics.run_summary_analysis(dataset_id)
    
    def generate_chart_data(self, dataset_id: int, chart_type: str, x_field: str, y_field: str = None):
        """Generate chart data for visualization"""
        return self.visualization.generate_chart_data(dataset_id, chart_type, x_field, y_field)
    
    def generate_time_series_data(self, dataset_id: int, time_field: str, value_field: str):
        """Generate time series data for visualization"""
        return self.visualization.generate_time_series_data(dataset_id, time_field, value_field)
    
    def get_available_datasets(self) -> List[Dict]:
        """Get all available datasets"""
        return self.ingestor.get_available_datasets()
    
    def get_analysis_history(self, dataset_id: int = None):
        """Get history of all analyses performed"""
        return self.analytics.get_analysis_history(dataset_id)
    
    def start_api_server(self, host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
        """Start the API server"""
        self.api_handler.db_session = self.db_session  # Ensure same session
        self.api_handler.ingestor = self.ingestor
        self.api_handler.processor = self.processor
        self.api_handler.app.run(host=host, port=port, debug=debug)
    
    def load_sample_data(self):
        """Load sample data to demonstrate the data hub capabilities"""
        print("Loading sample data...")
        
        # Create a sample dataset for demonstration
        sample_data = [
            {"name": "Product A", "price": 29.99, "category": "Electronics", "date": "2023-01-01", "sales": 150},
            {"name": "Product B", "price": 19.99, "category": "Books", "date": "2023-01-02", "sales": 89},
            {"name": "Product C", "price": 49.99, "category": "Electronics", "date": "2023-01-03", "sales": 210},
            {"name": "Product D", "price": 14.99, "category": "Books", "date": "2023-01-04", "sales": 65},
            {"name": "Product E", "price": 99.99, "category": "Home", "date": "2023-01-05", "sales": 42},
            {"name": "Product F", "price": 39.99, "category": "Electronics", "date": "2023-01-06", "sales": 180},
            {"name": "Product G", "price": 24.99, "category": "Books", "date": "2023-01-07", "sales": 95},
            {"name": "Product H", "price": 79.99, "category": "Home", "date": "2023-01-08", "sales": 33},
        ]
        
        # Register a sample data source
        sample_source = self.register_data_source(
            name="Sample Data",
            source_type="DUMMY",
            description="Sample data for demonstration"
        )
        
        # Create a sample dataset
        sample_dataset = self.create_dataset(
            name="Sample Product Data",
            source_id=sample_source.id,
            description="Sample product data for demonstration"
        )
        
        # Add the sample data to the dataset
        from .models import DataRecord
        for record_data in sample_data:
            record = DataRecord(
                dataset_id=sample_dataset.id,
                data=record_data,
                metadata={"source": "sample", "created_at": datetime.utcnow().isoformat()}
            )
            self.db_session.add(record)
        
        self.db_session.commit()
        print(f"Sample data loaded into dataset '{sample_dataset.name}' (ID: {sample_dataset.id})")
        
        return sample_dataset.id
    
    def demo_workflow(self):
        """Demonstrate a complete workflow with the data hub"""
        print("Starting Real-World AI Data Hub Demo...")
        print("=" * 50)
        
        # Load sample data
        dataset_id = self.load_sample_data()
        
        print(f"\n1. Dataset Created with ID: {dataset_id}")
        
        # Show basic dataset info
        datasets = self.get_available_datasets()
        print(f"Available datasets: {len(datasets)}")
        for ds in datasets:
            print(f"  - {ds['name']}: {ds['record_count']} records")
        
        # Run summary analysis
        print(f"\n2. Running summary analysis...")
        summary_result = self.run_summary_analysis(dataset_id)
        print(f"Analysis ID: {summary_result.get('analysis_id', 'N/A')}")
        
        # Run statistical analysis
        print(f"\n3. Running statistical analysis...")
        stat_result = self.run_statistical_analysis(dataset_id)
        if 'error' not in stat_result:
            print("Statistical analysis completed successfully")
        else:
            print(f"Statistical analysis error: {stat_result['error']}")
        
        # Generate chart data
        print(f"\n4. Generating visualization data...")
        chart_data = self.generate_chart_data(
            dataset_id=dataset_id,
            chart_type="bar",
            x_field="name",
            y_field="price"
        )
        if 'error' not in chart_data:
            print(f"Generated chart data with {len(chart_data['x_axis'])} data points")
        else:
            print(f"Chart data generation error: {chart_data['error']}")
        
        # Run trend analysis if possible
        print(f"\n5. Running trend analysis...")
        trend_result = self.run_trend_analysis(
            dataset_id=dataset_id,
            time_field="date",
            value_field="sales"
        )
        if 'error' not in trend_result:
            trend = trend_result['results']['trend']
            print(f"Trend direction: {trend['direction']}, R-squared: {trend['r_squared']:.3f}")
        else:
            print(f"Trend analysis error: {trend_result['error']}")
        
        print(f"\n6. Analysis history:")
        history = self.get_analysis_history(dataset_id)
        for analysis in history:
            print(f"  - {analysis['analysis_type']} (ID: {analysis['id']})")
        
        print("\nDemo completed! Data hub is ready for real-world usage.")
        print("Start the API server with: data_hub.start_api_server()")

# Main entry point
def main():
    hub = RealWorldAIHub()
    hub.demo_workflow()
    
    # Uncomment the following line to start the API server
    # hub.start_api_server(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main()