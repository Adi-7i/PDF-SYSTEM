# AI-Powered PDF Q&A System

A robust AI-powered PDF-based Q&A system built with Python and FastAPI that allows users to upload multiple PDFs and ask questions about their content. Now featuring Google's Gemini AI for enhanced summaries and more accurate answers!

## Features

- Upload and process multiple PDF files
- Extract and understand text from PDFs
- Ask questions about the content of uploaded PDFs
- Get accurate answers based on the PDF content
- **NEW: Gemini AI integration for advanced summarization and question answering**
- **NEW: Compare standard vs AI-powered answers**
- Clean and intuitive web interface
- Batch upload functionality
- PDF content verification

## Requirements

- Python 3.8+
- FastAPI
- SQLAlchemy
- PyPDF2
- Google's Generative AI SDK
- Other dependencies listed in requirements.txt

## Installation

1. Clone the repository:
```
git clone <repository-url>
cd pdfbook
```

2. Create and activate a virtual environment:
```
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

3. Install the required packages:
```
pip install -r requirements.txt
```

4. Set up environment variables:
```
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your Gemini API key
# Get your API key from https://aistudio.google.com/
```

## Usage

1. Start the application:
```
python run.py
```

2. Open your browser and navigate to `http://localhost:8082`

3. Upload PDF files using the upload form

4. Ask questions about the content of the uploaded PDFs

5. Use the Gemini AI toggle to get enhanced AI-powered answers

6. View detailed AI summaries of your PDF documents

## Project Structure

```
pdfbook/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   │   └── database.py
│   ├── models/
│   │   └── models.py
│   ├── services/
│   │   ├── embedding_service.py
│   │   ├── gemini_service.py    # New Gemini AI integration
│   │   ├── pdf_service.py
│   │   └── qa_service.py
│   ├── static/
│   │   ├── css/
│   │   │   ├── styles.css
│   │   │   └── gemini.css       # Gemini styling
│   │   ├── js/
│   │   │   ├── main.js
│   │   │   └── gemini.js        # Gemini functionality
│   │   └── uploads/
│   ├── templates/
│   │   └── index.html
│   └── main.py
├── venv/
├── .env.example
├── README.md
└── requirements.txt
```

## How It Works

1. **PDF Upload**: Users upload PDF files through the web interface
2. **Text Extraction**: The system extracts text from the PDFs using PyPDF2
3. **Text Processing**: The text is split into chunks and processed
4. **Embedding Generation**: Embeddings are generated for each chunk
5. **Question Answering**: 
   - **Standard Mode**: The system finds the most relevant chunks using similarity search
   - **Gemini AI Mode**: The system uses Google's Gemini AI to analyze the PDF content and generate more accurate, context-aware answers

## Gemini AI Features

### AI-Powered PDF Summaries
- Generate comprehensive summaries of PDF documents
- Extract key topics and themes
- Identify important keywords
- Format information in a structured, readable way

### Enhanced Question Answering
- More accurate answers to complex questions
- Better understanding of context and nuance
- Proper citation of sources from the PDF
- Option to compare with standard embedding-based answers

### Setup
To use the Gemini AI features:
1. Obtain an API key from [Google AI Studio](https://aistudio.google.com/)
2. Add your key to the `.env` file
3. Restart the application

## Future Improvements

- Add user authentication
- Implement document categorization
- Add support for more document types (DOCX, TXT, etc.)
- Enhance batch processing capabilities
- Integrate additional AI models for specialized domains # PDF-SYSTEM
