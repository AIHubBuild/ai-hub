# AI Hub Platform

# API Design

| Document | AI Hub Platform – API Design |
|----------|------------------------------|
| Version | 1.0 |
| Status | Draft |
| Product | AI Hub Platform |
| Author | Abiola Akinselure |
| Reviewer | DaizSign Damilare Oloyede |
| Date | July 2026 |

---

# Table of Contents

1. Purpose
2. API Objectives
3. API Design Principles
4. API Standards
5. API Architecture
6. Authentication & Authorization
7. API Versioning
8. Request & Response Standards
9. HTTP Status Codes
10. Error Handling
11. Authentication APIs *(Part 2)*
12. User APIs *(Part 2)*
13. Resume APIs *(Part 2)*
14. Skills APIs *(Part 2)*
15. Job APIs *(Part 2)*
16. Job Application APIs *(Part 2)*
17. Cover Letter APIs *(Part 2)*
18. Interview APIs *(Part 3)*
19. AI Conversation APIs *(Part 3)*
20. Notification APIs *(Part 3)*
21. Assistant Catalogue APIs *(Part 3)*
22. API Security *(Part 3)*
23. Rate Limiting *(Part 3)*
24. OpenAPI Documentation *(Part 3)*
25. Future APIs *(Part 3)*
26. Related Documents *(Part 3)*
27. Revision History *(Part 3)*
28. Conclusion *(Part 3)*

---

# 1. Purpose

This document defines the REST API specification for the AI Hub Platform.

The API serves as the communication layer between the frontend application, backend services, AI services, and supporting infrastructure. It provides a standardized interface for authentication, user management, resume optimization, interview preparation, job tracking, and AI-powered career services.

The API has been designed to be:

- Secure
- Consistent
- Scalable
- Maintainable
- Versioned
- Developer-friendly

This document acts as the contract between frontend and backend developers, ensuring both teams can develop independently while maintaining compatibility.

---

# 2. API Objectives

The API is designed to achieve the following objectives:

- Provide secure access to platform resources.
- Support all MVP features.
- Enable communication between frontend and backend.
- Integrate AI services seamlessly.
- Support future mobile applications.
- Provide predictable responses.
- Enable API versioning.
- Maintain backward compatibility.
- Support automated documentation.

---

# 3. API Design Principles

The API follows modern RESTful design principles.

---

## 3.1 Resource-Oriented Design

Every endpoint represents a resource.

Examples include:

```
/users
/resumes
/jobs
/applications
/interviews
/skills
```

Resources are manipulated using standard HTTP methods.

---

## 3.2 Stateless Communication

Each request contains all information required to process it.

The server does not store client session state between requests.

Authentication is performed using JWT Bearer Tokens.

---

## 3.3 Consistency

Endpoints follow consistent naming conventions.

Examples:

```
GET     /users
POST    /users
GET     /users/{id}
PUT     /users/{id}
DELETE  /users/{id}
```

This consistency simplifies frontend development and API consumption.

---

## 3.4 Predictable Responses

All endpoints return standardized JSON responses.

Example:

```json
{
    "success": true,
    "message": "Resume uploaded successfully",
    "data": {
        "resume_id": "uuid"
    }
}
```

---

## 3.5 Idempotency

Where appropriate, API operations are idempotent.

Examples:

- GET
- PUT
- DELETE

Repeated requests should produce the same result when no data changes occur.

---

## 3.6 Separation of Concerns

The API is organized into logical domains:

- Authentication
- Users
- Career
- Recruitment
- AI
- Notifications

This mirrors the modular monolith architecture defined in the System Architecture document.

---

# 4. API Standards

---

## Protocol

HTTPS only.

All communication must be encrypted.

---

## Data Format

The API accepts and returns JSON.

Example:

```json
{
    "email": "user@example.com",
    "password": "********"
}
```

---

## Character Encoding

UTF-8

---

## Base URL

Development

```
https://dev-api.aihub.com/api/v1
```

Production

```
https://api.aihub.com/api/v1
```

---

## Naming Convention

Resources use plural nouns.

Examples:

```
/users
/resumes
/jobs
/applications
/interviews
/notifications
```

