// Lucifer AI integration - Main wrapper for AI functionality
// This file initializes the Gemini AI integration and advanced features

document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing Lucifer AI...');
    
    // Create new UI layout with sidebar
    createSidebarLayout();
    
    // Load the Gemini integration
    loadScript('/static/js/gemini.js', function() {
        console.log('Gemini AI module loaded successfully');
        
        // Add AI badge to the header
        addAIBadgeToHeader();
        
        // Initialize AI context menu for PDFs
        initializeAIContextMenu();
        
        // Add delete buttons to PDF items (with delay to ensure DOM is ready)
        setTimeout(function() {
            addDeleteButtonsToPDFs();
        }, 500);
    });
    
    // Initialize direct question button if it exists
    initializeDirectQuestionButton();
    
    // Override the standard question form submission to intercept and fix source display
    overrideQuestionForm();
});

// Create new sidebar layout
function createSidebarLayout() {
    // Check if container exists
    const container = document.querySelector('.container');
    if (!container) return;
    
    // Create wrapper for new layout
    const wrapper = document.createElement('div');
    wrapper.className = 'app-wrapper';
    wrapper.style.display = 'flex';
    wrapper.style.height = '100vh';
    wrapper.style.maxHeight = '100vh';
    wrapper.style.overflow = 'hidden';
    
    // Create sidebar
    const sidebar = document.createElement('div');
    sidebar.className = 'app-sidebar';
    sidebar.style.width = '280px';
    sidebar.style.backgroundColor = '#f8f9fa';
    sidebar.style.borderRight = '1px solid #dee2e6';
    sidebar.style.padding = '15px';
    sidebar.style.display = 'flex';
    sidebar.style.flexDirection = 'column';
    sidebar.style.height = '100%';
    sidebar.style.overflowY = 'auto';
    
    // Create main content area
    const mainContent = document.createElement('div');
    mainContent.className = 'app-main-content';
    mainContent.style.flex = '1';
    mainContent.style.overflowY = 'auto';
    mainContent.style.padding = '20px';
    
    // Add sidebar sections
    sidebar.innerHTML = `
        <div class="sidebar-header mb-4">
            <h4 class="mb-0"><i class="fas fa-book-reader me-2"></i>PDF Book</h4>
            <div class="small text-muted">Powered by Lucifer AI</div>
        </div>
        
        <div class="sidebar-section mb-4">
            <div class="section-header d-flex align-items-center mb-3">
                <h5 class="mb-0"><i class="fas fa-file-pdf me-2"></i>PDF Management</h5>
            </div>
            <div class="section-content">
                <button id="sidebarUploadBtn" class="btn btn-primary btn-block w-100">
                    <i class="fas fa-cloud-upload-alt me-2"></i>Upload PDF
                </button>
                <div id="sidebarPdfList" class="mt-3">
                    <!-- PDFs will be listed here -->
                </div>
            </div>
        </div>
        
        <div class="sidebar-section mb-4">
            <div class="section-header d-flex align-items-center mb-3">
                <h5 class="mb-0"><i class="fas fa-robot me-2"></i>AI Chat</h5>
            </div>
            <div class="section-content">
                <button id="startNewChatBtn" class="btn btn-outline-primary btn-block w-100">
                    <i class="fas fa-plus-circle me-2"></i>New Chat
                </button>
            </div>
        </div>
        
        <div class="sidebar-section">
            <div class="section-header d-flex align-items-center mb-3">
                <h5 class="mb-0"><i class="fas fa-history me-2"></i>Chat History</h5>
            </div>
            <div class="section-content">
                <div id="chatHistoryList">
                    <!-- Chat history will be listed here -->
                </div>
            </div>
        </div>
    `;
    
    // Move the existing content to the main content area
    while (container.firstChild) {
        mainContent.appendChild(container.firstChild);
    }
    
    // Add sidebar and main content to wrapper
    wrapper.appendChild(sidebar);
    wrapper.appendChild(mainContent);
    
    // Add wrapper to container
    container.appendChild(wrapper);
    
    // Setup sidebar event listeners
    setupSidebarEvents();
}

// Setup sidebar event listeners
function setupSidebarEvents() {
    // Setup upload button
    const uploadBtn = document.getElementById('sidebarUploadBtn');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', function() {
            // Create a file input
            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = '.pdf';
            fileInput.multiple = true;
            fileInput.style.display = 'none';
            
            // Add to body and trigger click
            document.body.appendChild(fileInput);
            fileInput.click();
            
            // Handle file selection
            fileInput.addEventListener('change', function() {
                if (fileInput.files && fileInput.files.length > 0) {
                    uploadPDFFiles(fileInput.files);
                }
                
                // Remove the input
                document.body.removeChild(fileInput);
            });
        });
    }
    
    // Setup new chat button
    const newChatBtn = document.getElementById('startNewChatBtn');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', function() {
            startNewChat();
        });
    }
    
    // Refresh PDF list in sidebar
    refreshSidebarPdfList();
}

// Upload PDF files
function uploadPDFFiles(files) {
    // Show loading indicator
    Swal.fire({
        title: 'Uploading PDFs',
        text: 'Please wait while we upload your files...',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
        formData.append('file', files[i]);
    }
    
    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Upload failed with status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            // Clear any session storage cache for PDFs to ensure freshness
            Object.keys(sessionStorage).forEach(key => {
                if (key.startsWith('checked_pdf_') || key.startsWith('pdf_name_')) {
                    sessionStorage.removeItem(key);
                }
            });
            
            Swal.fire({
                title: 'Success!',
                text: 'PDFs uploaded successfully',
                icon: 'success',
                timer: 2000,
                timerProgressBar: true,
                showConfirmButton: false
            });
            
            // Refresh PDF list and automatically select the first uploaded PDF
            refreshSidebarPdfList(true);
        } else {
            Swal.fire({
                title: 'Error!',
                text: data.message || 'Failed to upload PDFs',
                icon: 'error',
                confirmButtonText: 'OK'
            });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        
        Swal.fire({
            title: 'Error!',
            text: 'An error occurred during upload: ' + error.message,
            icon: 'error',
            confirmButtonText: 'OK'
        });
    });
}

// Refresh PDF list in sidebar
function refreshSidebarPdfList(selectFirstPdf = false) {
    const pdfListContainer = document.getElementById('sidebarPdfList');
    if (!pdfListContainer) return;
    
    // Show loading state
    pdfListContainer.innerHTML = '<div class="text-center py-3"><div class="spinner-border text-primary" role="status"></div></div>';
    
    // Fetch PDFs
    fetch('/pdfs')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to fetch PDFs with status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.pdfs && data.pdfs.length > 0) {
                let html = '<ul class="list-group pdf-sidebar-list">';
                
                // Store the first PDF ID for later use
                const firstPdfId = data.pdfs[0].id;
                
                data.pdfs.forEach(pdf => {
                    // Make sure to use a safe filename - extract actual filename from original_filename
                    let displayName = pdf.original_filename || `PDF #${pdf.id}`;
                    
                    // Remove file extension for cleaner display
                    displayName = displayName.replace(/\.[^/.]+$/, "");
                    
                    html += `
                        <li class="list-group-item d-flex justify-content-between align-items-center pdf-sidebar-item" data-id="${pdf.id}" data-filename="${displayName}">
                            <div class="pdf-name text-truncate" style="max-width: 170px;" title="${displayName}">
                                <i class="fas fa-file-pdf me-2 text-danger"></i>${displayName}
                            </div>
                            <div class="pdf-actions">
                                <button class="btn btn-sm btn-danger delete-pdf-btn" data-pdf-id="${pdf.id}" title="Delete PDF">
                                    <i class="fas fa-trash-alt"></i>
                                </button>
                            </div>
                        </li>
                    `;
                });
                
                html += '</ul>';
                pdfListContainer.innerHTML = html;
                
                // Add event listeners to PDF items
                addPdfItemListeners();
                
                // Auto-select the first PDF if requested
                if (selectFirstPdf && firstPdfId) {
                    setTimeout(() => {
                        selectPDF(firstPdfId.toString());
                    }, 100);
                }
            } else {
                pdfListContainer.innerHTML = '<div class="text-muted text-center py-3">No PDFs uploaded yet</div>';
            }
        })
        .catch(error => {
            console.error('Error fetching PDFs:', error);
            pdfListContainer.innerHTML = `<div class="text-danger text-center py-3">
                Error loading PDFs<br>
                <small>${error.message}</small><br>
                <button class="btn btn-sm btn-outline-primary mt-2" onclick="refreshSidebarPdfList()">Retry</button>
            </div>`;
        });
}

