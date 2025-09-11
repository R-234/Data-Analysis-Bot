import os
import requests
import pandas as pd
import threading
import time
from dotenv import load_dotenv
import numpy as np

# Load environment variables
load_dotenv()
GOOGLE_SHEETS_API_KEY = os.getenv('GOOGLE_SHEETS_API_KEY', 'c5bfab5ca306d208dd4ff70a8f6e8c6e576596df')
SHEET_ID = os.getenv('SHEET_ID', '1ovGPQzFgiWsxR_T3oFyYw-pkyyUXq9tOX4I4rGC_F5g')
RANGE_NAME = 'Sheet1!A1:AA'  # For 27 columns
DATA_API_URL = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{RANGE_NAME}?key={GOOGLE_SHEETS_API_KEY}'

# Global DataFrame and last update time
data_df = pd.DataFrame()
last_update_time = 0
data_columns = []

def fetch_data():
    global data_df, last_update_time, data_columns
    try:
        print(f"Fetching data from {DATA_API_URL}")
        response = requests.get(DATA_API_URL)
        response.raise_for_status()
        data = response.json().get('values', [])
        
        if not data or len(data) < 2:
            raise ValueError("No data or invalid response from Google Sheets.")
            
        headers = data[0]
        data_rows = data[1:]
        
        # Store column names for dynamic filtering
        data_columns = headers
        
        # Create DataFrame with dynamic columns
        data_df = pd.DataFrame(data_rows, columns=headers)
        
        # Try to set index to first column if it exists
        if len(headers) > 0:
            data_df.set_index(headers[0], inplace=True, drop=False)
        
        # Auto-detect numeric columns for type conversion
        for col in data_df.columns:
            if any(keyword in col.lower() for keyword in ['qty', 'quantity', 'amount', 'value', 'number', 'rate', 'ratio', 'score', 'mark']):
                data_df[col] = pd.to_numeric(data_df[col], errors='coerce')
            elif 'date' in col.lower():
                data_df[col] = pd.to_datetime(data_df[col], errors='coerce')
                
        last_update_time = time.time()
        print(f"Loaded {len(data_rows)} rows with {len(headers)} columns from Google Sheets")
        return True
        
    except Exception as e:
        print(f"Error fetching from Google Sheets: {e}. Loading sample data.")
        create_sample_data()
        return False

def create_sample_data():
    global data_df, data_columns
    # Create sample data with 50 rows and 10 columns
    np.random.seed(42)  # For reproducible results
    
    # Generate sample data
    sample_data = {
        'ID': [f"ID_{i:03d}" for i in range(1, 51)],
        'Category': np.random.choice(['A', 'B', 'C', 'D', 'E'], 50),
        'Type': np.random.choice(['X', 'Y', 'Z'], 50),
        'Value1': np.random.randint(10, 100, 50),
        'Value2': np.random.randint(5, 50, 50),
        'Value3': np.random.normal(50, 15, 50).round(2),
        'Status': np.random.choice(['Active', 'Inactive', 'Pending'], 50),
        'Score': np.random.uniform(0, 100, 50).round(2),
        'Date': pd.date_range('2023-01-01', periods=50, freq='D'),
        'Location': np.random.choice(['North', 'South', 'East', 'West'], 50)
    }
    
    data_df = pd.DataFrame(sample_data)
    data_df.set_index('ID', inplace=True)
    data_columns = data_df.columns.tolist()
    print("Loaded sample data with 50 rows and 10 columns")

def start_polling(interval=30):
    def poll():
        while True:
            fetch_data()
            time.sleep(interval)
    thread = threading.Thread(target=poll, daemon=True)
    thread.start()

# Initial fetch
fetch_data()