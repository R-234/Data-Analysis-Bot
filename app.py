import streamlit as st
import time
import plotly.express as px
import pandas as pd
from data_fetch import data_df, start_polling, fetch_data, last_update_time, data_columns
from analysis import analyze_data
from filters import apply_multi_column_filters, excel_like_table, show_column_insights
import base64
from io import BytesIO
import plotly.io as pio
import tempfile
import os

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
    </style>
""", unsafe_allow_html=True)

# Function to convert fig to image for download
def fig_to_image(fig, format='png'):
    """Convert plotly figure to image bytes"""
    if format == 'png':
        return pio.to_image(fig, format='png')
    elif format == 'jpeg':
        return pio.to_image(fig, format='jpeg')
    elif format == 'svg':
        return pio.to_image(fig, format='svg')
    return None

# Function to convert fig to PDF
def fig_to_pdf(fig):
    """Convert plotly figure to PDF bytes"""
    img_bytes = pio.to_image(fig, format='pdf')
    return img_bytes

# Initialize session state
if 'last_update' not in st.session_state:
    st.session_state.last_update = last_update_time
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

# Start real-time polling for default data
start_polling()

if last_update_time != st.session_state.last_update:
    st.session_state.last_update = last_update_time
    st.rerun()

# App header
st.title("🤖 Data Analysis Bot")
st.caption("Powerful data analysis with natural language queries")

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

# Manual refresh button for default data
if data_source_info == "Default Data":
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh Data", help="Fetch the latest data from the source"):
            fetch_data()
            st.rerun()

# Prompt examples
with st.expander("💡 Prompt Examples", expanded=True):
    st.markdown("""
    <div class="prompt-examples">
    <h4>Try these prompts:</h4>
    <ul>
    <li>"Show distribution of Value1 as histogram"</li>
    <li>"Display Value2 by Category as pie chart"</li>
    <li>"Compare Value1 and Value2 as bar chart"</li>
    <li>"Filter Status to Active and show Value1 distribution"</li>
    <li>"Top 5 categories by Value1 as bar chart"</li>
    <li>"Show me trends over time" (if you have date columns)</li>
    <li>"What are the summary statistics for numeric columns?"</li>
    </ul>
    
    <h4>Advanced prompts:</h4>
    <ul>
    <li>"Show correlation between all numeric variables"</li>
    <li>"Create a scatter plot of Value1 vs Value2 colored by Category"</li>
    <li>"Display the top 10 values by Value1 as a bar chart"</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

# Multi-column filters
st.sidebar.markdown('<div class="section-header">Filter Options</div>', unsafe_allow_html=True)
filtered_df = apply_multi_column_filters(current_df)

# Show column insights in sidebar
show_column_insights(current_df)

# Manual Filter Visualization Section
st.sidebar.markdown('<div class="section-header">Manual Visualization</div>', unsafe_allow_html=True)

