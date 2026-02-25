/**
 * Dashboard Alpine.js Components
 * Handles all interactions and data management for the Lucifer AI dashboard
 */

document.addEventListener('alpine:init', () => {
    // Main Dashboard Component
    Alpine.data('dashboard', () => ({
        pdfs: [],
        chatSessions: [],
        practiceTests: [],
        isLoading: true,

        init() {
            this.fetchUserData();
        },

        // Fetch user's data from the server
        async fetchUserData() {
            try {
                this.isLoading = true;

                // Clear existing data to avoid stale information
                this.pdfs = [];
                this.chatSessions = [];
                this.practiceTests = [];

                // Call the API to get dashboard data
                const response = await fetch('/api/dashboard-data');
                const data = await response.json();
                
                if (data.success) {
                    // Only display PDFs that actually exist in the backend
                    this.pdfs = data.pdfs || [];
                    this.chatSessions = data.chatSessions || [];
                    this.practiceTests = data.practiceTests || [];
                    
                    console.log(`Loaded ${this.pdfs.length} PDFs from backend`);
                } else {
                    console.error('Error fetching dashboard data:', data.message);
                    this.showNotification('Failed to load dashboard data', 'error');
                }

                this.isLoading = false;
            } catch (error) {
                console.error('Error fetching data:', error);
                this.isLoading = false;
                this.showNotification('Failed to connect to server', 'error');
                
                // Clear data on error to avoid showing stale information
                this.pdfs = [];
                this.chatSessions = [];
                this.practiceTests = [];
            }
        },

        // File Upload Handling
        openFileBrowser() {
            document.getElementById('fileInput').click();
        },

        handleFileUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            if (file.type !== 'application/pdf') {
                this.showNotification('Please upload a PDF file', 'error');
                return;
            }
            
            if (file.size > 50 * 1024 * 1024) { // 50MB
                this.showNotification('File size exceeds 50MB limit', 'error');
                return;
            }
            
            this.uploadFile(file);
        },

        async uploadFile(file) {
            try {
                // Show upload in progress by adding to the list immediately
                const tempId = Date.now();
                const newPdf = {
                    id: tempId,
                    name: file.name,
                    timeAgo: "Just now",
                    pages: "Analyzing...",
                    isUploading: true
                };
                
                this.pdfs.unshift(newPdf);
                
                // Create form data for file upload
                const formData = new FormData();
                formData.append('file', file);
                
                // Upload the file to the server
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Remove the temp entry
                    this.pdfs = this.pdfs.filter(pdf => pdf.id !== tempId);
                    
                    // Refresh dashboard data to get the new PDF with accurate information
                    await this.fetchUserData();
                    
                    this.showNotification('File uploaded successfully', 'success');
                } else {
                    // Remove the temp entry
                    this.pdfs = this.pdfs.filter(pdf => pdf.id !== tempId);
                    this.showNotification(result.message || 'Failed to upload file', 'error');
                }
            } catch (error) {
                console.error('Error uploading file:', error);
                this.showNotification('Failed to upload file', 'error');
                
                // Remove the temp entry
                this.pdfs = this.pdfs.filter(pdf => pdf.id !== tempId);
                
                // Refresh data to ensure UI is in sync with backend
                await this.fetchUserData();
            }
        },

        // Navigation
        openPdf(id) {
            window.location.href = `/view/${id}`;
        },
        
        openChat(pdfId) {
            window.location.href = `/chat`;
        },
        
        openChatSession(id) {
            window.location.href = `/chat`;
        },
        
        openTest(id) {
            window.location.href = `/test`;
        },

        // Delete PDF
        async deletePDF(pdfId) {
            // Confirm deletion
            if (!confirm('Are you sure you want to delete this PDF? This action cannot be undone.')) {
                return;
            }
            
            // Show deletion in progress
            this.showNotification('Deleting PDF...', 'info');
            
            try {
                console.log(`Sending DELETE request to /pdf/${pdfId}`);
                
                // Send delete request to the server
                const response = await fetch(`/pdf/${pdfId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                console.log('Delete response status:', response.status);
                const result = await response.json();
                console.log('Delete response data:', result);
                
                if (result.success) {
                    // Immediately remove PDF from the list to ensure UI sync
                    this.pdfs = this.pdfs.filter(pdf => pdf.id !== pdfId);
                    
                    // Show success notification
                    this.showNotification('PDF deleted successfully', 'success');
                    
                    // Verify backend state by refreshing data
                    await this.fetchUserData();
                } else {
                    this.showNotification(result.message || 'Failed to delete PDF', 'error');
                    // Still refresh data to ensure UI is in sync with backend
                    await this.fetchUserData();
                }
            } catch (error) {
                console.error('Error deleting PDF:', error);
                this.showNotification('Failed to delete PDF: ' + error.message, 'error');
                // Refresh data even on error to ensure UI is in sync with backend
                await this.fetchUserData();
            }
        },

        // Notifications
        showNotification(message, type = 'info') {
            // This could use a toast library in a real app
            // For now, just log to console
            console.log(`Notification (${type}): ${message}`);
            
            // Simple notification element creation
            const notification = document.createElement('div');
            notification.className = `notification notification-${type}`;
            notification.textContent = message;
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.classList.add('notification-show');
            }, 10);
            
            setTimeout(() => {
                notification.classList.remove('notification-show');
                setTimeout(() => {
                    notification.remove();
                }, 300);
            }, 3000);
        }
    }));

    // Dropzone Component for handling drag and drop
    Alpine.data('dropzone', () => ({
        isDragging: false,
        
        handleDragOver(e) {
            e.preventDefault();
            this.isDragging = true;
        },
        
        handleDragLeave() {
            this.isDragging = false;
        },
        
        handleDrop(e) {
            e.preventDefault();
            this.isDragging = false;
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const file = files[0];
                this.$dispatch('file-dropped', { file });
            }
        }
    }));
}); 