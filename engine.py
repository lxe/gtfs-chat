from functools import wraps
from flask import jsonify, request
from database import query_to_dict 
from gtfs_processor import gtfs_schema
from decimal import Decimal
import json

import anthropic
import groq

from rich import print as rprint
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

# Constants for prompts
SQL_SYSTEM_PROMPT = """
You are a professional, creative, and highly-paid GTFS and SQL engineer with a nobel prize in SQL and 45 years of professional experience with GTFS.
Respond ONLY with valid geospatial postgres/postgis queries to answer questions based on the following GTFS SQL schema:

{schema}

Guidelines:
0. Assume ambiguous results, so use smart queries to match on partial strings. Colors usually refer to strings.
1. DO NOT NEST AGGREGATION FUNCTIONS. Use subselects for nested aggregate functions.
2. Always disambiguate column names and use table names.
3. Include human-readable names or IDs in the final result when possible.
4. Be aware of GTFS quirks, especially when calculating lengths or dealing with duplicate trips.
5. Only use valid postgres and postgis SQL functions.
6. Do NOT invent columns or tables that don't exist in the schema.
7. Use subqueries when nesting aggregation functions is necessary.
8. Use CTEs (Common Table Expressions) almost all the time instead of nesting complicated queries
9. Don't use reserved keywords as column or table names.

Common Errors to Avoid:
1.  Error message: aggregate function calls cannot be nested 
    LINE 10:     MAX(ST_Length(ST_MakeLine(ST_MakePoint(shape_pt_lon, sha...  
2.  Error executing query: function st_makeline(geography) does not exist
    LINE 7:             ST_MakeLine(

Your response should be structured as follows:
-- [Your thought process as comments]
[A single valid SQL query]

Do not include any other text, explanations, or codeboxes in your response.
"""

SUMMARY_SYSTEM_PROMPT = """
Summarize the provided answer using natural conversational language.

Guidelines:
1. Include the total number of results.
2. Mention key data points or trends.
3. Do not include technical details about the data format or query.
4. Do not mention "truncated" data or "full answer length".
5. Provide a concise, human-readable summary.
6. Do not use preambled like "this query returned" or "the results show". Just the answer to the question please!
7. The user will provide the "total answer length". Use this number in your summary instead of the truncated length.

Use short, clear sentences and avoid jargon. Maximum response length: 100 characters.

Format your response as plain HTML, highlighting relevant portions with <b> or <em>, and utilizing lists and paragraphs when applicable.
"""

DATA_VALIDATION_PROMPT = """
Analyze the given public transportation data for suspicious or unrealistic information.
Consider:
1. Route lengths (typically <100 km for buses, possibly longer for rail)
2. Operating hours (usually 5 AM to 1 AM)
3. Vehicle speeds (typically 10-80 km/h for buses, possibly higher for rail)
4. Number of stops (usually <100 per route)
5. Service frequency (typically not more than every 5 minutes, not less than every 2 hours)

Respond ONLY with:
VALID
or
SUSPICIOUS: [Brief explanation]
"""

SQL_ERROR_CORRECTION_PROMPT = """
Correct the following SQL query that resulted in an error:

{query}

Error message: {error_message}

GTFS SQL schema:
{schema}

Provide ONLY the corrected SQL query with explanations as comments. Do not include any other text.
"""

EMPTY_RESULTS_CORRECTION_PROMPT = """
Modify the following SQL query that returned no results:

{query}

Consider:
1. Are WHERE clauses too restrictive?
2. Are JOINs eliminating all rows?
3. Do all selected columns exist and are they correctly referenced?

GTFS SQL schema:
{schema}

Provide ONLY the modified SQL query. Do not include any explanations or comments.
"""

# Map of clients and their models
LLM_CLIENTS = {
    "anthropic": {
        "client": anthropic.Anthropic(),
        "models": ["claude-3-5-sonnet-20240620"]
    },
    "groq": {
        "client": groq.Groq(),
        "models": ["llama-3.1-70b-versatile", "llama-3.1-405b-reasoning"]
    }
}

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def llm_call(system_prompt, messages, client_name="anthropic", model=None, max_tokens=1000):
    console = Console()

    console.print(Panel(system_prompt, title="System Prompt", expand=False, border_style="cyan"))

    message_table = Table(title="Messages", show_header=True, header_style="bold magenta")
    message_table.add_column("Role", style="dim", width=12)
    message_table.add_column("Content", style="green")

    for message in messages:
        message_table.add_row(message['role'], message['content'][0]['text'])

    console.print(message_table)

    if client_name not in LLM_CLIENTS:
        raise ValueError(f"Unsupported client: {client_name}")

    client = LLM_CLIENTS[client_name]["client"]
    
    if model is None:
        model = LLM_CLIENTS[client_name]["models"][0]  # Use the first model as default
    elif model not in LLM_CLIENTS[client_name]["models"]:
        raise ValueError(f"Unsupported model for {client_name}: {model}")

    if client_name == "anthropic":
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
            system=system_prompt,
            messages=messages
        )
        result = response.content[0].text.strip()
    elif client_name == "groq":
        # Convert messages to Groq-compatible format
        groq_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            groq_messages.append({
                "role": msg["role"],
                "content": msg["content"][0]["text"]  # Extract the text content
            })

        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
            messages=groq_messages
        )

        result = response.choices[0].message.content.strip()

    console.print(Panel(Syntax(result, "markdown", theme="monokai", line_numbers=True), 
                        title=f"LLM Response ({client_name} - {model})", expand=False, border_style="green"))

    return result