if not filtered_df.empty:
    # Let user select chart type and columns for manual visualization
    chart_type = st.sidebar.selectbox(
        "Chart Type",
        ["Bar Chart", "Pie Chart", "Histogram", "Line Chart", "Scatter Plot"],
        key="manual_chart_type"
    )
    
    # Get column lists
    numeric_cols = filtered_df.select_dtypes(include=['number']).columns.tolist()
    categorical_cols = filtered_df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    if chart_type in ["Bar Chart", "Pie Chart"]:
        if categorical_cols and numeric_cols:
            x_col = st.sidebar.selectbox("Category Column", categorical_cols, key="manual_x_col")
            y_col = st.sidebar.selectbox("Value Column", numeric_cols, key="manual_y_col")
            
            if st.sidebar.button("Generate Chart", key="manual_generate"):
                with st.spinner("Creating visualization..."):
                    if chart_type == "Bar Chart":
                        fig = px.bar(
                            filtered_df.groupby(x_col)[y_col].sum().reset_index(), 
                            x=x_col, y=y_col, 
                            title=f"{y_col} by {x_col}"
                        )
                    else:  # Pie Chart
                        fig = px.pie(
                            filtered_df.groupby(x_col)[y_col].sum().reset_index(), 
                            values=y_col, names=x_col, 
                            title=f"{y_col} by {x_col}"
                        )
                    
                    st.session_state.manual_fig = fig
                    st.session_state.manual_viz_type = chart_type.lower().replace(" ", "_")
        
    elif chart_type == "Histogram" and numeric_cols:
        col = st.sidebar.selectbox("Select Column", numeric_cols, key="manual_hist_col")
        
        if st.sidebar.button("Generate Chart", key="manual_hist_generate"):
            with st.spinner("Creating histogram..."):
                fig = px.histogram(filtered_df, x=col, title=f"Distribution of {col}")
                st.session_state.manual_fig = fig
                st.session_state.manual_viz_type = "histogram"
    
    elif chart_type == "Scatter Plot" and len(numeric_cols) >= 2:
        x_col = st.sidebar.selectbox("X Axis", numeric_cols, key="manual_scatter_x")
        y_col = st.sidebar.selectbox("Y Axis", numeric_cols, key="manual_scatter_y")
        color_col = st.sidebar.selectbox("Color By", [None] + categorical_cols, key="manual_scatter_color")
        
        if st.sidebar.button("Generate Chart", key="manual_scatter_generate"):
            with st.spinner("Creating scatter plot..."):
                fig = px.scatter(
                    filtered_df, x=x_col, y=y_col, color=color_col,
                    title=f"{y_col} vs {x_col}" + (f" by {color_col}" if color_col else "")
                )
                st.session_state.manual_fig = fig
                st.session_state.manual_viz_type = "scatter"

# Display manual visualization if available
if 'manual_fig' in st.session_state:
    st.markdown('<div class="section-header">Manual Visualization</div>', unsafe_allow_html=True)
    st.plotly_chart(st.session_state.manual_fig, use_container_width=True)
    
    # Add download buttons for the manual chart
    st.markdown("**Download Chart:**")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        png_img = fig_to_image(st.session_state.manual_fig, 'png')
        st.download_button(
            label="📥 PNG",
            data=png_img,
            file_name="manual_chart.png",
            mime="image/png",
        )
    with col2:
        jpg_img = fig_to_image(st.session_state.manual_fig, 'jpeg')
        st.download_button(
            label="📥 JPEG",
            data=jpg_img,
            file_name="manual_chart.jpg",
            mime="image/jpeg",
        )
    with col3:
        svg_img = fig_to_image(st.session_state.manual_fig, 'svg')
        st.download_button(
            label="📥 SVG",
            data=svg_img,
            file_name="manual_chart.svg",
            mime="image/svg+xml",
        )
    with col4:
        pdf_img = fig_to_pdf(st.session_state.manual_fig)
        st.download_button(
            label="📥 PDF",
            data=pdf_img,
            file_name="manual_chart.pdf",
            mime="application/pdf",
        )

# Prompt input section
st.markdown('<div class="section-header">Natural Language Analysis</div>', unsafe_allow_html=True)

with st.form(key="prompt_form"):
    prompt = st.text_area(
        "Enter your analysis prompt:", 
        placeholder="Example: Show me the distribution of Value1 by Category as a pie chart", 
        key="analysis_prompt",
        height=100
    )
    
    # Add chart type preference
    col1, col2 = st.columns(2)
    with col1:
        chart_type = st.selectbox(
            "Preferred Chart Type",
            ["Auto-detect", "Bar Chart", "Pie Chart", "Histogram", "Line Chart", "Scatter Plot"],
            help="Specify your preferred visualization type"
        )
    with col2:
        agg_method = st.selectbox(
            "Aggregation Method",
            ["Auto", "Sum", "Mean", "Count", "Min", "Max"],
            help="How to aggregate numeric values"
        )
    
    col1, col2 = st.columns([1, 3])
    with col1:
        submit_button = st.form_submit_button(label="Analyze 🚀")
    with col2:
        if st.session_state.last_results and st.form_submit_button("🔄 Rerun Last Analysis"):
            prompt = st.session_state.last_prompt