// Add event listeners to PDF items in sidebar
function addPdfItemListeners() {
    console.log("Adding PDF item listeners");
    
    // Find all PDF items
    const pdfItems = document.querySelectorAll('.pdf-sidebar-item');
    console.log(`Found ${pdfItems.length} PDF items in sidebar`);
    
    pdfItems.forEach(item => {
        // Add click event listener
        item.addEventListener('click', function(e) {
            const pdfId = this.dataset.id;
            console.log(`PDF item clicked: ${pdfId}`);
            
            // If this is the delete button, don't select the PDF
            if (e.target.closest('.delete-pdf-btn')) {
                console.log("Delete button clicked, not selecting PDF");
                return;
            }
            
            // Deselect all other PDFs
            pdfItems.forEach(p => {
                p.classList.remove('active');
                p.style.backgroundColor = '';
            });
            
            // Select this PDF
            this.classList.add('active');
            this.style.backgroundColor = '#e9ecef';
            
            // Initialize chat with this PDF
            selectPDF(pdfId);
        });
        
        // Add delete button listener
        const deleteBtn = item.querySelector('.delete-pdf-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function(e) {
                e.stopPropagation(); // Prevent PDF selection
                const pdfId = this.dataset.pdfId;
                console.log(`Delete button clicked for PDF ${pdfId}`);
                confirmDeletePDF(pdfId);
            });
        }
    });
    
    console.log("PDF item listeners added");
}

// Select a PDF
function selectPDF(pdfId) {
    if (!pdfId) {
        console.error('Cannot select PDF: No PDF ID provided');
        return;
    }
    
    console.log('Selecting PDF ID:', pdfId);
    
    // Highlight selected PDF
    const pdfItems = document.querySelectorAll('.pdf-sidebar-item');
    let foundItem = false;
    
    pdfItems.forEach(item => {
        if (item.dataset.id === pdfId) {
            item.classList.add('active');
            item.style.backgroundColor = '#e9ecef';
            foundItem = true;
            console.log(`Found and highlighted PDF item with ID ${pdfId}`);
        } else {
            item.classList.remove('active');
            item.style.backgroundColor = '';
        }
    });
    
    // Check if we found the item in the sidebar
    if (!foundItem) {
        console.warn(`PDF item with ID ${pdfId} not found in the sidebar, but continuing with chat interface`);
    }
    
    // Update chat UI to show we're chatting with this PDF
    initChatWithPDF(pdfId);
}

// Initialize chat with PDF
function initChatWithPDF(pdfId) {
    console.log(`Initializing chat with PDF ID: ${pdfId}`);
    
    if (!pdfId) {
        console.error("Cannot initialize chat: No PDF ID provided");
        return;
    }
    
    // Get PDF name - use a fallback if not found
    let pdfName = getPDFNameById(pdfId) || `PDF ${pdfId}`;
    console.log(`Using PDF name: ${pdfName} for chat`);
    
    // Make sure we're not using a generic format with # symbols
    if (pdfName.includes('#')) {
        pdfName = pdfName.replace('#', '');
        pdfName = pdfName.trim();
    }
    
    // Update main content area with chat interface immediately
    const mainContent = document.querySelector('.app-main-content');
    if (mainContent) {
        console.log("Updating main content area with chat interface");
        
        mainContent.innerHTML = `
            <div class="chat-container">
                <div class="chat-header">
                    <h3><i class="fas fa-comments me-2"></i>Chat with ${pdfName}</h3>
                    <p class="text-muted">Ask questions about this document or any general topic</p>
                </div>
                
                <div class="chat-messages" id="chatMessages">
                    <div class="system-message">
                        <div class="message-content">
                            <p>Hello! I'm Lucifer AI. You can ask me questions about ${pdfName} or general questions like "What is Flask?" 👋</p>
                        </div>
                    </div>
                </div>
                
                <div class="chat-input">
                    <form id="chatForm" class="d-flex">
                        <input type="hidden" id="chatPdfId" value="${pdfId}">
                        <input type="text" id="chatQuestion" class="form-control" placeholder="Ask about the PDF or any topic...">
                        <button type="submit" class="btn btn-primary ms-2">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </form>
                </div>
            </div>
        `;
        
        // Add event listener to chat form
        const chatForm = document.getElementById('chatForm');
        if (chatForm) {
            console.log("Adding event listener to chat form");
            
            chatForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const question = document.getElementById('chatQuestion').value.trim();
                const pdfIdFromForm = document.getElementById('chatPdfId').value;
                
                console.log(`Chat form submitted with question: ${question}, PDF ID: ${pdfIdFromForm}`);
                
                if (question) {
                    console.log("Sending chat question");
                    sendChatQuestion(question, pdfIdFromForm);
                    document.getElementById('chatQuestion').value = '';
                } else {
                    console.log("Empty question submitted");
                    
                    // Alert user to enter a question
                    const chatMessages = document.getElementById('chatMessages');
                    if (chatMessages) {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'error-message';
                        errorDiv.innerHTML = `<div class="message-content"><p>Please type a question first.</p></div>`;
                        chatMessages.appendChild(errorDiv);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                        
                        // Remove the error message after 3 seconds
                        setTimeout(() => {
                            errorDiv.remove();
                        }, 3000);
                    }
                }
            });
            
            // Focus the input field
            setTimeout(() => {
                const chatQuestion = document.getElementById('chatQuestion');
                if (chatQuestion) {
                    chatQuestion.focus();
                }
            }, 100);
        } else {
            console.error("Chat form not found after initializing chat interface");
        }
    } else {
        console.error("Main content area not found");
    }
    
    // Try to fetch PDF info in background to update the UI with the correct name
    // But don't block the chat functionality if this fails
    if (pdfName === `PDF ${pdfId}`) {
        console.log(`Fetching info for PDF ${pdfId} to update UI`);
        
        fetch(`/pdf/${pdfId}/info`)
            .then(response => {
                if (!response.ok) {
                    console.log(`Could not fetch info for PDF ${pdfId}, but continuing with chat`);
                    return null;
                }
                return response.json();
            })
            .then(data => {
                if (data && data.success && data.filename) {
                    // Clean up filename
                    let cleanFilename = data.filename.replace(/\.[^/.]+$/, "") || `PDF ${pdfId}`;
                    console.log(`Updated PDF name from API: ${cleanFilename}`);
                    
                    // Update the chat header with the correct name
                    const chatHeader = document.querySelector('.chat-header h3');
                    if (chatHeader) {
                        chatHeader.innerHTML = `<i class="fas fa-comments me-2"></i>Chat with ${cleanFilename}`;
                    }
                    
                    // Update the welcome message
                    const welcomeMsg = document.querySelector('#chatMessages .system-message .message-content p');
                    if (welcomeMsg) {
                        welcomeMsg.innerHTML = `Hello! I'm Lucifer AI. You can ask me questions about ${cleanFilename} or general questions like "What is Flask?" 👋`;
                    }
                    
                    // Store the name for later use
                    const pdfItem = document.querySelector(`.pdf-sidebar-item[data-id="${pdfId}"]`);
                    if (pdfItem) {
                        pdfItem.dataset.filename = cleanFilename;
                    }
                }
            })
            .catch(err => {
                console.error('Error fetching PDF info, but continuing with chat:', err);
            });
    }
}

// Send chat question
async function sendChatQuestion(question, pdfId) {
    // If the question is provided as a parameter, use it
    // Otherwise try to get it from the input field
    if (!question) {
        const questionInput = document.getElementById('chatQuestion');
        if (!questionInput) {
            console.error("Question input element not found");
            return;
        }
        question = questionInput.value.trim();
        
        if (!question) {
            console.warn("Empty question submitted");
            return;
        }
        
        // Clear the input field and focus it for the next question
        questionInput.value = '';
        questionInput.focus();
    }
    
    console.log(`Processing question: "${question}" for PDF ID: ${pdfId}`);
    
    // Add the user's question to the chat
    addMessageToChat('user', question);
    
    // Check if the question is small talk
    if (isSmallTalk(question)) {
        // Generate a small talk response
        const response = generateSmallTalkResponse(question);
        
        // Simulate a brief delay as if processing
        await new Promise(resolve => setTimeout(resolve, 800));
        
        // Add the response to the chat
        addMessageToChat('ai', response);
        return;
    }
    
    // Check if it's a general knowledge question
    if (isGeneralKnowledgeQuestion(question)) {
        try {
            // Show typing indicator
            addTypingIndicator();
            
            // Send to general knowledge endpoint
            const response = await fetch('/general-knowledge', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question }),
            });
            
            // If we get a 500 error, it likely means the gemini_model is not defined
            // So we'll skip directly to the PDF question function
            if (response.status === 500) {
                console.log("Server error (500) from general knowledge endpoint, falling back to PDF search");
                removeTypingIndicator();
                sendPdfQuestion(question, pdfId);
                return;
            }
            
            // Remove typing indicator
            removeTypingIndicator();
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // Add the AI's answer to the chat
                    addMessageToChat('ai', data.answer, data.source, true);
                    
                    // Save to chat history if we have a PDF ID
                    if (pdfId) {
                        saveChatHistory(pdfId, question, data.answer);
                    }
                } else {
                    // If general knowledge fails, fall back to searching PDF
                    sendPdfQuestion(question, pdfId);
                }
            } else {
                // Fall back to PDF question if general knowledge endpoint fails
                sendPdfQuestion(question, pdfId);
            }
        } catch (error) {
            console.error('Error sending general knowledge question:', error);
            removeTypingIndicator();
            // Fall back to PDF-specific question
            sendPdfQuestion(question, pdfId);
        }
    } else {
        // Send as PDF-specific question
        sendPdfQuestion(question, pdfId);
    }
}

