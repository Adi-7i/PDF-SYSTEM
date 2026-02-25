// Initialize AOS (Animate on Scroll)
AOS.init({
    duration: 800,
    easing: 'ease-in-out',
    once: true,
    mirror: false
});

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Elements
    const uploadForm = document.getElementById('uploadForm');
    const questionForm = document.getElementById('questionForm');
    const uploadStatus = document.getElementById('uploadStatus');
    const pdfList = document.getElementById('pdfList');
    const answerContainer = document.getElementById('answerContainer');
    const answerText = document.getElementById('answerText');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const questionInput = document.getElementById('question');
    const fileInput = document.getElementById('pdfFile');
    const helpBtn = document.getElementById('helpBtn');

    // Help button functionality
    if (helpBtn) {
        helpBtn.addEventListener('click', function() {
            Swal.fire({
                title: 'How to use PDF Q&A',
                html: `
                    <div class="text-start">
                        <p><strong>1.</strong> Upload a PDF document using the form.</p>
                        <p><strong>2.</strong> Wait for the upload confirmation.</p>
                        <p><strong>3.</strong> Type your question about the PDF content.</p>
                        <p><strong>4.</strong> Click "Ask Question" to get your answer.</p>
                        <p><strong>5.</strong> View the answer with source information and confidence level.</p>
                    </div>
                `,
                icon: 'info',
                confirmButtonText: 'Got it!',
                confirmButtonColor: '#4361ee',
                showClass: {
                    popup: 'animate__animated animate__fadeInDown'
                },
                hideClass: {
                    popup: 'animate__animated animate__fadeOutUp'
                }
            });
        });
    }

    // File input change event
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const fileName = this.files[0]?.name;
            if (fileName) {
                const fileLabel = document.querySelector('.custom-file-label');
                if (fileLabel) {
                    fileLabel.textContent = fileName;
                }
            }
        });
    }

    // Upload form submission
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Check if file is selected
            const fileInput = document.getElementById('pdfFile');
            if (!fileInput.files || fileInput.files.length === 0) {
                // Show error notification
                Swal.fire({
                    title: 'Error!',
                    text: 'Please select a PDF file to upload',
                    icon: 'error',
                    confirmButtonText: 'OK'
                });
                
                // Update status
                uploadStatus.className = 'upload-error';
                uploadStatus.innerHTML = '<i class="fas fa-exclamation-circle"></i> Please select a PDF file to upload';
                return;
            }
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]); // Make sure the field name is 'file'
            
            const uploadBtn = document.getElementById('uploadBtn');
            
            // Disable button and show loading state
            if (uploadBtn) {
                uploadBtn.disabled = true;
                uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Uploading...';
            }
            
            // Clear previous status
            uploadStatus.innerHTML = '';
            uploadStatus.className = '';
            
            // Log the form data for debugging
            console.log('Uploading file:', fileInput.files[0].name);
            
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Server responded with status: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                // Re-enable button
                if (uploadBtn) {
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = '<i class="fas fa-cloud-upload-alt me-2"></i>Upload';
                }
                
                if (data.success) {
                    // Show success notification
                    Swal.fire({
                        title: 'Success!',
                        text: 'PDF uploaded successfully',
                        icon: 'success',
                        timer: 2000,
                        timerProgressBar: true,
                        showConfirmButton: false
                    });
                    
                    // Update status
                    uploadStatus.className = 'upload-success';
                    uploadStatus.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message || 'PDF uploaded successfully'}`;
                    
                    // Reset form
                    uploadForm.reset();
                    
                    // Refresh PDF list
                    fetchPDFs();
                } else {
                    // Show error notification
                    Swal.fire({
                        title: 'Error!',
                        text: data.message || 'Failed to upload PDF',
                        icon: 'error',
                        confirmButtonText: 'OK'
                    });
                    
                    // Update status
                    uploadStatus.className = 'upload-error';
                    uploadStatus.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${data.message || 'Failed to upload PDF'}`;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                
                // Re-enable button
                if (uploadBtn) {
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = '<i class="fas fa-cloud-upload-alt me-2"></i>Upload';
                }
                
                // Show error notification
                Swal.fire({
                    title: 'Error!',
                    text: 'An error occurred during upload: ' + error.message,
                    icon: 'error',
                    confirmButtonText: 'OK'
                });
                
                // Update status
                uploadStatus.className = 'upload-error';
                uploadStatus.innerHTML = '<i class="fas fa-exclamation-circle"></i> An error occurred during upload: ' + error.message;
            });
        });
    }

    // Question form submission
    if (questionForm) {
        questionForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const question = questionInput.value.trim();
            
            if (!question) {
                // Show warning for empty question
                Swal.fire({
                    title: 'Warning!',
                    text: 'Please enter a question',
                    icon: 'warning',
                    confirmButtonText: 'OK'
                });
                return;
            }
            
            const askBtn = document.getElementById('askBtn');
            
            // Disable button and show loading state
            if (askBtn) {
                askBtn.disabled = true;
                askBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            }
            
            // Show loading indicator
            answerText.style.display = 'none';
            loadingIndicator.style.display = 'flex';
            
            fetch('/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question: question })
            })
            .then(response => response.json())
            .then(data => {
                // Re-enable button
                if (askBtn) {
                    askBtn.disabled = false;
                    askBtn.innerHTML = 'Ask Question';
                }
                
                // Hide loading indicator
                loadingIndicator.style.display = 'none';
                answerText.style.display = 'block';
                
                if (data.success) {
                    // Process the answer to extract source and confidence
                    const processedAnswer = processAnswer(data.answer);
                    
                    // Display the answer with animation
                    answerContainer.style.opacity = '0';
                    setTimeout(() => {
                        answerContainer.innerHTML = processedAnswer;
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
                    
                    // Display error message
                    answerContainer.style.opacity = '0';
                    setTimeout(() => {
                        answerContainer.innerHTML = `
                            <div class="alert alert-danger">
                                <i class="fas fa-exclamation-triangle"></i> ${data.message || 'Failed to get an answer'}
                            </div>
                        `;
                        answerContainer.style.opacity = '1';
                    }, 200);
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
                loadingIndicator.style.display = 'none';
                answerText.style.display = 'block';
                
                // Show error notification
                Swal.fire({
                    title: 'Error!',
                    text: 'An error occurred while processing your question',
                    icon: 'error',
                    confirmButtonText: 'OK'
                });
                
                // Display error message
                answerContainer.style.opacity = '0';
                setTimeout(() => {
                    answerContainer.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle"></i> An error occurred while processing your question
                        </div>
                    `;
                    answerContainer.style.opacity = '1';
                }, 200);
            });
        });
    }

    // Process answer to extract source and confidence information
    function processAnswer(answer) {
        // Default values
        let mainAnswer = answer;
        let source = "Unknown";
        let confidence = 0;
        
        // Try to extract source and confidence from the answer
        const sourceMatch = answer.match(/Source: (.*?)(?:\n|$)/);
        const confidenceMatch = answer.match(/Confidence: (\d+)%/);
        
        if (sourceMatch) {
            source = sourceMatch[1].trim();
            // Remove the source line from the main answer
            mainAnswer = mainAnswer.replace(/Source: .*?(?:\n|$)/, '');
        }
        
        if (confidenceMatch) {
            confidence = parseInt(confidenceMatch[1]);
            // Remove the confidence line from the main answer
            mainAnswer = mainAnswer.replace(/Confidence: \d+%(?:\n|$)/, '');
        }
        
        // Trim the main answer
        mainAnswer = mainAnswer.trim();
        
        // Create HTML for the answer
        return createAnswerHTML(mainAnswer, source, confidence);
    }

    // Create HTML for the answer with source and confidence
    function createAnswerHTML(answer, source, confidence) {
        // Determine confidence badge class
        let confidenceBadgeClass = 'bg-info';
        if (confidence >= 80) {
            confidenceBadgeClass = 'bg-success';
        } else if (confidence >= 50) {
            confidenceBadgeClass = 'bg-warning';
        } else if (confidence > 0) {
            confidenceBadgeClass = 'bg-danger';
        }
        
        // Format the answer text with markdown-like processing
        const formattedAnswer = formatAnswerText(answer);
        
        return `
            <div class="answer-content">
                <div id="answerText">${formattedAnswer}</div>
            </div>
            <div class="answer-metadata">
                <div class="d-flex justify-content-between flex-wrap">
                    <div class="source-info mb-2">
                        <span class="me-2"><i class="fas fa-file-pdf"></i> Source:</span>
                        <span class="badge bg-info">${source}</span>
                    </div>
                    <div class="confidence-info mb-2">
                        <span class="me-2"><i class="fas fa-chart-line"></i> Confidence:</span>
                        <span class="badge ${confidenceBadgeClass}">${confidence}%</span>
                    </div>
                </div>
            </div>
        `;
    }

    // Format answer text with basic markdown-like processing
    function formatAnswerText(text) {
        // Replace **text** with <strong>text</strong>
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Replace *text* with <em>text</em>
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Replace newlines with <br>
        text = text.replace(/\n/g, '<br>');
        
        return text;
    }

    // Fetch PDFs function
    function fetchPDFs() {
        console.log("Fetching PDFs from server...");
        fetch('/pdfs')
            .then(response => {
                console.log("Response status:", response.status);
                if (!response.ok) {
                    console.error("Response not OK:", response.statusText);
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("PDFs data received:", JSON.stringify(data));
                if (data.success) {
                    // Clear current list
                    pdfList.innerHTML = '';
                    
                    if (!data.pdfs || data.pdfs.length === 0) {
                        console.log("No PDFs found in response");
                        pdfList.innerHTML = '<div class="text-center p-3">No PDFs uploaded yet</div>';
                        return;
                    }
                    
                    console.log(`Found ${data.pdfs.length} PDFs, rendering list`);
                    
                    // Add each PDF to the list with animation
                    data.pdfs.forEach((pdf, index) => {
                        console.log(`Rendering PDF: ${pdf.filename}, ID: ${pdf.id}, Date: ${pdf.upload_date}`);
                        const listItem = document.createElement('li');
                        listItem.className = 'list-group-item';
                        listItem.setAttribute('data-aos', 'fade-up');
                        listItem.setAttribute('data-aos-delay', (index * 100).toString());
                        
                        listItem.innerHTML = `
                            <div class="pdf-item">
                                <div>
                                    <span><i class="fas fa-file-pdf text-danger me-2"></i>${pdf.filename}</span>
                                    <small class="d-block text-muted">Uploaded: ${new Date(pdf.upload_date).toLocaleString()}</small>
                                </div>
                                <div class="pdf-actions">
                                    <button class="btn btn-sm btn-outline-primary view-pdf-btn" data-id="${pdf.id}" title="View PDF">
                                        <i class="fas fa-eye"></i>
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger delete-pdf-btn" data-id="${pdf.id}" title="Delete PDF">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                            </div>
                        `;
                        
                        pdfList.appendChild(listItem);
                    });
                    
                    // Refresh AOS
                    AOS.refresh();
                    
                    // Add event listeners to view buttons
                    document.querySelectorAll('.view-pdf-btn').forEach(button => {
                        button.addEventListener('click', function() {
                            const pdfId = this.getAttribute('data-id');
                            console.log(`Opening PDF with ID: ${pdfId}`);
                            window.open(`/view/${pdfId}`, '_blank');
                        });
                    });
                    
                    // Add event listeners to delete buttons
                    document.querySelectorAll('.delete-pdf-btn').forEach(button => {
                        button.addEventListener('click', function() {
                            const pdfId = this.getAttribute('data-id');
                            const pdfItem = this.closest('.list-group-item');
                            const pdfName = pdfItem.querySelector('span').innerText;
                            
                            // Confirm deletion
                            Swal.fire({
                                title: 'Delete PDF?',
                                text: `Are you sure you want to delete "${pdfName}"? This cannot be undone.`,
                                icon: 'warning',
                                showCancelButton: true,
                                confirmButtonColor: '#d33',
                                cancelButtonColor: '#3085d6',
                                confirmButtonText: 'Yes, delete it!',
                                cancelButtonText: 'Cancel'
                            }).then((result) => {
                                if (result.isConfirmed) {
                                    // Send delete request
                                    fetch(`/pdf/${pdfId}`, {
                                        method: 'DELETE'
                                    })
                                    .then(response => response.json())
                                    .then(data => {
                                        if (data.success) {
                                            // Show success message
                                            Swal.fire({
                                                title: 'Deleted!',
                                                text: data.message || 'PDF has been deleted.',
                                                icon: 'success',
                                                timer: 2000,
                                                timerProgressBar: true,
                                                showConfirmButton: false
                                            });
                                            
                                            // Remove from list with animation
                                            pdfItem.style.opacity = '0';
                                            setTimeout(() => {
                                                pdfItem.remove();
                                                // Show "No PDFs" message if list is empty
                                                if (pdfList.children.length === 0) {
                                                    pdfList.innerHTML = '<div class="text-center p-3">No PDFs uploaded yet</div>';
                                                }
                                            }, 300);
                                        } else {
                                            // Show error message
                                            Swal.fire({
                                                title: 'Error!',
                                                text: data.message || 'Failed to delete PDF.',
                                                icon: 'error'
                                            });
                                        }
                                    })
                                    .catch(error => {
                                        console.error('Error deleting PDF:', error);
                                        Swal.fire({
                                            title: 'Error!',
                                            text: 'An error occurred while deleting the PDF.',
                                            icon: 'error'
                                        });
                                    });
                                }
                            });
                        });
                    });
                } else {
                    console.error("Error fetching PDFs:", data.message);
                    pdfList.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle"></i> ${data.message || 'Failed to load PDFs'}
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Error fetching PDFs:', error);
                pdfList.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i> An error occurred while loading PDFs
                    </div>
                `;
            });
    }

    // Initial fetch of PDFs
    fetchPDFs();

    // Add typing animation to question input
    if (questionInput) {
        questionInput.addEventListener('focus', function() {
            this.setAttribute('placeholder', '');
        });
        
        questionInput.addEventListener('blur', function() {
            if (!this.value) {
                const placeholders = [
                    'What is the main topic of this PDF?',
                    'Can you summarize this document?',
                    'What are the key findings in this paper?',
                    'Who is the author of this document?',
                    'When was this research conducted?'
                ];
                
                let i = 0;
                const placeholder = placeholders[Math.floor(Math.random() * placeholders.length)];
                const typeWriter = () => {
                    if (i < placeholder.length) {
                        this.setAttribute('placeholder', placeholder.substring(0, i + 1));
                        i++;
                        setTimeout(typeWriter, 50);
                    }
                };
                
                typeWriter();
            }
        });
        
        // Trigger blur once to start the animation
        setTimeout(() => {
            questionInput.blur();
        }, 1000);
    }

    // Add scroll to top button functionality
    const scrollTopBtn = document.getElementById('scrollTopBtn');
    if (scrollTopBtn) {
        window.addEventListener('scroll', function() {
            if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
                scrollTopBtn.style.display = 'flex';
            } else {
                scrollTopBtn.style.display = 'none';
            }
        });
        
        scrollTopBtn.addEventListener('click', function() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
});
