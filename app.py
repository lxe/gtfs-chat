import logging
import os
from flask import Flask, render_template, request, jsonify, Response
from queue import Queue
from dotenv import load_dotenv
import sqlite3
import pandas as pd
from openai import OpenAI
import logging
import zipfile
import io
import time
import json
import anthropic
from collections import OrderedDict

from groq import Groq

llm_clients = {
    # "anthropic": {
    #     "api_key": os.environ.get("ANTHROPIC_API_KEY"),
    #     "client": anthropic.Anthropic(),
    #     "models": ["claude-3-5-sonnet-20240620"],
    # },
    "openai": {
        "api_key": os.environ.get("OPENAI_API_KEY"),
        "client": OpenAI(),
        "models": ["gpt-4o"]
    },
    "groq": {
        "api_key": os.environ.get("GROQ_API_KEY"),
        "client": Groq(api_key=os.environ.get("GROQ_API_KEY")),
        "models": ["llama-3.1-70b-versatile"]
    }
}

llm_clients['openai']['completions'] = llm_clients['openai']['client'].chat.completions.create
llm_clients['groq']['completions'] = llm_clients['groq']['client'].chat.completions.create

# Get the first client key
first_client_key = next(iter(llm_clients))

# Set the client and model
client = llm_clients[first_client_key]["client"]
model = llm_clients[first_client_key]["models"][0]
completions = llm_clients[first_client_key]["completions"]

def change_llm_client(client_name, model_name):
    global client, model, completions
    client = llm_clients[client_name]["client"]
    completions = llm_clients[client_name]["completions"]
    model = model_name

# Set up logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DATABASE'] = 'gtfs.db'

# Create a queue to hold debug messages
debug_queue = Queue()

# Add a global variable to store sample data
sample_data = {}

def send_debug(message):
    """
    Add a debug message to the queue
    """
    debug_queue.put(message)

@app.route('/debug-stream')
def debug_stream():
    def generate():
        while True:
            if not debug_queue.empty():
                message = debug_queue.get()
                yield f"data: {json.dumps(message)}\n\n"
            else:
                yield f"data: \n\n"
            time.sleep(0.1)
    return Response(generate(), mimetype='text/event-stream')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/available-llms', methods=['GET'])
def available_llms():
    clients_and_models = OrderedDict((client, data['models']) for client, data in llm_clients.items())
    return jsonify(list(clients_and_models.items())), 200

@app.route('/change-llm-client', methods=['POST'])
def change_llm():
    client_name = request.json['client']
    model_name = request.json['model']
    change_llm_client(client_name, model_name)
    return jsonify({'message': f"LLM client changed to {client_name} with model {model_name}"}), 200

@app.route('/upload', methods=['POST'])
def upload_file():
    send_debug("File upload started")
    if 'file' not in request.files:
        send_debug("Error: No file part in request")
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        send_debug("Error: No selected file")
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.endswith('.zip'):
        filename = 'gtfs.zip'
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        send_debug(f"File saved: {filename}")
        process_gtfs(filename)
        generate_sample_data()
        send_debug("File processed and sample data generated successfully")
        return jsonify({'message': 'File uploaded, processed, and sample data generated successfully'}), 200
    send_debug("Error: Invalid file type")
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/query', methods=['POST'])
def query_data():
    if not os.path.exists(app.config['DATABASE']):
        return jsonify({'error': 'Database does not exist. Please upload a GTFS file first.'}), 400
    
    user_query = request.json['query']
    try:
        sql_query = generate_sql_query(user_query)
        result = execute_sql_query(sql_query)
        
        # Humanize the result
        humanized_result = humanize_query_result(user_query, result)
        
        return jsonify({
            'result': result,
            'humanized_result': humanized_result
        }), 200
    except Exception as e:
        send_debug(f"Error executing query: {str(e)}")
        try:
            adjusted_query = adjust_query(user_query, sql_query, str(e))
            send_debug(f"Adjusted SQL query: {adjusted_query}")
            result = execute_sql_query(adjusted_query)
            
            # Humanize the adjusted result
            adjusted_humanized_result = humanize_query_result(user_query, result)
            
            send_debug("Adjusted query executed successfully")
            return jsonify({
                'result': result,
                'humanized_result': adjusted_humanized_result,
                'adjusted': True
            }), 200
        except Exception as e:
            logger.error(f"Error processing adjusted query: {str(e)}", exc_info=True)
            send_debug(f"Error processing adjusted query: {str(e)}")
            return jsonify({
                'error': str(e),
                'original_query': sql_query,
                'adjusted_query': adjusted_query
            }), 400