# Process prompt
if submit_button and prompt:
    st.session_state.last_prompt = prompt
    with st.spinner("Analyzing your data... This may take a few moments"):
        # Add chart type hint to prompt if specified
        enhanced_prompt = prompt
        if chart_type != "Auto-detect":
            enhanced_prompt = f"{prompt} as {chart_type.lower().replace(' chart', '')}"
        if agg_method != "Auto":
            enhanced_prompt = f"{enhanced_prompt} using {agg_method.lower()} aggregation"
            
        result_df, fig, viz_type = analyze_data(enhanced_prompt, filtered_df)
        st.session_state.last_results = (result_df, fig, viz_type)
        
    if not result_df.empty:
        st.success("✅ Analysis complete!")
        
        # Show results
        st.markdown('<div class="section-header">Analysis Results</div>', unsafe_allow_html=True)
        
        # Display statistics about the results
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Result Rows", len(result_df))
        with col2:
            st.metric("Result Columns", len(result_df.columns))
        with col3:
            st.metric("Visualization", viz_type.capitalize() if fig else "None")
        
        st.dataframe(result_df, use_container_width=True)
        
        # Show visualization
        if fig:
            st.markdown('<div class="section-header">Visualization</div>', unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True)
            
            # Add download buttons for the chart
            st.markdown("**Download Chart:**")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                png_img = fig_to_image(fig, 'png')
                st.download_button(
                    label="📥 PNG",
                    data=png_img,
                    file_name="chart.png",
                    mime="image/png",
                )
            with col2:
                jpg_img = fig_to_image(fig, 'jpeg')
                st.download_button(
                    label="📥 JPEG",
                    data=jpg_img,
                    file_name="chart.jpg",
                    mime="image/jpeg",
                )
            with col3:
                svg_img = fig_to_image(fig, 'svg')
                st.download_button(
                    label="📥 SVG",
                    data=svg_img,
                    file_name="chart.svg",
                    mime="image/svg+xml",
                )
            with col4:
                pdf_img = fig_to_pdf(fig)
                st.download_button(
                    label="📥 PDF",
                    data=pdf_img,
                    file_name="chart.pdf",
                    mime="application/pdf",
                )
        else:
            st.info("No visualization was generated for this query")
            
    else:
        st.error(f"❌ Could not process your query: {viz_type}")
        st.info("💡 Try being more specific about what you want to analyze or check your data structure")

# Interactive data explorer
st.markdown('<div class="section-header">Data Explorer</div>', unsafe_allow_html=True)

if not current_df.empty:
    excel_like_table(filtered_df)
    
    # Add data summary
    with st.expander("📈 Data Summary Statistics"):
        if not filtered_df.empty:
            # Show numeric columns summary
            numeric_cols = filtered_df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                st.write("**Numeric Columns Summary:**")
                st.dataframe(filtered_df[numeric_cols].describe(), use_container_width=True)
            
            # Show categorical columns summary
            cat_cols = filtered_df.select_dtypes(include=['object', 'category']).columns
            if len(cat_cols) > 0:
                st.write("**Categorical Columns Summary:**")
                for col in cat_cols:
                    st.write(f"**{col}**: {filtered_df[col].nunique()} unique values")
                    if filtered_df[col].nunique() <= 10:
                        st.write(filtered_df[col].value_counts())
else:
    st.warning("No data available. Please check your data connection.")

# Status footer
st.markdown("---")
st.info(f"🕒 Data last updated: {time.ctime(last_update_time)} (Auto-updates every 30s)")

# Add a feedback section
with st.expander("💬 Provide Feedback"):
    feedback = st.text_area("How can we improve this tool?")
    if st.button("Submit Feedback"):
        st.success("Thank you for your feedback!")

st.markdown('<div class="footer">This bot developed by "Rakesh Rathod"</div>', unsafe_allow_html=True)