from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

Base = declarative_base()

class DataSource(Base):
    __tablename__ = 'data_sources'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    source_type = Column(String(100), nullable=False)  # API, FILE, DATABASE, STREAM, etc.
    connection_info = Column(JSON)  # Connection parameters
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    datasets = relationship("Dataset", back_populates="source")

class Dataset(Base):
    __tablename__ = 'datasets'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    source_id = Column(Integer, ForeignKey('data_sources.id'))
    schema_info = Column(JSON)  # Schema of the dataset
    record_count = Column(Integer, default=0)
    size_bytes = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    source = relationship("DataSource", back_populates="datasets")
    data_records = relationship("DataRecord", back_populates="dataset")

class DataRecord(Base):
    __tablename__ = 'data_records'
    
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    data = Column(JSON)  # Store the actual data record
    metadata = Column(JSON)  # Additional metadata about the record
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    dataset = relationship("Dataset", back_populates="data_records")

class DataIngestionLog(Base):
    __tablename__ = 'data_ingestion_logs'
    
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    source_id = Column(Integer, ForeignKey('data_sources.id'))
    records_processed = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    status = Column(String(50), default='RUNNING')  # RUNNING, COMPLETED, FAILED
    error_message = Column(Text)
    
    dataset = relationship("Dataset")
    source = relationship("DataSource")

class AIModel(Base):
    __tablename__ = 'ai_models'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    provider = Column(String(100), nullable=False)  # OpenAI, Groq, etc.
    model_type = Column(String(100))  # chat, completion, embedding, etc.
    api_key = Column(String(500))  # Encrypted API key
    is_active = Column(Boolean, default=True)
    config = Column(JSON)  # Model configuration
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DataAnalysis(Base):
    __tablename__ = 'data_analyses'
    
    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    analysis_type = Column(String(100))  # trend, correlation, summary, etc.
    parameters = Column(JSON)  # Analysis parameters
    results = Column(JSON)  # Analysis results
    created_at = Column(DateTime, default=datetime.utcnow)
    
    dataset = relationship("Dataset")

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DataQuery(Base):
    __tablename__ = 'data_queries'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    query_text = Column(Text, nullable=False)
    dataset_id = Column(Integer, ForeignKey('datasets.id'))
    results = Column(JSON)  # Query results
    execution_time = Column(Float)  # Execution time in seconds
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
    dataset = relationship("Dataset")

# Create engine and session
def get_db_session(database_url="sqlite:///data_hub.db"):
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()