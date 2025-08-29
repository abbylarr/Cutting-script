# Implementation Plan

- [x] 1. Setup project structure and core dependencies
  - Create FastAPI project structure with proper directory organization
  - Setup virtual environment with Python 3.11 and install core dependencies (FastAPI, Uvicorn, SQLAlchemy, Redis, etc.)
  - Configure development environment with .env template and basic configuration management
  - _Requirements: 8.1, 8.4_

- [x] 2. Implement core data models and database setup
  - [x] 2.1 Create SQLAlchemy models for users, tasks, projects, and transactions
    - Define User, ProcessingTask, FilmProject, and Transaction models with proper relationships
    - Implement database connection and session management
    - Create Alembic migrations for initial schema
    - _Requirements: 4.1, 4.2, 7.1_

  - [x] 2.2 Create Pydantic schemas for API request/response validation
    - Define request/response schemas for all API endpoints
    - Implement validation for file uploads, montage data, and film metadata
    - Create error response schemas with proper HTTP status codes
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 2.3 Setup Redis connection and caching utilities
    - Configure Redis connection with connection pooling
    - Implement caching utilities for task progress and user sessions
    - Create rate limiting utilities using Redis
    - _Requirements: 2.1, 6.1_

- [x] 3. Implement authentication and user management system
  - [x] 3.1 Create user authentication with JWT tokens
    - Implement user registration, login, and JWT token generation
    - Create password hashing utilities and token validation middleware
    - Write unit tests for authentication flows
    - _Requirements: 4.3, 4.4_

  - [x] 3.2 Implement billing and balance management
    - Create billing service with cost calculation (75 rubles per minute)
    - Implement balance checking and charging functionality
    - Create transaction logging for all billing operations
    - Write unit tests for billing calculations and balance operations
    - _Requirements: 4.4_

  - [x] 3.3 Setup СБП payment integration
    - Implement payment processing through СБП API
    - Create payment confirmation and balance update workflows
    - Add payment transaction logging and error handling
    - Write integration tests for payment flows
    - _Requirements: 4.4_

- [x] 4. Create file upload and management system
  - [x] 4.1 Implement secure file upload endpoints
    - Create POST /upload endpoint with file validation (format, size limits)
    - Implement secure file storage with user isolation
    - Add virus scanning and file integrity checks
    - Write unit tests for file upload validation and security
    - _Requirements: 1.1, 5.1, 6.3_

  - [x] 4.2 Create SRT file upload and processing
    - Implement POST /upload_srt/{task_id} endpoint for SRT file uploads
    - Create SRT file parsing and validation utilities
    - Implement SRT text extraction and scene mapping
    - Write unit tests for SRT processing with various file formats
    - _Requirements: 1.3, 7.4_

- [x] 5. Implement video processing pipeline core components
  - [x] 5.1 Create video validation and metadata extraction
    - Implement video format validation using FFmpeg
    - Extract video metadata (duration, fps, resolution, codec)
    - Create video integrity checking and error reporting
    - Write unit tests for video validation with various formats
    - _Requirements: 5.1, 5.10_

  - [x] 5.2 Implement audio extraction using FFmpeg
    - Create audio extraction service using FFmpeg subprocess calls
    - Implement error handling for FFmpeg operations
    - Add audio format conversion and quality optimization
    - Write unit tests for audio extraction with different video formats
    - _Requirements: 5.2_

  - [x] 5.3 Create scene detection using python-scenedetect
    - Implement scene detection with configurable sensitivity thresholds
    - Add filtering for short scenes to avoid false positives from flashes
    - Create scene boundary optimization and merging logic
    - Write unit tests for scene detection with test videos
    - _Requirements: 5.3_

- [x] 6. Implement speech processing and transcription
  - [x] 6.1 Create OpenAI Whisper transcription service
    - Implement Whisper API integration with Russian language settings
    - Configure verbose_json output format for detailed transcription data
    - Add retry logic with exponential backoff for API rate limits
    - Write unit tests for transcription with mock API responses
    - _Requirements: 5.4, 6.1_

  - [x] 6.2 Implement speaker diarization with pyannote.audio
    - Create conditional diarization service based on HF_TOKEN availability
    - Implement speaker identification and labeling
    - Add speaker timeline generation and voice activity detection
    - Write unit tests for diarization with test audio files
    - _Requirements: 5.6_

  - [x] 6.3 Create text post-processing with GPT-5-mini
    - Implement grammar correction service using GPT-5-mini API
    - Create economical text processing with batch operations
    - Add text cleaning and formatting for Russian language
    - Write unit tests for text processing with various input types
    - _Requirements: 5.5_

