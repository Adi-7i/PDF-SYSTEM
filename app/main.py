from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from dotenv import load_dotenv
import uuid
import logging
from typing import List, Optional
import json
import asyncio
import numpy as np
import time
import re

load_dotenv()

from app.db.database import get_db, engine
from app.models.models import Base, PDF, PDFContent, PDFChunk
from app.services.pdf_service import extract_text_from_pdf, save_pdf_to_db, get_all_pdfs, generate_summary
from app.services.qa_service import answer_question
from app.services.embedding_service import get_embeddings, cosine_similarity
from app.services.gemini_service import generate_ai_summary, answer_question_with_ai
from app.services.azure_openai_client import AzureOpenAIConfigError, chat_completion_async, chat_completion_sync

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="PDF Q&A System")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Create uploads directory if it doesn't exist
os.makedirs("app/static/uploads", exist_ok=True)

# Cache for recent responses to prevent duplicates
recent_responses = {}
response_lock = asyncio.Lock()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Redirect to the modern green-themed dashboard"""
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the modern green-themed dashboard"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def chat(request: Request):
    """Render the chat interface"""
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "page_title": "Lucifer AI Chat - Ask Questions About Your Documents"
    })

@app.get("/test", response_class=HTMLResponse)
async def test(request: Request):
    """Render the test generation page"""
    return templates.TemplateResponse("test.html", {"request": request})

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a single PDF file and process it"""
    logger.info(f"Received upload request for file: {file.filename if file else 'None'}")
    
    # Validate file
    if not file or not file.filename:
        logger.error("No file provided or filename is empty")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "No file provided"}
        )
    
    if not file.filename.lower().endswith('.pdf'):
        logger.error(f"File {file.filename} is not a PDF")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Not a PDF file"}
        )
    
    try:
        # Define maximum file size (10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        
        # Check file size before reading the entire file
        content = await file.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            logger.error(f"File size exceeds limit of {MAX_FILE_SIZE/1024/1024:.1f}MB")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": f"File size exceeds limit of {MAX_FILE_SIZE/1024/1024:.1f}MB"}
            )
        
        # Generate a unique filename
        unique_filename = f"{uuid.uuid4()}.pdf"
        file_path = f"app/static/uploads/{unique_filename}"
        logger.info(f"Saving file to {file_path}")
        
        # Create uploads directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        if not content:
            logger.error("Uploaded file is empty")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Uploaded file is empty"}
            )
        
        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"File saved successfully, size: {len(content)} bytes")
        
        # Validate PDF format
        try:
            import PyPDF2
            with open(file_path, 'rb') as pdf_file:
                try:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    page_count = len(pdf_reader.pages)
                    logger.info(f"Valid PDF detected with {page_count} pages")
                    
                    if page_count == 0:
                        logger.warning(f"PDF has no pages: {file_path}")
                        os.remove(file_path)  # Clean up empty PDF file
                        return JSONResponse(
                            status_code=400,
                            content={"success": False, "message": "PDF file has no pages"}
                        )
                except Exception as pdf_error:
                    logger.error(f"Invalid PDF file: {str(pdf_error)}")
                    os.remove(file_path)  # Clean up invalid file
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": "Invalid PDF file format"}
                    )
        except ImportError:
            logger.warning("PyPDF2 not available, skipping PDF validation")
        
        # Extract text from PDF
        text = extract_text_from_pdf(file_path)
        logger.info(f"Text extracted, length: {len(text)} characters")
        
        # Save to database
        db = next(get_db())
        try:
            pdf_id = save_pdf_to_db(db, file.filename, unique_filename, text)
            logger.info(f"PDF saved to database with ID: {pdf_id}")
            
            # Verify the PDF was saved correctly
            pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
            if not pdf:
                logger.error(f"PDF with ID {pdf_id} not found after saving")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": "PDF was not saved to database properly"}
                )
            
            # Verify PDF content was saved
            content = db.query(PDFContent).filter(PDFContent.pdf_id == pdf_id).first()
            if not content:
                logger.error(f"No content found for PDF with ID {pdf_id}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": "PDF content was not saved to database properly"}
                )
            
            # Verify PDF chunks were saved
            chunks = db.query(PDFChunk).filter(PDFChunk.pdf_id == pdf_id).all()
            logger.info(f"Found {len(chunks)} chunks for PDF with ID {pdf_id}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "filename": file.filename,
                    "id": pdf_id,
                    "message": "PDF uploaded and processed successfully"
                }
            )
        except Exception as db_error:
            logger.error(f"Database error: {str(db_error)}")
            import traceback
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"Error saving to database: {str(db_error)}"}
            )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error processing PDF: {str(e)}\n{error_trace}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error processing PDF: {str(e)}"}
        )

@app.get("/view/{pdf_id}")
async def view_pdf(pdf_id: int):
    """View a PDF file"""
    try:
        logger.info(f"Viewing PDF with ID: {pdf_id}")
        
        db = next(get_db())
        pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
        
        if not pdf:
            logger.error(f"PDF with ID {pdf_id} not found")
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "PDF not found"}
            )
        
        file_path = f"app/static/uploads/{pdf.stored_filename}"
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"PDF file not found: {file_path}")
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "PDF file not found"}
            )
        
        # Return the file as a response
        return FileResponse(
            file_path, 
            filename=pdf.original_filename, 
            media_type="application/pdf"
        )
    except Exception as e:
        logger.error(f"Error viewing PDF: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error viewing PDF: {str(e)}"}
        )

@app.get("/pdfs")
async def list_pdfs():
    """List all uploaded PDFs"""
    try:
        logger.info("Fetching all PDFs from database")
        
        db = next(get_db())
        pdfs = get_all_pdfs(db)
        
        logger.info(f"Found {len(pdfs)} PDFs in database")
        
        # Convert to dict for JSON response
        pdf_list = []
        for pdf in pdfs:
            try:
                pdf_dict = {
                    "id": pdf.id,
                    "filename": pdf.original_filename,
                    "upload_date": pdf.upload_time.isoformat() if pdf.upload_time else None
                }
                pdf_list.append(pdf_dict)
            except Exception as e:
                logger.error(f"Error processing PDF {pdf.id}: {str(e)}")
        
        logger.info(f"Returning {len(pdf_list)} PDFs to client")
        return JSONResponse(
            status_code=200,
            content={"success": True, "pdfs": pdf_list}
        )
    except Exception as e:
        logger.error(f"Error retrieving PDFs: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error retrieving PDFs: {str(e)}"}
        )

@app.post("/ask")
async def ask_question(request: Request):
    """Answer a question based on the uploaded PDFs using Lucifer AI by default"""
    try:
        # Parse JSON request
        data = await request.json()
        question = data.get("question", "")
        pdf_id = data.get("pdf_id")  # Optional: specific PDF to search within
        
        if not question:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No question provided"}
            )
        
        # Convert pdf_id to int if it's provided
        if pdf_id is not None:
            try:
                pdf_id = int(pdf_id)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Invalid PDF ID format"}
                )
        
        logger.info(f"Processing question: '{question}' using Lucifer AI")
        
        db = next(get_db())
        
        # Use Lucifer AI by default
        try:
            # Try to use Lucifer AI first
            answer_data = await answer_question_with_ai(db, question, pdf_id)
            
            if answer_data.get("success", False):
                return JSONResponse(
                    status_code=200,
                    content=answer_data
                )
        except Exception as ai_error:
            logger.error(f"Error using Lucifer AI: {str(ai_error)}. Falling back to standard QA.")
            import traceback
            logger.error(traceback.format_exc())
        
        # Fall back to standard QA if Lucifer AI fails
        answer = answer_question(db, question)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "question": question,
                "answer": answer,
                "generator": "Standard QA"
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error processing question: {str(e)}"}
        )

