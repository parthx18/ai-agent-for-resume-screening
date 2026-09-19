import os
import shutil
import time
import secrets
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings, UPLOADS_DIR, RECORDS_DIR
from app.database import (
    init_db, get_all_jobs, get_job_by_id, create_job,
    create_candidate, save_screening_report, get_candidates_with_reports,
    get_candidate_detail, get_notification_logs, log_notification,
    create_user, get_user_by_email, authenticate_user
)
from app.services.parser import parse_resume_content
from app.services.ai_agent import screen_resume
from app.services.excel_service import sync_candidate_to_excel, refresh_entire_excel
from app.services.notification_service import dispatch_candidate_notification

# Initialize database on startup
init_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Dual-Portal AI Resume Screening Agent with Live Excel Synchronization and Automated Notifications"
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# CORS Middleware (restricted to local web origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Rate Limiter State for Auth (Brute Force Protection)
# Structure: {ip_or_email: {"count": int, "blocked_until": float}}
_FAILED_LOGIN_ATTEMPTS: Dict[str, Dict[str, Any]] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutes

def check_login_rate_limit(key: str):
    now = time.time()
    record = _FAILED_LOGIN_ATTEMPTS.get(key)
    if record:
        if record.get("blocked_until", 0) > now:
            remaining = int(record["blocked_until"] - now)
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed login attempts. For your security, this account/IP is temporarily locked for {remaining} seconds."
            )
        # Reset if window expired
        if record.get("blocked_until", 0) != 0 and record.get("blocked_until", 0) <= now:
            _FAILED_LOGIN_ATTEMPTS.pop(key, None)

def record_failed_login(key: str):
    now = time.time()
    record = _FAILED_LOGIN_ATTEMPTS.get(key, {"count": 0, "blocked_until": 0})
    record["count"] += 1
    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["blocked_until"] = now + LOCKOUT_SECONDS
    _FAILED_LOGIN_ATTEMPTS[key] = record

def record_successful_login(key: str):
    _FAILED_LOGIN_ATTEMPTS.pop(key, None)

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$")

# Pydantic Schemas
class CustomCriterion(BaseModel):
    name: str
    weight: float
    description: Optional[str] = ""

class JobCreateRequest(BaseModel):
    title: str
    company_name: Optional[str] = ""
    department: str = "Technology"
    description: str
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    min_experience_years: float = 0.0
    min_education: str = ""
    custom_criteria: List[CustomCriterion] = []

class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    ai_provider: Optional[str] = None
    enable_real_email: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str
    role: Optional[str] = None

class RegisterRequest(BaseModel):
    role: str
    full_name: str
    email: str
    password: str

# --- AUTHENTICATION ROUTES (SECURITY HARDENED) ---

@app.post("/api/auth/login")
def auth_login(req: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_key = f"{client_ip}_{req.email.strip().lower()}"
    
    check_login_rate_limit(rate_limit_key)

    user = authenticate_user(req.email, req.password, expected_role=req.role)
    if not user:
        record_failed_login(rate_limit_key)
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials. Please verify your email, password, and portal role."
        )
    
    record_successful_login(rate_limit_key)
    session_token = f"talentai_{secrets.token_urlsafe(32)}"
    return {
        "success": True,
        "message": f"Welcome back, {user['full_name']}!",
        "user": user,
        "token": session_token
    }

