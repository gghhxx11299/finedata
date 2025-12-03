import requests
import json
import time
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from sqlalchemy.orm import Session
from .models import DataSource, Dataset, DataRecord, DataIngestionLog, get_db_session
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

class DataIngestor:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        
    def register_data_source(self, name: str, source_type: str, description: str = "", connection_info: dict = None) -> DataSource:
        """Register a new data source in the system"""
        data_source = DataSource(
            name=name,
            description=description,
            source_type=source_type,
            connection_info=connection_info or {}
        )
        self.db_session.add(data_source)
        self.db_session.commit()
        return data_source
    
    def create_dataset(self, name: str, source_id: int, description: str = "", schema_info: dict = None) -> Dataset:
        """Create a new dataset linked to a data source"""
        dataset = Dataset(
            name=name,
            description=description,
            source_id=source_id,
            schema_info=schema_info or {}
        )
        self.db_session.add(dataset)
        self.db_session.commit()
        return dataset
    
    def ingest_from_api(self, source_id: int, dataset_id: int, endpoint: str, 
                        headers: dict = None, params: dict = None, 
                        data_field: str = None) -> DataIngestionLog:
        """Ingest data from an API endpoint"""
        source = self.db_session.query(DataSource).filter(DataSource.id == source_id).first()
        dataset = self.db_session.query(Dataset).filter(Dataset.id == dataset_id).first()
        
        if not source or not dataset:
            raise ValueError("Source or dataset not found")
        
        log = DataIngestionLog(
            dataset_id=dataset_id,
            source_id=source_id,
            status="RUNNING"
        )
        self.db_session.add(log)
        self.db_session.commit()
        
        try:
            start_time = time.time()
            records_processed = 0
            records_failed = 0
            
            response = requests.get(endpoint, headers=headers, params=params, timeout=60)
            if response.status_code != 200:
                raise Exception(f"API request failed with status {response.status_code}")
            
            data = response.json()
            
            # Handle nested data if data_field is specified
            if data_field:
                records = data.get(data_field, data)
            else:
                records = data if isinstance(data, list) else [data]
            
            for record in records:
                if isinstance(record, dict):
                    try:
                        data_record = DataRecord(
                            dataset_id=dataset_id,
                            data=record,
                            metadata={"source_id": source_id, "ingested_at": datetime.utcnow().isoformat()}
                        )
                        self.db_session.add(data_record)
                        records_processed += 1
                    except Exception as e:
                        logger.error(f"Failed to process record: {e}")
                        records_failed += 1
                else:
                    records_failed += 1
            
            self.db_session.commit()
            
            # Update dataset record count
            dataset.record_count = self.db_session.query(DataRecord).filter(
                DataRecord.dataset_id == dataset_id
            ).count()
            self.db_session.commit()
            
            log.records_processed = records_processed
            log.records_failed = records_failed
            log.end_time = datetime.utcnow()
            log.status = "COMPLETED"
            
        except Exception as e:
            log.error_message = str(e)
            log.status = "FAILED"
            logger.error(f"Data ingestion failed: {e}")
        
        finally:
            self.db_session.commit()
            return log
    
    def ingest_from_file(self, source_id: int, dataset_id: int, file_path: str, 
                         file_format: str = "json") -> DataIngestionLog:
        """Ingest data from a local file"""
        source = self.db_session.query(DataSource).filter(DataSource.id == source_id).first()
        dataset = self.db_session.query(Dataset).filter(Dataset.id == dataset_id).first()
        
        if not source or not dataset:
            raise ValueError("Source or dataset not found")
        
        log = DataIngestionLog(
            dataset_id=dataset_id,
            source_id=source_id,
            status="RUNNING"
        )
        self.db_session.add(log)
        self.db_session.commit()
        
        try:
            records_processed = 0
            records_failed = 0
            
            if file_format.lower() == "json":
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    records = data if isinstance(data, list) else [data]
            elif file_format.lower() == "csv":
                df = pd.read_csv(file_path)
                records = df.to_dict('records')
            else:
                raise ValueError(f"Unsupported file format: {file_format}")
            
            for record in records:
                if isinstance(record, dict):
                    try:
                        data_record = DataRecord(
                            dataset_id=dataset_id,
                            data=record,
                            metadata={"source_id": source_id, "ingested_at": datetime.utcnow().isoformat()}
                        )
                        self.db_session.add(data_record)
                        records_processed += 1
                    except Exception as e:
                        logger.error(f"Failed to process record: {e}")
                        records_failed += 1
                else:
                    records_failed += 1
            
            self.db_session.commit()
            
            # Update dataset record count
            dataset.record_count = self.db_session.query(DataRecord).filter(
                DataRecord.dataset_id == dataset_id
            ).count()
            self.db_session.commit()
            
            log.records_processed = records_processed
            log.records_failed = records_failed
            log.end_time = datetime.utcnow()
            log.status = "COMPLETED"
            
        except Exception as e:
            log.error_message = str(e)
            log.status = "FAILED"
            logger.error(f"File ingestion failed: {e}")
        
        finally:
            self.db_session.commit()
            return log
    
    def get_available_datasets(self) -> List[Dict]:
        """Get list of all available datasets"""
        datasets = self.db_session.query(Dataset).all()
        return [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "record_count": d.record_count,
                "last_updated": d.last_updated.isoformat() if d.last_updated else None
            }
            for d in datasets
        ]

class DataProcessor:
    """Handles data processing and transformation"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def clean_data(self, dataset_id: int, cleaning_rules: Dict[str, Callable]) -> int:
        """Apply cleaning rules to a dataset"""
        records = self.db_session.query(DataRecord).filter(
            DataRecord.dataset_id == dataset_id
        ).all()
        
        cleaned_count = 0
        for record in records:
            original_data = record.data.copy()
            
            for field, rule in cleaning_rules.items():
                if field in record.data:
                    try:
                        record.data[field] = rule(record.data[field])
                    except Exception as e:
                        logger.warning(f"Cleaning rule failed for field {field}: {e}")
            
            # Update the record only if there were changes
            if record.data != original_data:
                record.updated_at = datetime.utcnow()
                cleaned_count += 1
        
        self.db_session.commit()
        return cleaned_count
    
    def transform_data(self, dataset_id: int, transformation_func: Callable) -> int:
        """Apply transformation function to all records in a dataset"""
        records = self.db_session.query(DataRecord).filter(
            DataRecord.dataset_id == dataset_id
        ).all()
        
        transformed_count = 0
        for record in records:
            original_data = record.data.copy()
            try:
                record.data = transformation_func(record.data)
                
                # Update the record only if there were changes
                if record.data != original_data:
                    record.updated_at = datetime.utcnow()
                    transformed_count += 1
            except Exception as e:
                logger.error(f"Transformation failed: {e}")
        
        self.db_session.commit()
        return transformed_count