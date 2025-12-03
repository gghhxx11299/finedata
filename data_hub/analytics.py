import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy.orm import Session
from .models import DataRecord, Dataset, DataAnalysis, get_db_session
from datetime import datetime
from typing import Dict, List, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)

class DataAnalytics:
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def run_statistical_analysis(self, dataset_id: int, analysis_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run statistical analysis on a dataset"""
        if analysis_params is None:
            analysis_params = {"include_descriptive_stats": True, "include_correlations": False}
        
        # Get all records for the dataset
        records = self.db_session.query(DataRecord).filter(
            DataRecord.dataset_id == dataset_id
        ).all()
        
        if not records:
            return {"error": "No records found for this dataset"}
        
        # Convert records to DataFrame
        df = pd.DataFrame([record.data for record in records])
        
        # Only analyze numeric columns
        numeric_df = df.select_dtypes(include=[np.number])
        
        results = {}
        
        # Descriptive statistics
        if analysis_params.get("include_descriptive_stats", True):
            if not numeric_df.empty:
                results["descriptive_stats"] = numeric_df.describe().to_dict()
            else:
                results["descriptive_stats"] = "No numeric columns found"
        
        # Correlation matrix
        if analysis_params.get("include_correlations", False):
            if not numeric_df.empty and len(numeric_df.columns) > 1:
                results["correlations"] = numeric_df.corr().to_dict()
            else:
                results["correlations"] = "Not enough numeric columns for correlation analysis"
        
        # Categorical analysis
        categorical_df = df.select_dtypes(include=['object', 'category'])
        if not categorical_df.empty:
            categorical_stats = {}
            for col in categorical_df.columns:
                value_counts = categorical_df[col].value_counts().to_dict()
                categorical_stats[col] = {
                    "unique_values": len(value_counts),
                    "top_values": value_counts,
                    "most_common": categorical_df[col].mode().iloc[0] if len(categorical_df[col].mode()) > 0 else None
                }
            results["categorical_stats"] = categorical_stats
        
        # Store the analysis result
        analysis = DataAnalysis(
            dataset_id=dataset_id,
            analysis_type="statistical",
            parameters=analysis_params,
            results=results
        )
        self.db_session.add(analysis)
        self.db_session.commit()
        
        return {
            "analysis_id": analysis.id,
            "dataset_id": dataset_id,
            "analysis_type": analysis.analysis_type,
            "results": results,
            "created_at": analysis.created_at.isoformat()
        }
    
    def run_trend_analysis(self, dataset_id: int, time_field: str, value_field: str) -> Dict[str, Any]:
        """Run trend analysis on time series data"""
        records = self.db_session.query(DataRecord).filter(
            DataRecord.dataset_id == dataset_id
        ).all()
        
        if not records:
            return {"error": "No records found for this dataset"}
        
        # Convert records to DataFrame
        df = pd.DataFrame([record.data for record in records])
        
        if time_field not in df.columns or value_field not in df.columns:
            return {"error": f"Required fields not found: {time_field}, {value_field}"}
        
        # Convert time field to datetime if it's not already
        df[time_field] = pd.to_datetime(df[time_field])
        
        # Sort by time
        df = df.sort_values(by=time_field)
        
        # Perform trend analysis
        try:
            # Convert value field to numeric
            df[value_field] = pd.to_numeric(df[value_field], errors='coerce')
            df = df.dropna(subset=[time_field, value_field])
            
            # Calculate trend using linear regression
            if len(df) < 2:
                return {"error": "Not enough valid data points for trend analysis"}
            
            # Create time index for regression
            df['time_index'] = (df[time_field] - df[time_field].min()).dt.days
            x = df['time_index'].values
            y = df[value_field].values
            
            # Perform linear regression
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            
            results = {
                "trend": {
                    "slope": slope,
                    "intercept": intercept,
                    "r_squared": r_value ** 2,
                    "p_value": p_value,
                    "std_err": std_err,
                    "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
                },
                "summary": {
                    "total_points": len(df),
                    "date_range": {
                        "start": df[time_field].min().isoformat(),
                        "end": df[time_field].max().isoformat()
                    },
                    "value_range": {
                        "min": float(df[value_field].min()),
                        "max": float(df[value_field].max()),
                        "mean": float(df[value_field].mean())
                    }
                }
            }
            
            # Store the analysis result
            analysis = DataAnalysis(
                dataset_id=dataset_id,
                analysis_type="trend",
                parameters={"time_field": time_field, "value_field": value_field},
                results=results
            )
            self.db_session.add(analysis)
            self.db_session.commit()
            
            return {
                "analysis_id": analysis.id,
                "dataset_id": dataset_id,
                "analysis_type": analysis.analysis_type,
                "results": results,
                "created_at": analysis.created_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Trend analysis failed: {e}")
            return {"error": str(e)}
    
    def run_summary_analysis(self, dataset_id: int) -> Dict[str, Any]:
        """Run a general summary analysis on a dataset"""
        records = self.db_session.query(DataRecord).filter(
            DataRecord.dataset_id == dataset_id
        ).all()
        
        if not records:
            return {"error": "No records found for this dataset"}
        
        # Convert records to DataFrame
        df = pd.DataFrame([record.data for record in records])
        
        results = {
            "summary": {
                "total_records": len(df),
                "total_columns": len(df.columns),
                "memory_usage": df.memory_usage(deep=True).sum(),
                "column_names": list(df.columns),
                "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "null_counts": {col: int(df[col].isnull().sum()) for col in df.columns}
            }
        }
        
        # Add numeric summary if applicable
        numeric_df = df.select_dtypes(include=[np.number])
        if not numeric_df.empty:
            results["numeric_summary"] = {
                "mean": numeric_df.mean().to_dict(),
                "std": numeric_df.std().to_dict(),
                "median": numeric_df.median().to_dict(),
                "quartiles": {
                    "25%": numeric_df.quantile(0.25).to_dict(),
                    "75%": numeric_df.quantile(0.75).to_dict()
                }
            }
        
        # Store the analysis result
        analysis = DataAnalysis(
            dataset_id=dataset_id,
            analysis_type="summary",
            parameters={},
            results=results
        )
        self.db_session.add(analysis)
        self.db_session.commit()
        
        return {
            "analysis_id": analysis.id,
            "dataset_id": dataset_id,
            "analysis_type": analysis.analysis_type,
            "results": results,
            "created_at": analysis.created_at.isoformat()
        }
    
    def get_analysis_history(self, dataset_id: int = None) -> List[Dict[str, Any]]:
        """Get history of all analyses performed"""
        query = self.db_session.query(DataAnalysis)
        if dataset_id:
            query = query.filter(DataAnalysis.dataset_id == dataset_id)
        
        analyses = query.all()
        
        return [
            {
                "id": analysis.id,
                "dataset_id": analysis.dataset_id,
                "analysis_type": analysis.analysis_type,
                "parameters": analysis.parameters,
                "created_at": analysis.created_at.isoformat(),
                "has_results": analysis.results is not None
            }
            for analysis in analyses
        ]
    
    def get_analysis_result(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        """Get results of a specific analysis"""
        analysis = self.db_session.query(DataAnalysis).filter(
            DataAnalysis.id == analysis_id
        ).first()
        
        if not analysis:
            return None
        
        return {
            "id": analysis.id,
            "dataset_id": analysis.dataset_id,
            "analysis_type": analysis.analysis_type,
            "parameters": analysis.parameters,
            "results": analysis.results,
            "created_at": analysis.created_at.isoformat()
        }

class DataVisualization:
    """Generate visualization-ready data"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.analytics = DataAnalytics(db_session)
    
    def generate_chart_data(self, dataset_id: int, chart_type: str, x_field: str, y_field: str = None) -> Dict[str, Any]:
        """Generate data appropriate for charting"""
        records = self.db_session.query(DataRecord).filter(
            DataRecord.dataset_id == dataset_id
        ).all()
        
        if not records:
            return {"error": "No records found for this dataset"}
        
        # Convert records to DataFrame
        df = pd.DataFrame([record.data for record in records])
        
        if x_field not in df.columns:
            return {"error": f"X field '{x_field}' not found in dataset"}
        
        if chart_type == "line" or chart_type == "bar":
            if y_field not in df.columns:
                return {"error": f"Y field '{y_field}' not found in dataset"}
            
            # Convert x and y to appropriate types
            x_data = df[x_field].values
            y_data = pd.to_numeric(df[y_field], errors='coerce').values
            
            # Remove nulls
            mask = ~(pd.isna(x_data) | pd.isna(y_data))
            x_data = x_data[mask]
            y_data = y_data[mask]
            
            return {
                "chart_type": chart_type,
                "x_axis": list(x_data),
                "y_axis": list(y_data),
                "x_label": x_field,
                "y_label": y_field
            }
        
        elif chart_type == "scatter":
            if y_field not in df.columns:
                return {"error": f"Y field '{y_field}' not found in dataset"}
            
            x_data = df[x_field].values
            y_data = pd.to_numeric(df[y_field], errors='coerce').values
            
            # Remove nulls
            mask = ~(pd.isna(x_data) | pd.isna(y_data))
            x_data = x_data[mask]
            y_data = y_data[mask]
            
            return {
                "chart_type": chart_type,
                "x_values": list(x_data),
                "y_values": list(y_data),
                "x_label": x_field,
                "y_label": y_field
            }
        
        elif chart_type == "pie":
            # For pie charts, we need categorical data
            if df[x_field].dtype == 'object' or df[x_field].dtype.name == 'category':
                value_counts = df[x_field].value_counts()
                return {
                    "chart_type": chart_type,
                    "labels": value_counts.index.tolist(),
                    "values": value_counts.values.tolist(),
                    "title": f"Distribution of {x_field}"
                }
            else:
                return {"error": f"Field '{x_field}' is not categorical, cannot create pie chart"}
        
        elif chart_type == "histogram":
            # For histograms, we need numeric data
            values = pd.to_numeric(df[x_field], errors='coerce').dropna()
            if values.empty:
                return {"error": f"Field '{x_field}' has no numeric data for histogram"}
            
            # Create bins for histogram
            bins = np.histogram(values, bins=20)
            
            return {
                "chart_type": chart_type,
                "bins": bins[1].tolist(),  # bin edges
                "values": bins[0].tolist(),  # bin counts
                "x_label": x_field,
                "title": f"Distribution of {x_field}"
            }
        
        else:
            return {"error": f"Unsupported chart type: {chart_type}"}
    
    def generate_time_series_data(self, dataset_id: int, time_field: str, value_field: str) -> Dict[str, Any]:
        """Generate time series data for visualization"""
        records = self.db_session.query(DataRecord).filter(
            DataRecord.dataset_id == dataset_id
        ).all()
        
        if not records:
            return {"error": "No records found for this dataset"}
        
        # Convert records to DataFrame
        df = pd.DataFrame([record.data for record in records])
        
        if time_field not in df.columns or value_field not in df.columns:
            return {"error": f"Required fields not found: {time_field}, {value_field}"}
        
        # Convert time field to datetime
        df[time_field] = pd.to_datetime(df[time_field])
        
        # Convert value field to numeric
        df[value_field] = pd.to_numeric(df[value_field], errors='coerce')
        
        # Remove nulls and sort
        df = df.dropna(subset=[time_field, value_field]).sort_values(by=time_field)
        
        return {
            "x_values": [ts.isoformat() for ts in df[time_field]],
            "y_values": df[value_field].tolist(),
            "x_label": time_field,
            "y_label": value_field,
            "title": f"Time Series: {value_field} over {time_field}"
        }