
import psycopg2
from psycopg2 import sql, OperationalError
from typing import Dict, List, Tuple, Union
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.conn_params = {
            "dbname": os.getenv("DB_NAME", "classicmodels"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "postgresql@70140"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432")
        }
        self.schema_cache = None

    def get_connection(self):
        """Establish a database connection"""
        try:
            return psycopg2.connect(**self.conn_params)
        except OperationalError as e:
            raise Exception(f"Database connection failed: {str(e)}")

    def get_database_schema(self) -> Dict[str, Union[str, List[Dict]]]:
        """
        Fetch complete database schema including:
        - Tables and columns
        - Primary keys
        - Foreign keys
        - Indexes
        """
        schema = {"tables": [], "relationships": []}
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get all tables in public schema
                    cur.execute("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                    tables = [row[0] for row in cur.fetchall()]

                    for table in tables:
                        # Get columns for each table
                        cur.execute(sql.SQL("""
                            SELECT 
                                column_name, 
                                data_type,
                                is_nullable,
                                column_default
                            FROM information_schema.columns
                            WHERE table_name = %s
                            ORDER BY ordinal_position
                        """), [table])
                        
                        columns = []
                        for col in cur.fetchall():
                            columns.append({
                                "name": col[0],
                                "type": col[1],
                                "nullable": col[2] == 'YES',
                                "default": col[3]
                            })

                        # Get primary keys
                        cur.execute(sql.SQL("""
                            SELECT column_name
                            FROM information_schema.key_column_usage
                            WHERE table_name = %s
                            AND constraint_name IN (
                                SELECT constraint_name
                                FROM information_schema.table_constraints
                                WHERE table_name = %s
                                AND constraint_type = 'PRIMARY KEY'
                            )
                        """), [table, table])
                        
                        primary_keys = [row[0] for row in cur.fetchall()]

                        # Get foreign keys
                        cur.execute(sql.SQL("""
                            SELECT
                                kcu.column_name,
                                ccu.table_name AS foreign_table,
                                ccu.column_name AS foreign_column
                            FROM 
                                information_schema.key_column_usage kcu
                            JOIN information_schema.constraint_column_usage ccu
                                ON ccu.constraint_name = kcu.constraint_name
                            WHERE kcu.table_name = %s
                            AND kcu.constraint_name IN (
                                SELECT constraint_name
                                FROM information_schema.table_constraints
                                WHERE table_name = %s
                                AND constraint_type = 'FOREIGN KEY'
                            )
                        """), [table, table])
                        
                        foreign_keys = []
                        for fk in cur.fetchall():
                            foreign_keys.append({
                                "column": fk[0],
                                "references": f"{fk[1]}({fk[2]})"
                            })
                            schema["relationships"].append({
                                "source_table": table,
                                "source_column": fk[0],
                                "target_table": fk[1],
                                "target_column": fk[2]
                            })

                        schema["tables"].append({
                            "name": table,
                            "columns": columns,
                            "primary_keys": primary_keys,
                            "foreign_keys": foreign_keys
                        })

                    # Cache the schema
                    self.schema_cache = schema
                    return schema

        except Exception as e:
            return {"error": str(e)}

    def execute_sql_query(self, sql_query: str) -> Dict[str, Union[str, List]]:
        """
        Execute SQL query and return results with metadata
        Handles both SELECT and DML queries
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # First validate the query
                    if not self._validate_query(sql_query):
                        return {"error": "Invalid or potentially dangerous query detected"}

                    # Execute the query
                    cur.execute(sql_query)
                    
                    # Handle different query types
                    if sql_query.strip().lower().startswith("select"):
                        columns = [desc[0] for desc in cur.description]
                        data = cur.fetchall()
                        return {
                            "type": "SELECT",
                            "columns": columns,
                            "data": data,
                            "row_count": len(data)
                        }
                    else:
                        conn.commit()
                        return {
                            "type": "DML",
                            "message": "Query executed successfully",
                            "row_count": cur.rowcount
                        }

        except psycopg2.Error as e:
            return {"error": str(e)}

    def _validate_query(self, query: str) -> bool:
        """Basic SQL injection prevention"""
        query = query.lower().strip()
        
        # Block suspicious patterns
        dangerous_patterns = [
            "--", "/*", "*/", ";", "drop ", "delete ", "truncate ",
            "insert ", "update ", "alter ", "create ", "grant ", "revoke "
        ]
        
        # Allow only SELECT queries for now (modify as needed)
        if not query.startswith("select "):
            for pattern in dangerous_patterns:
                if pattern in query:
                    return False
        
        return True

    def get_formatted_schema(self) -> str:
        """Return schema as formatted string for NL-to-SQL generation"""
        if not self.schema_cache:
            self.get_database_schema()
            
        if "error" in self.schema_cache:
            return self.schema_cache["error"]
            
        schema_text = []
        for table in self.schema_cache["tables"]:
            schema_text.append(f"Table: {table['name']}")
            
            # Columns
            cols = []
            for col in table["columns"]:
                col_def = f"{col['name']} ({col['type']}"
                if not col["nullable"]:
                    col_def += " NOT NULL"
                if col["default"]:
                    col_def += f" DEFAULT {col['default']}"
                cols.append(col_def)
            schema_text.append("  Columns: " + ", ".join(cols))
            
            # Primary keys
            if table["primary_keys"]:
                schema_text.append(f"  Primary Key: {', '.join(table['primary_keys'])}")
            
            # Foreign keys
            for fk in table["foreign_keys"]:
                schema_text.append(f"  Foreign Key: {fk['column']} references {fk['references']}")
            
            schema_text.append("")  # Empty line between tables
        
        # Add relationships summary
        if self.schema_cache["relationships"]:
            schema_text.append("\nRelationships:")
            for rel in self.schema_cache["relationships"]:
                schema_text.append(
                    f"{rel['source_table']}.{rel['source_column']} → "
                    f"{rel['target_table']}.{rel['target_column']}"
                )
        
        return "\n".join(schema_text)

# Singleton instance for the application
db_manager = DatabaseManager()

# Interface functions for FastAPI
def get_database_schema() -> str:
    """Public interface for schema retrieval"""
    return db_manager.get_formatted_schema()

def execute_sql_query(sql_query: str) -> Dict[str, Union[str, List]]:
    """Public interface for query execution"""
    return db_manager.execute_sql_query(sql_query)