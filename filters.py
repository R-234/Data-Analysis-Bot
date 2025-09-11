import streamlit as st
import pandas as pd

def apply_multi_column_filters(df):
    """
    Apply dynamic multi-select filters based on current data structure
    
    Args:
        df (DataFrame): The dataframe to filter
        
    Returns:
        DataFrame: Filtered dataframe based on user selections
    """
    st.sidebar.header("🔍 Dynamic Filters")
    
    # Display data info
    if not df.empty:
        st.sidebar.info(f"Data: {df.shape[0]} rows, {df.shape[1]} columns")
    
    filters = {}
    
    if not df.empty:
        # Get all column names for filtering
        all_columns = df.columns.tolist()
        
        # Add index as a filterable column if it's named
        if df.index.name and df.index.name not in all_columns:
            all_columns.insert(0, df.index.name)
        
        # Create tabs for better organization if many columns
        if len(all_columns) > 5:
            tab1, tab2 = st.sidebar.tabs(["Main Filters", "Additional Filters"])
            tabs = [tab1, tab2]
        else:
            tabs = [st.sidebar]
        
        # Distribute columns across tabs
        for i, col in enumerate(all_columns):
            tab_idx = 0 if i < min(5, len(all_columns)) else 1
            
            try:
                if col == df.index.name:
                    # Handle index column
                    unique_vals = df.index.dropna().unique()
                else:
                    # Handle regular column
                    unique_vals = df[col].dropna().unique()
                
                # Skip columns with too many unique values (like IDs)
                if len(unique_vals) > 50:
                    continue
                
                # Limit to 20 values for performance
                display_vals = unique_vals[:20] if len(unique_vals) > 20 else unique_vals
                
                if len(display_vals) > 0:
                    with tabs[tab_idx]:
                        selected = st.multiselect(
                            f"Filter {col}", 
                            options=display_vals, 
                            default=None,
                            key=f"filter_{col}",
                            help=f"Select values to filter by {col}"
                        )
                        if selected:
                            filters[col] = selected
                            
                        # Show count if many values
                        if len(unique_vals) > 20:
                            st.caption(f"{len(unique_vals)} total values, showing first 20")
            except Exception as e:
                st.sidebar.write(f"Could not filter {col}: {str(e)}")
    
    # Apply filters
    filtered_df = df.copy()
    for col, vals in filters.items():
        try:
            if col == df.index.name:
                filtered_df = filtered_df[filtered_df.index.isin(vals)]
            else:
                filtered_df = filtered_df[filtered_df[col].isin(vals)]
        except Exception as e:
            st.sidebar.error(f"Error applying filter for {col}: {str(e)}")
            continue
    
    # Show filter summary
    if filters:
        filter_info = ", ".join([f"{k}: {len(v)} values" for k, v in filters.items()])
        st.sidebar.success(f"Active filters: {filter_info}")
        st.sidebar.info(f"Filtered to {len(filtered_df)} rows")
    
    return filtered_df

def excel_like_table(df):
    """
    Display interactive table using Streamlit's native data editor
    
    Args:
        df (DataFrame): The dataframe to display
    """
    if df.empty:
        st.warning("No data to display")
        return
        
    # For display, ensure index is visible if it has a name
    display_df = df.reset_index() if df.index.name else df
    
    # Add download button
    csv = display_df.to_csv(index=False)
    st.download_button(
        label="📥 Download filtered data as CSV",
        data=csv,
        file_name="filtered_data.csv",
        mime="text/csv",
    )
    
    # Use Streamlit's data editor with some basic functionality
    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(400, 35 * (len(display_df) + 1)),  # Dynamic height
        hide_index=False
    )

def get_column_statistics(df, column_name):
    """
    Get basic statistics for a column
    
    Args:
        df (DataFrame): The dataframe
        column_name (str): The column to analyze
        
    Returns:
        dict: Statistics about the column
    """
    if column_name not in df.columns:
        return {}
    
    col_data = df[column_name]
    stats = {
        'type': str(col_data.dtype),
        'non_null_count': col_data.count(),
        'null_count': col_data.isnull().sum(),
        'unique_count': col_data.nunique()
    }
    
    # Add numeric-specific stats
    if pd.api.types.is_numeric_dtype(col_data):
        stats.update({
            'min': col_data.min(),
            'max': col_data.max(),
            'mean': col_data.mean(),
            'median': col_data.median()
        })
    
    return stats

def show_column_insights(df):
    """
    Display insights about dataframe columns
    
    Args:
        df (DataFrame): The dataframe to analyze
    """
    if df.empty:
        return
        
    with st.sidebar.expander("📊 Column Insights", expanded=False):
        for col in df.columns:
            stats = get_column_statistics(df, col)
            if stats:
                st.write(f"**{col}** ({stats['type']})")
                st.write(f"Non-null: {stats['non_null_count']}, Null: {stats['null_count']}")
                
                if 'min' in stats:
                    st.write(f"Range: {stats['min']:.2f} - {stats['max']:.2f}")
                    st.write(f"Mean: {stats['mean']:.2f}, Median: {stats['median']:.2f}")
                
                st.write("---")