// Function to handle PDF-specific questions
function sendPdfQuestion(question, pdfId) {
    console.log("Sending PDF-specific question:", question, "for PDF ID:", pdfId);
    
    // Show typing indicator
    addTypingIndicator();
    
    // Prepare request data - always include the question
    const requestData = {
        question: question
    };
    
    // Only add pdf_id if it's valid
    if (pdfId && pdfId !== 'undefined' && pdfId !== 'null') {
        requestData.pdf_id = pdfId;
        console.log("Including PDF ID in request:", pdfId);
    } else {
        console.log("Sending question without PDF context");
    }
    
    // Send request to server
    fetch('/ask-ai', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        console.log("Response status:", response.status);
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log("Received data:", data);
        
        // Remove typing indicator
        removeTypingIndicator();
        
        if (data && data.success && data.answer) {
            // Add AI response to chat with typing animation
            addMessageToChat('ai', data.answer, data.sources, true);
            
            // Save chat to history with source
            saveChatHistory(pdfId, question, data.answer, data.sources);
        } else {
            console.log("AI endpoint returned no answer or error, trying regular endpoint");
            
            // Show an informative message about trying alternative method
            addMessageToChat('system', 'I\'m finding the answer in a different way...', null, false);
            
            // Try the regular ask endpoint as fallback
            return fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Fallback responded with status: ${response.status}`);
                }
                return response.json();
            })
            .then(fallbackData => {
                console.log("Fallback data:", fallbackData);
                
                if (fallbackData && fallbackData.success && fallbackData.answer) {
                    // Add fallback response to chat
                    addMessageToChat('ai', fallbackData.answer, fallbackData.source, true);
                    
                    // Save chat to history with source
                    saveChatHistory(pdfId, question, fallbackData.answer, fallbackData.source);
                } else {
                    // Add helpful error message for final failure
                    addMessageToChat('error', 'I couldn\'t find any information about that. Please try asking a different question.', null, false);
                }
            })
            .catch(fallbackError => {
                console.error('Fallback error:', fallbackError);
                addMessageToChat('error', 'I couldn\'t process your question. Please try again.', null, false);
            });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        
        // Remove typing indicator
        removeTypingIndicator();
        
        // Try direct fallback without showing error message first
        console.log("Connection error, trying direct fallback to /ask endpoint");
        
        fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Direct fallback responded with status: ${response.status}`);
            }
            return response.json();
        })
        .then(directFallbackData => {
            console.log("Direct fallback data:", directFallbackData);
            
            if (directFallbackData && directFallbackData.success && directFallbackData.answer) {
                // Add fallback response to chat
                addMessageToChat('ai', directFallbackData.answer, directFallbackData.source, true);
                
                // Save chat to history with source
                saveChatHistory(pdfId, question, directFallbackData.answer, directFallbackData.source);
            } else {
                // Add user-friendly error message
                addMessageToChat('error', 'I couldn\'t find any relevant information. Try asking a different question.', null, false);
            }
        })
        .catch(directFallbackError => {
            console.error('Direct fallback error:', directFallbackError);
            addMessageToChat('error', 'There was a problem processing your request. Please check your connection and try again.', null, false);
        });
    });
}

// Add message to chat
function addMessageToChat(type, message, source = null, withTyping = false) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = type === 'user' ? 'user-message' : (type === 'ai' ? 'ai-message' : 'error-message');
    
    if (type === 'ai' && withTyping) {
        // Add empty content that will be filled character by character
        let htmlContent = `<div class="message-content"><p class="typing-text"></p>`;
        
        // Add source for AI messages
        if (source) {
            // Check if there are multiple sources
            if (source.includes(',')) {
                const sources = source.split(',').map(s => s.trim()).filter(Boolean);
                if (sources.length > 1) {
                    htmlContent += `<div class="message-source" data-source-ids="${sources.map(s => {
                        // Extract PDF ID if format is "PDF X"
                        const match = s.match(/PDF\s+(\d+)/i);
                        return match ? match[1] : '';
                    }).join(',')}"><small><i class="fas fa-file-pdf me-1"></i>Sources:</small>`;
                    htmlContent += `<ul class="mb-0 ps-3 mt-1">`;
                    sources.forEach(src => {
                        htmlContent += `<li><small>${src}</small></li>`;
                    });
                    htmlContent += `</ul></div>`;
                } else if (sources.length === 1) {
                    // Extract PDF ID if format is "PDF X"
                    const match = sources[0].match(/PDF\s+(\d+)/i);
                    const pdfId = match ? match[1] : '';
                    
                    htmlContent += `<div class="message-source" data-source-id="${pdfId}"><small><i class="fas fa-file-pdf me-1"></i>Source: ${sources[0]}</small></div>`;
                }
            } else {
                // Extract PDF ID if format is "PDF X"
                const match = source.match(/PDF\s+(\d+)/i);
                const pdfId = match ? match[1] : '';
                
                htmlContent += `<div class="message-source" data-source-id="${pdfId}"><small><i class="fas fa-file-pdf me-1"></i>Source: ${source}</small></div>`;
            }
        }
        
        htmlContent += '</div>';
        messageDiv.innerHTML = htmlContent;
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to new message
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        // Start typing animation
        const typingText = messageDiv.querySelector('.typing-text');
        typeText(message, typingText);
    } else {
        // Regular message without typing animation
        let htmlContent = `<div class="message-content"><p>${formatChatText(message)}</p>`;
        
        // Add source for AI messages
        if (type === 'ai' && source) {
            // Check if there are multiple sources
            if (source.includes(',')) {
                const sources = source.split(',').map(s => s.trim()).filter(Boolean);
                if (sources.length > 1) {
                    htmlContent += `<div class="message-source" data-source-ids="${sources.map(s => {
                        // Extract PDF ID if format is "PDF X"
                        const match = s.match(/PDF\s+(\d+)/i);
                        return match ? match[1] : '';
                    }).join(',')}"><small><i class="fas fa-file-pdf me-1"></i>Sources:</small>`;
                    htmlContent += `<ul class="mb-0 ps-3 mt-1">`;
                    sources.forEach(src => {
                        htmlContent += `<li><small>${src}</small></li>`;
                    });
                    htmlContent += `</ul></div>`;
                } else if (sources.length === 1) {
                    // Extract PDF ID if format is "PDF X"
                    const match = sources[0].match(/PDF\s+(\d+)/i);
                    const pdfId = match ? match[1] : '';
                    
                    htmlContent += `<div class="message-source" data-source-id="${pdfId}"><small><i class="fas fa-file-pdf me-1"></i>Source: ${sources[0]}</small></div>`;
                }
            } else {
                // Extract PDF ID if format is "PDF X"
                const match = source.match(/PDF\s+(\d+)/i);
                const pdfId = match ? match[1] : '';
                
                htmlContent += `<div class="message-source" data-source-id="${pdfId}"><small><i class="fas fa-file-pdf me-1"></i>Source: ${source}</small></div>`;
            }
        }
        
        htmlContent += '</div>';
        messageDiv.innerHTML = htmlContent;
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // After adding message with sources, check if any referenced PDFs still exist
    if (type === 'ai' && source) {
        setTimeout(() => {
            // Check source IDs for existence
            const sourceEls = messageDiv.querySelectorAll('.message-source[data-source-id]');
            sourceEls.forEach(el => {
                const pdfId = el.dataset.sourceId;
                if (pdfId) {
                    checkPDFExistence(pdfId);
                }
            });
            
            // Check multi-source IDs
            const multiSourceEls = messageDiv.querySelectorAll('.message-source[data-source-ids]');
            multiSourceEls.forEach(el => {
                const pdfIds = el.dataset.sourceIds.split(',').filter(Boolean);
                pdfIds.forEach(pdfId => {
                    if (pdfId) {
                        checkPDFExistence(pdfId);
                    }
                });
            });
        }, 500); // Slight delay to allow rendering first
    }
}

