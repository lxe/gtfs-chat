# app.py

from flask import Flask
from database import init_db
from routes import index, execute_query, chat, upload_file, get_available_models

app = Flask(__name__)

# Initialize the database
init_db()

# Register routes
app.add_url_rule('/', view_func=index)
app.add_url_rule('/upload', view_func=upload_file, methods=['POST'])
app.add_url_rule('/query', view_func=execute_query, methods=['POST'])
app.add_url_rule('/chat', view_func=chat, methods=['POST'])
app.add_url_rule('/get_available_models', view_func=get_available_models)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)