Actions are represented through HTTP methods rather than verbs in URLs.

---

# 5. API Architecture

The API follows a layered architecture.

```
Frontend (Next.js)
        │
        ▼
 REST API
        │
        ▼
FastAPI Backend
        │
 ┌──────┼───────────┐
 ▼      ▼           ▼
Database OpenAI  Storage
```

---

## API Flow

```
Client Request
      │
      ▼
Authentication
      │
      ▼
Request Validation
      │
      ▼
Business Logic
      │
      ▼
Database / AI Service
      │
      ▼
Response Formatter
      │
      ▼
JSON Response
```

---

# 6. Authentication & Authorization

Authentication is managed through Supabase Authentication.

The backend validates JWT access tokens before processing protected requests.

---

## Authentication Flow

```
User Login
      │
      ▼
Supabase Auth
      │
      ▼
JWT Access Token
      │
      ▼
Frontend Stores Token
      │
      ▼
Authorization Header
      │
      ▼
FastAPI Validation
```

---

## Authorization Header

Protected endpoints require:

```http
Authorization: Bearer <JWT_TOKEN>
```

---

## Public Endpoints

Examples:

- Login
- Register
- Forgot Password
- Reset Password

---

## Protected Endpoints

Examples:

- Resume Upload
- Resume Analysis
- Job Applications
- Interview Sessions
- AI Conversations
- User Profile

---

## Role-Based Authorization

Future platform versions may introduce role-specific access.

Examples:

- User
- Recruiter
- Administrator

---

# 7. API Versioning

Versioning ensures future updates do not break existing client applications.

---

## URL Versioning

The platform uses URL-based versioning.

Example:

```
/api/v1/users
```

Future versions:

```
/api/v2/users
```

---

## Backward Compatibility

Existing versions remain supported during migration periods.

Deprecated endpoints will be announced before removal.

---

## Version Lifecycle

```
Development
      │
      ▼
Release
      │
      ▼
Maintenance
      │
      ▼
Deprecation
```

---

# 8. Request & Response Standards

All API requests and responses follow a consistent structure.

---

## Successful Response

```json
{
    "success": true,
    "message": "Operation completed successfully",
    "data": {}
}
```

---

## Error Response

```json
{
    "success": false,
    "message": "Validation failed",
    "errors": [
        {
            "field": "email",
            "message": "Email is required"
        }
    ]
}
```

---

## Pagination Response

```json
{
    "success": true,
    "page": 1,
    "page_size": 20,
    "total_records": 125,
    "total_pages": 7,
    "data": []
}
```

---

## Standard Metadata

Responses may include:

- Pagination
- Timestamps
- Request ID
- Processing Time

Example:

```json
{
    "success": true,
    "request_id": "req_123456789",
    "processing_time": "42ms",
    "data": {}
}
```

---

# 9. HTTP Status Codes

The API uses standard HTTP status codes.

| Status Code | Description |
|-------------|-------------|
| 200 | OK |
| 201 | Created |
| 202 | Accepted |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 413 | Payload Too Large |
| 415 | Unsupported Media Type |
| 422 | Validation Error |
| 429 | Too Many Requests |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

# 10. Error Handling

Errors follow a standardized structure.

---

## Validation Error

```json
{
    "success": false,
    "message": "Validation failed",
    "errors": [
        {
            "field": "password",
            "message": "Password must contain at least 8 characters."
        }
    ]
}
```

---

## Authentication Error

```json
{
    "success": false,
    "message": "Authentication required."
}
```

---

## Resource Not Found

```json
{
    "success": false,
    "message": "Resume not found."
}
```

---

## Internal Server Error

```json
{
    "success": false,
    "message": "An unexpected error occurred. Please try again later."
}
```

---

## API Error Handling Principles

The API should:

- Return meaningful error messages.
- Avoid exposing internal implementation details.
- Log unexpected exceptions.
- Include request identifiers for troubleshooting.
- Use appropriate HTTP status codes.
- Maintain consistent error formats across all endpoints.

These practices improve developer experience, simplify debugging, and provide a reliable contract for frontend applications.

---
# 11. Authentication APIs