// Type text character by character for a realistic typing effect
function typeText(text, element, index = 0) {
    // Process the full text with formatting first so we know the final state
    const formattedText = formatChatText(text);
    
    // For typing, we want to first type the plain text, then replace with formatted HTML
    // This creates a more realistic effect while preserving formatting
    
    // Extract just the text content without HTML tags for typing
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = formattedText;
    const plainText = tempDiv.textContent;
    
    // Faster typing speed for longer responses
    const baseSpeed = plainText.length > 500 ? 8 : (plainText.length > 200 ? 15 : 20);
    
    if (index < plainText.length) {
        // Add one character at a time (for plain text)
        element.textContent = plainText.substring(0, index + 1);
        
        // Random typing speed between baseSpeed and baseSpeed+15ms
        const typingSpeed = Math.floor(Math.random() * 15) + baseSpeed;
        
        // Add natural pauses at punctuation
        const currentChar = plainText.charAt(index);
        let delay = typingSpeed;
        
        if (currentChar === '.') {
            delay = 300; // Longer pause at end of sentence
        } else if (currentChar === ',' || currentChar === ';') {
            delay = 150; // Medium pause at commas
        } else if (currentChar === '?' || currentChar === '!') {
            delay = 300; // Longer pause at question or exclamation
        }
        
        // Schedule the next character
        setTimeout(() => {
            typeText(text, element, index + 1);
        }, delay);
    } else {
        // When done typing the plain text, replace with the fully formatted HTML
        element.innerHTML = formattedText;
        
        // Add copy buttons functionality to code blocks
        const codeBlocks = element.querySelectorAll('.code-block-wrapper');
        if (codeBlocks.length > 0) {
            codeBlocks.forEach(block => {
                const button = block.querySelector('.copy-code-btn');
                if (button) {
                    button.addEventListener('click', function() {
                        copyToClipboard(this);
                    });
                }
            });
        }
        
        // Scroll to the latest message
        const chatMessages = document.getElementById('chatMessages');
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }
}

/**
 * Checks if a question is small talk
 * @param {string} question - The user's question
 * @returns {boolean} - Whether this is small talk
 */
function isSmallTalk(question) {
    const lowerQuestion = question.toLowerCase().trim();
    
    // Common small talk patterns
    const smallTalkPatterns = [
        'hello', 'hi', 'hey', 'greetings', 'howdy',
        'how are you', 'how\'s it going', 'hows it going', 
        'what\'s up', 'whats up', 'sup',
        'good morning', 'good afternoon', 'good evening', 'good night',
        'thank you', 'thanks', 'thx', 'thank',
        'bye', 'goodbye', 'see you', 'cya', 'later',
        'who are you', 'what is your name', 'what do you do',
        'how old are you', 'where are you from',
        'help me', 'can you help', 'need help',
        'nice to meet you', 'pleasure',
        'lol', 'haha', 'cool', 'nice', 'awesome',
        'what can you do', 'your purpose'
    ];
    
    // Check if the question contains or starts with small talk patterns
    return smallTalkPatterns.some(pattern => 
        lowerQuestion === pattern || 
        lowerQuestion.startsWith(pattern) || 
        lowerQuestion.includes(pattern)
    );
}

/**
 * Generates a response to small talk
 * @param {string} question - The user's small talk question
 * @returns {string} - The response
 */
function generateSmallTalkResponse(question) {
    const lowerQuestion = question.toLowerCase().trim();
    
    // Greeting responses
    if (lowerQuestion.includes('hello') || lowerQuestion.includes('hi') || 
        lowerQuestion.includes('hey') || lowerQuestion.includes('greetings') || 
        lowerQuestion.includes('howdy')) {
        return "Hello! How can I help you with your document today?";
    }
    
    // How are you responses
    if (lowerQuestion.includes('how are you') || lowerQuestion.includes('how\'s it going') || 
        lowerQuestion.includes('hows it going') || lowerQuestion.includes('what\'s up') || 
        lowerQuestion.includes('whats up') || lowerQuestion.includes('sup')) {
        return "I'm doing well, thanks for asking! I'm ready to help you with your PDF document. What would you like to know?";
    }
    
    // Time of day greetings
    if (lowerQuestion.includes('good morning')) {
        return "Good morning! How can I assist you with your document today?";
    }
    if (lowerQuestion.includes('good afternoon')) {
        return "Good afternoon! What would you like to know about your document?";
    }
    if (lowerQuestion.includes('good evening')) {
        return "Good evening! I'm here to help with any questions about your document.";
    }
    if (lowerQuestion.includes('good night')) {
        return "Good night! Feel free to come back anytime you have questions about your document.";
    }
    
    // Thank you responses
    if (lowerQuestion.includes('thank you') || lowerQuestion.includes('thanks') || 
        lowerQuestion.includes('thx') || lowerQuestion === 'thank') {
        return "You're welcome! Is there anything else you'd like to know about your document?";
    }
    
    // Goodbye responses
    if (lowerQuestion.includes('bye') || lowerQuestion.includes('goodbye') || 
        lowerQuestion.includes('see you') || lowerQuestion.includes('cya') || 
        lowerQuestion.includes('later')) {
        return "Goodbye! Feel free to come back anytime you have questions about your document.";
    }
    
    // Identity questions
    if (lowerQuestion.includes('who are you') || lowerQuestion.includes('what is your name') || 
        lowerQuestion.includes('what\'s your name')) {
        return "I'm your PDF assistant, designed to help you understand and extract information from your documents. What would you like to know?";
    }
    
    // Purpose questions
    if (lowerQuestion.includes('what do you do') || lowerQuestion.includes('what can you do') || 
        lowerQuestion.includes('your purpose')) {
        return "I'm here to help you with your PDF documents. I can answer questions about the content, summarize sections, or extract specific information. What would you like to know?";
    }
    
    // Help requests
    if (lowerQuestion.includes('help me') || lowerQuestion.includes('can you help') || 
        lowerQuestion.includes('need help')) {
        return "I'd be happy to help! You can ask me questions about your PDF document, and I'll try to find the answers. What would you like to know?";
    }
    
    // Other pleasantries
    if (lowerQuestion.includes('nice to meet you') || lowerQuestion.includes('pleasure')) {
        return "Likewise! I'm here whenever you need assistance with your document.";
    }
    
    if (lowerQuestion.includes('lol') || lowerQuestion.includes('haha') || 
        lowerQuestion.includes('cool') || lowerQuestion.includes('nice') || 
        lowerQuestion.includes('awesome')) {
        return "I'm glad you're enjoying our conversation! How else can I help with your document?";
    }
    
    // Default response for other small talk
    return "I'm here to help you with your document. Feel free to ask me anything about its content!";
}

// Format chat text
function formatChatText(text) {
    if (!text) return '';
    
    // Replace newlines with <br>
    text = text.replace(/\n/g, '<br>');
    
    // Handle code blocks with ```
    text = text.replace(/```([\s\S]*?)```/g, function(match, codeContent) {
        // Remove the first <br> if it exists (from newline replacement)
        codeContent = codeContent.replace(/^<br>/, '');
        // Remove the last <br> if it exists
        codeContent = codeContent.replace(/<br>$/, '');
        
        // Create a copy button for the code block
        return `<div class="code-block-wrapper">
            <div class="code-block-header">
                <button class="copy-code-btn" onclick="copyToClipboard(this)">
                    <i class="fas fa-copy"></i> Copy
                </button>
            </div>
            <pre class="code-block">${codeContent}</pre>
        </div>`;
    });
    
    // Handle inline code with `
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Handle formatting
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    return text;
}

