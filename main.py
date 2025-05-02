
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration
from sql import execute_sql_query, get_database_schema
from typing import Dict, Any
import logging
import traceback
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def looks_like_sql(query: str) -> bool:
    """Check if the generated output resembles valid SQL"""
    if not query or not isinstance(query, str):
        return False
    
    query = query.lower().strip()
    
    # Check for common SQL keywords
    sql_keywords = ["select", "insert", "update", "delete", "with", "from", "where"]
    has_keywords = any(keyword in query for keyword in sql_keywords)
    
    # Check for proper structure (basic pattern matching)
    structure_valid = (
        re.match(r"^\s*(select|insert|update|delete|with)", query) is not None
        and ("from " in query or "into " in query or "set " in query)
    )
    
    return has_keywords and structure_valid


app = FastAPI(
    title="NL to SQL Converter API",
    description="API for converting natural language to SQL and executing queries",
    version="1.0"
)

class QueryRequest(BaseModel):
    query: str

class SQLRequest(BaseModel):
    sql_query: str

class ExplanationRequest(BaseModel):
    sql_query: str
    question: str = None

# Initialize model and tokenizer
model_name = "mrm8488/t5-base-finetuned-wikiSQL"
try:
    logger.info("Loading tokenizer and model...")
    tokenizer = T5Tokenizer.from_pretrained(model_name, legacy=False)
    model = T5ForConditionalGeneration.from_pretrained(model_name)
    logger.info("Model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load model: {str(e)}")
    raise RuntimeError("Model loading failed") from e

@app.on_event("startup")
async def startup_event():
    """Initialize resources when the app starts"""
    try:
        logger.info("Pre-loading database schema...")
        schema = get_database_schema()
        if isinstance(schema, dict) and "error" in schema:
            logger.error(f"Schema loading failed: {schema['error']}")
        else:
            logger.info("Schema loaded successfully")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")

def generate_sql(nl_query: str, schema: str) -> Dict[str, Any]:
    """Generate SQL query using the T5 model finetuned on WikiSQL"""
    try:
        if not nl_query.strip():
            return {"status": "error", "message": "Empty query"}

        # Use input format expected by the model
        input_text = f"translate English to SQL: {nl_query} | table = {schema}"
        logger.debug(f"Input text: {input_text[:200]}...")
        logger.debug(f"Schema being passed to model: {schema}")

        input_ids = tokenizer(input_text, return_tensors="pt").input_ids

        with torch.no_grad():
            outputs = model.generate(
                input_ids,
                max_length=150,
                num_beams=4,
                early_stopping=True,
                no_repeat_ngram_size=2,
                temperature=0.7
            )

        decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
        sql_query = decoded.split("|")[0].strip()
        sql_query = sql_query.replace("SQL:", "").strip()
        return {"status": "success", "sql_query": sql_query}


    except Exception as e:
        logger.error(f"Generation failed: {str(e)}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(e)}


@app.post("/generate_sql", response_model=Dict[str, Any])
async def get_sql(request: QueryRequest):
    """Endpoint for generating SQL from natural language"""
    try:
        schema = get_database_schema()
        if isinstance(schema, dict) and "error" in schema:
            raise HTTPException(status_code=500, detail=schema["error"])
        
        result = generate_sql(request.query, schema)
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "status": "success",
            "sql_query": result["sql_query"],
            "schema_sample": schema[:500] + "..." if len(schema) > 500 else schema
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/schema", response_model=Dict[str, Any])
async def get_schema():
    """Endpoint to fetch database schema"""
    try:
        schema = get_database_schema()
        if isinstance(schema, dict) and "error" in schema:
            raise HTTPException(status_code=500, detail=schema["error"])
        
        return {
            "status": "success",
            "schema": schema
        }
    except Exception as e:
        logger.error(f"Schema fetch failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/explain_sql", response_model=Dict[str, Any])
async def explain_sql(request: ExplanationRequest):
    """Endpoint to explain generated SQL queries"""
    try:
        explanation = (
            f"Query: {request.sql_query}\n"
            f"Purpose: {request.question or 'Not specified'}\n"
            f"Note: This is a placeholder explanation"
        )
        
        return {
            "status": "success",
            "explanation": explanation,
            "sql_query": request.sql_query
        }
    except Exception as e:
        logger.error(f"Explanation failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Verify model is loaded
        if not model or not tokenizer:
            raise RuntimeError("Model not loaded")
        
        # Verify database connection
        schema = get_database_schema()
        if isinstance(schema, dict) and "error" in schema:
            raise RuntimeError(f"Database connection failed: {schema['error']}")
            
        return {
            "status": "healthy",
            "details": {
                "model_loaded": True,
                "database_connected": True
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=str(e))