- [x] 7. Implement dialogue and scene integration
  - [x] 7.1 Create dialogue-to-scene mapping algorithm
    - Implement algorithm to distribute dialogue across scenes without breaking sentences
    - Add logic for handling sentence boundaries at scene transitions
    - Create ellipsis insertion for dialogue breaks and continuations
    - Write unit tests for dialogue mapping with various text patterns
    - _Requirements: 5.7_

  - [x] 7.2 Implement music detection in scenes
    - Create audio analysis for music detection in each scene
    - Implement volume and frequency analysis to identify musical content
    - Add music labeling and integration with dialogue processing
    - Write unit tests for music detection with test audio samples
    - _Requirements: 1.3_

- [x] 8. Create visual analysis and keyframe extraction
  - [x] 8.1 Implement keyframe extraction at 35% and 70% positions
    - Create keyframe extraction service using FFmpeg
    - Implement frame quality assessment and selection
    - Add keyframe image optimization and storage
    - Write unit tests for keyframe extraction with test videos
    - _Requirements: 5.8_

  - [x] 8.2 Create professional montage assistant prompt system
    - Implement specialized prompt template for montage director assistant role
    - Create shot type definitions and classification system (Дальний, Общий, Средний, Крупный, Деталь)
    - Add special tags system (ЗТМ, НДП, ГЗК) with detection logic
    - Implement single-sentence description generation without emotional coloring
    - Create strict JSON response validation and parsing
    - Write unit tests for prompt system with various scene types
    - _Requirements: 5.9_

  - [x] 8.3 Integrate GPT-5-mini visual analysis with prompt system
    - Implement image analysis using GPT-5-mini with the professional montage assistant prompt
    - Create dual-frame analysis system (35% and 70% keyframes) for unified scene description
    - Integrate shot type classification with prompt-based definitions
    - Implement JSON response parsing and validation for structured analysis results
    - Add context integration between visual analysis and dialogue for ГЗК detection
    - Write integration tests for complete visual analysis pipeline
    - _Requirements: 5.9_

- [x] 9. Implement montage table generation and formatting
  - [x] 9.1 Create montage table assembly from processed data
    - Implement algorithm to combine scenes, dialogue, and visual analysis
    - Create proper numbering and sequencing of montage rows
    - Add data validation and consistency checking
    - Write unit tests for table generation with various input combinations
    - _Requirements: 1.4, 5.9_

  - [x] 9.2 Implement advanced timecode conversion and continuity system
    - Create timecode conversion from seconds to HH:MM:SS:FF format with configurable start time
    - Implement frame rate detection and proper frame counting
    - Add timecode continuity ensuring exactly one frame gap between scenes
    - Create project settings for timecode start (01:00:00:00 or 00:00:00:00) and standard (ГФФ or Красногорский)
    - Implement timecode validation and automatic continuity correction
    - Write unit tests for timecode conversion with different frame rates and settings
    - _Requirements: 5.10, 5.11, 8.1, 8.2, 8.3_

- [x] 10. Create DOCX document generation
  - [x] 10.1 Implement DOCX template and generation service
    - Create DOCX template following Госфильмфонд requirements
    - Implement document generation using python-docx library
    - Add proper table formatting with required columns
    - Write unit tests for document generation with test data
    - _Requirements: 1.4_

  - [x] 10.2 Add film metadata integration to documents
    - Implement metadata insertion into DOCX headers and footers
    - Create proper document formatting with production information
    - Add document validation and compliance checking
    - Write unit tests for metadata integration with various film data
    - _Requirements: 4.1_