Authentication is managed by **Supabase Authentication**, while the backend validates JWT access tokens for protected resources.

---

## 11.1 Register User

### Endpoint

```http
POST /api/v1/auth/register
```

### Description

Registers a new user account.

### Authentication

Not Required

### Request Body

```json
{
    "email": "john@example.com",
    "password": "StrongPassword123!"
}
```

### Success Response (201)

```json
{
    "success": true,
    "message": "User registered successfully.",
    "data": {
        "user_id": "uuid"
    }
}
```

### Possible Errors

| Status | Description |
|---------|-------------|
|400|Invalid request|
|409|Email already exists|
|500|Internal Server Error|

---

## 11.2 Login

### Endpoint

```http
POST /api/v1/auth/login
```

### Authentication

Not Required

### Request

```json
{
    "email":"john@example.com",
    "password":"StrongPassword123!"
}
```

### Success Response

```json
{
    "success": true,
    "message": "Login successful.",
    "data": {
        "access_token": "<JWT>",
        "refresh_token": "<JWT>",
        "expires_in":3600
    }
}
```

---

## 11.3 Logout

### Endpoint

```http
POST /api/v1/auth/logout
```

Authentication Required

### Success Response

```json
{
    "success": true,
    "message":"Logged out successfully."
}
```

---

## 11.4 Forgot Password

```http
POST /api/v1/auth/forgot-password
```

---

## 11.5 Reset Password

```http
POST /api/v1/auth/reset-password
```

---

# 12. User APIs

These endpoints manage user accounts and profile information.

---

## 12.1 Get Current User

```http
GET /api/v1/users/me
```

Authentication Required

### Success Response

```json
{
    "success":true,
    "data":{
        "id":"uuid",
        "email":"john@example.com",
        "profile":{
            "first_name":"John",
            "last_name":"Doe",
            "location":"Berlin"
        }
    }
}
```

---

## 12.2 Update Profile

```http
PUT /api/v1/users/me
```

Authentication Required

### Request

```json
{
    "first_name":"John",
    "last_name":"Doe",
    "phone":"+49123456789",
    "location":"Berlin",
    "professional_summary":"Experienced IT Support Engineer"
}
```

### Success Response

```json
{
    "success":true,
    "message":"Profile updated successfully."
}
```

---

## 12.3 Get User Roles

```http
GET /api/v1/users/me/roles
```

Returns all career paths selected by the user.

---

## 12.4 Assign Career Role

```http
POST /api/v1/users/me/roles
```

### Request

```json
{
    "role_id":"uuid"
}
```

---

## 12.5 Remove Career Role

```http
DELETE /api/v1/users/me/roles/{roleId}
```

---

# 13. Resume APIs

The Resume module manages uploads, versioning, optimization, and ATS analysis.

---

## 13.1 Upload Resume

```http
POST /api/v1/resumes
```

Authentication Required

Content-Type:

```
multipart/form-data
```

### Request

```
resume.pdf
```

### Success Response

```json
{
    "success":true,
    "message":"Resume uploaded successfully.",
    "data":{
        "resume_id":"uuid"
    }
}
```

---

## 13.2 Get My Resumes

```http
GET /api/v1/resumes
```

Returns all uploaded resumes.

---

## 13.3 Get Resume

```http
GET /api/v1/resumes/{resumeId}
```

---

## 13.4 Delete Resume

```http
DELETE /api/v1/resumes/{resumeId}
```

---

## 13.5 Optimize Resume

```http
POST /api/v1/resumes/{resumeId}/optimize
```

Uses AI to optimize the resume.

### Success Response

```json
{
    "success":true,
    "message":"Resume optimized successfully.",
    "data":{
        "version":"3",
        "ats_score":92
    }
}
```

---

## 13.6 ATS Analysis

```http
POST /api/v1/resumes/{resumeId}/ats-analysis
```

Returns ATS recommendations.

---

## 13.7 Resume Version History

```http
GET /api/v1/resumes/{resumeId}/versions
```

---

## 13.8 Restore Resume Version

```http
POST /api/v1/resumes/{resumeId}/versions/{versionId}/restore
```

---

# 14. Skills APIs