// Add function to copy code to clipboard
window.copyToClipboard = function(button) {
    const preElement = button.closest('.code-block-wrapper').querySelector('pre.code-block');
    const text = preElement.innerText;
    
    navigator.clipboard.writeText(text).then(() => {
        // Show copied feedback
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check"></i> Copied!';
        button.classList.add('copied');
        
        // Reset after 2 seconds
        setTimeout(() => {
            button.innerHTML = originalText;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text: ', err);
        alert('Failed to copy text. Please try again.');
    });
};

// Add typing indicator
function addTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
    
    chatMessages.appendChild(typingDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Remove typing indicator
function removeTypingIndicator() {
    const typingIndicator = document.querySelector('.typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Add custom styles for sidebar and chat
function addCustomStyles() {
    const styleElement = document.createElement('style');
    styleElement.textContent = `
        .app-wrapper {
            display: flex;
            height: 100vh;
            max-height: 100vh;
            overflow: hidden;
        }
        
        .app-sidebar {
            width: 280px;
            background-color: #f8f9fa;
            border-right: 1px solid #dee2e6;
            padding: 15px;
            display: flex;
            flex-direction: column;
            height: 100%;
            overflow-y: auto;
        }
        
        .app-main-content {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }
        
        .sidebar-section {
            margin-bottom: 25px;
        }
        
        .pdf-sidebar-list {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .pdf-sidebar-item {
            cursor: pointer;
            padding: 8px 10px;
            font-size: 0.9rem;
        }
        
        .pdf-sidebar-item:hover {
            background-color: #f1f3f5;
        }
        
        .pdf-sidebar-item.active {
            background-color: #e9ecef;
            font-weight: bold;
        }
        
        .chat-container {
            display: flex;
            flex-direction: column;
            height: calc(100vh - 140px);
            background-color: #fff;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .chat-header {
            padding: 15px 20px;
            border-bottom: 1px solid #eee;
            background-color: #f8f9fa;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .system-message, .user-message, .ai-message, .error-message {
            max-width: 75%;
            padding: 10px 15px;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        
        .system-message {
            align-self: center;
            background-color: #f1f3f5;
            color: #495057;
        }
        
        .user-message {
            align-self: flex-end;
            background-color: #4361ee;
            color: white;
        }
        
        .ai-message {
            align-self: flex-start;
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            color: #212529;
        }
        
        .error-message {
            align-self: center;
            background-color: #ffeeee;
            border: 1px solid #ffcccc;
            color: #dc3545;
        }
        
        .message-source {
            margin-top: 5px;
            font-size: 0.8rem;
            color: #6c757d;
            border-top: 1px dotted #dee2e6;
            padding-top: 5px;
        }
        
        /* Styles for sources list */
        .message-source ul {
            margin-top: 2px;
            margin-bottom: 0;
            padding-left: 16px;
            list-style-type: disc;
        }
        
        .message-source li {
            margin-bottom: 2px;
            color: #666;
        }
        
        /* Style for deleted PDF references */
        .message-source small .fa-exclamation-triangle {
            color: #f59e0b;
            margin-right: 3px;
        }
        
        .message-source ul li small .fa-exclamation-triangle {
            color: #f59e0b;
            margin-right: 3px;
        }
        
        .chat-input {
            padding: 15px;
            border-top: 1px solid #eee;
            background-color: #f8f9fa;
        }
        
        .typing-indicator {
            display: flex;
            align-items: center;
            align-self: flex-start;
            background-color: #f1f3f5;
            padding: 12px 15px;
            border-radius: 10px;
        }
        
        .typing-indicator .dot {
            height: 8px;
            width: 8px;
            border-radius: 50%;
            background-color: #adb5bd;
            margin: 0 3px;
            animation: typing 1.5s infinite ease-in-out;
        }
        
        .typing-indicator .dot:nth-child(1) {
            animation-delay: 0s;
        }
        
        .typing-indicator .dot:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .typing-indicator .dot:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes typing {
            0% { opacity: 0.3; transform: scale(0.8); }
            50% { opacity: 1; transform: scale(1.2); }
            100% { opacity: 0.3; transform: scale(0.8); }
        }
    `;
    
    document.head.appendChild(styleElement);
}

// Add to local storage chat history
function saveChatHistory(pdfId, question, answer, source = null) {
    if (!pdfId || !question || !answer) {
        console.warn('Missing required data for saving chat history');
        return;
    }
    
    console.log(`Saving chat history for PDF ${pdfId}`);
    
    try {
        // Get existing history
        let history = JSON.parse(localStorage.getItem('chatHistory')) || {};
        
        // Initialize array for this PDF if it doesn't exist
        if (!history[pdfId]) {
            history[pdfId] = [];
        }
        
        // Add new chat entry with timestamp
        history[pdfId].push({
            question: question,
            answer: answer,
            source: source,
            timestamp: new Date().toISOString()
        });
        
        // Keep only the latest 50 entries for each PDF
        if (history[pdfId].length > 50) {
            history[pdfId] = history[pdfId].slice(-50);
        }
        
        // Save back to localStorage
        localStorage.setItem('chatHistory', JSON.stringify(history));
        
        // Update history sidebar
        updateChatHistorySidebar();
    } catch (e) {
        console.error('Error saving chat history:', e);
    }
}

// Update chat history sidebar
function updateChatHistorySidebar() {
    const historyContainer = document.getElementById('chatHistoryList');
    if (!historyContainer) return;
    
    try {
        let history = JSON.parse(localStorage.getItem('chatHistory')) || {};
        let html = '';
        
        // Check if history exists
        if (Object.keys(history).length === 0) {
            html = '<div class="text-muted text-center py-3">No chat history yet</div>';
        } else {
            html = '<ul class="list-group history-list">';
            
            // For each PDF
            for (const pdfId in history) {
                // Get PDF name - ensure it doesn't use # format
                const pdfName = getPDFNameById(pdfId).replace('#', '').trim();
                
                // Get latest chat
                const latestChat = history[pdfId][history[pdfId].length - 1];
                if (latestChat) {
                    const date = new Date(latestChat.timestamp);
                    const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
                    
                    html += `
                        <li class="list-group-item history-item" data-pdf-id="${pdfId}">
                            <div class="d-flex justify-content-between">
                                <div class="history-pdf-name">${pdfName}</div>
                                <small class="text-muted">${formattedDate}</small>
            </div>
                            <div class="history-question text-truncate">${latestChat.question}</div>
                        </li>
                    `;
                }
            }
            
            html += '</ul>';
        }
        
        historyContainer.innerHTML = html;
        
        // Add click listeners
        const historyItems = document.querySelectorAll('.history-item');
        historyItems.forEach(item => {
            item.addEventListener('click', function() {
                const pdfId = this.dataset.pdfId;
                selectPDF(pdfId);
                
                // Open the chat history for this PDF
                showChatHistory(pdfId);
            });
        });
    } catch (e) {
        console.error('Error updating chat history sidebar:', e);
        historyContainer.innerHTML = '<div class="text-danger text-center py-3">Error loading chat history</div>';
    }
}

// Show chat history for a PDF
function showChatHistory(pdfId) {
    try {
        let history = JSON.parse(localStorage.getItem('chatHistory')) || {};
        
        if (!history[pdfId] || history[pdfId].length === 0) {
            console.warn(`No chat history found for PDF ID: ${pdfId}`);
            return;
        }
        
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) {
            console.error("Chat messages container not found");
            return;
        }
        
        // Get PDF name
        const pdfName = getPDFNameById(pdfId);
        
        // Clear current chat
        chatMessages.innerHTML = `
            <div class="system-message">
                <div class="message-content">
                    <p><i class="fas fa-history me-2"></i>Showing chat history for ${pdfName}</p>
                </div>
            </div>
        `;
        
        console.log(`Displaying ${history[pdfId].length} history entries for PDF ID: ${pdfId}`);
        
        // Add chat history
        history[pdfId].forEach(chat => {
            // Add user question
            const userDiv = document.createElement('div');
            userDiv.className = 'user-message';
            userDiv.innerHTML = `<div class="message-content"><p>${formatChatText(chat.question)}</p></div>`;
            chatMessages.appendChild(userDiv);
            
            // Add AI answer
            const aiDiv = document.createElement('div');
            aiDiv.className = 'ai-message';
            
            // Format content including code blocks
            const formattedAnswer = formatChatText(chat.answer);
            
            // Add source if it exists
            let sourceHTML = '';
            if (chat.source) {
                sourceHTML = `
                    <div class="message-source">
                        <small><i class="fas fa-file-pdf me-1"></i>Source: ${chat.source}</small>
                    </div>
                `;
            }
            
            aiDiv.innerHTML = `
                <div class="message-content">
                    <p>${formattedAnswer}</p>
                    ${sourceHTML}
                </div>
            `;
            chatMessages.appendChild(aiDiv);
            
            // Add timestamp if available
            if (chat.timestamp) {
                const date = new Date(chat.timestamp);
                const timeDiv = document.createElement('div');
                timeDiv.className = 'chat-timestamp';
                timeDiv.innerHTML = `<small class="text-muted">${date.toLocaleString()}</small>`;
                chatMessages.appendChild(timeDiv);
            }
        });
        
        // Add copy functionality to any code blocks
        const codeBlocks = chatMessages.querySelectorAll('.code-block-wrapper');
        if (codeBlocks.length > 0) {
            codeBlocks.forEach(block => {
                const button = block.querySelector('.copy-code-btn');
                if (button) {
                    button.addEventListener('click', function() {
                        copyToClipboard(this);
                    });
                }
            });
        }
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (e) {
        console.error('Error showing chat history:', e);
    }
}

// Start new chat
function startNewChat() {
    // Get currently selected PDF
    const activePdf = document.querySelector('.pdf-sidebar-item.active');
    if (activePdf) {
        const pdfId = activePdf.dataset.id;
        initChatWithPDF(pdfId);
    } else {
        // Show message to select a PDF first
        Swal.fire({
            title: 'Select a PDF',
            text: 'Please select a PDF from the sidebar to start a chat',
            icon: 'info',
            confirmButtonText: 'OK'
        });
    }
}

// Helper function to load scripts dynamically
function loadScript(url, callback) {
    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = url;
    script.onload = callback;
    document.head.appendChild(script);
}

// Add AI badge to the header
function addAIBadgeToHeader() {
    const header = document.querySelector('header');
    if (header) {
        const aiLabel = document.createElement('div');
        aiLabel.className = 'ai-badge';
        aiLabel.innerHTML = '<i class="fas fa-robot me-1"></i> Powered by Lucifer AI';
        header.appendChild(aiLabel);
    }
}

// Initialize AI context menu for PDFs
function initializeAIContextMenu() {
    // Add context menu to PDF items
    const pdfList = document.getElementById('pdfList');
    if (pdfList) {
        pdfList.addEventListener('click', function(e) {
            // Check if the click is on a PDF item
            const pdfItem = e.target.closest('.pdf-item');
            if (pdfItem) {
                // Check if the click is on the more options button (add this button in the future)
                const moreBtn = e.target.closest('.more-options');
                if (moreBtn) {
                    showAIOptionsMenu(moreBtn, pdfItem.dataset.id);
                }
            }
        });
    }
}

// Override the default question form to fix source display
function overrideQuestionForm() {
    const questionForm = document.getElementById('questionForm');
    if (questionForm) {
        questionForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const question = document.getElementById('question').value.trim();
            
            if (!question) {
                Swal.fire({
                    title: 'Warning!',
                    text: 'Please enter a question',
                    icon: 'warning',
                    confirmButtonText: 'OK'
                });
                return;
            }
            
            // Show loading state
            const askBtn = document.getElementById('askBtn');
            if (askBtn) {
                askBtn.disabled = true;
                askBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            }
            
            // Show loading indicator
            const answerText = document.getElementById('answerText');
            const loadingIndicator = document.getElementById('loadingIndicator');
            if (answerText) answerText.style.display = 'none';
            if (loadingIndicator) loadingIndicator.style.display = 'flex';
            
            // Get the currently selected PDF if any
            const currentPdfId = getCurrentPdfId();
            
            // Prepare request data
            const requestData = { question: question };
            if (currentPdfId) {
                requestData.pdf_id = currentPdfId;
            }
            
            // Send request
            fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            })
            .then(response => response.json())
            .then(data => {
                // Re-enable button
                if (askBtn) {
                    askBtn.disabled = false;
                    askBtn.innerHTML = 'Ask Question';
                }
                
                // Hide loading indicator
                if (loadingIndicator) loadingIndicator.style.display = 'none';
                if (answerText) answerText.style.display = 'block';
                
                if (data.success) {
                    const answerContainer = document.getElementById('answerContainer');
                    
                    // Display the answer with proper source information
                    answerContainer.style.opacity = '0';
                    setTimeout(() => {
                        // If there's source information, use it; otherwise, use the filename
                        let sourceName = data.source || (currentPdfId ? getPDFNameById(currentPdfId) : 'Unknown');
                        
                        // Create enhanced answer HTML with visible source
                        const answerHTML = `
                            <div class="answer-content">
                                <div id="answerText">${data.answer}</div>
                            </div>
                            <div class="answer-metadata">
                                <div class="d-flex justify-content-between flex-wrap">
                                    <div class="source-info mb-2">
                                        <span class="me-2"><i class="fas fa-file-pdf"></i> Source:</span>
                                        <span class="badge bg-info">${sourceName}</span>
                                    </div>
                                    <div class="confidence-info">
                                        <span>Confidence: </span>
                                        <span class="badge ${getConfidenceBadgeClass(data.confidence)}">${data.confidence || '0%'}</span>
                                    </div>
                                </div>
                            </div>
                        `;
                        
                        answerContainer.innerHTML = answerHTML;
                        answerContainer.style.opacity = '1';
                    }, 200);
                } else {
                    // Show error notification
                    Swal.fire({
                        title: 'Error!',
                        text: data.message || 'Failed to get an answer',
                        icon: 'error',
                        confirmButtonText: 'OK'
                    });
                }
            })
            .catch(error => {
                console.error('Error:', error);
                
                // Re-enable button
                if (askBtn) {
                    askBtn.disabled = false;
                    askBtn.innerHTML = 'Ask Question';
                }
                
                // Hide loading indicator
                if (loadingIndicator) loadingIndicator.style.display = 'none';
                if (answerText) answerText.style.display = 'block';
                
                // Show error notification
                Swal.fire({
                    title: 'Error!',
                    text: 'An error occurred while processing your question',
                    icon: 'error',
                    confirmButtonText: 'OK'
                });
            });
        });
    }
}

// Add delete buttons to all PDF items
function addDeleteButtonsToPDFs() {
    console.log('Adding delete buttons to PDFs');
    const pdfItems = document.querySelectorAll('.pdf-item');
    console.log('Found PDF items:', pdfItems.length);
    
    if (pdfItems.length === 0) {
        // If no items found, try again after a delay (DOM might not be fully loaded)
        setTimeout(addDeleteButtonsToPDFs, 1000);
        return;
    }
    
    pdfItems.forEach(item => {
        // Only add if it doesn't already have a delete button
        if (!item.querySelector('.delete-pdf-btn')) {
            const pdfId = item.dataset.id || item.getAttribute('data-id');
            if (!pdfId) return;
            
            console.log('Adding delete button to PDF ID:', pdfId);
            
            // Create delete button with appropriate styling
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-sm btn-danger delete-pdf-btn ms-2';
            deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
            deleteBtn.title = 'Delete PDF';
            deleteBtn.setAttribute('data-pdf-id', pdfId);
            deleteBtn.style.position = 'absolute';
            deleteBtn.style.right = '10px';
            deleteBtn.style.top = '10px';
            deleteBtn.style.zIndex = '100';
            
            // Make sure the item has relative positioning for absolute positioning of the button
            item.style.position = 'relative';
            
            // Append directly to the item
            item.appendChild(deleteBtn);
            
            // Add event listener
            deleteBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                confirmDeletePDF(pdfId);
            });
            
            console.log('Delete button added successfully');
        }
    });
    
    // Add observer to handle dynamically added PDFs
    setupPDFListObserver();
}

