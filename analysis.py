import os
import google.generativeai as genai
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
import streamlit as st
import numpy as np

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyA1suRYe9DTXdnJ1BGtrdpk8LnishTRtgk')

# Configure Gemini with correct model name
try:
    genai.configure(api_key=GEMINI_API_KEY)
    # Try the correct model name for Gemini Pro
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    st.error(f"Gemini API configuration error: {e}")
    model = None

def clean_code_snippet(text):
    """Extract Python code from LLM response"""
    # Look for code blocks
    code_match = re.search(r'```python(.*?)```', text, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    
    # Look for code without markers
    lines = text.split('\n')
    code_lines = []
    in_code = False
    
    for line in lines:
        if any(keyword in line for keyword in ['import ', 'def ', '= px.', 'fig = ', 'result_df =']):
            in_code = True
        if in_code and not line.strip().startswith('#'):
            code_lines.append(line)
    
    if code_lines:
        return '\n'.join(code_lines).strip()
    
    return None

def interpret_prompt_with_llm(prompt, df):
    """Use Gemini to interpret natural language prompts"""
    if model is None:
        raise Exception("Gemini model not available. Using fallback.")
    
    try:
        # Get data structure information
        columns = list(df.columns)
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        sample_data = df.head(3).to_dict()
        
        # Create a more specific prompt for the LLM
        system_prompt = f"""
        You are a data analysis assistant. The user will ask questions about a dataset.
        
        DATASET INFORMATION:
        - Columns: {columns}
        - Data types: {dtypes}
        - Sample data: {sample_data}
        
        Your task is to generate Python code that:
        1. Filters or processes the DataFrame (named 'df')
        2. Creates appropriate visualizations using Plotly Express (px)
        3. Returns three variables: result_df, fig, and viz_type
        
        IMPORTANT RULES:
        - Always return the filtered/processed DataFrame as 'result_df'
        - Create a visualization figure as 'fig'
        - Specify the chart type as 'viz_type' (e.g., 'bar', 'pie', 'histogram')
        - The code must work with the actual dataset structure
        - Handle potential errors gracefully
        - Focus on the most relevant columns for the query
        - If the prompt mentions a chart type, use that type
        
        EXAMPLE FOR "Show sales by category as pie chart":
        result_df = df.groupby('Category')['Sales'].sum().reset_index()
        fig = px.pie(result_df, values='Sales', names='Category', title='Sales by Category')
        viz_type = 'pie'
        
        EXAMPLE FOR "Distribution of values":
        fig = px.histogram(df, x='Value', title='Value Distribution')
        result_df = df[['Value']]
        viz_type = 'histogram'
        
        EXAMPLE FOR "Top 5 categories by Value1 as bar chart":
        top_categories = df.groupby('Category')['Value1'].sum().nlargest(5).reset_index()
        result_df = top_categories
        fig = px.bar(top_categories, x='Category', y='Value1', title='Top 5 Categories by Value1')
        viz_type = 'bar'
        
        Respond with ONLY the Python code, no explanations.
        """
        
        response = model.generate_content(system_prompt + "\n\nUser query: " + prompt)
        code_snippet = clean_code_snippet(response.text)
        
        if not code_snippet:
            raise ValueError("No valid code generated")
            
        return code_snippet
        
    except Exception as e:
        st.error(f"Gemini API error: {e}. Using fallback logic.")
        return generate_fallback_code(prompt, df)

def generate_fallback_code(prompt, df):
    """Generate code when Gemini fails - improved version with better parsing"""
    prompt_lower = prompt.lower()
    
    # Extract potential numbers from prompt (for top N queries)
    numbers = re.findall(r'\d+', prompt_lower)
    n = int(numbers[0]) if numbers else 5  # Default to top 5
    
    # Find likely columns for analysis
    value_columns = [col for col in df.columns if any(kw in col.lower() for kw in 
                    ['value', 'amount', 'qty', 'quantity', 'number', 'count', 'total', 'sum', 'score', 'mark'])]
    category_columns = [col for col in df.columns if any(kw in col.lower() for kw in 
                       ['category', 'type', 'status', 'name', 'group', 'class', 'city', 'location'])]
    date_columns = [col for col in df.columns if any(kw in col.lower() for kw in 
                   ['date', 'time', 'day', 'month', 'year'])]
    
    # Try to extract specific column names from prompt
    mentioned_columns = []
    for col in df.columns:
        if col.lower() in prompt_lower:
            mentioned_columns.append(col)
    
    # Determine value column (priority: mentioned, then detected, then default)
    if mentioned_columns and df[mentioned_columns[0]].dtype in [np.number, 'int64', 'float64']:
        value_col = mentioned_columns[0]
    elif value_columns:
        value_col = value_columns[0]
    else:
        # Find first numeric column
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        value_col = numeric_cols[0] if len(numeric_cols) > 0 else df.columns[0]
    
    # Determine category column (priority: mentioned, then detected, then default)
    if mentioned_columns and len(mentioned_columns) > 1 and df[mentioned_columns[1]].dtype in ['object', 'category']:
        category_col = mentioned_columns[1]
    elif mentioned_columns and df[mentioned_columns[0]].dtype in ['object', 'category']:
        category_col = mentioned_columns[0]
    elif category_columns:
        category_col = category_columns[0]
    else:
        # Find first categorical column
        cat_cols = df.select_dtypes(include=['object', 'category']).columns
        category_col = cat_cols[0] if len(cat_cols) > 0 else df.columns[0]
    
    # Handle specific prompt patterns with better logic
    if 'top' in prompt_lower:
        # Top N query
        code = f"""
top_data = df.groupby('{category_col}')['{value_col}'].sum().nlargest({n}).reset_index()
result_df = top_data
fig = px.bar(top_data, x='{category_col}', y='{value_col}', title='Top {n} {category_col} by {value_col}')
viz_type = 'bar'
"""
    elif 'distribution' in prompt_lower or 'histogram' in prompt_lower:
        # Distribution query
        code = f"""
fig = px.histogram(df, x='{value_col}', title='Distribution of {value_col}')
result_df = df[['{value_col}']]
viz_type = 'histogram'
"""
    elif 'pie' in prompt_lower or 'percent' in prompt_lower:
        # Pie chart query
        code = f"""
result_df = df.groupby('{category_col}')['{value_col}'].sum().reset_index()
fig = px.pie(result_df, values='{value_col}', names='{category_col}', title='{value_col} by {category_col}')
viz_type = 'pie'
"""
    elif 'compare' in prompt_lower or 'correlation' in prompt_lower or 'scatter' in prompt_lower:
        # Comparison query - find a second value column
        second_value_cols = [col for col in value_columns if col != value_col]
        second_value_col = second_value_cols[0] if second_value_cols else value_col
        
        code = f"""
result_df = df[['{category_col}', '{value_col}', '{second_value_col}']]
fig = px.scatter(df, x='{value_col}', y='{second_value_col}', color='{category_col}', 
                 title='{value_col} vs {second_value_col} by {category_col}')
viz_type = 'scatter'
"""
    elif 'trend' in prompt_lower and date_columns:
        # Time trend query
        date_col = date_columns[0]
        code = f"""
df['{date_col}'] = pd.to_datetime(df['{date_col}'])
trend_data = df.groupby(pd.Grouper(key='{date_col}', freq='D'))['{value_col}'].sum().reset_index()
result_df = trend_data
fig = px.line(trend_data, x='{date_col}', y='{value_col}', title='{value_col} Trend Over Time')
viz_type = 'line'
"""
    else:
        # Default to summary by category
        code = f"""
result_df = df.groupby('{category_col}')['{value_col}'].agg(['sum', 'mean', 'count']).reset_index()
result_df.columns = ['{category_col}', 'Total_{value_col}', 'Average_{value_col}', 'Count']
fig = px.bar(result_df, x='{category_col}', y='Total_{value_col}', title='{value_col} by {category_col}')
viz_type = 'bar'
"""
    
    return code

def analyze_data(prompt, df):
    """Main function to analyze data based on prompt"""
    if df.empty:
        return pd.DataFrame(), None, "No data available"
    
    try:
        # Get code from LLM or fallback
        code = interpret_prompt_with_llm(prompt, df)
        
        # Create a safe execution environment
        local_vars = {'df': df, 'px': px, 'pd': pd, 'np': np}
        
        # Execute the code
        exec(code, {}, local_vars)
        
        # Extract results
        result_df = local_vars.get('result_df', pd.DataFrame())
        fig = local_vars.get('fig', None)
        viz_type = local_vars.get('viz_type', 'none')
        
        # Validate results
        if result_df.empty:
            return pd.DataFrame(), None, "No results generated from the query"
            
        return result_df, fig, viz_type
        
    except Exception as e:
        error_msg = f"Error processing prompt: {str(e)}"
        st.error(error_msg)
        return pd.DataFrame(), None, error_msg