class GTFSQueryEngine:
    def __init__(self):
        self.schema = gtfs_schema()
        self.sql_system_prompt = SQL_SYSTEM_PROMPT.format(schema=self.schema)
        self.summary_system_prompt = SUMMARY_SYSTEM_PROMPT
        self.data_validation_prompt = DATA_VALIDATION_PROMPT
        self.sql_error_correction_prompt = SQL_ERROR_CORRECTION_PROMPT
        self.empty_results_correction_prompt = EMPTY_RESULTS_CORRECTION_PROMPT

    def generate_query(self, messages, company, model):
        return llm_call(self.sql_system_prompt, messages, client_name=company, model=model)

    def correct_sql_error(self, query, error_message, company, model):
        correction_prompt = self.sql_error_correction_prompt.format(query=query, error_message=error_message, schema=self.schema)
        return llm_call(correction_prompt, [{"role": "user", "content": [{"type": "text", "text": "Correct the SQL query."}]}], client_name=company, model=model)

    def correct_empty_results(self, query, company, model):
        correction_prompt = self.empty_results_correction_prompt.format(query=query, schema=self.schema)
        return llm_call(correction_prompt, [{"role": "user", "content": [{"type": "text", "text": "Modify the query to potentially return results."}]}], client_name=company, model=model)

    def execute_query_with_retries(self, query, company, model, max_retries=3):
        for attempt in range(max_retries):
            try:
                results = query_to_dict(query)
                if results:
                    return results, query
                else:
                    print(f"Attempt {attempt + 1}: Query returned no results. Attempting to correct the query.")
                    query = self.correct_empty_results(query, company, model)
                    print(f"Corrected query for empty results: {query}")
            except Exception as e:
                error_message = str(e)
                print(f"Attempt {attempt + 1}: Error executing query: {error_message}")
                query = self.correct_sql_error(query, error_message, company, model)
                print(f"Corrected query: {query}")
        
        # If we've exhausted all retries, make one last attempt
        return query_to_dict(query), query

    def summarize_results(self, question, results, query, company, model):
        truncated_results = json.dumps([dict(row) for row in results[:10]], indent=4, cls=DecimalEncoder)
        summary_message = [{
            "role": "user",
            "content": [{
                "type": "text",
                "text": f"""
                    Question: {question},
                    Truncated Answer: \n---\n{truncated_results}\n---\n
                    Full Answer Length: {len(results)}
                """
            }]
        }]
        return llm_call(self.summary_system_prompt, summary_message, client_name=company, model=model, max_tokens=100)

    def validate_data(self, summary, results, company, model):
        validation_message = [{
            "role": "user",
            "content": [{
                "type": "text",
                "text": f"""
                    Summary: {summary}
                    Full data: {json.dumps(results[:20], indent=2, cls=DecimalEncoder)}
                """
            }]
        }]
        return llm_call(self.data_validation_prompt, validation_message, client_name=company, model=model, max_tokens=100)

    def process_query(self, messages, company="anthropic", model="claude-3-sonnet-20240229"):
        query = self.generate_query(messages, company, model)
        print(f"Generated query: {query}")
        
        results, final_query = self.execute_query_with_retries(query, company, model)
        
        question = messages[-1]['content'][0]['text']
        summary = self.summarize_results(question, results, final_query, company, model)
        
        validation_result = self.validate_data(summary, results, company, model)
        if validation_result.startswith("SUSPICIOUS"):
            print(f"Data flagged as suspicious: {validation_result}")
            corrected_query = self.correct_empty_results(final_query, company, model)
            print(f"Corrected query for suspicious data: {corrected_query}")
            results, final_query = self.execute_query_with_retries(corrected_query, company, model)
            summary = self.summarize_results(question, results, final_query, company, model)
        
        return summary, results, final_query

def execute_query():
    query = request.json.get('query')
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    try:
        results = query_to_dict(query)
        return jsonify(json.loads(json.dumps(results, cls=DecimalEncoder))), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def chat():
    messages = request.json.get('messages')
    company_model = request.json.get('company_model', 'anthropic - claude-3-sonnet-20240229')
    company, model = company_model.split(' - ')
    
    print(f"Received messages: {messages}")
    print(f"Selected company: {company}, model: {model}")

    engine = GTFSQueryEngine()
    summary, results, query = engine.process_query(messages, company, model)

    return jsonify({
        "summary": summary,
        "table": json.loads(json.dumps(results, cls=DecimalEncoder)),
        "query": query
    }), 200