The Skills module supports career recommendations and skill gap analysis.

---

## 14.1 Get Skills

```http
GET /api/v1/skills
```

Returns the master skills catalogue.

---

## 14.2 Search Skills

```http
GET /api/v1/skills?search=linux
```

---

## 14.3 Add User Skill

```http
POST /api/v1/users/me/skills
```

### Request

```json
{
    "skill_id":"uuid",
    "proficiency_level":"Intermediate",
    "years_of_experience":2
}
```

---

## 14.4 Update User Skill

```http
PUT /api/v1/users/me/skills/{skillId}
```

---

## 14.5 Delete User Skill

```http
DELETE /api/v1/users/me/skills/{skillId}
```

---

## 14.6 Get My Skills

```http
GET /api/v1/users/me/skills
```

---

# 15. Job APIs

The Job module manages available job opportunities.

---

## 15.1 Get Jobs

```http
GET /api/v1/jobs
```

Supports filtering.

Example:

```
/jobs?location=Berlin&keyword=IT
```

---

## 15.2 Get Job Details

```http
GET /api/v1/jobs/{jobId}
```

---

## 15.3 Get Recommended Jobs

```http
GET /api/v1/jobs/recommended
```

Uses AI recommendations.

---

## 15.4 Compare Resume with Job

```http
POST /api/v1/jobs/{jobId}/match
```

### Response

```json
{
    "match_score":88,
    "missing_skills":[
        "Docker",
        "Terraform"
    ]
}
```

---

# 16. Job Application APIs

These endpoints manage the user's job application lifecycle.

---

## 16.1 Create Application

```http
POST /api/v1/applications
```

### Request

```json
{
    "job_id":"uuid",
    "resume_id":"uuid"
}
```

---

## 16.2 Get Applications

```http
GET /api/v1/applications
```

---

## 16.3 Get Application

```http
GET /api/v1/applications/{applicationId}
```

---

## 16.4 Update Application Status

```http
PATCH /api/v1/applications/{applicationId}
```

### Request

```json
{
    "application_status":"Interview"
}
```

Possible values:

- Saved
- Applied
- Assessment
- Interview
- Offer
- Accepted
- Rejected

---

## 16.5 Delete Application

```http
DELETE /api/v1/applications/{applicationId}
```

---

# 17. Cover Letter APIs

The Cover Letter module generates and manages AI-powered cover letters.

---

## 17.1 Generate Cover Letter

```http
POST /api/v1/applications/{applicationId}/cover-letter
```

Uses AI to generate a tailored cover letter.

### Success Response

```json
{
    "success":true,
    "message":"Cover letter generated successfully.",
    "data":{
        "cover_letter_id":"uuid"
    }
}
```

---

## 17.2 Get Cover Letter

```http
GET /api/v1/cover-letters/{coverLetterId}
```

---

## 17.3 Update Cover Letter

```http
PUT /api/v1/cover-letters/{coverLetterId}
```

---

## 17.4 Download Cover Letter

```http
GET /api/v1/cover-letters/{coverLetterId}/download
```

Supports:

- PDF
- DOCX

---

## 17.5 Delete Cover Letter

```http
DELETE /api/v1/cover-letters/{coverLetterId}
```

---

### API Design Notes

The endpoints in this section follow RESTful conventions and align directly with the entities defined in **05_Database_Design.md** and the service boundaries described in **04_System_Architecture.md**. Authentication, User, Career, and Recruitment APIs are intentionally grouped by business domain to maintain consistency with the platform's modular monolith architecture.

---

# 18. Interview APIs

The Interview module provides AI-powered interview preparation, question generation, response evaluation, and performance tracking.

---

## 18.1 Start Interview Session

```http
POST /api/v1/interviews
```

**Authentication**

Bearer Token Required

### Description

Creates a new interview practice session.

### Request

```json
{
    "application_id": "uuid",
    "interview_type": "Technical"
}
```

### Success Response (201)

```json
{
    "success": true,
    "message": "Interview session started.",
    "data": {
        "session_id": "uuid"
    }
}
```

---

## 18.2 Get Interview Sessions

```http
GET /api/v1/interviews
```

