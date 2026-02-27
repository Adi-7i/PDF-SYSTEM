import os
import logging
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import re
import nltk
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import sympy as sp
import random

from app.models.models import PDF, PDFContent, PDFChunk
from .azure_openai_client import AzureOpenAIConfigError, chat_completion_async, chat_completion_sync

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Downloading at import-time can hang in offline environments; keep it opt-in.
if os.environ.get("NLTK_AUTO_DOWNLOAD", "false").lower() == "true":
    try:
        nltk.download("punkt", quiet=True)
        nltk.download("vader_lexicon", quiet=True)
        nltk.download("averaged_perceptron_tagger", quiet=True)
        logger.info("NLTK data downloaded successfully")
    except Exception as e:
        logger.warning(f"Failed to download NLTK data: {str(e)}")

# AI Identity configuration
AI_NAME = "Lucifer"
AI_VERSION = "1.0.0"
AI_CREATOR = "Lucifer"
AI_DESCRIPTION = "An intelligent assistant that can analyze documents, answer questions, and engage in natural conversation."

# Define AI model configuration
TEMPERATURE = 0.2  # Lower temperature for more factual responses
MAX_OUTPUT_TOKENS = 2048  # Maximum length of generated text

def _llm_configured() -> bool:
    # Primary config requested by user + common fallbacks.
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("LLM_AZURE_BASE_URL") or os.environ.get("AZURE_OPENAI_ENDPOINT") or os.environ.get("AZURE_OPENAI_BASE_URL")
    deployment = os.environ.get("LLM_AZURE_DEPLOYMENT") or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    return bool(api_key and base_url and deployment)


