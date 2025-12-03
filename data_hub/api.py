from flask import Flask, request, jsonify, render_template_string
from sqlalchemy.orm import Session
from .models import get_db_session, Dataset, DataRecord, DataQuery, User
from .ingestion import DataIngestor, DataProcessor
from .analytics import DataAnalytics, DataVisualization
from .visualization import VisualizationGenerator
from typing import Dict, Any, List
import json
from datetime import datetime
import hashlib

class APIHandler:
    def __init__(self):
        self.app = Flask(__name__)
        self.db_session = get_db_session()
        self.ingestor = DataIngestor(self.db_session)
        self.processor = DataProcessor(self.db_session)
        self.setup_routes()
    
    def setup_routes(self):
        """Setup all API routes"""
        @self.app.route('/api/datasets', methods=['GET'])
        def get_datasets():
            """Get list of all datasets"""
            try:
                datasets = self.ingestor.get_available_datasets()
                return jsonify({"status": "success", "data": datasets})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route('/api/dataset/<int:dataset_id>', methods=['GET'])
        def get_dataset(dataset_id: int):
            """Get details about a specific dataset"""
            try:
                dataset = self.db_session.query(Dataset).filter(Dataset.id == dataset_id).first()
                if not dataset:
                    return jsonify({"status": "error", "message": "Dataset not found"}), 404
                
                return jsonify({
                    "status": "success",
                    "data": {
                        "id": dataset.id,
                        "name": dataset.name,
                        "description": dataset.description,
                        "record_count": dataset.record_count,
                        "schema_info": dataset.schema_info,
                        "last_updated": dataset.last_updated.isoformat() if dataset.last_updated else None
                    }
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route('/api/dataset/<int:dataset_id>/records', methods=['GET'])
        def get_dataset_records(dataset_id: int):
            """Get records from a specific dataset with optional filtering"""
            try:
                # Get query parameters
                limit = request.args.get('limit', 100, type=int)
                offset = request.args.get('offset', 0, type=int)
                filter_query = request.args.get('filter', None, type=str)
                
                # Build query for dataset records
                query = self.db_session.query(DataRecord).filter(DataRecord.dataset_id == dataset_id)
                
                # Apply filtering if provided
                if filter_query:
                    # This is a simple implementation - in a real system you'd want more sophisticated filtering
                    try:
                        filter_dict = json.loads(filter_query)
                        # Filter by keys in the data field
                        for key, value in filter_dict.items():
                            query = query.filter(DataRecord.data[key].astext == str(value))
                    except json.JSONDecodeError:
                        return jsonify({"status": "error", "message": "Invalid filter query"}), 400
                
                # Apply pagination
                records = query.offset(offset).limit(limit).all()
                
                result = [
                    {
                        "id": record.id,
                        "data": record.data,
                        "metadata": record.metadata,
                        "created_at": record.created_at.isoformat() if record.created_at else None
                    }
                    for record in records
                ]
                
                return jsonify({
                    "status": "success",
                    "data": result,
                    "count": len(result),
                    "offset": offset,
                    "limit": limit
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route('/api/dataset/<int:dataset_id>/query', methods=['POST'])
        def query_dataset(dataset_id: int):
            """Execute a complex query on a dataset"""
            try:
                data = request.json
                query_text = data.get('query', '')
                
                # In a real system, this would be a SQL-like query or a more sophisticated query language
                # For now, we'll implement basic filtering and aggregation
                records = self.db_session.query(DataRecord).filter(DataRecord.dataset_id == dataset_id).all()
                
                # Apply query logic (simplified for this example)
                result = []
                for record in records:
                    # For now, just return all records
                    result.append({
                        "id": record.id,
                        "data": record.data,
                        "metadata": record.metadata
                    })
                
                # Save the query for analytics
                query_entry = DataQuery(
                    user_id=1,  # In a real system, this would come from authentication
                    query_text=query_text,
                    dataset_id=dataset_id,
                    results={"count": len(result), "sample": result[:5] if result else []},
                    execution_time=0.1  # Placeholder
                )
                self.db_session.add(query_entry)
                self.db_session.commit()
                
                return jsonify({
                    "status": "success",
                    "data": result,
                    "count": len(result)
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route('/api/ingest/api', methods=['POST'])
        def ingest_from_api():
            """Ingest data from an API endpoint"""
            try:
                data = request.json
                source_name = data.get('source_name')
                dataset_name = data.get('dataset_name')
                endpoint = data.get('endpoint')
                headers = data.get('headers', {})
                params = data.get('params', {})
                data_field = data.get('data_field')
                
                # Register the source if it doesn't exist
                source = self.db_session.query(DataSource).filter(DataSource.name == source_name).first()
                if not source:
                    source = self.ingestor.register_data_source(
                        name=source_name,
                        source_type='API',
                        description=f'API source for {source_name}',
                        connection_info={'endpoint': endpoint}
                    )
                
                # Create dataset if it doesn't exist
                dataset = self.db_session.query(Dataset).filter(Dataset.name == dataset_name).first()
                if not dataset:
                    dataset = self.ingestor.create_dataset(
                        name=dataset_name,
                        source_id=source.id,
                        description=f'Dataset from {source_name}'
                    )
                
                # Perform the ingestion
                log = self.ingestor.ingest_from_api(
                    source_id=source.id,
                    dataset_id=dataset.id,
                    endpoint=endpoint,
                    headers=headers,
                    params=params,
                    data_field=data_field
                )
                
                return jsonify({
                    "status": "success",
                    "log_id": log.id,
                    "records_processed": log.records_processed,
                    "records_failed": log.records_failed,
                    "status": log.status
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route('/api/ingest/file', methods=['POST'])
        def ingest_from_file():
            """Ingest data from a file"""
            try:
                data = request.json
                source_name = data.get('source_name')
                dataset_name = data.get('dataset_name')
                file_path = data.get('file_path')
                file_format = data.get('file_format', 'json')
                
                # Register the source if it doesn't exist
                source = self.db_session.query(DataSource).filter(DataSource.name == source_name).first()
                if not source:
                    source = self.ingestor.register_data_source(
                        name=source_name,
                        source_type='FILE',
                        description=f'File source for {source_name}',
                        connection_info={'file_path': file_path}
                    )
                
                # Create dataset if it doesn't exist
                dataset = self.db_session.query(Dataset).filter(Dataset.name == dataset_name).first()
                if not dataset:
                    dataset = self.ingestor.create_dataset(
                        name=dataset_name,
                        source_id=source.id,
                        description=f'Dataset from {source_name}'
                    )
                
                # Perform the ingestion
                log = self.ingestor.ingest_from_file(
                    source_id=source.id,
                    dataset_id=dataset.id,
                    file_path=file_path,
                    file_format=file_format
                )
                
                return jsonify({
                    "status": "success",
                    "log_id": log.id,
                    "records_processed": log.records_processed,
                    "records_failed": log.records_failed,
                    "status": log.status
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        
        @self.app.route('/api/analytics/describe/<int:dataset_id>', methods=['GET'])
        def describe_dataset(dataset_id: int):
            """Get basic analytics for a dataset"""
            try:
                dataset = self.db_session.query(Dataset).filter(Dataset.id == dataset_id).first()
                if not dataset:
                    return jsonify({"status": "error", "message": "Dataset not found"}), 404

                records = self.db_session.query(DataRecord).filter(DataRecord.dataset_id == dataset_id).all()

                if not records:
                    return jsonify({
                        "status": "success",
                        "data": {
                            "dataset_id": dataset_id,
                            "name": dataset.name,
                            "record_count": 0,
                            "fields": [],
                            "summary": {}
                        }
                    })

                # Analyze the first record to determine fields
                first_record_data = records[0].data
                fields = list(first_record_data.keys()) if isinstance(first_record_data, dict) else []

                # Calculate basic statistics
                summary = {}
                if isinstance(first_record_data, dict):
                    for field in fields:
                        # Count non-null values for each field
                        non_null_count = sum(1 for r in records if r.data.get(field) is not None)
                        summary[field] = {
                            "total_records": len(records),
                            "non_null_count": non_null_count,
                            "null_percentage": (len(records) - non_null_count) / len(records) * 100
                        }

                return jsonify({
                    "status": "success",
                    "data": {
                        "dataset_id": dataset_id,
                        "name": dataset.name,
                        "record_count": len(records),
                        "fields": fields,
                        "summary": summary
                    }
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/visualize/line/<int:dataset_id>', methods=['GET'])
        def get_line_chart(dataset_id: int):
            """Get data for a line chart"""
            try:
                x_field = request.args.get('x', 'index')
                y_field = request.args.get('y', '')

                if not y_field:
                    return jsonify({"status": "error", "message": "y field is required"}), 400

                viz_gen = VisualizationGenerator(self.db_session)
                chart_data = viz_gen.generate_chart_data(
                    dataset_id, "line", x_field, y_field
                )

                return jsonify({
                    "status": "success",
                    "data": chart_data,
                    "chart_type": "line"
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/visualize/bar/<int:dataset_id>', methods=['GET'])
        def get_bar_chart(dataset_id: int):
            """Get data for a bar chart"""
            try:
                x_field = request.args.get('x', 'index')
                y_field = request.args.get('y', '')

                if not y_field:
                    return jsonify({"status": "error", "message": "y field is required"}), 400

                viz_gen = VisualizationGenerator(self.db_session)
                chart_data = viz_gen.generate_chart_data(
                    dataset_id, "bar", x_field, y_field
                )

                return jsonify({
                    "status": "success",
                    "data": chart_data,
                    "chart_type": "bar"
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/visualize/pie/<int:dataset_id>', methods=['GET'])
        def get_pie_chart(dataset_id: int):
            """Get data for a pie chart"""
            try:
                field = request.args.get('field', '')

                if not field:
                    return jsonify({"status": "error", "message": "field is required"}), 400

                viz_gen = VisualizationGenerator(self.db_session)
                chart_data = viz_gen.generate_chart_data(
                    dataset_id, "pie", field, None
                )

                return jsonify({
                    "status": "success",
                    "data": chart_data,
                    "chart_type": "pie"
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/dashboard/<int:dataset_id>', methods=['GET'])
        def get_dashboard(dataset_id: int):
            """Get a dashboard for a dataset"""
            try:
                viz_gen = VisualizationGenerator(self.db_session)
                dashboard_html = viz_gen.create_dashboard(dataset_id)

                return jsonify({
                    "status": "success",
                    "html": dashboard_html
                })
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/', methods=['GET'])
        def home():
            """Home page for the data hub"""
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Real-World AI Data Hub</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .container { max-width: 1200px; margin: 0 auto; }
                    .header { background-color: #4CAF50; color: white; padding: 20px; text-align: center; }
                    .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
                    .btn { background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 5px; }
                    .btn:hover { background-color: #45a049; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🤖 Real-World AI Data Hub</h1>
                        <p>Collect, Process, Analyze, and Visualize Real-World Data</p>
                    </div>

                    <div class="section">
                        <h2>Quick Start</h2>
                        <p>The Real-World AI Data Hub provides a comprehensive platform for:</p>
                        <ul>
                            <li>Data ingestion from multiple sources (APIs, files, databases)</li>
                            <li>Data processing and cleaning</li>
                            <li>Statistical analysis and insights</li>
                            <li>Data visualization and dashboards</li>
                            <li>API access for integration</li>
                        </ul>
                    </div>

                    <div class="section">
                        <h2>API Endpoints</h2>
                        <h3>Dataset Management</h3>
                        <ul>
                            <li><code>GET /api/datasets</code> - List all datasets</li>
                            <li><code>GET /api/dataset/&lt;id&gt;</code> - Get dataset details</li>
                            <li><code>GET /api/dataset/&lt;id&gt;/records</code> - Get dataset records</li>
                        </ul>

                        <h3>Data Analysis</h3>
                        <ul>
                            <li><code>GET /api/analytics/describe/&lt;id&gt;</code> - Dataset statistics</li>
                            <li><code>POST /api/dataset/&lt;id&gt;/query</code> - Query dataset</li>
                        </ul>

                        <h3>Data Ingestion</h3>
                        <ul>
                            <li><code>POST /api/ingest/api</code> - Ingest from API</li>
                            <li><code>POST /api/ingest/file</code> - Ingest from file</li>
                        </ul>

                        <h3>Visualization</h3>
                        <ul>
                            <li><code>GET /api/visualize/line/&lt;id&gt;?x=&lt;field&gt;&y=&lt;field&gt;</code> - Line chart data</li>
                            <li><code>GET /api/visualize/bar/&lt;id&gt;?x=&lt;field&gt;&y=&lt;field&gt;</code> - Bar chart data</li>
                            <li><code>GET /api/visualize/pie/&lt;id&gt;?field=&lt;field&gt;</code> - Pie chart data</li>
                            <li><code>GET /api/dashboard/&lt;id&gt;</code> - Dataset dashboard</li>
                        </ul>
                    </div>

                    <div class="section">
                        <h2>Try It Out</h2>
                        <p>To use the data hub:</p>
                        <ol>
                            <li>Add data sources via the ingestion API</li>
                            <li>Run analyses on your datasets</li>
                            <li>Visualize your data with the built-in tools</li>
                            <li>Integrate with your own applications via the API</li>
                        </ol>
                    </div>
                </div>
            </body>
            </html>
            """
            return render_template_string(html_template)
    
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Run the API server"""
        self.app.run(host=host, port=port, debug=debug)