Returns all interview sessions for the authenticated user.

---

## 18.3 Get Interview Details

```http
GET /api/v1/interviews/{sessionId}
```

Returns:

- Questions
- Responses
- AI Scores
- AI Feedback

---

## 18.4 Submit Interview Response

```http
POST /api/v1/interviews/{sessionId}/responses
```

### Request

```json
{
    "question_id":"uuid",
    "response":"I would begin troubleshooting by identifying the user's issue..."
}
```

### Success Response

```json
{
    "success":true,
    "message":"Response submitted successfully."
}
```

---

## 18.5 Complete Interview

```http
POST /api/v1/interviews/{sessionId}/complete
```

Returns:

- Overall Score
- AI Feedback
- Improvement Areas
- Recommended Learning Topics

---

## 18.6 Interview Analytics

```http
GET /api/v1/interviews/analytics
```

Provides insights such as:

- Average interview score
- Strongest categories
- Weakest categories
- Historical performance trends
- Recommended practice areas

---

# 19. AI Conversation APIs

The AI Conversation module stores interactions between users and AI-powered services.

---

## 19.1 Create AI Conversation

```http
POST /api/v1/ai/conversations
```

### Request

```json
{
    "module":"Resume Optimizer",
    "prompt":"Improve my resume for an IT Support role."
}
```

### Success Response

```json
{
    "success":true,
    "data":{
        "conversation_id":"uuid",
        "response":"Here is an optimized version of your resume..."
    }
}
```

---

## 19.2 Get Conversation History

```http
GET /api/v1/ai/conversations
```

Returns previous AI conversations.

---

## 19.3 Get Conversation

```http
GET /api/v1/ai/conversations/{conversationId}
```

---

## 19.4 Delete Conversation

```http
DELETE /api/v1/ai/conversations/{conversationId}
```

---

# 20. Notification APIs

The Notification module manages platform notifications and reminders.

---

## 20.1 Get Notifications

```http
GET /api/v1/notifications
```

---

## 20.2 Mark Notification as Read

```http
PATCH /api/v1/notifications/{notificationId}
```

---

## 20.3 Mark All Notifications as Read

```http
PATCH /api/v1/notifications/read-all
```

---

## 20.4 Delete Notification

```http
DELETE /api/v1/notifications/{notificationId}
```

---

# 21. Assistant Catalogue APIs

The Assistant Catalogue module exposes the platform assistant registry — the list of AI applications available on AI Hub. It is the seed of the pluggable domain registry described in `09_Migration_Analysis.md` (§3.3).

---

## 21.1 Get Assistant Catalogue

```http
GET /api/v1/assistants
```

### Authentication

Not Required

### Description

Returns all assistants currently registered on the platform.

### Success Response (200)

```json
{
    "success": true,
    "message": "Assistant catalogue retrieved",
    "data": [
        {
            "id": "resume-ats",
            "name": "ATS Resume Assistant",
            "description": "Analyzes a resume against a job description...",
            "status": "available",
            "capabilities": [
                "ATS resume analysis",
                "Keyword matching",
                "Tailored cover letter",
                "DOCX export"
            ],
            "launch_url": null,
            "repository_url": "https://github.com/akinselureabiola/ATS-Resume-Assistant"
        }
    ]
}
```

### Field Notes

- `status`: `available` (ready for integration) or `in_development`.
- `launch_url`: `null` until a verified hosted deployment exists. A launch URL may only be advertised once a real deployment is verified.
- `repository_url`: reference link only — never presented as a launch destination.
- The AI Testing Framework is an internal QA/developer tool and is intentionally excluded from the public catalogue (see `09_Migration_Analysis.md` §3.4).

---

# 22. API Security

Security is enforced across every API endpoint to protect user data and ensure platform integrity.

---

## Authentication

Protected endpoints require:

- JWT Bearer Tokens
- Token validation
- Secure session management

---

## Authorization

Role-Based Access Control (RBAC) ensures users can only access authorized resources.

Examples:

- Users may only access their own resumes.
- Users may only modify their own profile.
- Users cannot retrieve another user's interview sessions.

---

## Input Validation

Every request is validated for:

- Required fields
- Data types
- Length constraints
- File size
- Allowed file formats

---

## Secure Communication

All API communication uses:

- HTTPS
- TLS encryption

---

## Data Protection

Security controls include:

- Row-Level Security (Supabase)
- Parameterized SQL queries
- Secure object storage
- Audit logging

---

## Security Headers

Recommended HTTP security headers include:

- Content-Security-Policy
- X-Content-Type-Options
- X-Frame-Options
- Strict-Transport-Security
- Referrer-Policy

---

# 23. Rate Limiting

Rate limiting protects the platform from abuse and denial-of-service attacks.

---

## Default Limits

| Endpoint Category | Limit |
|-------------------|-------|
| Authentication | 10 requests/minute |
| AI Endpoints | 30 requests/minute |
| Resume Upload | 10 requests/hour |
| Standard APIs | 100 requests/minute |

---

## Response

```http
429 Too Many Requests
```

```json
{
    "success": false,
    "message": "Rate limit exceeded. Please try again later."
}
```

---

# 24. OpenAPI Documentation

The AI Hub Platform API will follow the OpenAPI 3.1 specification.

Interactive documentation will be generated automatically using FastAPI.

Available documentation endpoints:

```text
/api/docs
```

Swagger UI

```text
/api/redoc
```

ReDoc

The OpenAPI specification enables:

- Interactive testing
- Client SDK generation
- API discovery
- Improved developer experience

---

# 25. Future APIs

Future platform releases may introduce additional APIs.

Potential modules include:

## Recruiter APIs

- Employer Management
- Candidate Search
- Resume Search
- Interview Scheduling

---

## Analytics APIs

- Career Progress
- Skill Gap Analysis
- Application Success Rate
- Interview Performance

---

## Learning APIs

- Learning Paths
- Recommended Courses
- Certification Tracking

---

## Billing APIs

- Subscription Plans
- Payments
- Invoices
- Usage Tracking

---

## Integration APIs

- LinkedIn
- GitHub
- Google Drive
- Microsoft 365
- Job Boards

---

# 26. Related Documents

This document should be read together with:

| Document | Purpose |
|-----------|---------|
| 01_Product_Vision_Document.md | Product strategy and vision |
| 02_Product_Requirements_Document.md | Functional requirements |
| 03_User_Journey.md | User experience and workflows |
| 04_System_Architecture.md | System components and interactions |
| 05_Database_Design.md | Database schema and ERD |
| 06_AWS_Cloud_Architecture.md | Infrastructure and cloud deployment |
| 08_Implementation_Roadmap.md | Development phases and milestones |

Together, these documents define the product, architecture, infrastructure, data model, and implementation strategy for the AI Hub Platform.

---

# 27. Revision History

| Version | Date | Author | Description |
|----------|------|--------|-------------|
| 1.1 | September 2026 | Abiola Akinselure | Added Assistant Catalogue APIs (GET /api/v1/assistants); renumbered sections 21–27 |
| 1.0 | July 2026 | Abiola Akinselure | Initial API Design document |

---

# 28. Conclusion

The AI Hub Platform API has been designed as a secure, scalable, and maintainable RESTful interface that enables seamless communication between the frontend application, backend services, AI capabilities, and supporting cloud infrastructure.

The API follows modern engineering best practices, including resource-oriented endpoint design, stateless communication, JWT-based authentication, standardized request and response formats, API versioning, comprehensive error handling, and OpenAPI documentation. These standards ensure consistency across the platform while providing an excellent developer experience.

By organizing endpoints into business domains—**Authentication, Users, Career, Recruitment, AI, and Notifications**—the API aligns with both the System Architecture and Database Design documents. This consistency simplifies development, testing, and future maintenance.

The API also establishes a solid foundation for future enhancements such as recruiter features, analytics, mobile applications, third-party integrations, and additional AI-powered services. Versioning and modular endpoint organization ensure that new capabilities can be introduced without disrupting existing clients.

As the primary integration layer of the AI Hub Platform, this API specification serves as the authoritative contract between frontend, backend, AI, and infrastructure components, enabling efficient collaboration, reliable deployments, and long-term platform evolution.