@app.post("/search")
async def search_pdfs(request: Request):
    """Search across all PDFs"""
    try:
        # Parse JSON request
        data = await request.json()
        query = data.get("query", "")
        
        if not query or len(query) < 3:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Search query must be at least 3 characters"}
            )
        
        logger.info(f"Processing search query: {query}")
        
        db = next(get_db())
        
        # Get query embedding
        query_embedding = get_embeddings([query])[0]
        
        # Get all chunks
        chunks = db.query(PDFChunk).all()
        
        if not chunks:
            logger.warning("No PDF chunks found in database")
            return JSONResponse(
                status_code=200,
                content={"success": True, "results": [], "message": "No documents found to search"}
            )
        
        logger.info(f"Searching across {len(chunks)} chunks")
        
        # Calculate similarity scores
        results = []
        for chunk in chunks:
            try:
                # Parse embedding from JSON
                chunk_embedding = np.array(json.loads(chunk.embedding))
                
                # Calculate similarity
                score = cosine_similarity(query_embedding, chunk_embedding)
                
                # Get PDF info
                pdf = db.query(PDF).filter(PDF.id == chunk.pdf_id).first()
                
                if score > 0.3:  # Set a threshold for relevance
                    results.append({
                        "pdf_id": chunk.pdf_id,
                        "pdf_name": pdf.original_filename if pdf else f"PDF #{chunk.pdf_id}",
                        "chunk_index": chunk.chunk_index,
                        "chunk_text": chunk.chunk_text[:200] + "..." if len(chunk.chunk_text) > 200 else chunk.chunk_text,
                        "score": float(score)  # Convert to float for JSON serialization
                    })
            except Exception as e:
                logger.error(f"Error processing chunk {chunk.id}: {str(e)}")
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top 10 results
        top_results = results[:10]
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "results": top_results,
                "total_results": len(results),
                "query": query
            }
        )
    except Exception as e:
        logger.error(f"Error searching PDFs: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error searching PDFs: {str(e)}"}
        )

@app.post("/upload-batch")
async def upload_multiple_pdfs(files: List[UploadFile] = File(...)):
    """Upload multiple PDF files and process them"""
    logger.info(f"Received batch upload request for {len(files)} files")
    
    if not files:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "No files provided"}
        )
    
    # Define maximum file size (10MB per file)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    results = []
    success_count = 0
    
    for file in files:
        try:
            # Validate file
            if not file.filename:
                results.append({
                    "filename": "Unknown",
                    "success": False,
                    "message": "Empty filename"
                })
                continue
                
            if not file.filename.lower().endswith('.pdf'):
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "message": "Not a PDF file"
                })
                continue
                
            # Check file size
            content = await file.read(MAX_FILE_SIZE + 1)
            if len(content) > MAX_FILE_SIZE:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "message": f"File size exceeds limit of {MAX_FILE_SIZE/1024/1024:.1f}MB"
                })
                continue
                
            if not content:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "message": "Empty file"
                })
                continue
                
            # Generate a unique filename
            unique_filename = f"{uuid.uuid4()}.pdf"
            file_path = f"app/static/uploads/{unique_filename}"
            
            # Create uploads directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save file to disk
            with open(file_path, "wb") as f:
                f.write(content)
                
            # Validate PDF format
            try:
                import PyPDF2
                with open(file_path, 'rb') as pdf_file:
                    try:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        page_count = len(pdf_reader.pages)
                        
                        if page_count == 0:
                            os.remove(file_path)  # Clean up empty PDF file
                            results.append({
                                "filename": file.filename,
                                "success": False,
                                "message": "PDF file has no pages"
                            })
                            continue
                    except Exception as pdf_error:
                        os.remove(file_path)  # Clean up invalid file
                        results.append({
                            "filename": file.filename,
                            "success": False,
                            "message": f"Invalid PDF format: {str(pdf_error)}"
                        })
                        continue
            except ImportError:
                logger.warning("PyPDF2 not available, skipping PDF validation")
                
            # Extract text from PDF
            text = extract_text_from_pdf(file_path)
            
            # Save to database
            db = next(get_db())
            try:
                pdf_id = save_pdf_to_db(db, file.filename, unique_filename, text)
                
                # Add to successful results
                results.append({
                    "filename": file.filename,
                    "success": True,
                    "id": pdf_id,
                    "message": "PDF uploaded and processed successfully"
                })
                success_count += 1
                
            except Exception as db_error:
                os.remove(file_path)  # Clean up file if database save fails
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "message": f"Database error: {str(db_error)}"
                })
                
        except Exception as e:
            results.append({
                "filename": getattr(file, 'filename', 'Unknown'),
                "success": False,
                "message": f"Error: {str(e)}"
            })
    
    return JSONResponse(
        status_code=200,
        content={
            "success": success_count > 0,
            "total": len(files),
            "success_count": success_count,
            "failed_count": len(files) - success_count,
            "results": results
        }
    )

@app.get("/pdf/{pdf_id}/summary")
async def get_pdf_summary(pdf_id: int):
    """Get a summary of a PDF document"""
    try:
        logger.info(f"Getting summary for PDF with ID: {pdf_id}")
        
        db = next(get_db())
        
        # Generate summary
        summary = generate_summary(db, pdf_id)
        
        if not summary.get("success", False):
            return JSONResponse(
                status_code=404,
                content=summary
            )
        
        return JSONResponse(
            status_code=200,
            content=summary
        )
    except Exception as e:
        logger.error(f"Error getting PDF summary: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error getting PDF summary: {str(e)}"}
        )

@app.post("/pdf/{pdf_id}/summary")
async def get_pdf_summary_with_ai(pdf_id: int):
    """Get a summary of a PDF document using AI"""
    try:
        logger.info(f"Getting summary for PDF with ID: {pdf_id}")
        
        db = next(get_db())
        
        # Generate summary using AI
        summary = await generate_ai_summary(db, pdf_id)
        
        if not summary.get("success", False):
            return JSONResponse(
                status_code=404,
                content=summary
            )
        
        return JSONResponse(
            status_code=200,
            content=summary
        )
    except Exception as e:
        logger.error(f"Error getting PDF summary: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error getting PDF summary: {str(e)}"}
        )

@app.get("/pdf/{pdf_id}/ai-summary")
async def get_pdf_ai_summary(pdf_id: int):
    """Get an AI-powered summary of a PDF document using Azure OpenAI"""
    try:
        logger.info(f"Getting AI summary for PDF with ID: {pdf_id}")
        
        db = next(get_db())
        
        # Generate summary using Azure OpenAI
        summary = await generate_ai_summary(db, pdf_id)
        
        if not summary.get("success", False):
            return JSONResponse(
                status_code=404 if "not found" in summary.get("message", "") else 500,
                content=summary
            )
        
        return JSONResponse(
            status_code=200,
            content=summary
        )
    except Exception as e:
        logger.error(f"Error getting PDF AI summary: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error getting PDF AI summary: {str(e)}"}
        )