def process_gtfs(filename):
    send_debug(f"Processing GTFS file: {filename}")
    conn = sqlite3.connect(app.config['DATABASE'])

    with zipfile.ZipFile(os.path.join(app.config['UPLOAD_FOLDER'], filename)) as z:
        for file in [
            'routes.txt', 'stops.txt', 'stop_times.txt', 'calendar.txt',
            'calendar_dates.txt', 'agency.txt', 'trips.txt', 'shapes.txt',
            'fare_attributes.txt', 'fare_rules.txt', 'frequencies.txt',
            'transfers.txt', 'feed_info.txt'
        ]:
            try:
                with z.open(file) as f:
                    df = pd.read_csv(io.TextIOWrapper(f))
                    table_name = file.split('.')[0]
                    df.to_sql(table_name, conn, if_exists='replace', index=False)
                    send_debug(f"Processed file: {file}")
            except:
                logger.error(f"File {file} not found", exc_info=True)
                send_debug(f"Error processing file: {file}")

    conn.close()
    send_debug("GTFS processing completed")

def generate_sample_data():
    global sample_data
    send_debug("Generating sample data")
    tables = ['routes', 'stops', 'stop_times', 'trips']
    for table in tables:
        sample_data[table] = get_sample_data(table)
    send_debug("Sample data generated and cached")

def get_db_schema():
    send_debug("Fetching database schema")
    if not os.path.exists(app.config['DATABASE']):
        send_debug("Error: Database does not exist")
        return None
    
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    
    schema = {}
    tables = ['routes', 'stops', 'stop_times', 'trips']
    
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [f"{row[1]} {row[2]}" for row in cursor.fetchall()]
        schema[table] = ", ".join(columns)
    
    conn.close()
    send_debug("Database schema fetched")
    return schema

def get_sample_data(table, limit=5):
    send_debug(f"Fetching sample data for table: {table}")
    if not os.path.exists(app.config['DATABASE']):
        send_debug("Error: Database does not exist")
        return None
    
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} LIMIT {limit}")
    sample = cursor.fetchall()
    conn.close()
    send_debug(f"Sample data fetched for table: {table}")
    return sample

def create_llm_prompt(prompt_type, user_query="", original_sql="", error_message=""):
    send_debug(f"Creating LLM prompt for type: {prompt_type}")
    schema = get_db_schema()
    
    if schema is None:
        return "Error: Database does not exist. Please upload a GTFS file first."
    
    base_prompt = f"""
    You are a SQL professional with 12 years of industry experience that generates SQL (specifically sqlite3) queries based on natural language questions about GTFS data.
    The database has the following tables:
    """

    alignment_prompt = f"""
    BE CAREFUL with your data. Don't show duplicate rows. Make good assumptions about what columns the user is interested in. 
    Always show both IDs and Human readable names if available, unless explicitly stated. 
    If asking for the last or first item, make sure there's at least one result. If asking for a specific item, make sure it exists.
    Some routes are circular, so if the user asks for the last stop, it might be the first stop. Detect the circles and handle them.
    Don't show a table of unrelated data... for example, if asking for stops, don't show routes or trips.
    IMPORTANT! Extrapolate the SQL query based on unstructured user input. For example, if the user asks for "Orange line", try to first see if "orange" is an exact match to a certain name, or just a semantically meaningful part, while figuring out what line ID they mean by that, using advanced SQL queries.
    IMPORTANT! Output MUST be in the form of a SQL query. No markdown characters, no codeboxes, no backticks, no explanation, just the plain query, in plain text, with comments explaining what each line does.
    NEVER OUTPUT \`\`\` characters! ONLY THE QUERY!
    """
    
    for table, columns in schema.items():
        base_prompt += f"{table} ({columns})\n"
    
    if prompt_type == "generate":
        base_prompt += f"""
        Sample data for routes:
        {sample_data['routes']}

        Sample data for stops:
        {sample_data['stops']}

        Sample data for stop times:
        {sample_data['stop_times']}

        Sample data for trips:
        {sample_data['trips']}

        (Note: the sample data does not represent the actual contents of the database, it is only for reference)

        User question: {user_query}

        Please generate a SQL query to answer this question, taking into account the GTFS spec information provided earlier. 
        
        {alignment_prompt}
        """
    elif prompt_type == "adjust":
        base_prompt += f"""
        The following SQL query was generated based on a user question, but it resulted in an error:

        User question: {user_query}
        
        Original SQL query:
        {original_sql}

        Error message: {error_message}

        Please generate a SQL query to fix the error. Consider the schema provided above. 
        
        {alignment_prompt}
        """
        
    send_debug(f"LLM prompt created for type: {prompt_type}")
    return base_prompt

