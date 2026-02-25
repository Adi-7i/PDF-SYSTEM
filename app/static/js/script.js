function displayQuestions(questions) {
    if (!questions || questions.length === 0) {
        document.getElementById('questions-container').innerHTML = '<p class="alert alert-warning">No questions were generated. Please try again with a different PDF or settings.</p>';
        return;
    }

    const container = document.getElementById('questions-container');
    container.innerHTML = '';

    // Validate questions to ensure we only display properly formatted ones
    const validQuestions = questions.filter(q => {
        // For MCQs, validate they have options and correct_answer
        if (q.options && Array.isArray(q.options)) {
            // Ensure exactly 4 options and valid correct_answer index
            return q.options.length === 4 && 
                   q.correct_answer !== undefined && 
                   typeof q.correct_answer === 'number' &&
                   q.correct_answer >= 0 && 
                   q.correct_answer < 4;
        }
        // For non-MCQs (long questions), just validate they have question text
        return q.question && q.question.trim().length > 0;
    });

    if (validQuestions.length === 0) {
        container.innerHTML = '<p class="alert alert-warning">No valid questions were found. Please try again with a different PDF or settings.</p>';
        return;
    }

    // Sort questions by type - MCQs first
    validQuestions.sort((a, b) => {
        const aIsMCQ = a.hasOwnProperty('options') && Array.isArray(a.options) && a.options.length === 4;
        const bIsMCQ = b.hasOwnProperty('options') && Array.isArray(b.options) && b.options.length === 4;
        if (aIsMCQ && !bIsMCQ) return -1;
        if (!aIsMCQ && bIsMCQ) return 1;
        return 0;
    });

    // Add questions
    validQuestions.forEach((question, index) => {
        const questionCard = document.createElement('div');
        questionCard.className = 'card mb-4 question-card';
        
        // Determine if this is an MCQ
        const isMCQ = question.hasOwnProperty('options') && Array.isArray(question.options) && question.options.length === 4;
        const questionType = isMCQ ? 'Multiple Choice' : 'Long Answer';
        
        // Create card content
        let cardContent = `
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">Question ${index + 1} (${questionType})</h5>
                <div>
                    <button class="btn btn-sm btn-outline-primary print-btn" data-question-id="${index}">
                        <i class="bi bi-printer"></i> Print
                    </button>
                </div>
            </div>
            <div class="card-body">
                <p class="card-text">${question.question}</p>
        `;
        
        // Add options for MCQs
        if (isMCQ) {
            cardContent += '<div class="options-container">';
            const options = ['A', 'B', 'C', 'D'];
            question.options.forEach((option, optIndex) => {
                const isCorrect = optIndex === question.correct_answer;
                cardContent += `
                    <div class="form-check">
                        <input class="form-check-input" type="radio" name="question${index}" id="q${index}opt${optIndex}" ${isCorrect ? 'data-correct="true"' : ''}>
                        <label class="form-check-label" for="q${index}opt${optIndex}">
                            <strong>${options[optIndex]}.</strong> ${option}
                        </label>
                    </div>
                `;
            });
            
            cardContent += `
                </div>
                <div class="mt-3 answer-feedback" style="display: none;">
                    <div class="alert alert-success correct-feedback">
                        <i class="bi bi-check-circle-fill"></i> Correct!
                    </div>
                    <div class="alert alert-danger incorrect-feedback">
                        <i class="bi bi-x-circle-fill"></i> Incorrect. The correct answer is ${options[question.correct_answer]}.
                    </div>
                </div>
            `;
        }
        // Don't show answer guidelines for long questions
        
        // Add source attribution if available
        if (question.source) {
            cardContent += `<p class="text-muted mt-3 small">${question.source}</p>`;
        }
        
        cardContent += '</div>'; // Close card-body
        questionCard.innerHTML = cardContent;
        container.appendChild(questionCard);
        
        // Add event listeners for MCQ options
        if (isMCQ) {
            const options = questionCard.querySelectorAll('input[type="radio"]');
            options.forEach(option => {
                option.addEventListener('change', function() {
                    const feedbackContainer = this.closest('.card-body').querySelector('.answer-feedback');
                    feedbackContainer.style.display = 'block';
                    
                    const correctFeedback = feedbackContainer.querySelector('.correct-feedback');
                    const incorrectFeedback = feedbackContainer.querySelector('.incorrect-feedback');
                    
                    if (this.hasAttribute('data-correct')) {
                        correctFeedback.style.display = 'block';
                        incorrectFeedback.style.display = 'none';
                    } else {
                        correctFeedback.style.display = 'none';
                        incorrectFeedback.style.display = 'block';
                    }
                });
            });
        }
    });

    // Add event listeners for print buttons
    document.querySelectorAll('.print-btn').forEach(button => {
        button.addEventListener('click', function() {
            const questionId = this.getAttribute('data-question-id');
            printQuestion(validQuestions[questionId]);
        });
    });

    document.getElementById('test-results').style.display = 'block';
    document.getElementById('loader').style.display = 'none';
} 