// Setup observer to watch for new PDF items added to the list
function setupPDFListObserver() {
    const pdfList = document.getElementById('pdfList');
    if (!pdfList) return;
    
    console.log('Setting up PDF list observer');
    
    // Create a MutationObserver to watch for new PDF items
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                // Check each added node
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1 && (node.classList.contains('pdf-item') || node.querySelector('.pdf-item'))) {
                        console.log('Observer detected new PDF items');
                        
                        // Add delete button to this new PDF item
                        const items = node.classList.contains('pdf-item') ? [node] : node.querySelectorAll('.pdf-item');
                        items.forEach(item => {
                            // Only add if it doesn't already have a delete button
                            if (!item.querySelector('.delete-pdf-btn')) {
                                const pdfId = item.dataset.id || item.getAttribute('data-id');
                                if (!pdfId) return;
                                
                                console.log('Adding delete button to new PDF ID:', pdfId);
                                
                                // Create delete button
                                const deleteBtn = document.createElement('button');
                                deleteBtn.className = 'btn btn-sm btn-danger delete-pdf-btn ms-2';
                                deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
                                deleteBtn.title = 'Delete PDF';
                                deleteBtn.setAttribute('data-pdf-id', pdfId);
                                deleteBtn.style.position = 'absolute';
                                deleteBtn.style.right = '10px';
                                deleteBtn.style.top = '10px';
                                deleteBtn.style.zIndex = '100';
                                
                                // Make sure the item has relative positioning
                                item.style.position = 'relative';
                                
                                // Append directly to the item
                                item.appendChild(deleteBtn);
                                
                                // Add event listener
                                deleteBtn.addEventListener('click', function(e) {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    confirmDeletePDF(pdfId);
                                });
                            }
                        });
                    }
                });
            }
        });
    });
    
    // Start observing
    observer.observe(pdfList, { childList: true, subtree: true });
    console.log('PDF list observer started');
}

// Get PDF name by ID
function getPDFNameById(pdfId) {
    if (!pdfId) return '';
    
    // First try to find in sidebar
    const pdfItem = document.querySelector(`.pdf-sidebar-item[data-id="${pdfId}"]`);
    if (pdfItem) {
        // First try to get from data attribute (cleanest)
        if (pdfItem.dataset.filename) {
            return pdfItem.dataset.filename;
        }
        
        // Then try to get from name element
        const nameElement = pdfItem.querySelector('.pdf-name');
        if (nameElement) {
            // Extract just the filename text without the icon
            const nameText = nameElement.textContent.trim();
            return nameText.replace(/^\s*\S+\s+/, ''); // Remove the icon's text if present
        }
    }
    
    // If not found in sidebar, try to find in the old pdf list
    const oldPdfItem = document.querySelector(`.pdf-item[data-id="${pdfId}"]`);
    if (oldPdfItem) {
        // First try to get from data attribute
        if (oldPdfItem.dataset.filename) {
            return oldPdfItem.dataset.filename;
        }
        
        const nameElement = oldPdfItem.querySelector('.pdf-name') || oldPdfItem.querySelector('.pdf-title');
        if (nameElement) {
            return nameElement.textContent.trim();
        }
    }
    
    // If we have a data attribute on any element with this ID
    const anyElement = document.querySelector(`[data-pdf-id="${pdfId}"][data-filename]`);
    if (anyElement && anyElement.dataset.filename) {
        return anyElement.dataset.filename;
    }
    
    // If still not found, just use a basic format but start checking in background
    checkPDFExistence(pdfId);
    return `PDF ${pdfId}`;
}

