// Lucifer AI functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize UI elements
    initLuciferUI();
    
    // Add event listeners
    setupLuciferEventListeners();
});

function initLuciferUI() {
    // Check if AI tabs already exist
    if (document.getElementById('aiSummaryTab')) {
        return; // Already initialized
    }
    
    // Add AI tabs to the PDF details modal if it exists
    const pdfDetailsContent = document.querySelector('.pdf-details-content');
    if (pdfDetailsContent) {
        // Add tabs
        const tabsContainer = document.createElement('div');
        tabsContainer.className = 'nav nav-tabs mb-3';
        tabsContainer.id = 'pdfDetailsTabs';
        
        tabsContainer.innerHTML = `
            <button class="nav-link active" id="basicTab" data-bs-toggle="tab" data-bs-target="#basicContent" type="button">Basic Info</button>
            <button class="nav-link" id="aiSummaryTab" data-bs-toggle="tab" data-bs-target="#aiSummaryContent" type="button">AI Summary</button>
        `;
        
        // Add tab content
        const tabContent = document.createElement('div');
        tabContent.className = 'tab-content';
        
        // Move existing content into the first tab
        const existingContent = pdfDetailsContent.innerHTML;
        pdfDetailsContent.innerHTML = '';
        
        // Create the basic info tab
        const basicContent = document.createElement('div');
        basicContent.className = 'tab-pane fade show active';
        basicContent.id = 'basicContent';
        basicContent.innerHTML = existingContent;
        
        // Create the AI summary tab
        const aiSummaryContent = document.createElement('div');
        aiSummaryContent.className = 'tab-pane fade';
        aiSummaryContent.id = 'aiSummaryContent';
        aiSummaryContent.innerHTML = `
            <div class="text-center mb-3" id="aiSummaryLoading" style="display: none;">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading AI Summary...</span>
                </div>
                <p class="mt-2">Generating AI Summary...</p>
            </div>
            <div id="aiSummaryContent" class="ai-summary-container">
                <div class="text-center">
                    <button id="generateAiSummaryBtn" class="btn btn-primary btn-glow">
                        <i class="fas fa-robot me-2"></i>Generate AI Summary
                    </button>
                </div>
                <div id="aiSummaryResult" class="mt-3" style="display: none;"></div>
            </div>
        `;
        
        // Add the tab content to the container
        tabContent.appendChild(basicContent);
        tabContent.appendChild(aiSummaryContent);
        
        // Add the tabs and content to the modal
        pdfDetailsContent.appendChild(tabsContainer);
        pdfDetailsContent.appendChild(tabContent);
    }
    
    // Remove AI toggle since we use Lucifer by default
    const questionForm = document.getElementById('questionForm');
    if (questionForm) {
        // Add compare button
        const compareButton = document.createElement('button');
        compareButton.type = 'button';
        compareButton.id = 'compareAnswersBtn';
        compareButton.className = 'btn btn-outline-info ms-2';
        compareButton.innerHTML = '<i class="fas fa-balance-scale me-1"></i> Compare';
        
        // Add to the form
        questionForm.querySelector('.input-group').appendChild(compareButton);
        
        // Add comparison result container
        const answerContainer = document.getElementById('answerContainer');
        if (answerContainer) {
            const comparisonContainer = document.createElement('div');
            comparisonContainer.id = 'comparisonContainer';
            comparisonContainer.className = 'p-3 mt-4';
            comparisonContainer.style.display = 'none';
            comparisonContainer.innerHTML = `
                <h4 class="mb-3"><i class="fas fa-balance-scale me-2"></i>Answer Comparison</h4>
                <div class="row">
                    <div class="col-md-6">
                        <div class="card mb-3">
                            <div class="card-header">Standard Answer</div>
                            <div class="card-body" id="standardAnswerComp"></div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">Lucifer AI Answer</div>
                            <div class="card-body" id="aiAnswerComp"></div>
                        </div>
                    </div>
                </div>
            `;
            
            answerContainer.parentNode.insertBefore(comparisonContainer, answerContainer.nextSibling);
        }
    }
}

