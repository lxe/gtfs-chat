// main.js

// DOM Elements
const fileUpload = document.getElementById('file-upload');
const fileName = document.getElementById('file-name');
const executeQueryBtn = document.getElementById('execute-query');
const queryInput = document.getElementById('query');
const resultsDiv = document.getElementById('results');
const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-message');
const debugToggle = document.getElementById('debug-toggle');
const debugDrawer = document.getElementById('debug-drawer');
const debugClose = document.getElementById('debug-close');
const debugInfo = document.getElementById('debug-info');
const debugColumn = document.getElementById('debug-column');
const leftColumn = document.getElementById('left-column');
const mainColumn = document.getElementById('main-column');
const llmModelSelect = document.getElementById('llm-model');

// State
const messages = [];

// Initial setup
queryInput.value = `SELECT 
    AVG(stop_lat) AS center_latitude,
    AVG(stop_lon) AS center_longitude,
    ST_AsText(ST_Centroid(ST_Collect(geometry))) AS geographic_center
FROM 
    stops;`;

// Helper Functions
function showLoadingSpinner() {
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner mb-2 p-2';
    spinner.innerHTML = '<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>';
    chatMessages.appendChild(spinner);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addMessage(message, isUser = false) {
    messages.push({ message, isUser });
    const messageElement = document.createElement('div');
    messageElement.className = `mb-2 p-2 rounded-lg ${isUser ? 'bg-blue-100 text-right' : 'bg-gray-100'}`;
    messageElement.innerHTML = message;
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addErrorMessage(errorText) {
    const errorElement = document.createElement('div');
    errorElement.className = 'mb-2 p-2 rounded-lg bg-red-100 text-red-700';
    errorElement.textContent = `Error: ${errorText}`;
    chatMessages.appendChild(errorElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function createTable(data) {
    const tableWrapper = document.createElement('div');
    tableWrapper.className = 'max-h-64 overflow-y-auto mt-4';
    const table = document.createElement('table');
    table.className = 'min-w-full divide-y divide-gray-200';
   
    const thead = document.createElement('thead');
    thead.className = 'bg-gray-50';
    const headerRow = document.createElement('tr');
    Object.keys(data[0]).forEach(key => {
        const th = document.createElement('th');
        th.className = 'px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider';
        th.textContent = key;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    tbody.className = 'bg-white divide-y divide-gray-200';
    data.forEach(row => {
        const tr = document.createElement('tr');
        Object.values(row).forEach(value => {
            const td = document.createElement('td');
            td.className = 'px-6 py-4 whitespace-nowrap text-sm text-gray-500';
            td.textContent = value;
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableWrapper.appendChild(table);
    return tableWrapper;
}

function addDebugEntry(entry) {
    const entryElement = document.createElement('div');
    entryElement.className = 'mb-2 p-2 border-b border-gray-700';
    entryElement.textContent = entry;
    debugInfo.appendChild(entryElement);
    debugInfo.scrollTop = debugInfo.scrollHeight;
}

// API Calls
function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    return fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json());
}

function executeQuery(query) {
    return fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
    })
    .then(response => response.json());
}

function callChatRoute() {
    const selectedModel = llmModelSelect.value;
    return fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            messages: messages.map(m => ({ 
                content: [{ type: 'text', text: m.message }], 
                role: m.isUser ? 'user' : 'assistant'
            })),
            company_model: selectedModel
        })
    })
    .then(response => response.json());
}

// Event Listeners
fileUpload.addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        fileName.textContent = `Selected file: ${file.name} (Uploading...)`;

        uploadFile(file)
            .then(data => {
                if (data.message) {
                    fileName.textContent = `${file.name} - ${data.message}`;
                } else if (data.error) {
                    fileName.textContent = `${file.name} - Error: ${data.error}`;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                fileName.textContent = `${file.name} - Error: ${error.message}`;
            });
    }
});

executeQueryBtn.addEventListener('click', function() {
    const query = queryInput.value;
    executeQuery(query)
        .then(data => {
            resultsDiv.innerHTML = '';
            if (Array.isArray(data) && data.length > 0) {
                resultsDiv.appendChild(createTable(data));
            } else {
                resultsDiv.textContent = JSON.stringify(data, null, 2);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
});

sendButton.addEventListener('click', function() {
    const message = userInput.value.trim();
    if (message) {
        addMessage(message, true);
        userInput.value = '';
        showLoadingSpinner();
        
        callChatRoute()
            .then(data => {
                console.log(data);
                addDebugEntry(JSON.stringify(data, null, 2));

                addMessage(data.summary);
                
                const tableElement = createTable(data.table);
                chatMessages.appendChild(tableElement);
                
                chatMessages.scrollTop = chatMessages.scrollHeight;

                if (data.query) {
                    queryInput.value = data.query;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                addDebugEntry(`Error: ${error.message}`);
                addErrorMessage(error.message);
            })
            .finally(() => {
                const spinner = document.querySelector('.loading-spinner');
                if (spinner) {
                    spinner.remove();
                }
            });
    }
});

userInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendButton.click();
    }
});

debugToggle.addEventListener('click', function() {
    debugColumn.classList.toggle('w-0');
    debugColumn.classList.toggle('w-1/4');
    leftColumn.classList.toggle('w-1/3');
    leftColumn.classList.toggle('w-1/4');
    mainColumn.classList.toggle('w-2/3');
    mainColumn.classList.toggle('w-1/2');
    debugDrawer.classList.toggle('hidden');
});

debugClose.addEventListener('click', function() {
    debugToggle.click();
});

// Function to fetch and populate the model dropdown
function populateModelDropdown() {
    fetch('/get_available_models')
        .then(response => response.json())
        .then(models => {
            llmModelSelect.innerHTML = '';
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                llmModelSelect.appendChild(option);
            });
        })
        .catch(error => console.error('Error fetching models:', error));
}

// Initial setup
document.addEventListener('DOMContentLoaded', () => {
    populateModelDropdown();
});

// Add this to your DOM Elements section
const clearChatBtn = document.getElementById('clear-chat');

// Add this function to your Helper Functions section
function clearChat() {
    chatMessages.innerHTML = '';
    messages.length = 0;
    queryInput.value = '';
    resultsDiv.innerHTML = '';
}

// Add this to your Event Listeners section
clearChatBtn.addEventListener('click', function() {
    if (confirm('Are you sure you want to clear the chat? This action cannot be undone.')) {
        clearChat();
    }
});