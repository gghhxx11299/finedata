import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from sqlalchemy.orm import Session
from .models import DataRecord, Dataset
from .analytics import DataAnalytics
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
import json

class VisualizationGenerator:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.analytics = DataAnalytics(db_session)
    
    def create_line_chart(self, dataset_id: int, x_field: str, y_field: str, title: str = None) -> str:
        """Create a line chart and return HTML representation"""
        chart_data = self.analytics.visualization.generate_chart_data(
            dataset_id, "line", x_field, y_field
        )
        
        if 'error' in chart_data:
            return f"<p>Error: {chart_data['error']}</p>"
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=chart_data['x_axis'],
            y=chart_data['y_axis'],
            mode='lines+markers',
            name=y_field
        ))
        
        fig.update_layout(
            title=title or f"Line Chart: {y_field} over {x_field}",
            xaxis_title=chart_data['x_label'],
            yaxis_title=chart_data['y_label']
        )
        
        return fig.to_html(include_plotlyjs=True, div_id="line_chart")
    
    def create_bar_chart(self, dataset_id: int, x_field: str, y_field: str, title: str = None) -> str:
        """Create a bar chart and return HTML representation"""
        chart_data = self.analytics.visualization.generate_chart_data(
            dataset_id, "bar", x_field, y_field
        )
        
        if 'error' in chart_data:
            return f"<p>Error: {chart_data['error']}</p>"
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=chart_data['x_axis'],
            y=chart_data['y_axis'],
            name=y_field
        ))
        
        fig.update_layout(
            title=title or f"Bar Chart: {y_field} by {x_field}",
            xaxis_title=chart_data['x_label'],
            yaxis_title=chart_data['y_label']
        )
        
        return fig.to_html(include_plotlyjs=True, div_id="bar_chart")
    
    def create_scatter_plot(self, dataset_id: int, x_field: str, y_field: str, title: str = None) -> str:
        """Create a scatter plot and return HTML representation"""
        chart_data = self.analytics.visualization.generate_chart_data(
            dataset_id, "scatter", x_field, y_field
        )
        
        if 'error' in chart_data:
            return f"<p>Error: {chart_data['error']}</p>"
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=chart_data['x_values'],
            y=chart_data['y_values'],
            mode='markers',
            name='Data Points'
        ))
        
        fig.update_layout(
            title=title or f"Scatter Plot: {y_field} vs {x_field}",
            xaxis_title=chart_data['x_label'],
            yaxis_title=chart_data['y_label']
        )
        
        return fig.to_html(include_plotlyjs=True, div_id="scatter_plot")
    
    def create_pie_chart(self, dataset_id: int, field: str, title: str = None) -> str:
        """Create a pie chart and return HTML representation"""
        chart_data = self.analytics.visualization.generate_chart_data(
            dataset_id, "pie", field, None
        )
        
        if 'error' in chart_data:
            return f"<p>Error: {chart_data['error']}</p>"
        
        fig = go.Figure(data=[go.Pie(
            labels=chart_data['labels'],
            values=chart_data['values'],
            name=field
        )])
        
        fig.update_layout(
            title=title or f"Pie Chart: Distribution of {field}"
        )
        
        return fig.to_html(include_plotlyjs=True, div_id="pie_chart")
    
    def create_histogram(self, dataset_id: int, field: str, bins: int = 20, title: str = None) -> str:
        """Create a histogram and return HTML representation"""
        chart_data = self.analytics.visualization.generate_chart_data(
            dataset_id, "histogram", field, None
        )
        
        if 'error' in chart_data:
            return f"<p>Error: {chart_data['error']}</p>"
        
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=chart_data['x_values'] if 'x_values' in chart_data else [],
            nbinsx=bins,
            name=field
        ))
        
        fig.update_layout(
            title=title or f"Histogram: Distribution of {field}",
            xaxis_title=chart_data['x_label'],
            yaxis_title="Frequency"
        )
        
        return fig.to_html(include_plotlyjs=True, div_id="histogram")
    
    def create_dashboard(self, dataset_id: int) -> str:
        """Create a comprehensive dashboard for a dataset"""
        # Get dataset info
        dataset = self.db_session.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            return "<p>Dataset not found</p>"
        
        # Get records
        records = self.db_session.query(DataRecord).filter(
            DataRecord.dataset_id == dataset_id
        ).all()
        
        if not records:
            return "<p>No records found in dataset</p>"
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame([record.data for record in records])
        
        # Create dashboard HTML
        html_parts = [
            f"<h1>Dataset Dashboard: {dataset.name}</h1>",
            f"<p><strong>Description:</strong> {dataset.description}</p>",
            f"<p><strong>Record Count:</strong> {dataset.record_count}</p>",
            f"<p><strong>Created:</strong> {dataset.created_at}</p>",
            "<hr>"
        ]
        
        # Add summary statistics
        summary_result = self.analytics.run_summary_analysis(dataset_id)
        if 'results' in summary_result:
            summary = summary_result['results']['summary']
            html_parts.append("<h2>Dataset Summary</h2>")
            html_parts.append("<ul>")
            html_parts.append(f"<li>Total Records: {summary['total_records']}</li>")
            html_parts.append(f"<li>Total Columns: {summary['total_columns']}</li>")
            html_parts.append(f"<li>Memory Usage: {summary['memory_usage']} bytes</li>")
            html_parts.append("</ul>")
        
        # Add sample data table
        html_parts.append("<h2>Sample Data</h2>")
        html_parts.append("<table border='1' style='border-collapse: collapse;'>")
        
        # Add header
        if not df.empty:
            html_parts.append("<tr>")
            for col in df.columns[:5]:  # Limit to first 5 columns for display
                html_parts.append(f"<th>{col}</th>")
            html_parts.append("</tr>")
            
            # Add first 5 rows
            for _, row in df.head().iterrows():
                html_parts.append("<tr>")
                for col in df.columns[:5]:
                    val = str(row[col])[:50] + "..." if len(str(row[col])) > 50 else str(row[col])
                    html_parts.append(f"<td>{val}</td>")
                html_parts.append("</tr>")
        
        html_parts.append("</table>")
        
        # Add visualizations for numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(numeric_cols) >= 1:
            # Create histogram for first numeric column
            hist_html = self.create_histogram(dataset_id, numeric_cols[0], title=f"Distribution of {numeric_cols[0]}")
            html_parts.append(f"<h2>Distribution of {numeric_cols[0]}</h2>")
            html_parts.append(hist_html)
        
        if len(numeric_cols) >= 2:
            # Create scatter plot for first two numeric columns
            scatter_html = self.create_scatter_plot(dataset_id, numeric_cols[0], numeric_cols[1], 
                                                    title=f"{numeric_cols[1]} vs {numeric_cols[0]}")
            html_parts.append(f"<h2>{numeric_cols[1]} vs {numeric_cols[0]}</h2>")
            html_parts.append(scatter_html)
        
        # Add categorical analysis
        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()[:2]  # Limit to 2 for performance
        for col in categorical_cols:
            if df[col].nunique() <= 20:  # Only plot if not too many unique values
                pie_html = self.create_pie_chart(dataset_id, col, title=f"Distribution of {col}")
                html_parts.append(f"<h2>Distribution of {col}</h2>")
                html_parts.append(pie_html)
        
        return "".join(html_parts)