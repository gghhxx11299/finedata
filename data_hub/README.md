# Real-World AI Data Hub

A comprehensive platform for collecting, processing, analyzing, and visualizing real-world data.

## Overview

The Real-World AI Data Hub is a complete data platform that enables organizations to:

- **Ingest data** from multiple sources (APIs, files, databases, streams)
- **Process and clean** data with configurable rules
- **Analyze** data with statistical and trend analysis
- **Visualize** data with interactive charts and dashboards
- **Access programmatically** via RESTful APIs
- **Integrate** with existing systems and workflows

## Architecture

The data hub is built with a modular architecture:

- **Data Ingestion Layer**: APIs and tools for collecting data from various sources
- **Data Storage Layer**: Flexible storage for structured and unstructured data
- **Processing Layer**: Tools for cleaning, transforming, and enriching data
- **Analytics Layer**: Statistical analysis and machine learning capabilities
- **Visualization Layer**: Interactive dashboards and charts
- **API Layer**: RESTful endpoints for system integration

## Features

- **Multi-source Data Ingestion**: Connect to APIs, import files, or stream data
- **Flexible Data Models**: Store structured, semi-structured, and unstructured data
- **Statistical Analysis**: Descriptive statistics, correlations, and trend analysis
- **Interactive Visualizations**: Charts, graphs, and dashboards
- **RESTful API**: Access data and analytics programmatically
- **Data Quality Tools**: Cleaning, validation, and transformation capabilities
- **Scalable Architecture**: Designed to handle growing data volumes

## Installation

1. Clone the repository:
```bash
git clone https://github.com/data-hub/real-world-ai-data-hub.git
cd real-world-ai-data-hub
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install the package:
```bash
pip install -e .
```

## Usage

### Running the Demo

```bash
python run_hub.py demo
```

This will load sample data and run through a complete workflow demonstrating the capabilities.

### Starting the API Server

```bash
python run_hub.py api
```

Or to specify a custom port:
```bash
python run_hub.py api 8080
```

The API will be available at `http://localhost:5000`

### API Endpoints

- `GET /api/datasets` - List all datasets
- `GET /api/dataset/<id>` - Get dataset details
- `GET /api/dataset/<id>/records` - Get dataset records
- `POST /api/dataset/<id>/query` - Query dataset
- `GET /api/analytics/describe/<id>` - Dataset statistics
- `POST /api/ingest/api` - Ingest from API
- `POST /api/ingest/file` - Ingest from file
- `GET /api/visualize/line/<id>?x=<field>&y=<field>` - Line chart data
- `GET /api/visualize/bar/<id>?x=<field>&y=<field>` - Bar chart data
- `GET /api/visualize/pie/<id>?field=<field>` - Pie chart data
- `GET /api/dashboard/<id>` - Dataset dashboard

## Data Hub Components

### Data Sources

Register and manage multiple data sources:
- APIs (REST, GraphQL)
- Files (JSON, CSV, Excel)
- Databases (SQL, NoSQL)
- Streaming sources (Kafka, etc.)

### Datasets

Organize data into logical collections with metadata and schema information.

### Analytics

Perform various types of analysis:
- Descriptive statistics
- Trend analysis
- Correlation analysis
- Custom analysis functions

### Visualizations

Create various types of visualizations:
- Line charts
- Bar charts
- Pie charts
- Scatter plots
- Histograms
- Dashboards

## Integration

The data hub can be integrated into existing systems:

1. **Direct API calls**: Use the REST API to add, query, and analyze data
2. **Python library**: Import the data hub modules directly into your code
3. **Webhooks**: Configure webhooks for real-time notifications

## Data Governance

The platform includes features for data governance:
- User authentication and authorization
- Data access logging
- Privacy controls
- Compliance with data protection regulations

## License

This project is licensed under the MIT License - see the LICENSE file for details.