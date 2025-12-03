#!/usr/bin/env python3
"""
Real-World AI Data Hub
A comprehensive platform for collecting, processing, analyzing, and visualizing real-world data.
"""

import os
import sys
from data_hub.main import RealWorldAIHub

def main():
    print("🤖 Starting Real-World AI Data Hub...")
    
    # Create the hub instance
    hub = RealWorldAIHub()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "demo":
            # Run the demo workflow
            hub.demo_workflow()
        elif sys.argv[1] == "api":
            # Start the API server
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
            print(f"🚀 Starting API server on port {port}...")
            hub.start_api_server(host='0.0.0.0', port=port)
        else:
            print("Usage:")
            print("  python run_hub.py demo          # Run the demo workflow")
            print("  python run_hub.py api [port]    # Start the API server (default port 5000)")
    else:
        print("Usage:")
        print("  python run_hub.py demo          # Run the demo workflow")
        print("  python run_hub.py api [port]    # Start the API server (default port 5000)")
        print("\nStarting demo workflow by default...")
        hub.demo_workflow()

if __name__ == "__main__":
    main()