async def _llm_generate(prompt: str, *, temperature: float = TEMPERATURE, max_tokens: int = MAX_OUTPUT_TOKENS) -> str:
    return await chat_completion_async(
        prompt=prompt,
        system=f"You are {AI_NAME}, a helpful assistant.",
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _llm_generate_sync(prompt: str, *, temperature: float = TEMPERATURE, max_tokens: int = MAX_OUTPUT_TOKENS) -> str:
    return chat_completion_sync(
        prompt=prompt,
        system=f"You are {AI_NAME}, a helpful assistant.",
        temperature=temperature,
        max_tokens=max_tokens,
    )


def llm_available() -> bool:
    # Evaluate at request-time so loading `.env` after import still works.
    return _llm_configured()

async def generate_ai_summary(db: Session, pdf_id: int) -> Dict[str, Any]:
    """
    Generate an AI-powered summary of a PDF document using Lucifer AI.
    Returns a dictionary with summary information.
    """
    logger.info(f"Generating AI summary for PDF {pdf_id} using Lucifer")
    
    if not llm_available():
        logger.error("LLM not configured. Cannot generate AI summary.")
        return {
            "success": False,
            "message": "AI summary generation not available. Configure LLM_API_KEY, LLM_AZURE_BASE_URL, and LLM_AZURE_DEPLOYMENT.",
        }
    
    # Get PDF information
    pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
    if not pdf:
        logger.error(f"PDF with ID {pdf_id} not found")
        return {
            "success": False,
            "message": "PDF not found"
        }
    
    # Get PDF content
    pdf_content = db.query(PDFContent).filter(PDFContent.pdf_id == pdf_id).first()
    if not pdf_content:
        logger.error(f"Content for PDF {pdf_id} not found")
        return {
            "success": False,
            "message": "PDF content not found"
        }
    
    try:
        # Extract text content from the PDF
        text_content = pdf_content.text_content
        
        # If text is too large, limit it to a reasonable size
        if len(text_content) > 30000:
            logger.info(f"Text content too large ({len(text_content)} chars), truncating to 30,000 chars")
            text_content = text_content[:30000] + "..."
        
        # Create prompt for summary generation
        prompt = f"""
        You are {AI_NAME}, an intelligent AI assistant with a friendly and helpful personality.
        
        Please generate a comprehensive summary of the following PDF document: "{pdf.original_filename}".
        
        The summary should include:
        1. A title and brief overview (2-3 sentences)
        2. Main topics and key points (3-5 bullet points)
        3. Important details, findings, or conclusions
        4. Any notable figures, statistics, or dates mentioned
        5. 5-10 keywords that best represent the document content
        
        Format the summary in a clear, structured way with headings. Keep it concise but informative.
        
        Here is the document content:
        
        {text_content}
        """
        
        # Generate summary using Azure OpenAI (configured via env vars)
        summary_text = await _llm_generate(prompt)
        
        # Extract keywords from the summary
        keyword_prompt = f"""
        You are {AI_NAME}, an intelligent AI assistant.
        
        Based on this text, provide exactly 10 keywords or key phrases that best represent the main topics.
        Format as a simple JSON array of strings. Only return the JSON array, nothing else.
        
        Text: {text_content[:5000]}
        """
        
        keywords_text = await _llm_generate(keyword_prompt)
        try:
            # Parse the keywords response
            keywords_text = keywords_text.strip()
            # Clean up the response to ensure it's valid JSON
            if keywords_text.startswith("```json"):
                keywords_text = keywords_text.split("```json")[1].split("```")[0].strip()
            elif keywords_text.startswith("```"):
                keywords_text = keywords_text.split("```")[1].split("```")[0].strip()
            
            keywords = json.loads(keywords_text)
        except Exception as e:
            logger.error(f"Error parsing keywords: {str(e)}")
            keywords = []
        
        result = {
            "success": True,
            "pdf_id": pdf_id,
            "filename": pdf.original_filename,
            "upload_date": pdf.upload_time.isoformat() if pdf.upload_time else None,
            "ai_summary": summary_text,
            "keywords": keywords,
            "content_length": len(text_content),
            "generator": f"{AI_NAME} AI"
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating AI summary: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "success": False,
            "message": f"Error generating AI summary: {str(e)}",
            "error": str(e)
        }

async def answer_question_with_ai(db: Session, question: str, pdf_id: Optional[int] = None, is_followup: bool = False, previous_answer: Optional[str] = None) -> Dict[str, Any]:
    """
    Use Lucifer AI to answer a question based on the content of uploaded PDFs.
    Can be restricted to a specific PDF by providing pdf_id.
    
    Args:
        db: Database session
        question: The question to answer
        pdf_id: Optional ID of a specific PDF to search within
        is_followup: Whether this is a follow-up to a previous answer
        previous_answer: The previous answer if this is a follow-up
        
    Returns:
        Dictionary with the answer and metadata
    """
    logger.info(f"Processing question with Lucifer AI: '{question}'")
    
    # Initialize variables
    relevant_chunks = []
    keywords = []
    all_pdf_content = ""
    
    # Function to detect simplification request
    def detect_simplification_request(text: str) -> bool:
        """
        Detect if the user is asking for a simpler explanation or clarification.
        Returns True if the text contains phrases indicating a request for simplification.
        """
        simplification_phrases = [
            "explain simply", "simpler explanation", "easier to understand",
            "simplify", "make it simple", "explain in simple terms",
            "explain like i'm", "eli5", "dumb it down", "easier format",
            "don't understand", "confused", "make it easier", "clarity",
            "clearer explanation", "layman's terms", "in plain english",
            "more details", "example", "diagram", "more deatiles", "samjhao",
            "I don't get it", "exapmle", "digram", "can you explain",
            "give me more", "detail about", "details about", "give example",
            "what do you mean", "not clear", "unclear", "confusing",
            "this doesn't make sense", "lost me", "too complicated", 
            "too complex", "hard to follow", "difficult to understand",
            "what is that", "what are you talking about", "huh", "what",
            "not sure what", "not sure I understand", "what exactly is",
            "can you clarify", "need clarification", "I'm confused"
        ]
        
        hindi_phrases = [
            "samjh nehi", "samajh nehi", "samajh nahi", "samjh nahi", 
            "samjhao", "batao", "samajh me nahi", "aur batao", 
            "aur detail", "ache se", "kya matlab", "matlab kya hai"
        ]
        
        text_lower = text.lower()
        return (any(phrase in text_lower for phrase in simplification_phrases) or
                any(phrase in text_lower for phrase in hindi_phrases))
    
    # Function to simplify a complex answer
    async def simplify_answer(complex_answer: str, question: str) -> str:
        """
        Create a simplified version of a complex answer.
        Uses the AI model to generate a more accessible explanation.
        """
        simplify_prompt = f"""
        I need to explain the following concept in much simpler terms. 
        The original question was: "{question}"
        
        Here is the complex explanation that needs simplification:
        {complex_answer}
        
        Please rewrite this explanation in extremely simple, accessible language. Use:
        1. Short, simple sentences
        2. Everyday examples if helpful
        3. Analogies that relate to common experiences
        4. Simple vocabulary (avoid jargon)
        5. Bullet points for key ideas
        
        Your simplified explanation should be easy for a non-expert to understand while still being accurate.
        """
        
        try:
            return (await _llm_generate(simplify_prompt)).strip()
        except Exception as e:
            logger.error(f"Error simplifying answer: {str(e)}")
            return f"I tried to simplify, but encountered an error. Here's the original answer: {complex_answer}"
    
    # Function to improve explanation with examples and visuals
    async def enhance_with_examples(complex_answer: str, question: str) -> str:
        """
        Create an improved answer with examples, diagrams, and more accessible explanations.
        """
        enhance_prompt = f"""
        I need to provide a better explanation of the following concept with examples and illustrations. 
        The original question was: "{question}"
        
        Here is my current explanation:
        {complex_answer}
        
        Please rewrite this explanation to:
        1. Include clear, concrete examples
        2. Add a basic diagram explanation (described in text, using simple ASCII art if helpful)
        3. Use step-by-step explanations for complex concepts
        4. Relate to everyday experiences when possible
        5. Use simpler vocabulary with technical terms properly defined
        
        Your enhanced explanation should help someone fully understand this topic with practical examples.
        """
        
        try:
            return (await _llm_generate(enhance_prompt)).strip()
        except Exception as e:
            logger.error(f"Error enhancing answer: {str(e)}")
            return f"I tried to provide better examples, but encountered an error. Here's the original answer: {complex_answer}"
    
    # Handle follow-up requests for better answers
    if is_followup and previous_answer:
        logger.info("This is a follow-up question, generating improved answer...")
        try:
            improved_answer = await generate_followup_answer(question, previous_answer)
            
            return {
                "success": True,
                "question": question,
                "answer": improved_answer,
                "sources": "Follow-up Enhancement",
                "sources_count": 0,
                "generator": f"{AI_NAME} AI",
                "is_conversational": True,
                "previous_answer": improved_answer  # Store this improved answer for potential future follow-ups
            }
        except Exception as e:
            logger.error(f"Error generating follow-up answer: {str(e)}")
            # Fall back to regular question answering
    
    # First, ensure the LLM is configured
    if not llm_available():
        logger.error("LLM not configured. Cannot answer question.")
        return {
            "success": False,
            "message": "AI services not available. Configure LLM_API_KEY, LLM_AZURE_BASE_URL, and LLM_AZURE_DEPLOYMENT.",
            "question": question
        }
    
    # Normalize question and extract keywords
    question_lower = question.lower()
    # Extract meaningful keywords (skip common words and short words)
    stop_words = {"the", "a", "is", "are", "in", "on", "of", "and", "or", "to", "for", "with", "about", "what", "how", "why", "when", "where", "who", "which"}
    keywords = [word for word in question_lower.split() if word not in stop_words and len(word) > 2]
    
    # Get PDF content based on pdf_id
    pdf_contents = []
    pdf_titles = []
    
    if pdf_id is not None:
        # Getting content for a specific PDF
        pdf = db.query(PDF).filter(PDF.id == pdf_id).first()
        if not pdf:
            logger.warning(f"PDF with ID {pdf_id} not found")
            return {
                "success": False,
                "message": f"The requested PDF (ID: {pdf_id}) was not found.",
                "question": question
            }
        
        # Get the PDF content - include the full content for context
        pdf_content = db.query(PDFContent).filter(PDFContent.pdf_id == pdf_id).first()
        if not pdf_content or not pdf_content.text_content:
            logger.warning(f"No content found for PDF with ID {pdf_id}")
            return {
                "success": False,
                "message": f"The PDF (ID: {pdf_id}) has no extractable content.",
                "question": question
            }
        
        # Always include the full PDF text to make sure we don't miss anything
        all_pdf_content = pdf_content.text_content
        pdf_contents.append(all_pdf_content)
        pdf_titles.append(pdf.original_filename)
        
        # Get all chunks for this PDF for better matching
        pdf_chunks = db.query(PDFChunk).filter(PDFChunk.pdf_id == pdf_id).all()
        for chunk in pdf_chunks:
            chunk_text = chunk.chunk_text.lower()
            if any(keyword in chunk_text for keyword in keywords):
                relevant_chunks.append((chunk.chunk_text, chunk.pdf_id))
    else:
        # Getting content from all PDFs - first check if we have any
        pdfs = db.query(PDF).all()
        if not pdfs:
            logger.warning("No PDFs found in database")
            
            # Special handling for general knowledge questions that don't require PDFs
            if is_tech_question(question):
                logger.info("Technology question detected, proceeding with general knowledge")
                tech_response = await handle_tech_question(question)
                if tech_response:
                    return tech_response
            
            # For general conversational queries
            conversational_response = await handle_conversational_query(question)
            if conversational_response:
                return conversational_response
            
            return {
                "success": False,
                "message": "No PDFs have been uploaded. Please upload PDFs first to enable document-based answers.",
                "question": question
            }
        
        # Get all PDF chunks for searching
        all_chunks = db.query(PDFChunk).all()
        
        # Get all PDF contents for fallback
        for pdf in pdfs:
            pdf_content = db.query(PDFContent).filter(PDFContent.pdf_id == pdf.id).first()
            if pdf_content and pdf_content.text_content:
                pdf_contents.append(pdf_content.text_content)
                pdf_titles.append(pdf.original_filename)
        
        # Combine all PDF contents into one string for full search
        all_pdf_content = "\n\n---\n\n".join(pdf_contents)
        
        # Find chunks with keyword matches
        relevant_chunks = []
        for chunk in all_chunks:
            chunk_text = chunk.chunk_text.lower()
            if any(keyword in chunk_text for keyword in keywords):
                # For each matching chunk, store the chunk text and the PDF ID
                relevant_chunks.append((chunk.chunk_text, chunk.pdf_id))
    
    # Check if we have any PDF content to work with
    if not pdf_contents:
        logger.warning("No PDF content available")
        
        # Handle conversational or knowledge-based queries instead
        if is_tech_question(question):
            logger.info("Technology question detected, proceeding with general knowledge")
            tech_response = await handle_tech_question(question)
            if tech_response:
                return tech_response
        
        # For general conversational queries
        conversational_response = await handle_conversational_query(question)
        if conversational_response:
            return conversational_response
        
        return {
            "success": False,
            "message": "No PDF content available to answer questions. Please upload PDFs with text content.",
            "question": question
        }
    
    try:
        # Process PDF contents to create context for the AI
        # Two approaches: First try with the most relevant chunks, 
        # and if we don't get a good answer, try with more context.
        combined_content = ""
        
        # APPROACH 1: Use the most relevant chunks if found
        if relevant_chunks:
            # Sort chunks by relevance (number of keywords matched)
            relevant_chunks.sort(key=lambda chunk: sum(keyword in chunk[0].lower() for keyword in keywords), reverse=True)
            
            # Take the top chunks (up to a token limit to avoid overwhelming the model)
            top_chunks = [chunk[0] for chunk in relevant_chunks[:8]]  # Include more chunks (8 instead of 5)
            combined_content = "\n\n---\n\n".join(top_chunks)
            
            # Create a prompt for the chunks-based approach
            chunks_prompt = f"""
            You are {AI_NAME}, an intelligent AI assistant specializing in analyzing documents and answering questions.
            
            Please answer the following question based ONLY on the PDF content provided below.
            If the answer cannot be derived from the PDF content, clearly state that the information is not in the provided documents.
            Do not fabricate information that isn't in the documents.
            
            Question: {question}
            
            PDF Content:
            {combined_content}
            
            Document Sources: {", ".join(pdf_titles)}
            
            Guidelines:
            1. Answer directly based on the provided document content
            2. Cite relevant sections if appropriate
            3. If the PDF content doesn't contain the answer, say so explicitly
            4. Be precise, concise, and accurate
            5. Format your answer clearly, using markdown if needed
            """
            
                # Generate answer from the model
            try:
                logger.info("Attempting to answer with most relevant chunks first")
                chunks_answer = await _llm_generate(chunks_prompt)
                
                # Check if the answer indicates no information was found
                not_found_phrases = [
                    "i don't have enough information", 
                    "i cannot find", 
                    "not contain", 
                    "does not contain",
                    "doesn't contain",
                    "not in the provided",
                    "not mentioned",
                    "not included",
                    "no information about",
                    "cannot answer"
                ]
                
                info_not_found = any(phrase in chunks_answer.lower() for phrase in not_found_phrases)
                
                if not info_not_found:
                    # We got a good answer from the chunks, use it
                    answer_text = chunks_answer
                else:
                    # No good answer from chunks, try with full content
                    logger.info("No information found in chunks, trying with full PDF content")
                    raise Exception("Information not found in chunks, using full content")
            except Exception as e:
                # Fall back to using more complete content
                logger.info(f"Falling back to full content approach: {str(e)}")
                
                # APPROACH 2: Use more of the PDF content for context
                # For each PDF, include up to 8000 chars of content
                sample_texts = []
                
                for content in pdf_contents:
                    # Use larger samples from each PDF
                    if len(content) > 8000:
                        # Take beginning, middle and end sections
                        beginning = content[:3000]
                        middle_start = max(0, len(content)//2 - 1500)
                        middle = content[middle_start:middle_start + 3000]
                        end = content[-2000:]
                        sample_texts.append(beginning + "\n...\n" + middle + "\n...\n" + end)
                    else:
                        sample_texts.append(content)
                
                full_context = "\n\n---\n\n".join(sample_texts)
                
                # Create a prompt for the full-content approach
                full_prompt = f"""
                You are {AI_NAME}, an intelligent AI assistant specializing in analyzing documents and answering questions.
                
                Please answer the following question based ONLY on the PDF content provided below.
                The content includes samples from the beginning, middle, and end of the documents.
                If the answer cannot be derived from the PDF content, clearly state that the information is not in the provided documents.
                Do not fabricate information that isn't in the documents.
                
                Question: {question}
                
                PDF Content:
                {full_context}
                
                Document Sources: {", ".join(pdf_titles)}
                
                Guidelines:
                1. Answer directly based on the provided document content
                2. Look carefully through the entire document context
                3. If you spot the answer anywhere in the content, provide it
                4. Be precise, concise, and accurate
                5. Format your answer clearly, using markdown if needed
                """
                
                # Generate answer using the full content approach
                answer_text = await _llm_generate(full_prompt)
                
                # If we still don't have a good answer, try one more time with different sampling
                not_found_phrases = [
                    "i don't have enough information", 
                    "i cannot find", 
                    "not contain", 
                    "does not contain",
                    "doesn't contain",
                    "not in the provided",
                    "not mentioned",
                    "not included",
                    "no information about",
                    "cannot answer"
                ]
                
                if any(phrase in answer_text.lower() for phrase in not_found_phrases):
                    logger.info("Still no information found, trying with a different sampling approach")
                    
                    # APPROACH 3: Try a sliding window approach
                    max_window_size = 7000
                    window_content = ""
                    
                    # Use a sliding window over the full content
                    for content in pdf_contents:
                        content = content.strip()
                        if len(content) <= max_window_size:
                            window_content += content + "\n\n---\n\n"
                        else:
                            # Create overlapping windows
                            for i in range(0, len(content), max_window_size // 2):
                                window = content[i:i + max_window_size]
                                if len(window.strip()) > 500:  # Ensure window has significant content
                                    window_content += window + "\n\n---\n\n"
                                if len(window_content) > 15000:  # Limit total context size
                                    break
                    
                    # Create a prompt for the sliding window approach
                    window_prompt = f"""
                    You are {AI_NAME}, an intelligent AI assistant specializing in analyzing documents and answering questions.
                    
                    Please answer the following question based ONLY on the PDF content provided below.
                    The content includes overlapping sections of documents to ensure complete coverage.
                    Search carefully through all sections to find the answer.
                    If the answer cannot be derived from the PDF content, clearly state that the information is not in the provided documents.
                    Do not fabricate information that isn't in the documents.
                    
                    Question: {question}
                    
                    PDF Content:
                    {window_content}
                    
                    Document Sources: {", ".join(pdf_titles)}
                    
                    Guidelines:
                    1. Answer directly based on the provided document content
                    2. Look carefully through ALL the sections
                    3. If you spot the answer anywhere in the content, provide it
                    4. Be precise, concise, and accurate
                    5. Format your answer clearly, using markdown if needed
                    """
                    
                    # Generate answer using the sliding window approach
                    answer_text = await _llm_generate(window_prompt)
        else:
            # No relevant chunks found, try with full content approach directly
            logger.info("No relevant chunks found, using full content approach")
            
            # Use samples from each PDF
            sample_texts = []
            
            for content in pdf_contents:
                # Use multiple samples from each PDF to cover more content
                if len(content) > 8000:
                    # Take beginning, middle and end sections
                    beginning = content[:3000]
                    middle_start = max(0, len(content)//2 - 1500)
                    middle = content[middle_start:middle_start + 3000]
                    end = content[-2000:]
                    sample_texts.append(beginning + "\n...\n" + middle + "\n...\n" + end)
                else:
                    sample_texts.append(content)
            
            full_context = "\n\n---\n\n".join(sample_texts)
            
            # Create a prompt for the full-content approach
            full_prompt = f"""
            You are {AI_NAME}, an intelligent AI assistant specializing in analyzing documents and answering questions.
            
            Please answer the following question based ONLY on the PDF content provided below.
            The content includes samples from the beginning, middle, and end of the documents.
            If the answer cannot be derived from the PDF content, clearly state that the information is not in the provided documents.
            Do not fabricate information that isn't in the documents.
            
            Question: {question}
            
            PDF Content:
            {full_context}
            
            Document Sources: {", ".join(pdf_titles)}
            
            Guidelines:
            1. Answer directly based on the provided document content
            2. Look carefully through the entire document context
            3. If you spot the answer anywhere in the content, provide it
            4. Be precise, concise, and accurate
            5. Format your answer clearly, using markdown if needed
            """
            
            # Generate answer using the full content approach
            answer_text = await _llm_generate(full_prompt)
        
        # Clean and format the answer
        answer_text = clean_response(answer_text, question)
        answer_text = format_code_blocks(answer_text)
        
        # For most questions, add a "thinking" effect
        # Skip for very simple questions
        if len(question.split()) > 3 and "?" in question:
            answer_text = add_thinking_effect(answer_text)
        
        # Check for simplification requests
        if detect_simplification_request(question):
            simplified_answer = simplify_complex_answer(answer_text, question)
            return {
                "success": True,
                "question": question,
                "answer": simplified_answer,
                "sources": pdf_titles,
                "sources_count": len(pdf_titles),
                "generator": f"{AI_NAME} AI",
                "is_conversational": False,
                "previous_answer": answer_text  # Store for potential follow-up questions
            }
        
        return {
            "success": True,
            "question": question,
            "answer": answer_text,
            "sources": pdf_titles,
            "sources_count": len(pdf_titles),
            "generator": f"{AI_NAME} AI",
            "is_conversational": False,
            "previous_answer": answer_text  # Store for potential follow-up questions
        }
        
    except Exception as e:
        logger.error(f"Error generating answer: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Handle specific cases
        if isinstance(e, AzureOpenAIConfigError):
            return {
                "success": False,
                "message": "AI services not available. Configure LLM_API_KEY, LLM_AZURE_BASE_URL, and LLM_AZURE_DEPLOYMENT.",
                "question": question
            }
        
        return {
            "success": False,
            "message": f"Error generating answer: {str(e)}",
            "question": question
        }

def clean_response(answer: str, question: str) -> str:
    """Clean the response to remove any references to previous interactions"""
    # Remove any phrases that might indicate referencing previous context
    patterns_to_remove = [
        r"As (I|we) (discussed|mentioned|talked about|said) (earlier|before|previously)",
        r"(Earlier|Previously|Before) (I|we|you) (mentioned|asked|discussed|talked about)",
        r"(Going back to|Returning to) (our|your) (previous|earlier) (question|discussion|conversation)",
        r"As (I|we) (were|have been) (discussing|talking about)",
        r"(Following up on|Continuing from) (our|your) (previous|earlier|last) (question|point|discussion)"
    ]
    
    # Apply each pattern
    for pattern in patterns_to_remove:
        answer = re.sub(pattern, "", answer, flags=re.IGNORECASE)
    
    # Remove redundant spaces and newlines
    answer = re.sub(r'\n{3,}', '\n\n', answer)
    answer = re.sub(r' {2,}', ' ', answer)
    
    # Ensure the first sentence is properly capitalized if we removed something
    answer = answer.strip()
    if answer and answer[0].islower():
        sentences = answer.split('.')
        if len(sentences) > 0:
            sentences[0] = sentences[0].capitalize()
            answer = '.'.join(sentences)
    
    return answer 

# New functions for enhanced conversational abilities
def detect_greeting(text: str) -> bool:
    """Detect if the input is a common greeting."""
    greetings = [
        'hi', 'hello', 'hey', 'hy', 'greetings', 'good morning', 'good afternoon', 
        'good evening', 'howdy', 'what\'s up', 'sup', 'how are you', 'how\'s it going',
        'how are you doing', 'how do you do', 'nice to meet you', 'pleasure to meet you'
    ]
    
    lower_text = text.lower().strip()
    for greeting in greetings:
        if lower_text.startswith(greeting) or lower_text == greeting:
            return True
    return False

def get_greeting_response(text: str) -> str:
    """Generate a friendly response to greetings."""
    greeting_responses = [
        "Hello! How can I assist you today?",
        "Hi there! What can I help you with?",
        "Hey! I'm here to help. What do you need?",
        "Greetings! How may I be of service?",
        "Hello! I'm your assistant. What can I do for you?",
        "Hi! I'm ready to help with any questions you have.",
        "Hey there! How can I make your day better?",
        "Hello! What would you like to know about?",
        "Hi! I'm excited to help you today. What's on your mind?"
    ]
    
    if "how are you" in text.lower():
        return "I'm doing well, thank you for asking! How can I assist you today?"
    
    return random.choice(greeting_responses)

def analyze_sentiment(text: str) -> Dict[str, Any]:
    """Analyze the sentiment of the input text using VADER."""
    analyzer = SentimentIntensityAnalyzer()
    sentiment_scores = analyzer.polarity_scores(text)
    
    # Also use TextBlob for a second opinion
    blob = TextBlob(text)
    textblob_polarity = blob.sentiment.polarity
    
    return {
        "vader_scores": sentiment_scores,
        "textblob_polarity": textblob_polarity,
        "is_positive": sentiment_scores['compound'] > 0.05,
        "is_negative": sentiment_scores['compound'] < -0.05,
        "is_neutral": -0.05 <= sentiment_scores['compound'] <= 0.05
    }

def handle_math_query(query: str) -> Optional[str]:
    """Handle mathematical queries using SymPy."""
    try:
        # Check if query contains any digits or common mathematical operators
        if not any(char.isdigit() or char in '+-*/^()=' for char in query):
            return None
            
        # Skip programming and technology terms
        tech_terms = ["flask", "python", "django", "api", "web", "framework", "html", "css", 
                     "javascript", "code", "function", "program", "docker", "git", "database"]
        
        for term in tech_terms:
            if term in query.lower():
                return None
        
        # Remove common math query indicators
        math_indicators = ["calculate", "compute", "solve", "what is", "evaluate"]
        for indicator in math_indicators:
            if query.lower().startswith(indicator):
                query = query[len(indicator):].strip()
        
        # Replace text operators with symbols
        query = query.replace("divided by", "/")
        query = query.replace("times", "*")
        query = query.replace("multiplied by", "*")
        query = query.replace("plus", "+")
        query = query.replace("minus", "-")
        query = query.replace("raised to", "**")
        query = query.replace("power", "**")
        
        # Try to evaluate the expression
        result = sp.sympify(query)
        return f"The result is: {result}"
    except Exception:
        # Not a mathematical query or couldn't be parsed
        return None

def is_identity_question(text: str) -> Optional[str]:
    """Check if the question is asking about the AI's identity."""
    identity_patterns = {
        r"who (are|r) you": "I am Lucifer, your intelligent AI assistant. I'm designed to help you with a variety of tasks, from answering questions to analyzing documents and solving problems.",
        r"what (are|r) you": "I am Lucifer, an AI assistant that can help you with document analysis, question answering, and many other tasks. How can I assist you today?",
        r"what'?s your name": "My name is Lucifer. I'm your AI assistant ready to help with whatever you need.",
        r"who (created|made) you": "Created by Lucifer"
    }
    
    lower_text = text.lower()
    for pattern, response in identity_patterns.items():
        if re.search(pattern, lower_text):
            return response
    
    return None

def is_tech_question(text: str) -> bool:
    """Check if the question is about programming or technology."""
    tech_terms = [
        "flask", "python", "django", "api", "web", "framework", "html", "css", 
        "javascript", "react", "node", "express", "database", "sql", "nosql",
        "mongodb", "programming", "code", "software", "development", "git",
        "docker", "cloud", "aws", "azure", "devops", "frontend", "backend",
        "fullstack", "algorithm", "data structure", "api", "rest", "graphql"
    ]
    
    lower_text = text.lower()
    
    # Check for common question patterns about tech
    if lower_text.startswith("what is") or lower_text.startswith("explain") or \
       lower_text.startswith("how does") or lower_text.startswith("tell me about"):
        for term in tech_terms:
            if term in lower_text:
                return True
    
    return False

# Add a new function to simulate thinking process
def add_thinking_effect(answer: str) -> str:
    """
    Modify the answer to make it appear as if the AI is thinking and typing.
    This improves the user experience by making the response seem more natural.
    """
    # Split answer into paragraphs
    paragraphs = answer.split('\n\n')
    
    # Add thinking indicators for longer answers
    if len(paragraphs) > 1:
        thinking_phrases = [
            "Let me think about this...",
            "Analyzing your question...",
            "Searching my knowledge base...",
            "Processing information...",
            "Let me gather the relevant details...",
            "I'm considering the best way to explain this..."
        ]
        
        # Add a thinking phrase at the beginning
        thinking = random.choice(thinking_phrases)
        
        # For longer answers, format with the thinking effect
        return thinking + "\n\n" + answer
    
    return answer

def format_code_blocks(answer: str) -> str:
    """
    Improve code block formatting to make them easier to copy and use.
    """
    # Check if answer likely contains code
    code_indicators = ["```", "def ", "class ", "import ", "function", "<html>", "SELECT ", "CREATE TABLE"]
    has_code = any(indicator in answer for indicator in code_indicators)
    
    if has_code:
        # Ensure code blocks are properly formatted
        if "```" not in answer:
            # Try to detect code sections and wrap them in backticks
            lines = answer.split("\n")
            in_code_block = False
            formatted_lines = []
            
            for line in lines:
                # Detect potential code lines
                is_code_line = any(indicator in line for indicator in ["def ", "class ", "import ", "from ", "    ", "\t", "#", "function", "<", "var ", "const "]) 
                
                if is_code_line and not in_code_block:
                    # Start a new code block with appropriate language
                    if "def " in line or "class " in line or "import " in line:
                        formatted_lines.append("```python")
                    elif "<html>" in line or "<div" in line:
                        formatted_lines.append("```html")
                    elif "function" in line or "var " in line or "const " in line:
                        formatted_lines.append("```javascript")
                    elif "SELECT " in line or "CREATE TABLE" in line:
                        formatted_lines.append("```sql")
                    else:
                        formatted_lines.append("```")
                    in_code_block = True
                
                formatted_lines.append(line)
                
                # Detect end of code block
                if in_code_block and (not line.strip() or line.strip().endswith((".", ":", "?"))) and not line.startswith(("    ", "\t")):
                    formatted_lines.append("```")
                    in_code_block = False
            
            if in_code_block:
                formatted_lines.append("```")
            
            answer = "\n".join(formatted_lines)
        
        # Add a note for users about copying the code
        if "```" in answer:
            copy_note = "\n\n*You can copy and use this code directly in your project.*"
            answer += copy_note
    
    return answer

# Add a function to provide follow-up answers
async def generate_followup_answer(question: str, previous_answer: str, fresh_model=None) -> str:
    """
    Generate a more detailed follow-up answer when user is not satisfied with the initial response.
    """
    try:
        followup_prompt = f"""
        You are {AI_NAME}, a helpful and detailed AI assistant.
        
        The user asked this question: "{question}"
        
        You previously provided this answer, but the user was not satisfied:
        ---
        {previous_answer}
        ---
        
        Please provide a more detailed, comprehensive, and reliable answer to the same question.
        Focus on:
        1. Including more specific examples and evidence
        2. Explaining concepts more clearly with analogies if appropriate
        3. Providing alternative approaches or perspectives
        4. Adding practical implementation details if it's a technical question
        5. Citing reliable sources or principles where relevant
        
        Make your explanation clearer, more detailed, and more authoritative than the previous answer.
        """
        
        improved_answer = await _llm_generate(followup_prompt)
        
        # Format the answer
        improved_answer = format_code_blocks(improved_answer)
        improved_answer = add_thinking_effect(improved_answer)
        
        return improved_answer
    
    except Exception as e:
        logger.error(f"Error generating follow-up answer: {str(e)}")
        return "I apologize, but I'm having trouble generating a better answer. Let me try a different approach to help you with your question."

# Modify handle_tech_question to add thinking effect and format code
async def handle_tech_question(query: str) -> Dict[str, Any]:
    """Handle technology or programming related questions."""
    try:
        # For user questions, first check if there are relevant PDFs
        lower_query = query.lower().strip()
        
        # Get database session
        from app.db.database import get_db
        db = next(get_db())
        
        # Check for PDF content related to the query
        from sqlalchemy import or_
        from app.models.models import PDFContent, PDFChunk
        
        # Get keywords from the query for searching PDF content
        query_keywords = lower_query.split()
        
        # Search for relevant chunks in PDFs
        relevant_chunks = []
        chunks = db.query(PDFChunk).filter(
            or_(*[PDFChunk.chunk_text.ilike(f"%{kw}%") for kw in query_keywords if len(kw) > 3])
        ).limit(5).all()
        
        for chunk in chunks:
            if any(kw in chunk.chunk_text.lower() for kw in query_keywords if len(kw) > 3):
                relevant_chunks.append(chunk.chunk_text)
        
        # If PDF content found relevant to the query
        if relevant_chunks:
            # Create context from relevant chunks
            context = "\n\n".join(relevant_chunks)
            
            # Create a prompt for Gemini to answer based on the PDF content
            pdf_prompt = f"""
            You are {AI_NAME}, a knowledgeable AI assistant.
            
            Please answer the following question based only on the provided PDF content:
            
            Question: {query}
            
            PDF Content:
            {context}
            
            Important instructions:
            1. Base your answer entirely on the PDF content provided
            2. Be concise and direct
            3. If the PDF content doesn't clearly answer the question, say so
            4. Format any code properly with ```language_name code blocks
            5. Do not invent information not present in the PDF content
            """
            
            answer_text = await _llm_generate(pdf_prompt)
            
            return {
                "success": True,
                "question": query,
                "answer": answer_text,
                "sources": "PDF Content",
                "sources_count": len(relevant_chunks),
                "generator": f"{AI_NAME} AI",
                "is_conversational": False,
                "previous_answer": answer_text
            }
        
        # If no relevant PDF content found, fall back to predefined answers or generate from general knowledge
        simple_tech_answers = {
            "what is flask": "Flask is a lightweight web framework for Python used to build web applications.",
            "what is python": "Python is a high-level, interpreted programming language known for its readability and versatility.",
            "what is django": "Django is a high-level Python web framework that enables rapid development of secure and maintainable websites.",
            "what is api": "API (Application Programming Interface) is a set of rules that allows different software applications to communicate with each other.",
            "what is html": "HTML (HyperText Markup Language) is the standard markup language for documents designed to be displayed in a web browser.",
            "what is css": "CSS (Cascading Style Sheets) is a style sheet language used for describing the presentation of a document written in HTML.",
            "what is javascript": "JavaScript is a programming language that enables interactive web pages and is an essential part of web applications."
        }
        
        # Check if the query matches any of our predefined simple questions
        if lower_query in simple_tech_answers:
            return {
                "success": True,
                "question": query,
                "answer": simple_tech_answers[lower_query],
                "sources": "Technology Knowledge",
                "sources_count": 0,
                "generator": f"{AI_NAME} AI",
                "is_conversational": True,
                "previous_answer": simple_tech_answers[lower_query]
            }
        
        # For more complex queries, create a focused prompt that emphasizes brevity
        tech_prompt = f"""
        You are {AI_NAME}, a knowledgeable AI assistant specializing in programming and technology.
        
        Please answer the following question about technology or programming:
        
        Question: {query}
        
        Important instructions:
        1. Be extremely concise and direct - no unnecessary explanations
        2. Answer ONLY what was asked - do not provide unrequested information
        3. If it's a "what is X" question, provide a single sentence definition
        4. Only provide code examples if specifically requested
        5. Focus on accuracy and brevity above all else
        
        If your answer includes code examples:
        1. Make sure to format them properly with ```language_name code blocks
        2. Keep examples minimal but functional
        3. Include only necessary imports
        """
        
        answer_text = await _llm_generate(tech_prompt)
        
        # Further trim the response for brevity
        sentences = answer_text.split(". ")
        if len(sentences) > 3 and "code" not in query.lower() and "example" not in query.lower():
            # For non-code questions, limit to 2-3 sentences
            answer_text = ". ".join(sentences[:3]) + "."
        
        # Format the answer with thinking effect and proper code blocks
        answer_text = format_code_blocks(answer_text)
        
        # For simple queries, don't add thinking effect
        if len(query.split()) <= 4:  # If query is 4 words or less
            thinking_effect = False
        else:
            thinking_effect = True
            
        if thinking_effect:
            answer_text = add_thinking_effect(answer_text)
        
        return {
            "success": True,
            "question": query,
            "answer": answer_text,
            "sources": "Technology Knowledge",
            "sources_count": 0,
            "generator": f"{AI_NAME} AI",
            "is_conversational": True,
            "previous_answer": answer_text  # Store for potential follow-up
        }
    except Exception as e:
        logger.error(f"Error handling tech question: {str(e)}")
        return None

async def handle_conversational_query(query: str) -> Dict[str, Any]:
    """Handle conversational queries that don't require document knowledge."""
    # First check if we have any relevant PDF content
    from app.db.database import get_db
    from sqlalchemy import or_
    from app.models.models import PDFContent, PDFChunk
    
    # Get keywords from the query for searching PDF content
    query_keywords = query.lower().split()
    db = next(get_db())
    
    # Search for relevant chunks in PDFs
    relevant_chunks = []
    chunks = db.query(PDFChunk).filter(
        or_(*[PDFChunk.chunk_text.ilike(f"%{kw}%") for kw in query_keywords if len(kw) > 3])
    ).limit(5).all()
    
    for chunk in chunks:
        if any(kw in chunk.chunk_text.lower() for kw in query_keywords if len(kw) > 3):
            relevant_chunks.append(chunk.chunk_text)
    
    # If PDF content found relevant to the query
    if relevant_chunks:
        # Create context from relevant chunks
        context = "\n\n".join(relevant_chunks)
        
        # Get a fresh model for the PDF-based question
        # Create a prompt for Gemini to answer based on the PDF content
        pdf_prompt = f"""
        You are {AI_NAME}, a knowledgeable AI assistant.
        
        Please answer the following question based only on the provided PDF content:
        
        Question: {query}
        
        PDF Content:
        {context}
        
        Important instructions:
        1. Base your answer entirely on the PDF content provided
        2. Be concise and direct
        3. If the PDF content doesn't clearly answer the question, say so
        4. Format any code properly with ```language_name code blocks
        5. Do not invent information not present in the PDF content
        """
        
        answer_text = await _llm_generate(pdf_prompt)
        
        return {
            "success": True,
            "question": query,
            "answer": answer_text,
            "sources": "PDF Content",
            "sources_count": len(relevant_chunks),
            "generator": f"{AI_NAME} AI",
            "is_conversational": False
        }
    
    # Check for special identity questions first
    identity_response = is_identity_question(query)
    if identity_response:
        return {
            "success": True,
            "question": query,
            "answer": identity_response,
            "sources": "Conversational",
            "sources_count": 0,
            "generator": f"{AI_NAME} AI",
            "is_conversational": True
        }
    
    # Check for greetings
    if detect_greeting(query):
        return {
            "success": True,
            "question": query,
            "answer": get_greeting_response(query),
            "sources": "Greeting",
            "sources_count": 0,
            "generator": f"{AI_NAME} AI",
            "is_conversational": True
        }
    
    # Check for technology questions
    if is_tech_question(query):
        tech_response = await handle_tech_question(query)
        if tech_response:
            return tech_response
    
    # Try to handle mathematical queries
    math_response = handle_math_query(query)
    if math_response:
        return {
            "success": True,
            "question": query,
            "answer": math_response,
            "sources": "Mathematical Calculation",
            "sources_count": 0,
            "generator": f"{AI_NAME} AI",
            "is_conversational": True
        }
    
    # Analyze sentiment if it's not a specific type of query
    sentiment = analyze_sentiment(query)
    
    # For highly emotional queries, acknowledge the emotion
    if sentiment["is_positive"] and sentiment["vader_scores"]["compound"] > 0.5:
        # For very positive sentiment
        return {
            "success": True,
            "question": query,
            "answer": "I appreciate your positive energy! How can I help you today?",
            "sources": "Sentiment Analysis",
            "sources_count": 0,
            "generator": f"{AI_NAME} AI",
            "is_conversational": True,
            "sentiment": sentiment
        }
    elif sentiment["is_negative"] and sentiment["vader_scores"]["compound"] < -0.5:
        # For very negative sentiment
        return {
            "success": True,
            "question": query,
            "answer": "I understand you might be feeling frustrated. Let me know how I can help make things better.",
            "sources": "Sentiment Analysis",
            "sources_count": 0,
            "generator": f"{AI_NAME} AI",
            "is_conversational": True,
            "sentiment": sentiment
        }
    
    # If it's a general conversational query, let the caller decide what to do.
    return None 

def simplify_complex_answer(complex_answer: str, user_query: str) -> str:
    """
    Simplify a complex answer for better user understanding.
    """
    try:
        logging.info(f"Simplifying complex answer for query: {user_query}")
        
        # Create a detailed prompt for simplification
        prompt = f"""You are Lucifer AI Assistant. A user asked: "{user_query}" 
        and received this answer: "{complex_answer}".
        
        Please rewrite this answer in a much simpler way that's easier to understand with these guidelines:
        1. Use simpler vocabulary (elementary school level) and short, direct sentences
        2. Break down complex concepts into step-by-step explanations with clear transitions
        3. Include 2-3 concrete, relatable examples that connect to everyday situations
        4. Use vivid analogies and metaphors to explain abstract concepts
        5. Organize information with bullet points or numbered lists
        6. Define any technical terms or jargon immediately when they're introduced
        7. Maintain all factual information from the original answer without omitting key details
        8. Add visual descriptions where helpful (e.g., "imagine a ball rolling down a hill" for gravity)
        9. Use a conversational, friendly tone as if explaining to a curious friend
        10. End with a simple summary of the 1-2 most important takeaways
        
        Your simplified answer should make complex ideas accessible while respecting the user's intelligence.
        """
        
        simplified_answer = _llm_generate_sync(prompt)
        
        # Add note about the simplification
        simplified_answer = f"{simplified_answer}\n\n(I've simplified this explanation to make it more accessible. Let me know if you need any part explained differently or in more detail.)"
        
        logging.info("Successfully simplified the complex answer")
        return simplified_answer
    except Exception as e:
        logging.error(f"Error in simplify_complex_answer: {str(e)}")
        return complex_answer 
