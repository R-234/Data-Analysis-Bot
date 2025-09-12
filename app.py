import streamlit as st
import time
import pandas as pd
import numpy as np
from io import BytesIO
import base64
import os

# Try to import plotly with fallback
try:
    import plotly.express as px
    import plotly.graph_objects as go
    import plotly.io as pio
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.error("Plotly is not installed. Please install it using: pip install plotly")

# Try to import other dependencies with fallbacks
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    st.warning("python-dotenv not installed. Environment variables may not load properly.")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    st.warning("Google Generative AI not installed. Some features may be limited.")

# Import local modules with error handling
try:
    from data_fetch import data_df, start_polling, fetch_data, last_update_time, data_columns
    from filters import apply_multi_column_filters, excel_like_table, show_column_insights
    from analysis import analyze_data
except ImportError as e:
    st.error(f"Error importing local modules: {e}")
    # Create fallback functions
    data_df = pd.DataFrame()
    def start_polling(): pass
    def fetch_data(): pass
    last_update_time = 0
    data_columns = []
    
    def apply_multi_column_filters(df): return df
    def excel_like_table(df): st.dataframe(df)
    def show_column_insights(df): pass
    def analyze_data(prompt, df): return pd.DataFrame(), None, "Analysis module not available"

# Professional CSS styling with dark theme
st.markdown("""
    <style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .stButton > button {
        background-color: #FF4B4B;
        color: white;
        border-radius: 5px;
        border: none;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #FF6B6B;
        color: white;
    }
    .stTextInput > div > div > div > input {
        background-color: #262730;
        color: white;
        border-radius: 5px;
        border: 1px solid #4B4B4B;
    }
    .sidebar .sidebar-content {
        background-color: #1E1E1E;
    }
    .reportview-container .main .block-container {
        background-color: #0E1117;
        border-radius: 10px;
        padding: 20px;
    }
    .footer {
        font-size: 12px;
        text-align: center;
        color: #AAA;
        margin-top: 30px;
    }
    .prompt-examples {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border-left: 4px solid #FF4B4B;
    }
    .data-info {
        background-color: #262730;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .section-header {
        color: #FF4B4B;
        border-bottom: 2px solid #FF4B4B;
        padding-bottom: 5px;
        margin-top: 20px;
    }
    .error-box {
        background-color: #FFE6E6;
        color: #D8000C;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .upload-box {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        border: 2px dashed #FF4B4B;
        margin-bottom: 15px;
    }
    .warning-box {
        background-color: #FFF3CD;
        color: #856404;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
        border-left: 4px solid #FFC107;
    }
    </style>
""", unsafe_allow_html=True)

# Function to convert fig to image for download (with fallback)
def fig_to_image(fig, format='png'):
    """Convert plotly figure to image bytes"""
    if not PLOTLY_AVAILABLE or fig is None:
        return None
    try:
        if format == 'png':
            return pio.to_image(fig, format='png')
        elif format == 'jpeg':
            return pio.to_image(fig, format='jpeg')
        elif format == 'svg':
            return pio.to_image(fig, format='svg')
    except Exception as e:
        st.error(f"Error converting figure: {e}")
    return None

def fig_to_pdf(fig):
    """Convert plotly figure to PDF bytes"""
    if not PLOTLY_AVAILABLE or fig is None:
        return None
    try:
        return pio.to_image(fig, format='pdf')
    except Exception as e:
        st.error(f"Error converting to PDF: {e}")
        return None

# Initialize session state
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()
if 'last_prompt' not in st.session_state:
    st.session_state.last_prompt = ""
if 'last_results' not in st.session_state:
    st.session_state.last_results = None
if 'api_status' not in st.session_state:
    st.session_state.api_status = "Checking..."
if 'uploaded_data' not in st.session_state:
    st.session_state.uploaded_data = None
if 'current_data_source' not in st.session_state:
    st.session_state.current_data_source = "default"
if 'manual_fig' not in st.session_state:
    st.session_state.manual_fig = None
if 'manual_viz_type' not in st.session_state:
    st.session_state.manual_viz_type = None

