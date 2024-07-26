# GTFS Query App

## Overview

The GTFS Query App is a web-based application that allows users to upload GTFS (General Transit Feed Specification) data and query it using natural language. The app leverages large language models (LLMs) to interpret user queries and generate corresponding SQL queries to retrieve information from the GTFS database.

## Features

- Upload GTFS data in ZIP format
- Process and store GTFS data in an SQLite database
- Query GTFS data using natural language
- Support for multiple LLM providers (OpenAI, Groq)
- Dynamic LLM model selection
- Real-time debug information display
- Responsive web interface

## Tech Stack

- Backend: Python with Flask
- Frontend: HTML, CSS (Tailwind CSS), JavaScript
- Database: SQLite
- LLM Integration: OpenAI API, Groq API
- Additional Libraries: pandas, anthropic, dotenv

## Prerequisites

- Python 3.7+
- pip (Python package manager)
- Node.js and npm (for Tailwind CSS)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/gtfs-query-app.git
   cd gtfs-query-app
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the root directory and add the following:
   ```
   OPENAI_API_KEY=your_openai_api_key
   GROQ_API_KEY=your_groq_api_key
   ```

5. Install Tailwind CSS:
   ```
   npm install tailwindcss
   npx tailwindcss init
   ```

## Running the Application

1. Start the Flask server:
   ```
   python app.py
   ```

2. Open a web browser and navigate to `http://localhost:5000`

## Usage

1. **Upload GTFS Data**: 
   - Click on the upload area or drag and drop a GTFS ZIP file.
   - The app will process the file and store it in the SQLite database.

2. **Select LLM Model**:
   - Choose the desired LLM provider and model from the dropdown menu.

3. **Query GTFS Data**:
   - Enter a natural language query in the input field (e.g., "What is the last stop on the orange line?").
   - Click "Submit Query" or press Enter.
   - The app will interpret your query, generate an SQL query, and display the results.

4. **View Debug Information**:
   - Click the bug icon in the bottom-right corner to open the debug drawer.
   - View real-time debug information about the app's operations.

## Application Structure

- `app.py`: Main Flask application file
- `static/js/main.js`: Frontend JavaScript code
- `templates/index.html`: HTML template for the web interface
- `uploads/`: Directory for storing uploaded GTFS files
- `gtfs.db`: SQLite database file (created after uploading GTFS data)

## LLM Integration

The app supports multiple LLM providers:
- OpenAI (GPT-4)
- Groq (LLaMA 3.1)

The LLM is used to:
1. Interpret the user's natural language query
2. Generate an appropriate SQL query
3. Humanize the query results for easier understanding

## Details

### How app.py Works

The `app.py` file is the core of the GTFS Query App, handling both backend logic and API endpoints. Here's a breakdown of its main components and functionality:

1. **Initialization and Configuration**
   - The app initializes Flask and sets up configurations for file uploads and database connections.
   - It sets up logging and creates a queue for debug messages.
   - LLM clients (OpenAI, Groq) are configured using environment variables.

2. **File Upload and Processing**
   - The `/upload` endpoint handles GTFS file uploads.
   - Uploaded ZIP files are processed using the `process_gtfs()` function.
   - GTFS data is extracted and stored in an SQLite database using pandas.

3. **LLM Client Management**
   - The app supports multiple LLM providers (OpenAI, Groq).
   - Users can switch between different LLM models using the `/change-llm-client` endpoint.

4. **Query Processing**
   - The `/query` endpoint handles natural language queries from users.
   - Queries go through a multi-step process to generate and execute SQL queries.

### Query Flow

When a user submits a query, the following steps occur:

1. **Natural Language Understanding**
   - The user's query is sent to the selected LLM for interpretation.
   - The LLM is provided with context about the GTFS specification and the database schema.

2. **SQL Query Generation**
   - Based on the interpreted query, the LLM generates an appropriate SQL query.
   - This process uses a two-shot approach:
     a. First, it asks about the GTFS spec relevant to the query.
     b. Then, it generates the SQL query based on this information and the database schema.

3. **SQL Query Execution**
   - The generated SQL query is executed against the SQLite database.
   - If an error occurs, the app attempts to adjust the query and retry.

4. **Result Processing**
   - Query results are fetched and formatted.
   - The LLM is used again to "humanize" the results, providing a natural language summary.

5. **Response Delivery**
   - Both the raw query results and the humanized summary are sent back to the frontend.

### Error Handling and Debugging

- The app includes robust error handling at each step of the process.
- Debug information is continuously sent to the frontend using Server-Sent Events (SSE).
- If a query fails, the app attempts to adjust it using the LLM and provides detailed error information.

### Key Functions

- `process_gtfs()`: Processes uploaded GTFS files and populates the database.
- `generate_sql_query()`: Uses the LLM to generate SQL queries from natural language.
- `execute_sql_query()`: Runs SQL queries against the database.
- `humanize_query_result()`: Uses the LLM to create human-readable summaries of query results.
- `adjust_query()`: Attempts to fix failed queries using the LLM.

### Database Interaction

- The app uses SQLite for storing GTFS data.
- Database schema is dynamically retrieved and provided to the LLM for context.
- Sample data is cached to help the LLM understand the data structure.

### LLM Interaction

- The app uses a consistent prompt structure for LLM interactions.
- Different prompts are used for SQL generation, query adjustment, and result humanization.
- The LLM's responses are parsed and used directly in query execution and result presentation.

This detailed flow demonstrates how the app combines database operations, LLM capabilities, and web technologies to provide a seamless natural language interface for querying GTFS data.

## Debug Information

The app provides real-time debug information, including:
- File upload status
- LLM query details
- SQL query generation and execution
- Error messages and adjustments

## Customization

- To add support for additional LLM providers, modify the `llm_clients` dictionary in `app.py`.
- Adjust the GTFS table schema in the `get_db_schema()` function if needed.

## Security Considerations

- Ensure that your API keys are kept secret and not exposed in the codebase.
- Implement proper input validation and sanitization for user queries to prevent SQL injection attacks.

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

If you encounter any issues or have questions, please open an issue on the GitHub repository.