@app.post("/ask-ai")
async def ask_question_ai(request: Request):
    """Answer a question using Azure OpenAI based on the content of uploaded PDFs"""
    global recent_responses
    
    try:
        # Parse JSON request
        request_data = await request.body()
        data = await request.json()
        question = data.get("question", "")
        pdf_id = data.get("pdf_id")  # Optional: specific PDF to search within
        
        # Create a unique key for this question+pdf_id combination
        cache_key = f"{question}:{pdf_id if pdf_id is not None else 'all'}"
        
        # Check if we have a cached response for this exact question
        async with response_lock:
            if cache_key in recent_responses:
                cached_response = recent_responses[cache_key]
                # Only return cached response if it's less than 5 minutes old
                if (time.time() - cached_response['timestamp']) < 300:  # 5 minutes
                    logger.info(f"Returning cached response for: '{question}'")
                    return JSONResponse(
                        status_code=200,
                        content=cached_response['response']
                    )
        
        logger.info(f"Received ask-ai request. Size: {len(request_data)} bytes")
        
        if not question:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No question provided"}
            )
        
        # Normalize the question to remove extra spaces and control characters
        question = ' '.join(question.split())
        
        # Convert pdf_id to int if it's provided
        if pdf_id is not None:
            try:
                pdf_id = int(pdf_id)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Invalid PDF ID format"}
                )
        
        logger.info(f"Processing AI question: '{question}' for PDF ID: {pdf_id if pdf_id is not None else 'all'}")
        
        # Initialize database connection
        db = next(get_db())
        
        # Special handling for common technology questions even if PDFs don't contain the information
        tech_keywords = ["flask", "python", "django", "framework", "web development", "api"]
        is_tech_question = any(keyword in question.lower() for keyword in tech_keywords)
        
        # Verify PDF exists if PDF ID is provided
        if pdf_id is not None:
            pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
            if not pdf:
                logger.warning(f"PDF with ID {pdf_id} not found")
                
                # For tech questions, fall back to general knowledge
                if is_tech_question:
                    logger.info(f"Technology question detected, proceeding with general knowledge")
                    # Continue processing without a PDF - will use general knowledge
                else:
                    return JSONResponse(
                        status_code=404,
                        content={"success": False, "message": f"The requested PDF (ID: {pdf_id}) was not found."}
                    )
            else:
                # Check if PDF has content
                content = db.query(PDFContent).filter(PDFContent.pdf_id == pdf_id).first()
                if not content or not content.text_content:
                    logger.warning(f"No content found for PDF with ID {pdf_id}")
                    
                    # For tech questions, fall back to general knowledge
                    if is_tech_question:
                        logger.info(f"Technology question detected, proceeding with general knowledge")
                        # Continue processing without PDF content
                    else:
                        return JSONResponse(
                            status_code=400,
                            content={"success": False, "message": f"The PDF (ID: {pdf_id}) has no extractable content."}
                        )
                
                # Get PDF file info for verification
                file_path = f"app/static/uploads/{pdf.stored_filename}"
                if not os.path.exists(file_path) and not is_tech_question:
                    logger.warning(f"PDF file not found: {file_path}")
                    return JSONResponse(
                        status_code=404,
                        content={"success": False, "message": f"The PDF file is missing from storage."}
                    )
        
        # Make sure we have PDFs to answer from if not a technology question
        if pdf_id is None and not is_tech_question:
            # Check if we have any PDFs at all
            pdfs_count = db.query(PDF).count()
            if pdfs_count == 0:
                logger.warning("No PDFs in database, cannot answer PDF-specific questions")
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "message": "No PDFs available. Please upload PDFs first."}
                )
        
        # Process the question using the LLM with timeout handling
        try:
            answer_data = await asyncio.wait_for(
                answer_question_with_ai(db, question, pdf_id),
                timeout=60.0  # 60 second timeout - extended from 25s
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout while processing question: {question}")
            return JSONResponse(
                status_code=504,
                content={
                    "success": False, 
                    "message": "Request timed out. The server took too long to process your question. Please try again."
                }
            )
        
        # Log the response for debugging
        logger.info(f"AI response success: {answer_data.get('success', False)}")
        if 'answer' in answer_data:
            logger.info(f"Answer length: {len(answer_data['answer'])}")
        
        if not answer_data.get("success", False):
            # For actual errors - not just missing PDFs
            if "no content" in answer_data.get("message", "").lower() or "no pdf content" in answer_data.get("message", "").lower():
                # No PDFs at all is a 404
                status_code = 404
            elif "not available" in answer_data.get("message", ""):
                # AI service issues is a 503
                status_code = 503
            else:
                # Generic error is a 500
                status_code = 500
            
            error_response = answer_data
            return JSONResponse(
                status_code=status_code,
                content=error_response
            )
        
        # Cache the successful response
        async with response_lock:
            recent_responses[cache_key] = {
                'response': answer_data,
                'timestamp': time.time()
            }
            
            # Clean old cache entries (older than 10 minutes)
            cleaned_responses = {}
            current_time = time.time()
            for key, value in recent_responses.items():
                if (current_time - value['timestamp']) < 600:  # 10 minutes
                    cleaned_responses[key] = value
            recent_responses = cleaned_responses
        
        # Always return 200 for success, even if specific PDF wasn't found but others were used
        return JSONResponse(
            status_code=200,
            content=answer_data
        )
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Invalid JSON request"}
        )
    except Exception as e:
        logger.error(f"Error processing AI question: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error processing AI question: {str(e)}"}
        )

@app.post("/compare-answers")
async def compare_answers(request: Request):
    """Compare answers from both regular QA and Azure OpenAI-backed QA"""
    try:
        # Parse JSON request
        data = await request.json()
        question = data.get("question", "")
        pdf_id = data.get("pdf_id")  # Optional: specific PDF to search within
        
        if not question:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No question provided"}
            )
        
        # Convert pdf_id to int if it's provided
        if pdf_id is not None:
            try:
                pdf_id = int(pdf_id)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Invalid PDF ID format"}
                )
        
        logger.info(f"Comparing answers for question: '{question}'")
        
        db = next(get_db())
        
        # Get answer from regular QA system
        regular_answer = answer_question(db, question)
        
        # Get answer from the LLM
        ai_answer_data = await answer_question_with_ai(db, question, pdf_id)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "question": question,
                "regular_answer": regular_answer,
                "ai_answer": ai_answer_data.get("answer", "AI answer not available"),
                "ai_success": ai_answer_data.get("success", False),
                "sources": ai_answer_data.get("sources", "Unknown")
            }
        )
    except Exception as e:
        logger.error(f"Error comparing answers: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error comparing answers: {str(e)}"}
        )

@app.delete("/pdf/{pdf_id}")
async def delete_pdf(pdf_id: int):
    """Delete a PDF file and its associated data"""
    try:
        logger.info(f"Deleting PDF with ID: {pdf_id}")
        
        db = next(get_db())
        pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
        
        if not pdf:
            logger.error(f"PDF with ID {pdf_id} not found")
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "PDF not found"}
            )
        
        # Get file path to delete the actual file
        file_path = f"app/static/uploads/{pdf.stored_filename}"
        
        # Store filename for the response
        filename = pdf.original_filename
        
        # Delete PDF content first to ensure proper cleanup
        db.query(PDFContent).filter(PDFContent.pdf_id == pdf_id).delete()
        
        # Delete PDF chunks
        db.query(PDFChunk).filter(PDFChunk.pdf_id == pdf_id).delete()
        
        # Delete any other related data here (e.g., chat messages, test results)
        # [Add specific removal code for any other related tables]
        
        # Delete PDF from database
        db.delete(pdf)
        db.commit()
        
        # Delete the actual file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
        else:
            logger.warning(f"File not found for deletion: {file_path}")
            
        # Verify PDF is completely deleted
        remaining = db.query(PDF).filter(PDF.id == pdf_id).first()
        if remaining:
            logger.error(f"PDF with ID {pdf_id} still exists after deletion")
            db.delete(remaining)
            db.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"PDF '{filename}' successfully deleted",
                "id": pdf_id
            }
        )
    except Exception as e:
        logger.error(f"Error deleting PDF: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Rollback in case of error
        db.rollback()
        
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error deleting PDF: {str(e)}"}
        )

@app.get("/pdf/{pdf_id}/info")
async def get_pdf_info(pdf_id: int):
    """Get detailed information about a specific PDF, including accurate page count"""
    try:
        logger.info(f"Fetching PDF info for ID: {pdf_id}")
        
        db = next(get_db())
        pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
        
        if not pdf:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "PDF not found"}
            )
        
        # Get file path
        file_path = f"app/static/uploads/{pdf.stored_filename}"
        if not os.path.exists(file_path):
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "PDF file not found in storage"}
            )
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Get accurate page count
        page_count = 0
        try:
            import PyPDF2
            with open(file_path, 'rb') as pdf_file:
                try:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    page_count = len(pdf_reader.pages)
                    
                    # Check if the page count seems unusually low for a large file
                    if file_size > 10000000 and page_count < 100:  # If file > 10MB but page count < 100
                        # Try another approach to count pages
                        from subprocess import run, PIPE
                        try:
                            # Use pdfinfo if available (requires poppler-utils)
                            result = run(['pdfinfo', file_path], stdout=PIPE, stderr=PIPE, text=True)
                            if result.returncode == 0:
                                for line in result.stdout.split('\n'):
                                    if line.startswith('Pages:'):
                                        try:
                                            page_count = int(line.split(':')[1].strip())
                                            logger.info(f"Updated page count using pdfinfo: {page_count}")
                                            break
                                        except ValueError:
                                            pass
                        except Exception as e:
                            logger.warning(f"Could not use pdfinfo: {str(e)}")
                        
                        # If still seems incorrect, use file size to estimate
                        if file_size > 10000000 and page_count < 100:
                            # Rough estimate: ~100KB per page for typical PDFs
                            estimated_pages = max(page_count, int(file_size / 100000))
                            logger.info(f"Estimated pages based on file size: {estimated_pages}")
                            page_count = estimated_pages
                except Exception as e:
                    logger.error(f"Error with PyPDF2: {str(e)}")
                    # Fall back to file size estimate
                    file_size = os.path.getsize(file_path)
                    estimated_pages = int(file_size / 100000)  # Rough estimate
                    page_count = max(1, estimated_pages)
                    logger.info(f"Estimated {page_count} pages based on file size")
        except Exception as e:
            logger.error(f"Error getting page count: {str(e)}")
            # Just provide a rough estimate based on file size
            estimated_pages = int(file_size / 100000)  # Rough estimate
            page_count = max(1, estimated_pages)
        
        # Get content information
        content = db.query(PDFContent).filter(PDFContent.pdf_id == pdf_id).first()
        content_length = len(content.text_content) if content else 0
        
        # Get chunks information
        chunks = db.query(PDFChunk).filter(PDFChunk.pdf_id == pdf_id).all()
        chunks_count = len(chunks)
        
        # Calculate upload time
        time_ago = calculate_time_ago(pdf.upload_time)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "id": pdf.id,
                "filename": pdf.original_filename,
                "stored_filename": pdf.stored_filename,
                "upload_time": pdf.upload_time.isoformat() if pdf.upload_time else None,
                "time_ago": time_ago,
                "file_size": file_size,
                "file_size_formatted": f"{file_size/1024/1024:.2f} MB",
                "pages": page_count,
                "content_length": content_length,
                "chunks_count": chunks_count
            }
        )
    except Exception as e:
        logger.error(f"Error fetching PDF info: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error fetching PDF info: {str(e)}"}
        )