# Start real-time polling for default data
try:
    start_polling()
except Exception as e:
    st.error(f"Error starting polling: {e}")

# App header
st.title("🤖 Data Analysis Bot")
st.caption("Powerful data analysis with natural language queries")

# Show warnings for missing dependencies
if not PLOTLY_AVAILABLE:
    st.markdown('<div class="warning-box">⚠️ Plotly is not installed. Visualization features will be limited.</div>', unsafe_allow_html=True)

if not GEMINI_AVAILABLE:
    st.markdown('<div class="warning-box">⚠️ Google Generative AI is not installed. Advanced analysis features will use fallback methods.</div>', unsafe_allow_html=True)

# File upload section
st.sidebar.markdown('<div class="section-header">Data Source</div>', unsafe_allow_html=True)
data_source = st.sidebar.radio(
    "Choose data source:",
    ["Default Data", "Upload Your File"],
    help="Select where to get your data from"
)

if data_source == "Upload Your File":
    st.sidebar.markdown('<div class="upload-box">Upload your data file</div>', unsafe_allow_html=True)
    uploaded_file = st.sidebar.file_uploader(
        "Choose a file",
        type=['csv', 'xlsx', 'xls', 'xlsm'],
        help="Upload CSV or Excel files for analysis"
    )
    
    if uploaded_file is not None:
        try:
            # Read the uploaded file
            if uploaded_file.name.endswith('.csv'):
                df_uploaded = pd.read_csv(uploaded_file)
            else:
                df_uploaded = pd.read_excel(uploaded_file)
            
            # Store in session state
            st.session_state.uploaded_data = df_uploaded
            st.session_state.current_data_source = "uploaded"
            st.sidebar.success(f"Uploaded {uploaded_file.name} with {df_uploaded.shape[0]} rows and {df_uploaded.shape[1]} columns")
            
        except Exception as e:
            st.sidebar.error(f"Error reading file: {str(e)}")
            st.session_state.uploaded_data = None
            st.session_state.current_data_source = "default"
    
    # Add button to clear uploaded data
    if st.session_state.uploaded_data is not None:
        if st.sidebar.button("Clear Uploaded Data"):
            st.session_state.uploaded_data = None
            st.session_state.current_data_source = "default"
            st.rerun()

# Get current data based on source
if st.session_state.current_data_source == "uploaded" and st.session_state.uploaded_data is not None:
    current_df = st.session_state.uploaded_data.copy()
    data_source_info = "Uploaded File"
else:
    current_df = data_df.copy()
    data_source_info = "Default Data"

# Display data info
if not current_df.empty:
    st.markdown(f'<div class="data-info">📊 <b>Data Source:</b> {data_source_info} | <b>Shape:</b> {current_df.shape[0]} rows × {current_df.shape[1]} columns</div>', 
                unsafe_allow_html=True)
    
    # Show current columns
    with st.expander("📋 View Data Structure"):
        st.write("**Index:**", current_df.index.name if current_df.index.name else "Unnamed")
        st.write("**Columns:**", list(current_df.columns))
        
        # Show data types
        dtype_info = pd.DataFrame({
            'Column': current_df.columns,
            'Data Type': current_df.dtypes.values,
            'Non-Null Count': current_df.count().values,
            'Null Count': current_df.isnull().sum().values
        })
        st.dataframe(dtype_info, use_container_width=True)
else:
    st.warning("No data available. Please upload a file or check your data connection.")

# Manual refresh button for default data
if data_source_info == "Default Data":
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh Data", help="Fetch the latest data from the source"):
            try:
                fetch_data()
                st.rerun()
            except Exception as e:
                st.error(f"Error refreshing data: {e}")

# Continue with the rest of your app code...
# [The rest of your app code remains the same, but make sure to add try-catch blocks around critical operations]

# For example, when calling analyze_data:
try:
    result_df, fig, viz_type = analyze_data(enhanced_prompt, filtered_df)
except Exception as e:
    st.error(f"Error during analysis: {e}")
    result_df, fig, viz_type = pd.DataFrame(), None, "Analysis failed"

# Add similar error handling throughout your app
