# routes.py
from flask import render_template, request, jsonify
from werkzeug.utils import secure_filename
from zipfile import ZipFile
from io import BytesIO
from gtfs_processor import process_gtfs_feed, gtfs_schema, VALID_GTFS_FILES
from database import query_to_dict
import traceback
from engine import GTFSQueryEngine, LLM_CLIENTS


def index():
    return render_template('index.html')

def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if not file.filename.endswith('.zip'):
        return jsonify({"error": "File must be a ZIP archive"}), 400

    try:
        zip_contents = {}
        with ZipFile(BytesIO(file.read())) as zip_file:
            for filename in zip_file.namelist():
                if filename in VALID_GTFS_FILES:
                    with zip_file.open(filename) as file:
                        zip_contents[filename] = file.read().decode('utf-8')
        
        if not zip_contents:
            return jsonify({"error": "No valid GTFS files found in the ZIP archive"}), 400

        process_gtfs_feed(zip_contents)
        print(f"Processed {len(zip_contents)} GTFS files")
        print(f"Schama:\n{gtfs_schema()}")
        
        return jsonify({"message": "GTFS data processed successfully"}), 200
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def execute_query():
    query = request.json.get('query')
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    try:
        results = query_to_dict(query)
        return jsonify(results), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def get_available_models():
    models = []
    for company, details in LLM_CLIENTS.items():
        for model in details['models']:
            models.append(f"{company} - {model}")
    return jsonify(models), 200

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
        "table": results,
        "query": query
    }), 200