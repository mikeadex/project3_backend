# AI CV Parser Module

## Overview

The AI CV Parser is a core module of Ella designed to extract, parse, analyze, and manage CVs using AI technologies. This module provides comprehensive functionalities for CV parsing, analysis, and intelligent data extraction to power Ella's CV management features.

## Architecture & Components

### Models

#### ParsedCV
- **Purpose**: Stores parsed CV data and metadata
- **Key Fields**:
  - `user`: Associated user (ForeignKey to User model)
  - `file_name`: Original CV file name
  - `file_size`: Size of the uploaded file in bytes
  - `mime_type`: MIME type of the uploaded file
  - `raw_text`: Raw extracted text from the CV
  - `parsed_data`: Structured JSON data extracted from the CV
  - `analysis_data`: Results of AI analysis on the CV
  - `analysis_date`: Timestamp of when analysis was performed
  - `status`: Current processing status (pending, queued, processing, completed, failed)

#### CVRewriteSession
- **Purpose**: Tracks CV rewriting sessions
- **Key Fields**:
  - `user`: Associated user
  - `input_data`: Original CV data for rewriting
  - `output_data`: AI-generated rewritten content
  - `status`: Processing status

### Services

#### DeepSeekService
- **Purpose**: Interfaces with DeepSeek's AI API for CV parsing and analysis
- **Key Methods**:
  - `parse_cv(text)`: Extracts structured data from CV text
  - `parse_document(file_path)`: Extracts text from document files and parses it
  - `make_custom_request(prompt)`: Makes generic requests to DeepSeek API

### Views & API Endpoints

#### AICVParserViewSet
- **Endpoints**:
  - `POST /parse-cv/`: Upload and parse a CV
  - `GET /{id}/`: Retrieve a parsed CV
  - `GET /{id}/status/`: Check the processing status of a CV
  - `POST /analyze/`: Perform AI analysis on a CV
  - `POST /job_status/`: Check the status of multiple CV parsing jobs
  - `POST /transfer-to-writer/`: Transfer parsed CV data to the CV writer module

## Key Algorithms & Logic

### CV Parsing Pipeline

1. **Document Upload & Validation**
   - CV files are uploaded and validated for size and type
   - A new `ParsedCV` record is created with status "queued"
   - The file is temporarily stored for processing

2. **Text Extraction**
   - The system detects the file type (PDF, DOCX, DOC, TXT)
   - Appropriate libraries are used to extract text:
     - PDF: PyPDF2
     - DOCX: python-docx
     - DOC: textract
     - TXT: Direct text reading

3. **AI Processing**
   - Extracted text is sent to DeepSeek AI API
   - The model extracts structured information including:
     - Personal information
     - Professional summary
     - Work experience
     - Education
     - Skills
     - Certifications
     - Languages

4. **Result Storage**
   - Parsed data is stored in the database
   - Status is updated to "completed"
   - The temporary file is cleaned up

### CV Analysis Logic

1. **Analysis Request Handling**
   - The system first checks if recent analysis exists (< 7 days old)
   - If available, cached analysis is returned immediately
   - If not, a new analysis is performed

2. **AI Analysis Process**
   - CV data is formatted and sent to DeepSeek API
   - The analysis prompt asks for:
     - Overall score and section scores
     - Strengths and weaknesses
     - Improvement suggestions
     - ATS readiness assessment
     - Experience level classification
     - Skills assessment
     - Potential matching roles

3. **Result Storage & Caching**
   - Analysis results are stored in the `analysis_data` field
   - The current timestamp is stored in `analysis_date`
   - This enables efficient caching and reduces API calls

### One CV Per User Policy

1. **Existing CV Detection**
   - When uploading a CV, the system checks if the user already has a CV
   - If found, a 409 Conflict response is returned with existing CV details

2. **Confirmation & Overwrite**
   - The frontend requests confirmation from the user
   - If confirmed, the existing CV is deleted and a new one is created

## Error Handling & Resilience

1. **API Service Fallbacks**
   - If DeepSeek API is not configured or fails, structured fallback responses are returned
   - Local fallback processing is used when possible

2. **Graceful Degradation**
   - Parsing partial data is supported when complete extraction fails
   - `completed_with_errors` status indicates partial success

3. **Comprehensive Error Reporting**
   - Detailed error messages stored in database
   - Client-friendly error responses with actionable information

## Security Considerations

1. **Authentication & Authorization**
   - All endpoints require user authentication
   - Users can only access their own CV data
   - JWT-based authentication with secure token handling

2. **File Upload Security**
   - File size limits (10MB max)
   - MIME type validation
   - Secure temporary file handling with automatic cleanup

3. **API Key Protection**
   - API keys stored in environment variables
   - Not exposed to clients
   - Fallback handling for missing API keys

## Performance Optimizations

1. **Asynchronous Processing**
   - CV parsing happens asynchronously
   - Status polling pattern for client updates
   - Prevents request timeouts for large documents

2. **Analysis Caching**
   - Analysis results are cached in the database
   - Cached results are served when available and not outdated
   - Reduces API costs and improves response times

3. **Custom Event Loop Management**
   - Proper handling of async/sync contexts
   - Prevents event loop issues in Django's synchronous environment

## Environment Configuration

Required environment variables:
- `DEEPSEEK_API_KEY`: API key for DeepSeek AI service
- `DEEPSEEK_API_URL`: Base URL for DeepSeek API (defaults to https://api.deepseek.com/v1)
- `DEEPSEEK_MODEL`: Model to use for parsing (defaults to deepseek-chat)

## Integration Points

- **CV Writer Module**: CV data can be transferred to the CV writer for further editing
- **Authentication System**: Uses the main authentication system for user identification
- **Frontend CV Parser Component**: Interacts with the API endpoints provided by this module