function setupLuciferEventListeners() {
    // Listen for the generate AI summary button
    const generateAiSummaryBtn = document.getElementById('generateAiSummaryBtn');
    if (generateAiSummaryBtn) {
        generateAiSummaryBtn.addEventListener('click', function() {
            generateAiSummary();
        });
    }
    
    // Listen for compare button
    const compareAnswersBtn = document.getElementById('compareAnswersBtn');
    if (compareAnswersBtn) {
        compareAnswersBtn.addEventListener('click', function() {
            compareAnswers();
        });
    }
    
    // Modify question form to directly use Lucifer
    const questionForm = document.getElementById('questionForm');
    if (questionForm) {
        // Keep the default form submission
    }
}

function generateAiSummary() {
    // Get the current PDF ID
    const pdfId = getCurrentPdfId();
    if (!pdfId) {
        showErrorNotification('Cannot generate summary: No PDF selected');
        return;
    }
    
    // Show loading indicator
    const loadingIndicator = document.getElementById('aiSummaryLoading');
    const resultContainer = document.getElementById('aiSummaryResult');
    
    if (loadingIndicator) loadingIndicator.style.display = 'block';
    if (resultContainer) resultContainer.style.display = 'none';
    
    // Fetch AI summary from the server
    fetch(`/pdf/${pdfId}/ai-summary`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to generate AI summary. Status: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            // Hide loading indicator
            if (loadingIndicator) loadingIndicator.style.display = 'none';
            
            if (data.success) {
                // Show the result
                if (resultContainer) {
                    // Format the summary with nice styling
                    let html = `<div class="ai-summary-content">`;
                    
                    // Add the main summary
                    html += `<div class="ai-summary-text">${formatSummaryText(data.ai_summary)}</div>`;
                    
                    // Add keywords if available
                    if (data.keywords && data.keywords.length > 0) {
                        html += `<div class="ai-keywords mt-3">
                            <strong>Keywords:</strong> 
                            <div class="keyword-list">`;
                        
                        data.keywords.forEach(keyword => {
                            html += `<span class="keyword-badge">${keyword}</span>`;
                        });
                        
                        html += `</div>
                        </div>`;
                    }
                    
                    // Add metadata
                    html += `<div class="ai-metadata mt-3">
                        <small class="text-muted">Generated by ${data.generator} | Document: ${data.filename}</small>
                    </div>`;
                    
                    html += `</div>`;
                    
                    resultContainer.innerHTML = html;
                    resultContainer.style.display = 'block';
                    
                    // Add button to regenerate
                    const regenerateBtn = document.createElement('button');
                    regenerateBtn.className = 'btn btn-sm btn-outline-primary mt-3';
                    regenerateBtn.innerHTML = '<i class="fas fa-sync-alt me-1"></i> Regenerate';
                    regenerateBtn.addEventListener('click', generateAiSummary);
                    resultContainer.appendChild(regenerateBtn);
                }
                
                // Show success notification
                Swal.fire({
                    title: 'Success',
                    text: 'AI summary generated successfully',
                    icon: 'success',
                    timer: 2000,
                    timerProgressBar: true,
                    showConfirmButton: false
                });
            } else {
                // Show error in the container
                if (resultContainer) {
                    resultContainer.innerHTML = `<div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        ${data.message || 'Failed to generate AI summary'}
                    </div>`;
                    resultContainer.style.display = 'block';
                }
                
                // Show error notification
                showErrorNotification(data.message || 'Failed to generate AI summary');
            }
        })
        .catch(error => {
            // Hide loading indicator
            if (loadingIndicator) loadingIndicator.style.display = 'none';
            
            console.error('Error generating AI summary:', error);
            
            // Show error in the container
            if (resultContainer) {
                resultContainer.innerHTML = `<div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    ${error.message}
                </div>`;
                resultContainer.style.display = 'block';
            }
            
            // Show error notification
            showErrorNotification(error.message);
        });
}