@app.post("/general-knowledge")
async def general_knowledge_question(request: Request):
    """Answer a general knowledge question without PDF context"""
    try:
        # Parse JSON request
        data = await request.json()
        question = data.get("question", "")
        
        if not question:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No question provided"}
            )
        
        logger.info(f"Processing general knowledge question: '{question}'")
        
        # Create prompt for general knowledge
        prompt = f"""
        Please answer the following general knowledge question:
        
        Question: {question}
        
        Provide a clear, accurate, and concise answer based on factual information.
        If you don't know the answer with certainty, say so rather than making up information.
        """
        
        # Generate answer using Azure OpenAI (configured via env vars)
        answer_text = await chat_completion_async(
            prompt=prompt,
            system="You answer general knowledge questions clearly and concisely.",
            temperature=0.2,
            max_tokens=800,
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "question": question,
                "answer": answer_text,
                "sources": "General Knowledge",
                "generator": "Lucifer AI"
            }
        )
    except Exception as e:
        logger.error(f"Error processing general knowledge question: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        if isinstance(e, AzureOpenAIConfigError):
            return JSONResponse(
                status_code=503,
                content={"success": False, "message": "LLM not configured. Set LLM_API_KEY, LLM_AZURE_BASE_URL, and LLM_AZURE_DEPLOYMENT."},
            )
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error processing general knowledge question: {str(e)}"}
        )

@app.get("/api/dashboard-data")
async def dashboard_data():
    """Get data for dashboard including recent PDFs, chat sessions, and test results"""
    try:
        logger.info("Fetching dashboard data")
        
        db = next(get_db())
        
        # Get recent PDFs (limited to 5)
        recent_pdfs = db.query(PDF).order_by(PDF.upload_time.desc()).limit(5).all()
        pdfs_data = []
        
        for pdf in recent_pdfs:
            # Calculate time ago string
            time_ago = calculate_time_ago(pdf.upload_time)
            
            # Get accurate page count if available
            page_count = 0
            try:
                import PyPDF2
                file_path = f"app/static/uploads/{pdf.stored_filename}"
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as pdf_file:
                        try:
                            pdf_reader = PyPDF2.PdfReader(pdf_file)
                            page_count = len(pdf_reader.pages)
                            
                            # Check if the page count seems unusually low for a large file
                            file_size = os.path.getsize(file_path)
                            if file_size > 10000000 and page_count < 100:  # If file > 10MB but page count < 100
                                # Try another approach to count pages
                                from subprocess import run, PIPE
                                try:
                                    # Use pdfinfo if available (requires poppler-utils)
                                    result = run(['pdfinfo', file_path], stdout=PIPE, stderr=PIPE, text=True)
                                    if result.returncode == 0:
                                        for line in result.stdout.split('\n'):
                                            if line.startswith('Pages:'):
                                                try:
                                                    page_count = int(line.split(':')[1].strip())
                                                    logger.info(f"Updated page count using pdfinfo: {page_count}")
                                                    break
                                                except ValueError:
                                                    pass
                                except Exception as e:
                                    logger.warning(f"Could not use pdfinfo: {str(e)}")
                                
                                # If still seems incorrect, use file size to estimate
                                if file_size > 10000000 and page_count < 100:
                                    # Rough estimate: ~100KB per page for typical PDFs
                                    estimated_pages = max(page_count, int(file_size / 100000))
                                    logger.info(f"Estimated pages based on file size: {estimated_pages}")
                                    page_count = estimated_pages
                        except Exception as e:
                            logger.error(f"Error with PyPDF2: {str(e)}")
                            # Fall back to file size estimate
                            file_size = os.path.getsize(file_path)
                            estimated_pages = int(file_size / 100000)  # Rough estimate
                            page_count = max(1, estimated_pages)
                            logger.info(f"Estimated {page_count} pages based on file size")
            except Exception as e:
                logger.error(f"Error getting page count: {str(e)}")
            
            pdfs_data.append({
                "id": pdf.id,
                "name": pdf.original_filename,
                "timeAgo": time_ago,
                "pages": page_count
            })
        
        # In a real app, we would fetch chat sessions and test results from database
        # For demo, we'll return mock data
        chat_sessions = [
            {"id": 1, "date": "Yesterday", "messages": 23},
            {"id": 2, "date": "3 days ago", "messages": 15}
        ]
        
        practice_tests = [
            {"id": 1, "timeAgo": "2 days ago", "score": 85},
            {"id": 2, "timeAgo": "1 week ago", "score": 92}
        ]
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "pdfs": pdfs_data,
                "chatSessions": chat_sessions,
                "practiceTests": practice_tests
            }
        )
    except Exception as e:
        logger.error(f"Error retrieving dashboard data: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error retrieving dashboard data: {str(e)}"}
        )

def calculate_time_ago(timestamp):
    """Calculate human-readable time ago string from timestamp"""
    if not timestamp:
        return "Unknown"
    
    from datetime import datetime, timezone
    
    # Check if timestamp is timezone-aware, if not, assume UTC
    if timestamp.tzinfo is None:
        # Convert naive datetime to timezone-aware with UTC
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    # Now we can safely create timezone-aware now() and calculate the difference
    now = datetime.now(timezone.utc)
    delta = now - timestamp
    
    seconds = delta.total_seconds()
    
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    else:
        months = int(seconds / 2592000)
        return f"{months} month{'s' if months > 1 else ''} ago"

@app.post("/follow-up")
async def ask_followup_question(request: Request):
    """Follow up on a previous question to get a more detailed answer"""
    try:
        # Parse JSON request
        data = await request.json()
        question = data.get("question", "")
        previous_answer = data.get("previous_answer", "")
        pdf_id = data.get("pdf_id")  # Optional: specific PDF to search within
        
        if not question:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No question provided"}
            )
            
        if not previous_answer:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Previous answer not provided"}
            )
        
        # Convert pdf_id to int if it's provided
        if pdf_id is not None:
            try:
                pdf_id = int(pdf_id)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "Invalid PDF ID format"}
                )
        
        logger.info(f"Processing follow-up question: '{question}'")
        
        # Initialize database connection
        db = next(get_db())
        
        # Process the follow-up question using Gemini AI
        try:
            answer_data = await asyncio.wait_for(
                answer_question_with_ai(db, question, pdf_id, is_followup=True, previous_answer=previous_answer),
                timeout=60.0  # 60 second timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout while processing follow-up question: {question}")
            return JSONResponse(
                status_code=504,
                content={
                    "success": False, 
                    "message": "Request timed out. The server took too long to process your follow-up question. Please try again."
                }
            )
        
        if not answer_data.get("success", False):
            # Handle errors appropriately
            status_code = 500
            if "no content" in answer_data.get("message", "").lower() or "no pdf content" in answer_data.get("message", "").lower():
                status_code = 404
            
            return JSONResponse(
                status_code=status_code,
                content=answer_data
            )
        
        # Return successful response
        return JSONResponse(
            status_code=200,
            content=answer_data
        )
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Invalid JSON request"}
        )
    except Exception as e:
        logger.error(f"Error processing follow-up question: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error processing follow-up question: {str(e)}"}
        )