// Check if a PDF exists by ID and update references if not
function checkPDFExistence(pdfId) {
    if (!pdfId) return;
    
    // Set a session storage flag to avoid repeated checks for the same PDF
    const checkedKey = `checked_pdf_${pdfId}`;
    if (sessionStorage.getItem(checkedKey)) {
        return;
    }
    
    fetch(`/pdf/${pdfId}/info`)
        .then(response => {
            if (!response.ok) {
                if (response.status === 404) {
                    console.log(`PDF ${pdfId} not found on server`);
                    // PDF doesn't exist, update any references
                    updateDeletedPDFReferences(pdfId);
                    sessionStorage.setItem(checkedKey, 'not_found');
                }
                return null;
            }
            return response.json();
        })
        .then(data => {
            if (data && data.success) {
                // PDF exists, update any missing references
                const cleanFilename = data.filename?.replace(/\.[^/.]+$/, "") || `PDF ${pdfId}`;
                sessionStorage.setItem(checkedKey, 'found');
                sessionStorage.setItem(`pdf_name_${pdfId}`, cleanFilename);
                
                // Update any existing references that might not have the correct name
                const elements = document.querySelectorAll(`[data-pdf-id="${pdfId}"]`);
                elements.forEach(el => {
                    if (!el.dataset.filename) {
                        el.dataset.filename = cleanFilename;
                    }
                });
            }
        })
        .catch(err => {
            console.error('Error checking PDF existence:', err);
            // Don't block the UI if this fails
        });
}

// Update references to deleted PDFs
function updateDeletedPDFReferences(pdfId) {
    if (!pdfId) return;
    
    console.log(`Updating references to deleted PDF ${pdfId}`);
    
    // Find and update individual message source references
    const individualSourceElements = document.querySelectorAll(`.message-source[data-source-id="${pdfId}"]`);
    individualSourceElements.forEach(sourceEl => {
        const smallEl = sourceEl.querySelector('small');
        if (smallEl) {
            smallEl.innerHTML = `<i class="fas fa-exclamation-triangle me-1 text-warning"></i>PDF no longer available`;
        }
    });
    
    // Find and update multi-source references
    const multiSourceElements = document.querySelectorAll('.message-source[data-source-ids]');
    multiSourceElements.forEach(sourceEl => {
        const pdfIds = sourceEl.dataset.sourceIds.split(',');
        
        if (pdfIds.includes(pdfId)) {
            // Find the specific list item that contains this PDF
            const listItems = sourceEl.querySelectorAll('li small');
            listItems.forEach(item => {
                if (item.textContent.includes(`PDF ${pdfId}`)) {
                    item.innerHTML = `<i class="fas fa-exclamation-triangle me-1 text-warning"></i>PDF no longer available`;
                }
            });
        }
    });
    
    // For backward compatibility, check text content too
    const messageSourceElements = document.querySelectorAll('.message-source small');
    messageSourceElements.forEach(source => {
        // Check if this source contains the PDF ID or name
        if (source.textContent.includes(`PDF ${pdfId}`) || source.textContent.includes(`#${pdfId}`)) {
            // Only update if it hasn't been updated by the data-attribute methods above
            if (!source.innerHTML.includes('no longer available')) {
                source.innerHTML = `<i class="fas fa-exclamation-triangle me-1 text-warning"></i>PDF no longer available`;
            }
        }
    });
    
    // Check if chat is currently with this deleted PDF
    const chatHeader = document.querySelector('.chat-header h3');
    if (chatHeader && chatHeader.textContent.includes(`PDF ${pdfId}`)) {
        chatHeader.innerHTML = `<i class="fas fa-comments me-2"></i>Chat with <span class="text-muted">(Deleted PDF)</span>`;
    }
}

// Get confidence badge class based on value
function getConfidenceBadgeClass(confidence) {
    if (!confidence) return 'bg-warning';
    
    const numValue = parseInt(confidence.replace('%', ''));
    if (numValue >= 80) return 'bg-success';
    if (numValue >= 50) return 'bg-info';
    if (numValue >= 30) return 'bg-warning';
    return 'bg-danger';
}

// Confirm and delete PDF
function confirmDeletePDF(pdfId) {
    if (!pdfId) return;
    
    console.log('Confirming delete for PDF ID:', pdfId);
    
    Swal.fire({
        title: 'Delete PDF?',
        text: 'Are you sure you want to delete this PDF? This action cannot be undone.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Yes, delete it!',
        cancelButtonText: 'Cancel'
    }).then((result) => {
        if (result.isConfirmed) {
            deletePDF(pdfId);
        }
    });
}

