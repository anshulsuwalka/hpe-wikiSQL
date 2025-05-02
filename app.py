
import streamlit as st
import requests
from typing import Dict, Any
import time

# Configuration
API_BASE_URL = "http://127.0.0.1:8000"  # Changed from localhost to 127.0.0.1
DB_SCHEMA_CACHE_KEY = "db_schema_cache"

def fetch_database_schema() -> Dict[str, Any]:
    """Fetch and cache the database schema with error handling"""
    if DB_SCHEMA_CACHE_KEY in st.session_state:
        return st.session_state[DB_SCHEMA_CACHE_KEY]
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/schema",
            timeout=30
        )
        response.raise_for_status()
        schema = response.json().get("schema", {})
        st.session_state[DB_SCHEMA_CACHE_KEY] = schema
        return schema
    except requests.exceptions.RequestException as e:
        st.error(f"Schema fetch failed: {str(e)}")
        return {"error": str(e)}


def generate_sql(query: str) -> Dict[str, Any]:
    try:
        response = requests.post(
            "http://127.0.0.1:8000/generate_sql",
            json={"query": query},  # Must match exactly with your QueryRequest model
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()  # This will raise an exception for 4XX/5XX errors
        return response.json()
    except requests.exceptions.RequestException as e:
        # This will give you more detailed error information
        if hasattr(e, 'response') and e.response is not None:
            error_details = e.response.json()
            return {"error": f"Backend Error: {error_details.get('detail', str(e))}"}
        return {"error": f"Connection Error: {str(e)}"}
    
def execute_sql(sql_query: str) -> Dict[str, Any]:
    """Execute the SQL query via FastAPI with validation"""
    if not sql_query.strip().lower().startswith(('select', 'with', 'explain')):
        return {
            "error": "Only SELECT queries are allowed for execution",
            "allowed_types": ["SELECT", "WITH", "EXPLAIN"]
        }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/execute_sql",
            json={"sql_query": sql_query},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def display_results(data: Any) -> None:
    """Improved results display with error handling"""
    if isinstance(data, dict):
        if "error" in data:
            st.error(data["error"])
            if "suggestion" in data:
                st.info(data["suggestion"])
        elif "columns" in data and "data" in data:
            st.dataframe(
                data["data"],
                column_config={col: col for col in data["columns"]},
                use_container_width=True
            )
            st.caption(f"Returned {len(data['data'])} rows")
        else:
            st.json(data)
    else:
        st.write(data)

def main():
    st.set_page_config(
        page_title="NL to SQL Converter",
        layout="wide",
        page_icon="🔍"
    )
    
    # Sidebar with database info
    with st.sidebar:
        st.header("Database Connection")
        if st.button("🔄 Refresh Schema", help="Reload database schema"):
            if DB_SCHEMA_CACHE_KEY in st.session_state:
                del st.session_state[DB_SCHEMA_CACHE_KEY]
            st.rerun()
        
        schema = fetch_database_schema()
        if schema and not isinstance(schema, dict):
            with st.expander("📋 Database Schema", expanded=False):
                st.code(schema, language="sql")
        elif isinstance(schema, dict) and "error" in schema:
            st.error("Schema load failed")
            st.code(str(schema), language="json")

    # Main interface
    st.title("🔍 Natural Language to SQL Converter")
    st.caption("Transform your questions into SQL queries")
    
    col1, col2 = st.columns([3, 2], gap="large")
    
    with col1:
        user_input = st.text_area(
            "**Your question in English:**",
            placeholder="e.g., Find the total count of employees in each department",
            height=150,
            key="nl_query"
        )
        
        if st.button("**✨ Generate SQL**", type="primary", use_container_width=True):
            if not user_input.strip():
                st.warning("Please enter a question")
                st.stop()
                
            with st.spinner("Generating SQL query..."):
                result = generate_sql(user_input)
                
            if "error" in result:
                st.error(result["error"])
                if "suggestion" in result:
                    st.info(result["suggestion"])
            else:
                sql_query = result.get("sql_query", "")
                st.session_state.generated_sql = sql_query
                st.text_area(
                    "**Generated SQL Query:**",
                    value=sql_query,
                    height=200,
                    key="sql_output"
                )
                if "generation_time" in result:
                    st.caption(f"Generated in {result['generation_time']:.2f} seconds")
    
    with col2:
        if "generated_sql" in st.session_state:
            st.subheader("Query Actions")
            
            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if st.button("📋 Copy SQL", help="Copy to clipboard", use_container_width=True):
                    st.session_state.sql_output = st.session_state.generated_sql
                    st.toast("SQL copied to clipboard!", icon="✓")
                
            with action_col2:
                if st.button("🛠️ Explain", help="Explain the query", use_container_width=True):
                    with st.spinner("Generating explanation..."):
                        st.info("""
                        **Explanation:**  
                        This feature would analyze the generated SQL query and explain:
                        - Which tables are being accessed
                        - The filtering conditions applied
                        - The relationships being used
                        """)
            
            if st.button("⚡ Execute Query", type="secondary", use_container_width=True):
                with st.spinner("Running query..."):
                    exec_result = execute_sql(st.session_state.generated_sql)
                    
                if "error" in exec_result:
                    st.error(exec_result["error"])
                else:
                    st.success("✅ Query executed successfully!")
                    display_results(exec_result.get("result", {}))

if __name__ == "__main__":
    main()