- [x] 11. Implement asynchronous task processing system
  - [x] 11.1 Create task queue and progress tracking
    - Implement asynchronous task processing using asyncio
    - Create task status tracking with Redis-based progress updates
    - Add task cancellation and cleanup functionality
    - Write unit tests for task lifecycle management
    - _Requirements: 2.1, 2.2_

  - [x] 11.2 Implement processing pipeline orchestration
    - Create pipeline coordinator that manages all processing steps
    - Add step-by-step progress reporting with ETA calculations
    - Implement error recovery and partial result preservation
    - Write integration tests for complete pipeline execution
    - _Requirements: 2.1, 2.2, 5.1-5.10_

- [x] 12. Create API endpoints and request handling
  - [x] 12.1 Implement core API endpoints
    - Create GET /status/{task_id} endpoint with detailed status information
    - Implement PATCH /montage/{task_id} for updating montage rows
    - Add GET /download/{task_id} endpoint for DOCX file downloads
    - Write API integration tests for all endpoints
    - _Requirements: 7.2, 7.3, 7.5_

  - [x] 12.2 Create project management endpoints
    - Implement POST /save/{task_id} for saving project changes
    - Create project listing and metadata management endpoints
    - Add project deletion and cleanup functionality
    - Write unit tests for project management operations
    - _Requirements: 7.6, 4.1, 4.2_

- [x] 13. Implement error handling and resilience
  - [x] 13.1 Create comprehensive error handling system
    - Implement structured error responses with proper HTTP status codes
    - Create error logging with detailed context and stack traces
    - Add user-friendly error messages for common failure scenarios
    - Write unit tests for error handling across all components
    - _Requirements: 6.3_

  - [x] 13.2 Implement fallback mechanisms for external services
    - Create fallback transcription service for OpenAI API unavailability
    - Implement graceful degradation when optional services are unavailable
    - Add service health checking and automatic failover
    - Write integration tests for fallback scenarios
    - _Requirements: 6.2_

- [-] 14. Create frontend interface components
  - [x] 14.1 Implement video upload and project creation interface
    - Create React components for video file upload with progress tracking
    - Implement project creation form with film metadata fields
    - Add SRT/auto-transcription mode selection interface
    - Create timecode settings interface with start time selector (01:00:00:00 or 00:00:00:00)
    - Add standard selection slider/toggle (ГФФ or Красногорский)
    - Write component tests for upload functionality and settings
    - _Requirements: 1.1, 1.2, 1.3, 4.1, 8.1, 8.2_

  - [x] 14.2 Create processing progress visualization
    - Implement animated progress interface with step descriptions
    - Add "magical" processing descriptions with time estimates
    - Create real-time progress updates using WebSocket or polling
    - Write component tests for progress visualization
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 14.3 Implement montage table editor interface
    - Create interactive table component with inline editing
    - Implement video player integration with timeline synchronization
    - Add shot type selection with colored tags
    - Create speaker renaming and management interface
    - Write component tests for table editing functionality
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 14.4 Create project sidebar and user account interface
    - Implement project listing sidebar with search and filtering
    - Create user account panel with balance display and payment integration
    - Add project management actions (rename, delete, duplicate)
    - Write component tests for sidebar and account functionality
    - _Requirements: 4.2, 4.3, 4.4_

- [x] 15. Implement testing and quality assurance
  - [x] 15.1 Create comprehensive test suite
    - Write unit tests for all service classes and utilities
    - Create integration tests for API endpoints and database operations
    - Add end-to-end tests for complete video processing workflows
    - Implement test data fixtures and mock services
    - _Requirements: 8.2_

  - [x] 15.2 Add performance and load testing
    - Create performance tests for video processing pipeline
    - Implement load testing for concurrent user scenarios
    - Add memory usage monitoring and optimization
    - Write stress tests for large file processing
    - _Requirements: 8.2_

- [x] 16. Setup deployment and documentation
  - [x] 16.1 Create deployment configuration
    - Setup Docker containers for all services
    - Create docker-compose configuration for development and production
    - Implement environment-specific configuration management
    - Add health checks and monitoring setup
    - _Requirements: 8.1, 8.4_

  - [x] 16.2 Create comprehensive documentation
    - Write detailed README with installation and setup instructions
    - Create API documentation using FastAPI's automatic Swagger generation
    - Add developer documentation for extending and maintaining the system
    - Create user guide for the web interface
    - _Requirements: 8.3_