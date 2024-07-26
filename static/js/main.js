const fileUpload = document.getElementById('file-upload');
const uploadForm = document.getElementById('upload-form');
const uploadStatus = document.getElementById('upload-status');
const uploadSuccess = document.getElementById('upload-success');
const uploadError = document.getElementById('upload-error');
const queryForm = document.getElementById('query-form');
const queryStatus = document.getElementById('query-status');
const resultContent = document.getElementById('result-content');
const debugInfo = document.getElementById('debug-info');
const llmSelector = document.getElementById('llm-selector');
const llmChangeStatus = document.getElementById('llm-change-status');
const debugToggle = document.getElementById('debug-toggle');
const debugDrawer = document.getElementById('debug-drawer');
const debugClose = document.getElementById('debug-close');
const mainContent = document.getElementById('main-content');

function toggleDebugDrawer() {
    debugDrawer.classList.toggle('translate-x-full');
    mainContent.classList.toggle('mr-96');
}

debugToggle.addEventListener('click', toggleDebugDrawer);
debugClose.addEventListener('click', toggleDebugDrawer);

fileUpload.addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        uploadFile(file);
    }
});

uploadForm.addEventListener('dragover', function(e) {
    e.preventDefault();
    e.stopPropagation();
});

uploadForm.addEventListener('drop', function(e) {
    e.preventDefault();
    e.stopPropagation();
    const file = e.dataTransfer.files[0];
    if (file) {
        uploadFile(file);
    }
});

function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    uploadStatus.classList.remove('hidden');
    uploadSuccess.classList.add('hidden');
    uploadError.classList.add('hidden');

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        uploadStatus.classList.add('hidden');
        uploadSuccess.classList.remove('hidden');
        updateDebugInfo(data.message);
    })
    .catch(error => {
        uploadStatus.classList.add('hidden');
        uploadError.classList.remove('hidden');
        updateDebugInfo('Error: ' + error.message);
    });
}

queryForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const query = document.getElementById('query-input').value;

    queryStatus.classList.remove('hidden');
    resultContent.innerHTML = '';

    fetch('/query', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({query: query})
    })
    .then(response => response.json())
    .then(data => {
        queryStatus.classList.add('hidden');
        if (data.error) {
            resultContent.innerHTML = `<p class="text-red-500">${data.error}</p>`;
        } else {
            displayResults(data.result);
            
            // Display the humanized result
            const humanizedResultElem = document.createElement('div');
            humanizedResultElem.className = 'mt-6 mb-8 p-4 bg-blue-50 border border-blue-200 rounded-lg shadow-sm';

            const humanizedTitle = document.createElement('h4');
            humanizedTitle.className = 'text-lg font-semibold text-blue-800 mb-2';
            humanizedTitle.textContent = 'Summary';
            humanizedResultElem.appendChild(humanizedTitle);

            const humanizedContent = document.createElement('div');
            humanizedContent.className = 'text-md text-gray-700 leading-relaxed';
            humanizedContent.innerHTML = data.humanized_result;
            humanizedResultElem.appendChild(humanizedContent);

            resultContent.prepend(humanizedResultElem);
        }
        updateDebugInfo(JSON.stringify(data, null, 2));
    })
    .catch(error => {
        queryStatus.classList.add('hidden');
        resultContent.innerHTML = `<p class="text-red-500">An error occurred: ${error.message}</p>`;
        updateDebugInfo('Error: ' + error.message);
    });
});

function displayResults(result) {
    if (result.error) {
        resultContent.innerHTML = `<p class="text-red-500">${result.error}</p>`;
        return;
    }

    const table = document.createElement('table');
    table.className = 'min-w-full divide-y divide-gray-200';

    // Create table header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    result.columns.forEach(column => {
        const th = document.createElement('th');
        th.className = 'px-6 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider';
        th.textContent = column;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Create table body
    const tbody = document.createElement('tbody');
    tbody.className = 'bg-white divide-y divide-gray-200';
    result.data.forEach(row => {
        const tr = document.createElement('tr');
        row.forEach(cell => {
            const td = document.createElement('td');
            td.className = 'px-6 py-4 whitespace-nowrap text-sm text-gray-500';
            td.textContent = cell;
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    resultContent.innerHTML = '';
    resultContent.appendChild(table);
}

// Modified function to fetch and populate the LLM options
function populateLLMOptions() {
    fetch('/available-llms')
        .then(response => response.json())
        .then(data => {
            llmSelector.innerHTML = '';
            data.forEach(([client, models]) => {
                models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = JSON.stringify({client, model});
                    option.textContent = `${client} - ${model}`;
                    llmSelector.appendChild(option);
                });
            });
        })
        .catch(error => {
            console.error('Error fetching LLM options:', error);
            updateDebugInfo('Error fetching LLM options: ' + error.message);
        });
}

// The rest of the code remains the same
function changeLLM(client, model) {
    llmChangeStatus.classList.remove('hidden');
    fetch('/change-llm-client', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({client, model})
    })
    .then(response => response.json())
    .then(data => {
        llmChangeStatus.classList.add('hidden');
        updateDebugInfo(data.message);
    })
    .catch(error => {
        llmChangeStatus.classList.add('hidden');
        console.error('Error changing LLM:', error);
        updateDebugInfo('Error changing LLM: ' + error.message);
    });
}

llmSelector.addEventListener('change', function() {
    const {client, model} = JSON.parse(this.value);
    changeLLM(client, model);
});

populateLLMOptions();

function updateDebugInfo(message) {
    const timestamp = new Date().toLocaleTimeString();
    debugInfo.innerHTML += `
        <div class="mb-2 p-2 bg-gray-700 rounded border border-gray-600">
            <span class="text-blue-300 mr-2">[${timestamp}]</span>
            <span class="whitespace-pre-wrap">${message}</span>
        </div>
    `;
    debugInfo.scrollTop = debugInfo.scrollHeight;
}

// SSE handler setup
const eventSource = new EventSource('/debug-stream');

eventSource.onmessage = function(event) {
    if (event.data.trim() !== '') {
        let eventData;
        try {
            eventData = JSON.parse(event.data);
        } catch (error) {
            eventData = event.data;
        }
        updateDebugInfo(eventData);
    }
};

eventSource.onerror = function(error) {
    console.error('EventSource failed:', error);
    updateDebugInfo('Debug stream connection lost. Reconnecting...');
};