def query_llm(messages):
    send_debug(f"Querying LLM: {json.dumps(messages, indent=4)}")
    try:
        response = completions(
            max_tokens=2048,
            model=model,
            messages=messages
        )

        result = response.choices[0].message.content.strip()
        send_debug(f"LLM query result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error querying LLM: {str(e)}", exc_info=True)
        send_debug(f"Error querying LLM: {str(e)}")
        raise Exception(f"Error querying LLM: {str(e)}")

def generate_sql_query(user_query):
    send_debug(f"Generating SQL query for user query: {user_query}")
    
    # First shot: Ask about GTFS spec
    gtfs_spec_prompt = f"In GTFS spec, {user_query}"
    gtfs_spec_messages = [
        {"role": "system", "content": "You are a GTFS (General Transit Feed Specification) expert. Provide concise information about the GTFS spec relevant to the user's question."},
        {"role": "user", "content": gtfs_spec_prompt}
    ]
    gtfs_spec_response = query_llm(gtfs_spec_messages)
    
    # Second shot: Generate SQL query based on GTFS spec information
    sql_prompt = create_llm_prompt("generate", user_query=user_query)
    sql_messages = [
        {"role": "system", "content": "You are a professional GTFS SQL Expert that writes thoughtful and correct SQL queries based on user questions."},
        {"role": "user", "content": gtfs_spec_prompt},
        {"role": "assistant", "content": gtfs_spec_response},
        {"role": "user", "content": sql_prompt}
    ]
    
    return query_llm(sql_messages)

def humanize_query_result(original_question, result):
    prompt = f"""
        You are a helpful assistant that interprets SQL query results and provides concise, human-friendly answers.

        Original question: {original_question}

        Query result:
        {result}

        Please provide a succinct answer to the original question based on this query result. If the result is a large table or a long list that directly answers the question, truncate it to about 5 items, and then simply direct the user to refer to the result. Otherwise, summarize the key information in a clear, conversational manner.

        Your response should be concise and directly address the user's question. If the user asks for a list, truncate it, and refer to the table. Do not include phrases like "Based on the query result" or "The data shows that". Just provide the answer as if you were directly responding to the user's question.

        Respond with well-formed HTML. Use tags for paragraphs, bold, italics, lists, and line breaks as needed.
        """

    messages = [
        {"role": "system", "content": "You are a helpful assistant that interprets SQL query results and provides concise, human-friendly answers."},
        {"role": "user", "content": prompt}
    ]

    return query_llm(messages)

def adjust_query(user_query, original_sql, error_message):
    send_debug(f"Adjusting SQL query. Original query: {original_sql}")
    prompt = create_llm_prompt("adjust", user_query=user_query, original_sql=original_sql, error_message=error_message)
    messages = [
        {"role": "system", "content": "You are a professional GTFS SQL Expert that adjusts SQL queries based on error messages."},
        {"role": "user", "content": prompt}
    ]
    return query_llm(messages)

def execute_sql_query(sql_query):
    print(sql_query)
    send_debug(f"Executing SQL query: {sql_query}")
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()

    try:
        cursor.execute(sql_query)
        result = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        conn.close()
        send_debug("SQL query executed successfully")
        return {"columns": columns, "data": result}
    except sqlite3.Error as e:
        conn.close()
        logger.error(f"SQLite error: {str(e)}", exc_info=True)
        send_debug(f"SQLite error: {str(e)}")
        raise Exception(f"SQLite error: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)