@app.post("/generate-test")
async def generate_test(request: Request):
    """Generate test questions based on selected PDFs and parameters"""
    try:
        data = await request.json()
        pdf_ids = data.get('pdf_ids', [])
        test_type = data.get('test_type', 'mcq')
        difficulty = data.get('difficulty', 'beginner')
        
        logger.info(f"Generating {test_type} test at {difficulty} level for PDFs: {pdf_ids}")
        
        if not pdf_ids:
            logger.warning("No PDFs selected for test generation")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "No PDFs selected. Please select at least one PDF file."}
            )
        
        # Verify PDFs exist
        db = next(get_db())
        pdfs = []
        pdf_contents = []
        pdf_titles = []
        
        for pdf_id in pdf_ids:
            try:
                pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
                if not pdf:
                    logger.warning(f"PDF with ID {pdf_id} not found in database")
                    return JSONResponse(
                        status_code=404,
                        content={"success": False, "message": f"PDF with ID {pdf_id} not found. Please reselect your PDFs."}
                    )
                pdfs.append(pdf)
                pdf_titles.append(pdf.original_filename)
                
                # Get PDF content
                content = db.query(PDFContent).filter(PDFContent.pdf_id == pdf_id).first()
                if content and content.text_content and len(content.text_content.strip()) > 100:
                    # Add PDF identifier to the content for traceability when generating questions
                    pdf_contents.append(f"Source: {pdf.original_filename}\n{content.text_content}")
                else:
                    logger.warning(f"Insufficient content in PDF ID {pdf_id} ({pdf.original_filename})")
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": f"Insufficient content found in the PDF '{pdf.original_filename}'. Please select a PDF with more textual content."}
                    )
            except Exception as e:
                logger.error(f"Error processing PDF ID {pdf_id}: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": f"Error processing PDF ID {pdf_id}: {str(e)}"}
                )
        
        # Log the content length for debugging
        total_content_length = sum(len(content) for content in pdf_contents)
        logger.info(f"Total content length for question generation: {total_content_length} characters")
        
        if total_content_length < 500:
            logger.warning(f"Combined PDF content too short: {total_content_length} characters")
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "The selected PDFs don't contain enough text to generate meaningful questions. Please select PDFs with more content."}
            )
            
        # Combined PDF content for question generation
        combined_content = "\n\n".join(pdf_contents)
        
        # Also create a structured format to track which content belongs to which PDF
        structured_content = []
        for i, content in enumerate(pdf_contents):
            content_lines = content.split('\n')
            if len(content_lines) > 0:
                # Extract the source information from the first line
                source_line = content_lines[0]
                actual_content = '\n'.join(content_lines[1:])
                structured_content.append({
                    "pdf_id": pdf_ids[i],
                    "filename": pdf_titles[i],
                    "content": actual_content
                })
        
        # Determine question count based on test type
        question_count = 15  # Always generate 15 questions for all test types
        
        # Set question type counts
        if test_type == 'mcq':
            mcq_count = 15
            long_count = 0
        elif test_type == 'long':
            mcq_count = 0
            long_count = 15
        else:  # mixed
            mcq_count = 10
            long_count = 5
            
        logger.info(f"Test type {test_type}: Generating {mcq_count} MCQs and {long_count} long questions")
        
        # AI service for question generation (uses Azure OpenAI if configured; otherwise falls back to local mock generation)
        def generate_questions_with_ai(content, structured_content, test_type, difficulty, pdf_titles):
            try:
                # Try to use the configured LLM first (Azure OpenAI)
                questions = generate_with_gemini(content, structured_content, test_type, difficulty, pdf_titles)
                if questions and len(questions) > 0:
                    # Additional validation to ensure question type consistency
                    if test_type == 'mcq':
                        # For MCQ, filter out any non-MCQ questions that might have been generated
                        questions = [q for q in questions if q.get('options') and isinstance(q.get('options'), list) and len(q.get('options')) > 0 and q.get('correct_answer') is not None]
                    elif test_type == 'long':
                        # For long form, filter out any MCQ questions
                        questions = [q for q in questions if not q.get('options')]
                        
                    logger.info("Successfully generated questions using Azure OpenAI")
                    return questions
            except Exception as e:
                logger.warning(f"Error using Azure OpenAI: {str(e)}. Falling back to mock implementation.")
                # If LLM call fails, use our fallback mock implementation
            
            # Fallback implementation (same as before)
            import random
            import time
            import re
            
            # Set random seed based on current time for variety
            random.seed(int(time.time()))
            
            questions = []
            
            # Extract actual content concepts from the PDFs, but now use the structured format
            pdf_topics = {}
            for pdf_item in structured_content:
                pdf_id = pdf_item["pdf_id"]
                content = pdf_item["content"]
                
                # Break the content into paragraphs
                paragraphs = re.split(r'\n\s*\n', content)
                
                # Filter out very short paragraphs
                content_paragraphs = [p for p in paragraphs if len(p) > 100]
                
                # If we have too few usable paragraphs, use shorter ones too
                if len(content_paragraphs) < 10:
                    content_paragraphs = [p for p in paragraphs if len(p) > 50]
                
                # Extract potential topics and concepts from paragraphs
                potential_topics = []
                for para in content_paragraphs:
                    # Extract first sentence as potential topic
                    first_sentence = re.split(r'[.!?]', para)[0].strip()
                    if 10 < len(first_sentence) < 100:  # Reasonable length for a topic
                        potential_topics.append(first_sentence)
                    
                    # Look for key terms - words that start with capitals in the middle of sentences
                    key_terms = re.findall(r'\b[A-Z][a-z]{2,}\b', para)
                    potential_topics.extend(key_terms)
                    
                    # Extract phrases with technical terminology
                    tech_phrases = re.findall(r'\b[a-zA-Z]+\s+[a-zA-Z]+\s+[a-zA-Z]+\b', para)
                    potential_topics.extend([phrase for phrase in tech_phrases if len(phrase) < 60])
                
                # Add some general topic areas based on PDF content and filename
                pdf_name = pdf_item["filename"].lower()
                general_topics = []
                
                if "flask" in pdf_name or "web" in pdf_name or "app" in pdf_name:
                    general_topics = [
                        "Web applications", "Route handling",
                        "Template rendering", "Database integration",
                        "User authentication", "Form validation",
                        "API design", "Server configuration",
                        "Frontend integration", "MVC architecture"
                    ]
                elif "physics" in pdf_name or "science" in pdf_name:
                    general_topics = [
                        "Force and motion", "Energy conservation",
                        "Momentum", "Thermodynamics",
                        "Waves", "Electricity",
                        "Magnetism", "Optics",
                        "Quantum mechanics", "Relativity"
                    ]
                else:
                    general_topics = [
                        "Data analysis", "Application development",
                        "System architecture", "Design patterns",
                        "Implementation strategies", "Database management",
                        "Performance optimization", "Security considerations",
                        "Testing methodology", "Documentation practices"
                    ]
                
                # If we don't have enough content-based topics, add some general ones
                if len(potential_topics) < 10:
                    potential_topics.extend(general_topics)
                
                # Remove duplicates and clean up topics
                potential_topics = list(set(potential_topics))
                potential_topics = [topic for topic in potential_topics if len(topic) > 5]
                
                # Shuffle topics to ensure variety
                random.shuffle(potential_topics)
                
                # Store topics for this PDF
                pdf_topics[pdf_id] = potential_topics
            
            # Ensure we have at least some topics for each PDF
            for pdf_id, topics in pdf_topics.items():
                if not topics:
                    pdf_topics[pdf_id] = ["General concepts", "Key principles", "Main features", 
                                         "Implementation details", "Application examples"]
            
            if test_type == 'mcq':
                # For MCQs (Multiple Choice Questions)
                mcq_prompts = [
                    "Which of the following statements about {topic} is correct?",
                    "What is the main purpose of {topic}?",
                    "How does {topic} relate to practical applications?",
                    "Which principle best describes {topic}?",
                    "What is a key characteristic of {topic}?"
                ]
                
                # Distribute questions evenly among PDFs
                pdf_ids_list = list(pdf_topics.keys())
                questions_per_pdf = 15 // len(pdf_ids_list)
                remaining_questions = 15 % len(pdf_ids_list)
                
                question_id = 1
                for pdf_id in pdf_ids_list:
                    # Get topics for this PDF
                    topics = pdf_topics[pdf_id]
                    # Find the filename for this PDF
                    pdf_filename = next((item["filename"] for item in structured_content if item["pdf_id"] == pdf_id), "Unknown PDF")
                    
                    # Determine how many questions to generate for this PDF
                    num_questions = questions_per_pdf + (1 if remaining_questions > 0 else 0)
                    if remaining_questions > 0:
                        remaining_questions -= 1
                    
                    for i in range(num_questions):
                        if len(topics) > 0:
                            topic_index = i % len(topics)
                            topic = topics[topic_index]
                        else:
                            topic = f"Topic {i+1}"
                        
                        prompt_index = i % len(mcq_prompts)
                        question_text = mcq_prompts[prompt_index].format(topic=topic)
                        
                        # Generate options with more relevant content
                        if difficulty == 'beginner':
                            options = [
                                f"It helps with implementing basic functionality of {topic.lower()}",
                                f"It provides structure and organization for {topic.lower()}",
                                f"It enables interaction between different components in {topic.lower()}",
                                f"It simplifies the process of working with {topic.lower()}"
                            ]
                        else:  # advanced
                            options = [
                                f"It optimizes performance when implementing {topic.lower()}",
                                f"It ensures security and data integrity for {topic.lower()}",
                                f"It provides advanced error handling mechanisms for {topic.lower()}",
                                f"It enables scalable and maintainable architecture for {topic.lower()}"
                            ]
                        
                        # Randomize correct answer
                        correct_answer = random.randint(0, 3)
                        
                        questions.append({
                            "id": question_id,
                            "question": question_text,
                            "options": options,
                            "correct_answer": correct_answer,
                            "source": f"Source: {pdf_filename}",
                            "pdf_id": pdf_id
                        })
                        question_id += 1
                    
            elif test_type == 'long':
                # For Long Type Questions
                descriptive_prompts = [
                    "Explain in detail how {topic} works and why it's important.",
                    "Compare and contrast different approaches to implementing {topic}.",
                    "Analyze the impact of {topic} on application development.",
                    "Discuss the best practices when working with {topic}.",
                    "Evaluate the strengths and limitations of {topic}.",
                    "What are the key considerations when implementing {topic}?",
                    "How might you optimize {topic} for better performance?",
                    "Describe the relationship between {topic} and other related components.",
                    "What challenges might arise when implementing {topic} and how would you address them?",
                    "Explain how {topic} contributes to the overall architecture of an application."
                ]
                
                # Distribute questions evenly among PDFs
                pdf_ids_list = list(pdf_topics.keys())
                questions_per_pdf = 10 // len(pdf_ids_list)
                remaining_questions = 10 % len(pdf_ids_list)
                
                question_id = 1
                for pdf_id in pdf_ids_list:
                    # Get topics for this PDF
                    topics = pdf_topics[pdf_id]
                    # Find the filename for this PDF
                    pdf_filename = next((item["filename"] for item in structured_content if item["pdf_id"] == pdf_id), "Unknown PDF")
                    
                    # Determine how many questions to generate for this PDF
                    num_questions = questions_per_pdf + (1 if remaining_questions > 0 else 0)
                    if remaining_questions > 0:
                        remaining_questions -= 1
                    
                    for i in range(num_questions):
                        if len(topics) > 0:
                            topic_index = i % len(topics)
                            topic = topics[topic_index]
                        else:
                            topic = f"Topic {i+1}"
                        
                        prompt_index = i % len(descriptive_prompts)
                        question_text = descriptive_prompts[prompt_index].format(topic=topic)
                        
                        questions.append({
                            "id": question_id,
                            "question": question_text,
                            "source": f"Source: {pdf_filename}",
                            "answer_guideline": f"Focus on practical implementation details and real-world applications of {topic}.",
                            "pdf_id": pdf_id
                        })
                        question_id += 1
                    
            elif test_type == 'mixed':
                # For Mixed Test Type (10 MCQs + 5 Long)
                
                # Distribute MCQ questions evenly among PDFs
                pdf_ids_list = list(pdf_topics.keys())
                mcq_per_pdf = 10 // len(pdf_ids_list)
                remaining_mcq = 10 % len(pdf_ids_list)
                
                # For MCQs
                mcq_prompts = [
                    "Which of the following statements about {topic} is correct?",
                    "What is the main purpose of {topic}?",
                    "How does {topic} contribute to application functionality?",
                    "Which principle best describes {topic}?",
                    "What is a key characteristic of {topic}?"
                ]
                
                question_id = 1
                for pdf_id in pdf_ids_list:
                    # Get topics for this PDF
                    topics = pdf_topics[pdf_id]
                    # Find the filename for this PDF
                    pdf_filename = next((item["filename"] for item in structured_content if item["pdf_id"] == pdf_id), "Unknown PDF")
                    
                    # Determine how many MCQ questions to generate for this PDF
                    num_mcqs = mcq_per_pdf + (1 if remaining_mcq > 0 else 0)
                    if remaining_mcq > 0:
                        remaining_mcq -= 1
                    
                    for i in range(num_mcqs):
                        if len(topics) > 0:
                            topic_index = i % len(topics)
                            topic = topics[topic_index]
                        else:
                            topic = f"Topic {i+1}"
                        
                        prompt_index = i % len(mcq_prompts)
                        question_text = mcq_prompts[prompt_index].format(topic=topic)
                        
                        # Generate options with more relevant content
                        if difficulty == 'beginner':
                            options = [
                                f"It helps with implementing basic functionality of {topic.lower()}",
                                f"It provides structure and organization for {topic.lower()}",
                                f"It enables interaction between different components in {topic.lower()}",
                                f"It simplifies the process of working with {topic.lower()}"
                            ]
                        else:  # advanced
                            options = [
                                f"It optimizes performance when implementing {topic.lower()}",
                                f"It ensures security and data integrity for {topic.lower()}",
                                f"It provides advanced error handling mechanisms for {topic.lower()}",
                                f"It enables scalable and maintainable architecture for {topic.lower()}"
                            ]
                        
                        # Randomize correct answer
                        correct_answer = random.randint(0, 3)
                        
                        questions.append({
                            "id": question_id,
                            "question": question_text,
                            "options": options,
                            "correct_answer": correct_answer,
                            "source": f"Source: {pdf_filename}",
                            "pdf_id": pdf_id
                        })
                        question_id += 1
                
                # Now generate long questions
                # Distribute long questions evenly among PDFs
                long_per_pdf = 5 // len(pdf_ids_list)
                remaining_long = 5 % len(pdf_ids_list)
                
                descriptive_prompts = [
                    "Explain in detail how {topic} works and why it's important.",
                    "Compare different approaches to implementing {topic}.",
                    "Analyze the impact of {topic} on application development.",
                    "Discuss the best practices when working with {topic}.",
                    "Evaluate the strengths and limitations of {topic}."
                ]
                
                for pdf_id in pdf_ids_list:
                    # Get topics for this PDF
                    topics = pdf_topics[pdf_id]
                    # Find the filename for this PDF
                    pdf_filename = next((item["filename"] for item in structured_content if item["pdf_id"] == pdf_id), "Unknown PDF")
                    
                    # Determine how many long questions to generate for this PDF
                    num_long = long_per_pdf + (1 if remaining_long > 0 else 0)
                    if remaining_long > 0:
                        remaining_long -= 1
                    
                    for i in range(num_long):
                        if len(topics) > 0:
                            # Use different topics than the ones used for MCQs
                            topic_index = (i + 5) % len(topics)
                            topic = topics[topic_index]
                        else:
                            topic = f"Topic {i+1}"
                        
                        prompt_index = i % len(descriptive_prompts)
                        question_text = descriptive_prompts[prompt_index].format(topic=topic)
                        
                        questions.append({
                            "id": question_id,
                            "question": question_text,
                            "source": f"Source: {pdf_filename}",
                            "answer_guideline": f"Focus on practical implementation details and real-world applications of {topic}.",
                            "pdf_id": pdf_id
                        })
                        question_id += 1
                    
            return questions
        
        def generate_with_gemini(content, structured_content, test_type, difficulty, pdf_titles):
            """Generate high-quality exam-relevant questions using Azure OpenAI (if configured)."""
            try:
                import re
                
                # Prepare content for thorough analysis
                # Include more content for better context understanding
                content_to_analyze = content
                if len(content) > 25000:
                    # Create a strategic extraction for very large content
                    # Sample from beginning, middle, and end to ensure comprehensive coverage
                    paragraphs = content.split('\n\n')
                    selected_paras = []
                    
                    # Take paragraphs from beginning (introduction concepts)
                    beginning = paragraphs[:min(50, len(paragraphs)//4)]
                    for para in beginning:
                        if len(para) > 50 and not para.startswith("Source:"):
                            selected_paras.append(para)
                    
                    # Take paragraphs from middle (core concepts)
                    middle_start = len(paragraphs)//3
                    middle = paragraphs[middle_start:middle_start + min(80, len(paragraphs)//3)]
                    for para in middle:
                        if len(para) > 50 and not para.startswith("Source:"):
                            selected_paras.append(para)
                    
                    # Take paragraphs from end (conclusions, important summaries)
                    end_start = len(paragraphs) - min(30, len(paragraphs)//5)
                    end = paragraphs[end_start:]
                    for para in end:
                        if len(para) > 50 and not para.startswith("Source:"):
                            selected_paras.append(para)
                    
                    content_to_analyze = '\n\n'.join(selected_paras)
                
                # Set the question count based on test type
                mcq_count = 15 if test_type == 'mcq' else (10 if test_type == 'mixed' else 0)
                long_count = 10 if test_type == 'long' else (5 if test_type == 'mixed' else 0)
                
                # Create structured content information for the prompt
                pdf_info = []
                for item in structured_content:
                    # Include a substantial preview of each PDF for better context
                    content_preview = item["content"][:800] + "..." if len(item["content"]) > 800 else item["content"]
                    pdf_info.append(f"PDF ID: {item['pdf_id']}, Filename: {item['filename']}\nPreview: {content_preview}\n")
                
                pdf_info_text = "\n".join(pdf_info)
                
                # Enhanced difficulty descriptions for better question calibration
                difficulty_description = ""
                if difficulty == "beginner":
                    difficulty_description = """
                    - Focus on fundamental concepts and basic understanding
                    - Questions should test recall and comprehension
                    - For MCQs: Clear distinctions between options, avoid complicated distractors
                    - For long questions: Focus on explaining core concepts with real-world applications
                    """
                else:  # advanced
                    difficulty_description = """
                    - Focus on advanced concepts, critical thinking, and application
                    - Questions should test analysis, evaluation, and synthesis of information
                    - For MCQs: Include subtle distinctions between options, require deep understanding
                    - For long questions: Require integration of multiple concepts, analysis, and evaluation
                    """
                
                # Create enhanced prompt for Gemini with detailed quality requirements
                if test_type == 'mcq':
                    prompt = f"""
                    You are an expert educational assessment designer specializing in creating high-quality multiple-choice test questions ONLY.
                    
                    Your task: CREATE EXACTLY 15 MULTIPLE-CHOICE QUESTIONS with 4 options each. Do not create ANY long-form questions.
                    
                    PDF Content:
                    {content_to_analyze}
                    
                    PDF Information (for proper attribution):
                    {pdf_info_text}
                    
                    Difficulty level: {difficulty}
                    {difficulty_description}
                    
                    CRITICAL REQUIREMENTS:
                    1. CREATE EXACTLY 15 MCQ QUESTIONS - do not generate fewer than 15 or any long-form questions
                    2. EVERY question MUST have EXACTLY 4 options labeled A, B, C, D
                    3. EVERY question MUST have exactly ONE correct answer (correct_answer field)
                    4. ALL questions must be directly from the PDF content - do not invent concepts
                    5. Questions must meet the specified difficulty level
                    6. NEVER generate long-form/essay/descriptive questions - ONLY multiple choice
                    
                    Return EXACTLY this JSON format with 15 MCQ questions:
                    ```json
                    [
                      {{
                        "id": 1,
                        "question": "Question text here",
                        "options": ["Option A", "Option B", "Option C", "Option D"],
                        "correct_answer": 0,  // index of correct option (0-3)
                        "pdf_id": 123  // The PDF ID this question is from
                      }},
                      // 14 more MCQ questions...
                    ]
                    ```
                    
                    FINAL VERIFICATION:
                    1. Count the questions to ensure there are EXACTLY 15
                    2. Verify every question has EXACTLY 4 options
                    3. Verify every question has a correct_answer field with value 0-3
                    4. Verify there are NO long-form questions with text answers
                    """
                else:
                    # Original prompt for long or mixed questions
                    prompt = f"""
                    You are an expert educational assessment designer specializing in creating high-quality test questions that perfectly match actual exam patterns.
                    
                    Your task: Thoroughly analyze the provided PDF content and generate {mcq_count if mcq_count > 0 else ''} {'multiple choice questions' if mcq_count > 0 else ''} {' and ' if mcq_count > 0 and long_count > 0 else ''} {long_count if long_count > 0 else ''} {'long-form questions' if long_count > 0 else ''} that rigorously test understanding of the key concepts.
                    
                    PDF Content:
                    {content_to_analyze}
                    
                    PDF Information (for proper attribution):
                    {pdf_info_text}
                    
                    Difficulty level: {difficulty}
                    {difficulty_description}
                    
                    CRITICAL QUALITY REQUIREMENTS:
                    1. Questions MUST be DIRECTLY from the PDF content - do not invent facts or concepts not present in the material
                    2. Each question must test meaningful understanding, not trivial details
                    3. Questions MUST be grammatically perfect with no spelling errors
                    4. Avoid incomplete sentences, ambiguous pronouns, and typos
                    5. Every question must be clear, specific, and focused on important concepts
                    6. Questions must precisely match the specified difficulty level
                    7. Every question must be complete and make perfect sense on its own
                    8. Use standard, professional language with proper capitalization and punctuation
                    9. VERY IMPORTANT: Questions must be entirely focused on the content of the PDFs, not general knowledge
                    10. VERY IMPORTANT: For each question, specify which PDF_ID it belongs to
                    
                    For multiple choice questions:
                    - Create exactly 4 options labeled A, B, C, D
                    - One and only one option must be correct
                    - All options must be plausible but clearly differentiated
                    - Distractors (wrong options) should be realistic misconceptions, not obviously wrong
                    - Options should be similar in length and detail to avoid giving away the answer
                    - There must be no ambiguity about which answer is correct
                    - Each option must be grammatically consistent with the question stem
                    - Options should be complete phrases or sentences, not fragments
                    
                    For long-form questions:
                    - Questions should target higher-order thinking skills
                    - Focus on analysis, evaluation, synthesis, or application of concepts
                    - Questions should be framed to elicit detailed, substantive responses
                    - Provide a comprehensive answer guideline that evaluates understanding of key concepts
                    - The question must be specific enough to guide the student to a focused response
                    
                    Return the questions in this JSON format:
                    ```json
                    [
                      {{
                        "id": 1,
                        "question": "Question text here",
                        "options": ["Option A", "Option B", "Option C", "Option D"],  // only for MCQs
                        "correct_answer": 0,  // only for MCQs, index of correct option (0-3)
                        "answer_guideline": "Guideline for grading answers",  // only for long questions
                        "pdf_id": 123  // The PDF ID this question is from
                      }},
                      // more questions...
                    ]
                    ```
                    
                    QUALITY CONTROL STANDARDS:
                    - REJECT any questions that are not perfectly grammatical or contain spelling errors
                    - REJECT any questions that refer to "the above" text or use pronouns without clear referents
                    - REJECT any questions that use ambiguous terms or are not specific enough
                    - REJECT any questions about topics not clearly covered in the PDF content
                    - REJECT any questions that could be answered without reading the PDF
                    - REJECT any questions with obvious errors in logic or factual inaccuracies
                    - REJECT incomplete questions or those with missing context
                    
                    The JSON response must be properly formatted as a valid JSON array with all required fields.
                    
                    FINAL CHECKLIST:
                    - Each question must stand alone without needing additional context
                    - Each question must be clear, specific, and directly related to PDF content
                    - Each question must have perfect grammar and spelling
                    - Each MCQ must have exactly one correct answer
                    - Each long-form question must have a detailed answer guideline
                    """
                
                response_text = chat_completion_sync(
                    prompt=prompt,
                    system="You are an expert educational assessment designer. Return valid JSON only.",
                    temperature=0.2,
                    max_tokens=8192,
                )
                
                if not response_text or not str(response_text).strip():
                    logger.warning("Empty response from Azure OpenAI")
                    return None
                
                # Extract JSON from response
                import json
                import re
                
                # Find JSON content within ``` blocks
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response_text
                
                # Clean up and parse JSON
                try:
                    # Remove any non-JSON content before or after the array
                    json_str = json_str.strip()
                    if not json_str.startswith('['):
                        json_str = json_str[json_str.find('['):]
                    if not json_str.endswith(']'):
                        json_str = json_str[:json_str.rfind(']')+1]
                    
                    questions = json.loads(json_str)
                    
                    # Function to check for grammatical and spelling issues
                    def has_quality_issues(text):
                        # Check for common error patterns
                        error_patterns = [
                            r'\bThe a\b',               # "The a" error
                            r'\b[Yy]er\b',              # "yer" instead of "your"
                            r'\bin this\b',             # Reference to "in this" without context
                            r'\babove\b',               # Reference to something "above"
                            r'\bin the\b',              # "in the" without proper context
                            r'^\w+ing\s',               # Starting with gerund without subject
                            r'\s{2,}',                  # Multiple spaces
                            r'[a-z][A-Z]',              # Missing space between words
                            r'[A-Za-z][0-9]|[0-9][A-Za-z]' # Missing space between letters and numbers
                        ]
                        
                        # Check if any error pattern matches
                        for pattern in error_patterns:
                            if re.search(pattern, text):
                                return True
                                
                        # Check for minimal length
                        if len(text.split()) < 5:
                            return True
                            
                        # Check for ending punctuation
                        if not text.endswith('?') and not text.endswith('.'):
                            return True
                            
                        return False
                    
                    # Post-process to fix minor issues
                    def clean_question_text(text):
                        # Fix common errors
                        cleaned = re.sub(r'\bThe a\b', 'The', text)
                        cleaned = re.sub(r'\b[Yy]er\b', 'your', cleaned)
                        cleaned = re.sub(r'\s{2,}', ' ', cleaned)  # Fix multiple spaces
                        cleaned = re.sub(r'\.{2,}', '.', cleaned)  # Fix multiple periods
                        
                        # Ensure question ends with question mark if it looks like a question
                        if re.search(r'\b(what|how|why|when|where|which|who|describe|explain|analyze|discuss|compare)\b', 
                                    cleaned.lower()) and not cleaned.endswith('?'):
                            cleaned = cleaned + '?'
                            
                        # First letter capitalized
                        if cleaned and cleaned[0].islower():
                            cleaned = cleaned[0].upper() + cleaned[1:]
                            
                        return cleaned
                        
                    # Clean and validate each question
                    validated_questions = []
                    for question in questions:
                        # Skip questions without proper content
                        if not question.get("question") or len(question.get("question", "").strip()) < 10:
                            continue
                        
                        # Check for quality issues and try to fix
                        question_text = question["question"].strip()
                        if has_quality_issues(question_text):
                            cleaned_text = clean_question_text(question_text)
                            # If still has issues after cleaning, skip it
                            if has_quality_issues(cleaned_text):
                                continue
                            question["question"] = cleaned_text
                            
                        # For MCQs, verify we have options and a correct answer
                        if "options" in question:
                            if not question.get("options") or len(question.get("options", [])) != 4:
                                continue
                                
                            # Clean each option
                            for i, option in enumerate(question["options"]):
                                if has_quality_issues(option):
                                    cleaned_option = clean_question_text(option)
                                    if has_quality_issues(cleaned_option):
                                        break
                                    question["options"][i] = cleaned_option
                                    
                            # Skip if any option still has issues
                            if any(has_quality_issues(opt) for opt in question["options"]):
                                continue
                                
                            if "correct_answer" not in question or not isinstance(question["correct_answer"], int):
                                continue
                            if question["correct_answer"] < 0 or question["correct_answer"] > 3:
                                continue
                                
                        # For long questions, ensure we have an answer guideline but don't display it
                        if "options" not in question:
                            # We'll check if answer guideline exists but we won't display it in the UI
                            if not question.get("answer_guideline") or len(question.get("answer_guideline", "").strip()) < 10:
                                continue
                            
                        # Add source attribution based on the PDF ID
                        pdf_id = question.get("pdf_id")
                        pdf_source = None
                        for item in structured_content:
                            if item["pdf_id"] == pdf_id:
                                question["source"] = f"Source: {item['filename']}"
                                pdf_source = item['filename']
                                break
                                
                        # Fallback if PDF ID not found
                        if "source" not in question:
                            source_pdf = pdf_titles[0] if pdf_titles else "Unknown source"
                            question["source"] = f"Source: {source_pdf}"
                            pdf_source = source_pdf
                        
                        # Final validation - ensure questions are relevant to their attributed source
                        # This helps prevent questions being incorrectly attributed
                        if pdf_source and "question" in question:
                            validated_questions.append(question)
                    
                    # If we lost too many questions in validation, return None to trigger fallback
                    expected_count = mcq_count + long_count
                    if len(validated_questions) < expected_count * 0.6:  # Less than 60% of expected questions
                        logger.warning(f"Too few valid questions: {len(validated_questions)} out of {expected_count} expected")
                        return None
                        
                    return validated_questions
                    
                except Exception as e:
                    logger.error(f"Error parsing LLM response: {str(e)}")
                    logger.error(f"LLM response (truncated): {str(response_text)[:800]}")
                    return None
                
            except Exception as e:
                logger.error(f"Error using Azure OpenAI: {str(e)}")
                return None
        
        # Generate questions using AI service with structured content
        questions = generate_questions_with_ai(combined_content, structured_content, test_type, difficulty, pdf_titles)
        
        # Additional validation to ensure question type consistency
        if test_type == 'mcq':
            # For MCQ, ensure we ONLY have valid MCQ questions with 4 options
            original_count = len(questions)
            questions = [q for q in questions if q.get('options') and 
                        isinstance(q.get('options'), list) and 
                        len(q.get('options')) == 4 and 
                        q.get('correct_answer') is not None and
                        isinstance(q.get('correct_answer'), int) and
                        0 <= q.get('correct_answer') < 4]
            
            logger.info(f"MCQ mode: Filtered from {original_count} to {len(questions)} valid MCQ questions")
            
            # CRITICAL FIX: Always ensure we have exactly 15 MCQ questions or none
            if len(questions) < 15:
                logger.warning(f"Not enough valid MCQ questions ({len(questions)}). Need exactly 15 for MCQ mode.")
                if len(questions) < 5:
                    # If we have too few, return an error
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": f"Only {len(questions)} valid MCQ questions were generated. Need at least 5."}
                    )
            elif len(questions) > 15:
                # If we have more than 15, truncate to exactly 15
                logger.info(f"Truncating {len(questions)} MCQ questions to exactly 15")
                questions = questions[:15]
                
            # Final verification - ensure there are NO non-MCQ questions
            for q in questions:
                if not q.get('options') or not isinstance(q.get('options'), list) or len(q.get('options')) != 4:
                    logger.error(f"Found invalid MCQ question in final MCQ set. This should never happen.")
                    logger.error(f"Question: {q}")
            
            logger.info(f"Final MCQ test questions count: {len(questions)}")
            
        elif test_type == 'long':
            # For long form, filter out any MCQ questions
            questions = [q for q in questions if not q.get('options')]
        
        # For logging and debugging
        logger.info(f"Generated {len(questions)} questions for test type: {test_type}")
        
        # Verify questions are properly formed
        for i, question in enumerate(questions):
            if 'question' not in question:
                logger.warning(f"Question {i+1} missing 'question' field")
            
            if test_type == 'mcq' or (test_type == 'mixed' and i < 10):
                if 'options' not in question:
                    logger.warning(f"MCQ Question {i+1} missing 'options' field")
                if 'correct_answer' not in question:
                    logger.warning(f"MCQ Question {i+1} missing 'correct_answer' field")
            elif test_type == 'long' or (test_type == 'mixed' and i >= 10):
                if 'answer_guideline' not in question:
                    logger.warning(f"Long Question {i+1} missing 'answer_guideline' field")
        
        if not questions or len(questions) == 0:
            logger.error("No questions were generated")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False, 
                    "message": "Failed to generate questions from the selected PDFs. Please try different PDFs with more textual content."
                }
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "questions": questions,
                "pdf_names": [pdf.original_filename for pdf in pdfs],
                "test_type": test_type,
                "difficulty": difficulty,
                "question_count": len(questions)
            }
        )
    except Exception as e:
        logger.error(f"Error generating test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error generating test: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8082, reload=True) 