@app.post("/api/auth/register")
def auth_register(req: RegisterRequest):
    if req.role not in ["candidate", "employer"]:
        raise HTTPException(status_code=400, detail="Invalid role specified.")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters for security.")
    clean_email = req.email.strip().lower()
    if not EMAIL_REGEX.match(clean_email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    clean_name = req.full_name.strip()
    if not clean_name or len(clean_name) < 2:
        raise HTTPException(status_code=400, detail="Please enter your full name.")
    
    try:
        user = create_user(
            role=req.role,
            full_name=clean_name,
            email=clean_email,
            password=req.password
        )
        session_token = f"talentai_{secrets.token_urlsafe(32)}"
        return {
            "success": True,
            "message": "Account registered securely!",
            "user": user,
            "token": session_token
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.get("/api/auth/demo-users")
def auth_demo_users():
    return {
        "employer": {
            "email": "recruiter@talentai.com",
            "password": "admin123",
            "role": "employer",
            "name": "Recruiter Admin",
            "title": "Senior Talent Acquisition Lead"
        },
        "candidate": {
            "email": "candidate@demo.com",
            "password": "demo123",
            "role": "candidate",
            "name": "Jane Candidate",
            "title": "Software Engineer Applicant"
        }
    }

# --- API ROUTES ---

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "ai_provider": settings.AI_PROVIDER,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "groq_configured": bool(settings.GROQ_API_KEY)
    }

# 1. Job Management (Employer Portal)
@app.get("/api/jobs")
def list_jobs():
    jobs = get_all_jobs(active_only=True)
    return {"jobs": jobs}

@app.get("/api/jobs/{job_id}")
def retrieve_job(job_id: int):
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job opening not found")
    return {"job": job}

@app.post("/api/jobs")
def add_job(payload: JobCreateRequest):
    data = payload.dict()
    # Serialize criteria to dicts
    data["custom_criteria"] = [c for c in data["custom_criteria"]]
    job_id = create_job(data)
    return {"success": True, "job_id": job_id, "message": "Job description and screening criteria posted successfully."}

# 2. Candidate Application & AI Screening (Candidate Portal)
@app.post("/api/apply")
async def apply_and_screen(
    job_id: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    linkedin_or_portfolio: Optional[str] = Form(None),
    resume_file: UploadFile = File(...)
):
    # Verify Job
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Invalid job selected.")

    # Read and parse resume file
    file_bytes = await resume_file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded resume file is empty.")

    try:
        resume_text = parse_resume_content(resume_file.filename, file_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read resume: {str(e)}")

    # Save physical file to uploads directory
    saved_filename = f"c_{email.replace('@', '_').replace('.', '_')}_{resume_file.filename}"
    saved_path = UPLOADS_DIR / saved_filename
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    # 1. Persist Candidate Record
    candidate_id = create_candidate({
        "job_id": job_id,
        "full_name": full_name.strip(),
        "email": email.strip(),
        "phone": (phone or "").strip(),
        "linkedin_or_portfolio": (linkedin_or_portfolio or "").strip(),
        "resume_filename": saved_filename,
        "resume_text": resume_text
    })

    # 2. Trigger Autonomous AI Screening Agent
    screening_result = screen_resume(
        job=job,
        resume_text=resume_text,
        candidate_name=full_name.strip()
    )

    # 3. Persist Screening Report
    screening_result["candidate_id"] = candidate_id
    screening_result["job_id"] = job_id
    report_id = save_screening_report(screening_result)

    # 4. Trigger Automated Candidate Notification (Email + Message)
    candidate_dict = {
        "id": candidate_id,
        "full_name": full_name.strip(),
        "email": email.strip(),
        "phone": (phone or "").strip()
    }
    notify_res = dispatch_candidate_notification(candidate_dict, job, screening_result)

    # 5. Live Sync to Excel Spreadsheet
    excel_payload = {
        "id": candidate_id,
        "candidate_id": candidate_id,
        "full_name": full_name.strip(),
        "email": email.strip(),
        "phone": (phone or "").strip(),
        "job_title": job["title"],
        "overall_score": screening_result["overall_score"],
        "recommendation": screening_result["recommendation"],
        "skills_match_score": screening_result.get("skills_match_score", 0),
        "experience_score": screening_result.get("experience_score", 0),
        "matched_skills": screening_result.get("matched_skills", []),
        "missing_skills": screening_result.get("missing_skills", []),
        "strengths": screening_result.get("strengths", []),
        "gaps_and_flags": screening_result.get("gaps_and_flags", []),
        "summary_feedback": screening_result.get("summary_feedback", ""),
        "notification_status": notify_res.get("email_status", "Sent"),
        "submitted_at": job.get("created_at")
    }
    sync_candidate_to_excel(excel_payload)

    return {
        "success": True,
        "candidate_id": candidate_id,
        "report_id": report_id,
        "overall_score": screening_result["overall_score"],
        "recommendation": screening_result["recommendation"],
        "notification": notify_res,
        "provider_used": screening_result.get("provider_used", "AI"),
        "message": f"Resume screened successfully! Score: {screening_result['overall_score']}/100. Notification triggered."
    }

# 3. Candidate Review & Evaluation Pipeline (Employer Portal)
@app.get("/api/candidates")
def list_candidates(
    job_id: Optional[int] = None,
    tier: Optional[str] = None,
    min_score: Optional[float] = None,
    user_email: Optional[str] = None
):
    candidates = get_candidates_with_reports(job_id=job_id)
    
    # For demo employer login, show only the two official sample candidates
    if user_email and user_email.strip().lower() == "recruiter@talentai.com":
        candidates = [
            c for c in candidates 
            if c.get("email") in ["sarah.chen@example.com", "david.miller@example.com"]
        ]
    
    # Filter by tier or score
    if tier:
        candidates = [c for c in candidates if c.get("recommendation") and c.get("recommendation").lower() == tier.lower()]
    if min_score is not None:
        candidates = [c for c in candidates if (c.get("overall_score") or 0) >= min_score]
        
    return {
        "candidates": candidates,
        "total": len(candidates)
    }

@app.get("/api/candidates/{candidate_id}")
def retrieve_candidate(candidate_id: int):
    c = get_candidate_detail(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"candidate": c}

# 4. Live Excel Download & Sync
@app.get("/api/excel/download")
def download_excel(user_email: Optional[str] = None):
    # Refresh all candidates into the Excel workbook to guarantee freshness
    all_candidates = get_candidates_with_reports()
    if user_email and user_email.strip().lower() == "recruiter@talentai.com":
        all_candidates = [
            c for c in all_candidates 
            if c.get("email") in ["sarah.chen@example.com", "david.miller@example.com"]
        ]
    excel_file = refresh_entire_excel(all_candidates)
    
    if not os.path.exists(excel_file):
        raise HTTPException(status_code=404, detail="Excel file not found.")
        
    return FileResponse(
        path=excel_file,
        filename="screened_candidates.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# 5. Automated Notification Outbox & Actions
@app.get("/api/notifications")
def list_notifications(limit: int = 50, user_email: Optional[str] = None):
    logs = get_notification_logs(limit=limit)
    if user_email and user_email.strip().lower() == "recruiter@talentai.com":
        logs = [
            l for l in logs 
            if l.get("recipient_email") in ["sarah.chen@example.com", "david.miller@example.com"]
        ]
    return {"notifications": logs}

@app.post("/api/notifications/resend/{candidate_id}")
def resend_notification(candidate_id: int):
    c = get_candidate_detail(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    job = get_job_by_id(c["job_id"])
    report = {
        "recommendation": c.get("recommendation", "Under Review"),
        "overall_score": c.get("overall_score", 0),
        "notification_message": c.get("summary_feedback", "Screening completed.")
    }
    
    notify_res = dispatch_candidate_notification(c, job or {"title": c.get("job_title", "Position")}, report)
    return {"success": True, "result": notify_res}

# 6. Runtime Settings Configuration
@app.get("/api/settings")
def get_current_settings():
    return {
        "ai_provider": settings.AI_PROVIDER,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "groq_configured": bool(settings.GROQ_API_KEY),
        "gemini_model": settings.GEMINI_MODEL,
        "groq_model": settings.GROQ_MODEL,
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": settings.SMTP_PORT,
        "smtp_user": settings.SMTP_USER,
        "smtp_from_email": settings.SMTP_FROM_EMAIL,
        "enable_real_email": settings.ENABLE_REAL_EMAIL
    }

@app.post("/api/settings")
def update_settings(payload: SettingsUpdateRequest):
    if payload.gemini_api_key is not None:
        settings.GEMINI_API_KEY = payload.gemini_api_key.strip()
    if payload.groq_api_key is not None:
        settings.GROQ_API_KEY = payload.groq_api_key.strip()
    if payload.ai_provider:
        settings.AI_PROVIDER = payload.ai_provider
    if payload.enable_real_email is not None:
        settings.ENABLE_REAL_EMAIL = payload.enable_real_email
    if payload.smtp_host:
        settings.SMTP_HOST = payload.smtp_host
    if payload.smtp_port:
        settings.SMTP_PORT = payload.smtp_port
    if payload.smtp_user is not None:
        settings.SMTP_USER = payload.smtp_user
    if payload.smtp_password is not None:
        settings.SMTP_PASSWORD = payload.smtp_password
    if payload.smtp_from_email:
        settings.SMTP_FROM_EMAIL = payload.smtp_from_email

    return {
        "success": True,
        "message": "Settings updated successfully for this session.",
        "settings": {
            "ai_provider": settings.AI_PROVIDER,
            "gemini_configured": bool(settings.GEMINI_API_KEY),
            "groq_configured": bool(settings.GROQ_API_KEY),
            "enable_real_email": settings.ENABLE_REAL_EMAIL
        }
    }

# Mount static web directory
STATIC_DIR = settings.BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))
