# Set up the data hub directory structure
import os
from .main import RealWorldAIHub

# Create the data_hub package structure
os.makedirs(os.path.dirname(__file__), exist_ok=True)

# Export the main class for easy access
__all__ = ['RealWorldAIHub']