function compareAnswers() {
    const question = document.getElementById('question').value.trim();
    
    if (!question) {
        // Show warning for empty question
        Swal.fire({
            title: 'Warning!',
            text: 'Please enter a question to compare answers',
            icon: 'warning',
            confirmButtonText: 'OK'
        });
        return;
    }
    
    // Optional: Get PDF ID if we're viewing a specific PDF
    const pdfId = getCurrentPdfId();
    
    // Disable compare button and show loading state
    const compareBtn = document.getElementById('compareAnswersBtn');
    if (compareBtn) {
        compareBtn.disabled = true;
        compareBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    }
    
    // Prepare request data
    const requestData = {
        question: question
    };
    
    // Add PDF ID if available
    if (pdfId) {
        requestData.pdf_id = pdfId;
    }
    
    // Send the request
    fetch('/compare-answers', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        // Re-enable button
        if (compareBtn) {
            compareBtn.disabled = false;
            compareBtn.innerHTML = '<i class="fas fa-balance-scale me-1"></i> Compare';
        }
        
        if (data.success) {
            // Show the comparison container
            const comparisonContainer = document.getElementById('comparisonContainer');
            if (comparisonContainer) {
                comparisonContainer.style.display = 'block';
                
                // Update the content
                const standardAnswerComp = document.getElementById('standardAnswerComp');
                const aiAnswerComp = document.getElementById('aiAnswerComp');
                
                if (standardAnswerComp) {
                    standardAnswerComp.innerHTML = formatAnswerText(data.regular_answer);
                }
                
                if (aiAnswerComp) {
                    aiAnswerComp.innerHTML = data.ai_success 
                        ? formatAnswerText(data.ai_answer)
                        : `<div class="alert alert-warning">AI answer not available</div>`;
                }
                
                // Scroll to the comparison
                comparisonContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        } else {
            // Show error notification
            Swal.fire({
                title: 'Error!',
                text: data.message || 'Failed to compare answers',
                icon: 'error',
                confirmButtonText: 'OK'
            });
        }
    })
    .catch(error => {
        console.error('Error comparing answers:', error);
        
        // Re-enable button
        if (compareBtn) {
            compareBtn.disabled = false;
            compareBtn.innerHTML = '<i class="fas fa-balance-scale me-1"></i> Compare';
        }
        
        // Show error notification
        Swal.fire({
            title: 'Error!',
            text: 'An error occurred while comparing answers: ' + error.message,
            icon: 'error',
            confirmButtonText: 'OK'
        });
    });
}

// Helper functions
function getCurrentPdfId() {
    // Try to get PDF ID from the URL or the current view
    const urlParams = new URLSearchParams(window.location.search);
    const pdfId = urlParams.get('pdf_id');
    
    if (pdfId) {
        return pdfId;
    }
    
    // Try to get from modal if open
    const pdfModal = document.querySelector('.modal.show');
    if (pdfModal) {
        const pdfIdAttribute = pdfModal.getAttribute('data-pdf-id');
        if (pdfIdAttribute) {
            return pdfIdAttribute;
        }
    }
    
    return null;
}

function formatSummaryText(text) {
    // Replace newlines with proper HTML breaks
    text = text.replace(/\n/g, '<br>');
    
    // Convert Markdown headings to HTML
    text = text.replace(/^# (.*?)$/gm, '<h3>$1</h3>');
    text = text.replace(/^## (.*?)$/gm, '<h4>$1</h4>');
    text = text.replace(/^### (.*?)$/gm, '<h5>$1</h5>');
    
    // Convert Markdown bullet points to HTML
    text = text.replace(/^\* (.*?)$/gm, '<li>$1</li>');
    text = text.replace(/^- (.*?)$/gm, '<li>$1</li>');
    
    // Wrap lists in ul tags
    text = text.replace(/<li>(.*?)<\/li>(\s*<li>)/g, '<li>$1</li>$2');
    text = text.replace(/<li>(.*?)<\/li>(\s*<br>)/g, '<li>$1</li></ul>$2');
    text = text.replace(/(<br>|^)\s*<li>/g, '$1<ul><li>');
    
    // Convert Markdown bold to HTML
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/__(.*?)__/g, '<strong>$1</strong>');
    
    // Convert Markdown italic to HTML
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    text = text.replace(/_(.*?)_/g, '<em>$1</em>');
    
    return text;
}

function formatAnswerText(text) {
    // More basic formatting for answers
    text = text.replace(/\n/g, '<br>');
    
    return text;
}

function showErrorNotification(message) {
    Swal.fire({
        title: 'Error',
        text: message,
        icon: 'error',
        confirmButtonText: 'OK'
    });
} 