// Delete PDF function
function deletePDF(pdfId) {
    console.log('Deleting PDF ID:', pdfId);
    
    // Show loading state
    Swal.fire({
        title: 'Deleting...',
        text: 'Please wait while we delete the PDF',
        allowOutsideClick: false,
        allowEscapeKey: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    // Send delete request
    fetch(`/pdf/${pdfId}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('PDF deleted successfully');
            
            // Update any references to this PDF in the UI
            updateDeletedPDFReferences(pdfId);
            
            // Show success message
            Swal.fire({
                title: 'Deleted!',
                text: 'The PDF has been deleted successfully',
                icon: 'success',
                timer: 2000,
                showConfirmButton: false
            });
            
            // Remove the PDF from the sidebar list
            const sidebarPdfItem = document.querySelector(`.pdf-sidebar-item[data-id="${pdfId}"]`);
            if (sidebarPdfItem) {
                sidebarPdfItem.remove();
            }
            
            // Remove the PDF from the old list if it exists
            const pdfItem = document.querySelector(`.pdf-item[data-id="${pdfId}"]`);
            if (pdfItem) {
                pdfItem.remove();
            }
            
            // Refresh PDF list in sidebar
            refreshSidebarPdfList();
        } else {
            console.error('Error deleting PDF:', data.message);
            
            // Show error
            Swal.fire({
                title: 'Error!',
                text: data.message || 'Failed to delete PDF',
                icon: 'error',
                confirmButtonText: 'OK'
            });
        }
    })
    .catch(error => {
        console.error('Error deleting PDF:', error);
        
        // Show error
        Swal.fire({
            title: 'Error!',
            text: 'An error occurred while deleting the PDF',
            icon: 'error',
            confirmButtonText: 'OK'
        });
    });
}

// Initialize direct question button
function initializeDirectQuestionButton() {
    const questionForm = document.getElementById('questionForm');
    if (questionForm) {
        const formGroup = questionForm.querySelector('.input-group');
        if (formGroup) {
            // Create direct AI question button with subtle indicator
            const aiBtn = document.createElement('button');
            aiBtn.type = 'button';
            aiBtn.id = 'askAiDirectBtn';
            aiBtn.className = 'btn btn-outline-danger ms-2';
            aiBtn.title = 'Ask Lucifer AI directly';
            aiBtn.innerHTML = '<i class="fas fa-robot"></i>';
            aiBtn.addEventListener('click', askDirectAIQuestion);
            
            // Add button after the form's submit button
            formGroup.appendChild(aiBtn);
        }
    }
}

// Ask AI directly
function askDirectAIQuestion() {
    const question = document.getElementById('question').value.trim();
    
    if (!question) {
        Swal.fire({
            title: 'Warning!',
            text: 'Please enter a question',
            icon: 'warning',
            confirmButtonText: 'OK'
        });
        return;
    }
    
    // Get current PDF ID if available
    const currentPdfId = getCurrentPdfId();
    
    // Show loading state
    const askBtn = document.getElementById('askAiDirectBtn');
    if (askBtn) {
        askBtn.disabled = true;
        askBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    }
    
    // Show loading indicator
    const answerText = document.getElementById('answerText');
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (answerText) answerText.style.display = 'none';
    if (loadingIndicator) loadingIndicator.style.display = 'flex';
    
    // Prepare request data
    const requestData = {
        question: question
    };
    
    // Add PDF ID if available
    if (currentPdfId) {
        requestData.pdf_id = currentPdfId;
    }
    
    // Send direct request to AI endpoint
    fetch('/ask-ai', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        // Re-enable button
        if (askBtn) {
            askBtn.disabled = false;
            askBtn.innerHTML = '<i class="fas fa-robot"></i>';
        }
        
        // Hide loading indicator
        if (loadingIndicator) loadingIndicator.style.display = 'none';
        if (answerText) answerText.style.display = 'block';
        
        const answerContainer = document.getElementById('answerContainer');
        
        if (data.success) {
            // Display the answer with AI styling
            answerContainer.style.opacity = '0';
            setTimeout(() => {
                answerContainer.innerHTML = createAIAnswerHTML(data.answer, data.sources);
                answerContainer.style.opacity = '1';
            }, 200);
        } else {
            // Try fallback to regular endpoint
            return fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Fallback responded with status: ${response.status}`);
                }
                return response.json();
            })
            .then(fallbackData => {
                if (fallbackData.success) {
                    // Display the answer from fallback
                    answerContainer.style.opacity = '0';
                    setTimeout(() => {
                        // Use standard display for fallback
                        answerContainer.innerHTML = `
                            <div class="answer-content">
                                <div id="answerText">${fallbackData.answer}</div>
                            </div>
                            <div class="answer-metadata">
                                <small class="text-muted">Standard answer</small>
                            </div>
                        `;
                        answerContainer.style.opacity = '1';
                    }, 200);
                } else {
                    // Show error notification
                    Swal.fire({
                        title: 'No Answer',
                        text: 'Could not find relevant information. Try rephrasing your question.',
                        icon: 'info',
                        confirmButtonText: 'OK'
                    });
                    
                    // Display error message
                    answerContainer.style.opacity = '0';
                    setTimeout(() => {
                        answerContainer.innerHTML = `
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-2"></i> Could not find relevant information. Try rephrasing your question.
                            </div>
                        `;
                        answerContainer.style.opacity = '1';
                    }, 200);
                }
            });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        
        // Re-enable button
        if (askBtn) {
            askBtn.disabled = false;
            askBtn.innerHTML = '<i class="fas fa-robot"></i>';
        }
        
        // Hide loading indicator
        if (loadingIndicator) loadingIndicator.style.display = 'none';
        if (answerText) answerText.style.display = 'block';
        
        const answerContainer = document.getElementById('answerContainer');
        
        // Try fallback to standard endpoint
        fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Fallback responded with status: ${response.status}`);
            }
            return response.json();
        })
        .then(fallbackData => {
            if (fallbackData.success) {
                // Display the answer from fallback
                answerContainer.style.opacity = '0';
                setTimeout(() => {
                    // Use standard display for fallback
                    answerContainer.innerHTML = `
                        <div class="answer-content">
                            <div id="answerText">${fallbackData.answer}</div>
                        </div>
                        <div class="answer-metadata">
                            <small class="text-muted">Standard answer (AI unavailable)</small>
                        </div>
                    `;
                    answerContainer.style.opacity = '1';
                }, 200);
            } else {
                // Show error notification
                Swal.fire({
                    title: 'Error',
                    text: 'Could not process your question. Please try again later.',
                    icon: 'error',
                    confirmButtonText: 'OK'
                });
                
                // Display error message
                answerContainer.style.opacity = '0';
                setTimeout(() => {
                    answerContainer.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle me-2"></i> Could not process your question. Please try again later.
                        </div>
                    `;
                    answerContainer.style.opacity = '1';
                }, 200);
            }
        })
        .catch(fallbackError => {
            console.error('Fallback error:', fallbackError);
            
            // Show error notification
            Swal.fire({
                title: 'Error',
                text: 'An error occurred while processing your question',
                icon: 'error',
                confirmButtonText: 'OK'
            });
            
            // Display error message
            answerContainer.style.opacity = '0';
            setTimeout(() => {
                answerContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i> An error occurred while processing your question. Please check your connection and try again.
                    </div>
                `;
                answerContainer.style.opacity = '1';
            }, 200);
        });
    });
}

// Helper function to get current PDF ID
function getCurrentPdfId() {
    // First try to get from active sidebar item
    const activePdf = document.querySelector('.pdf-sidebar-item.active');
    if (activePdf && activePdf.dataset.id) {
        return activePdf.dataset.id;
    }
    
    // Then try to get from chat form
    const chatPdfIdInput = document.getElementById('chatPdfId');
    if (chatPdfIdInput && chatPdfIdInput.value) {
        return chatPdfIdInput.value;
    }
    
    // Try to get from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const pdfId = urlParams.get('pdf_id');
    if (pdfId) {
        return pdfId;
    }
    
    // Try to get from old style active PDF item
    const oldActivePdf = document.querySelector('.pdf-item.active');
    if (oldActivePdf && oldActivePdf.dataset.id) {
        return oldActivePdf.dataset.id;
    }
    
    // Try to get from modal if open
    const pdfModal = document.querySelector('.modal.show');
    if (pdfModal) {
        const pdfIdAttribute = pdfModal.getAttribute('data-pdf-id');
        if (pdfIdAttribute) {
            return pdfIdAttribute;
        }
    }
    
    // Return null if no PDF is selected
    return null;
}

// Create AI answer HTML
function createAIAnswerHTML(answer, sources) {
    // Format the answer text with markdown-like processing
    const formattedAnswer = formatAnswerText(answer);
    
    // Format sources properly
    let sourceBadges = '';
    if (sources) {
        if (typeof sources === 'string') {
            // Split by comma if it's a comma-separated string
            const sourceList = sources.split(',').map(s => s.trim()).filter(s => s);
            if (sourceList.length > 0) {
                sourceBadges = sourceList.map(source => 
                    `<span class="badge bg-info me-1">${source}</span>`
                ).join('');
            } else {
                sourceBadges = '<span class="badge bg-warning">Unknown</span>';
            }
        } else if (Array.isArray(sources)) {
            // If it's already an array
            if (sources.length > 0) {
                sourceBadges = sources.map(source => 
                    `<span class="badge bg-info me-1">${source}</span>`
                ).join('');
            } else {
                sourceBadges = '<span class="badge bg-warning">Unknown</span>';
            }
        } else {
            sourceBadges = '<span class="badge bg-info">' + sources + '</span>';
        }
    } else {
        // Try to get the current PDF name if no sources are provided
        const currentPdfId = getCurrentPdfId();
        if (currentPdfId) {
            const pdfName = getPDFNameById(currentPdfId);
            sourceBadges = `<span class="badge bg-info">${pdfName}</span>`;
        } else {
            sourceBadges = '<span class="badge bg-warning">Unknown</span>';
        }
    }
    
    return `
        <div class="ai-badge"><i class="fas fa-robot me-1"></i> Lucifer AI</div>
        <div class="answer-content ai-answer">
            <div id="answerText">${formattedAnswer}</div>
        </div>
        <div class="answer-metadata">
            <div class="d-flex justify-content-between flex-wrap">
                <div class="source-info mb-2">
                    <span class="me-2"><i class="fas fa-file-pdf"></i> Source:</span>
                    ${sourceBadges}
                </div>
                <div class="ai-metadata">
                    <small class="text-muted">Generated by Lucifer AI</small>
                </div>
            </div>
        </div>
    `;
}

// Format answer text with basic markdown-like processing
function formatAnswerText(text) {
    if (!text) return '';
    
    // Replace **text** with <strong>text</strong>
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Replace *text* with <em>text</em>
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Replace newlines with <br>
    text = text.replace(/\n/g, '<br>');
    
    return text;
}

// Call to add custom styles
addCustomStyles();

/**
 * Determines if a question is asking for general knowledge
 * @param {string} question - The user's question
 * @returns {boolean} - Whether this is a general knowledge question
 */
function isGeneralKnowledgeQuestion(question) {
    // Temporarily disable general knowledge questions completely
    // until server issue with gemini_model is fixed
    return false;
}

/**
 * Sends a question specifically about the PDF content
 * @param {string} question - The user's question
 */
async function sendPdfQuestion(question) {
    try {
        // Show typing animation
        startTyping();
        
        // Get the current PDF ID from the page
        const pdfId = getCurrentPdfId();
        
        // Prepare request data
        const requestData = {
            question: question,
            pdf_id: pdfId
        };
        
        // Send to PDF-specific endpoint
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData),
        });
        
        // Stop typing animation
        stopTyping();
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                // Fix parameter order: type first, then message, then source
                addMessageToChat('ai', data.answer, data.source);
            } else {
                // Fix parameter order: type first, then message
                addMessageToChat('error', "I'm sorry, I couldn't find an answer to your question in this document.");
            }
        } else {
            // Fix parameter order: type first, then message
            addMessageToChat('error', "Sorry, I had trouble processing your request. Please try again.");
        }
    } catch (error) {
        console.error('Error sending PDF question:', error);
        stopTyping();
        // Fix parameter order: type first, then message
        addMessageToChat('error', "I couldn't connect to the server. Please check your connection and try again.");
    }
}

/**
 * Gets the current PDF ID from the page
 * @returns {string} - The current PDF ID
 */
function getCurrentPdfId() {
    // This function should retrieve the PDF ID from wherever it's stored in your application
    // For example, it might be in a data attribute, URL parameter, or global variable
    
    // Example implementation - replace with your actual method:
    return document.getElementById('pdf-container').getAttribute('data-pdf-id') || '';
}

/**
 * Starts the typing animation
 */
function startTyping() {
    // Use the correct element ID
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.id = 'typing-indicator';
    typingIndicator.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
    
    chatMessages.appendChild(typingIndicator);
    
    // Scroll to the bottom to show the typing indicator
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Stops the typing animation
 */
function stopTyping() {
    // Remove typing indicator
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}