import sqlite3
import json
import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.config import settings

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Jobs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        company_name TEXT,
        department TEXT,
        description TEXT NOT NULL,
        required_skills TEXT DEFAULT '[]',
        preferred_skills TEXT DEFAULT '[]',
        min_experience_years REAL DEFAULT 0,
        min_education TEXT,
        custom_criteria TEXT DEFAULT '[]',
        created_at TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
    )
    """)
    # Migration: add company_name to existing databases that predate this column
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN company_name TEXT")
        conn.commit()
    except Exception:
        pass  # Column already exists
    
    # Candidates Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        linkedin_or_portfolio TEXT,
        resume_filename TEXT,
        resume_text TEXT,
        submitted_at TEXT NOT NULL,
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    )
    """)
    
    # Screening Reports Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS screening_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL UNIQUE,
        job_id INTEGER NOT NULL,
        overall_score REAL NOT NULL,
        recommendation TEXT NOT NULL,
        skills_match_score REAL DEFAULT 0,
        experience_score REAL DEFAULT 0,
        matched_skills TEXT DEFAULT '[]',
        missing_skills TEXT DEFAULT '[]',
        strengths TEXT DEFAULT '[]',
        gaps_and_flags TEXT DEFAULT '[]',
        criteria_breakdown TEXT DEFAULT '[]',
        suggested_questions TEXT DEFAULT '[]',
        summary_feedback TEXT,
        raw_ai_response TEXT,
        provider_used TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (candidate_id) REFERENCES candidates (id),
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    )
    """)
    
    # Notification Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notification_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        candidate_name TEXT,
        recipient_email TEXT,
        recipient_phone TEXT,
        channel TEXT NOT NULL,
        subject TEXT,
        message_body TEXT NOT NULL,
        status TEXT NOT NULL,
        sent_at TEXT NOT NULL
    )
    """)
    
    # Users Table (Employer & Candidate Auth)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    conn.commit()
    
    # Pre-seed default employer & candidate if not present
    now_iso = datetime.now().isoformat()
    cursor.execute("SELECT COUNT(*) FROM users WHERE email = 'recruiter@talentai.com'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO users (role, full_name, email, password_hash, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, ("employer", "Recruiter Admin", "recruiter@talentai.com", hashlib.sha256("admin123".encode("utf-8")).hexdigest(), now_iso))

    cursor.execute("SELECT COUNT(*) FROM users WHERE email = 'candidate@demo.com'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO users (role, full_name, email, password_hash, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, ("candidate", "Jane Candidate", "candidate@demo.com", hashlib.sha256("demo123".encode("utf-8")).hexdigest(), now_iso))
    conn.commit()
    
    # Insert default starter job if table is empty so employer has demo data ready
    cursor.execute("SELECT COUNT(*) FROM jobs")
    if cursor.fetchone()[0] == 0:
        now = datetime.now().isoformat()
        cursor.execute("""
        INSERT INTO jobs (title, company_name, department, description, required_skills, preferred_skills, min_experience_years, min_education, custom_criteria, created_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            "Senior AI & Python Engineer",
            "TalentAI Inc.",
            "Engineering",
            "We are seeking an experienced AI/Python Engineer to architect and build autonomous agent systems, integrate LLMs, and develop scalable FastAPI web services.",
            json.dumps(["Python", "FastAPI", "LLMs", "LangChain/LlamaIndex", "REST APIs", "Docker", "Git"]),
            json.dumps(["OpenAI/Gemini APIs", "PostgreSQL", "Prompt Engineering", "Cloud Deployment"]),
            3.0,
            "Bachelor's in Computer Science or related experience",
            json.dumps([
                {"name": "Agentic AI & LLM Experience", "weight": 40, "description": "Hands-on experience with LLM prompting, autonomous tools, or multi-agent frameworks."},
                {"name": "Backend Python Architecture", "weight": 35, "description": "FastAPI, asynchronous programming, clean code, database persistence."},
                {"name": "Problem Solving & System Design", "weight": 25, "description": "Scalable design, caching, edge cases, error resilience."}
            ]),
            now
        ))
        conn.commit()

    conn.close()

# Helper queries
def get_all_jobs(active_only: bool = True) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM jobs" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY id DESC"
    cursor.execute(query)
    rows = cursor.fetchall()
    jobs = []
    for r in rows:
        d = dict(r)
        d["required_skills"] = json.loads(d["required_skills"] or "[]")
        d["preferred_skills"] = json.loads(d["preferred_skills"] or "[]")
        d["custom_criteria"] = json.loads(d["custom_criteria"] or "[]")
        jobs.append(d)
    conn.close()
    return jobs

def get_job_by_id(job_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["required_skills"] = json.loads(d["required_skills"] or "[]")
    d["preferred_skills"] = json.loads(d["preferred_skills"] or "[]")
    d["custom_criteria"] = json.loads(d["custom_criteria"] or "[]")
    return d

def create_job(job_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO jobs (title, company_name, department, description, required_skills, preferred_skills, min_experience_years, min_education, custom_criteria, created_at, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        job_data.get("title", "Software Engineer"),
        job_data.get("company_name", ""),
        job_data.get("department", "Technology"),
        job_data.get("description", ""),
        json.dumps(job_data.get("required_skills", [])),
        json.dumps(job_data.get("preferred_skills", [])),
        float(job_data.get("min_experience_years", 0)),
        job_data.get("min_education", ""),
        json.dumps(job_data.get("custom_criteria", [])),
        now
    ))
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id

def create_candidate(candidate_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO candidates (job_id, full_name, email, phone, linkedin_or_portfolio, resume_filename, resume_text, submitted_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        candidate_data["job_id"],
        candidate_data["full_name"],
        candidate_data["email"],
        candidate_data.get("phone", ""),
        candidate_data.get("linkedin_or_portfolio", ""),
        candidate_data.get("resume_filename", ""),
        candidate_data.get("resume_text", ""),
        now
    ))
    candidate_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return candidate_id

def save_screening_report(report_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    # Check if report exists, replace or insert
    cursor.execute("""
    INSERT OR REPLACE INTO screening_reports (
        candidate_id, job_id, overall_score, recommendation, skills_match_score,
        experience_score, matched_skills, missing_skills, strengths, gaps_and_flags,
        criteria_breakdown, suggested_questions, summary_feedback, raw_ai_response,
        provider_used, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        report_data["candidate_id"],
        report_data["job_id"],
        report_data["overall_score"],
        report_data["recommendation"],
        report_data.get("skills_match_score", 0),
        report_data.get("experience_score", 0),
        json.dumps(report_data.get("matched_skills", [])),
        json.dumps(report_data.get("missing_skills", [])),
        json.dumps(report_data.get("strengths", [])),
        json.dumps(report_data.get("gaps_and_flags", [])),
        json.dumps(report_data.get("criteria_breakdown", [])),
        json.dumps(report_data.get("suggested_questions", [])),
        report_data.get("summary_feedback", ""),
        report_data.get("raw_ai_response", ""),
        report_data.get("provider_used", "ai"),
        now
    ))
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id

def get_candidates_with_reports(job_id: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT 
        c.id, c.job_id, c.full_name, c.email, c.phone, c.linkedin_or_portfolio,
        c.resume_filename, c.submitted_at,
        j.title as job_title, j.department as job_department,
        sr.id as report_id, sr.overall_score, sr.recommendation, sr.skills_match_score,
        sr.experience_score, sr.matched_skills, sr.missing_skills, sr.strengths,
        sr.gaps_and_flags, sr.criteria_breakdown, sr.suggested_questions,
        sr.summary_feedback, sr.provider_used, sr.created_at as screened_at,
        (SELECT status FROM notification_logs WHERE candidate_id = c.id ORDER BY id DESC LIMIT 1) as notification_status
    FROM candidates c
    JOIN jobs j ON c.job_id = j.id
    LEFT JOIN screening_reports sr ON c.id = sr.candidate_id
    """
    params = []
    if job_id:
        query += " WHERE c.job_id = ?"
        params.append(job_id)
    query += " ORDER BY c.id DESC"
    
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("matched_skills"):
            d["matched_skills"] = json.loads(d["matched_skills"])
        if d.get("missing_skills"):
            d["missing_skills"] = json.loads(d["missing_skills"])
        if d.get("strengths"):
            d["strengths"] = json.loads(d["strengths"])
        if d.get("gaps_and_flags"):
            d["gaps_and_flags"] = json.loads(d["gaps_and_flags"])
        if d.get("criteria_breakdown"):
            d["criteria_breakdown"] = json.loads(d["criteria_breakdown"])
        if d.get("suggested_questions"):
            d["suggested_questions"] = json.loads(d["suggested_questions"])
        results.append(d)
    conn.close()
    return results

def get_candidate_detail(candidate_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
        c.*, j.title as job_title, j.department as job_department,
        j.description as job_description, j.required_skills, j.preferred_skills,
        sr.id as report_id, sr.overall_score, sr.recommendation, sr.skills_match_score,
        sr.experience_score, sr.matched_skills, sr.missing_skills, sr.strengths,
        sr.gaps_and_flags, sr.criteria_breakdown, sr.suggested_questions,
        sr.summary_feedback, sr.provider_used, sr.created_at as screened_at
    FROM candidates c
    JOIN jobs j ON c.job_id = j.id
    LEFT JOIN screening_reports sr ON c.id = sr.candidate_id
    WHERE c.id = ?
    """, (candidate_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    for k in ["required_skills", "preferred_skills", "matched_skills", "missing_skills", "strengths", "gaps_and_flags", "criteria_breakdown", "suggested_questions"]:
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d

def log_notification(data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO notification_logs (candidate_id, candidate_name, recipient_email, recipient_phone, channel, subject, message_body, status, sent_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("candidate_id"),
        data.get("candidate_name", ""),
        data.get("recipient_email", ""),
        data.get("recipient_phone", ""),
        data.get("channel", "email"),
        data.get("subject", ""),
        data.get("message_body", ""),
        data.get("status", "sent"),
        now
    ))
    nid = cursor.lastrowid
    conn.commit()
    conn.close()
    return nid

def get_notification_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notification_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ============================================================
# USER & AUTHENTICATION SERVICES (HARDENED SECURITY)
# ============================================================
def hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    PBKDF2-HMAC-SHA256 with 100,000 iterations and a 16-byte cryptographic salt.
    Guarantees resistance against rainbow tables, dictionary attacks, and GPU acceleration.
    """
    if not salt:
        salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100_000).hex()
    return f"{salt}${derived}"

def verify_password(stored_hash: str, password: str) -> bool:
    """
    Verifies a password against the stored hash in constant time (prevents timing attacks).
    Supports salted PBKDF2 hashes (salt$hash) and backwards-compatible legacy SHA-256 hashes.
    """
    if not stored_hash or not password:
        return False
    if "$" in stored_hash:
        try:
            salt, expected_hash = stored_hash.split("$", 1)
            derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100_000).hex()
            return hmac.compare_digest(derived, expected_hash)
        except Exception:
            return False
    # Legacy fallback for old demo SHA-256 hashes
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(stored_hash, legacy_hash)

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    if not email:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, role, full_name, email, password_hash, created_at FROM users WHERE email = ?", (email.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(role: str, full_name: str, email: str, password: str) -> Dict[str, Any]:
    email_clean = email.strip().lower()
    existing = get_user_by_email(email_clean)
    if existing:
        raise ValueError("An account with this email address already exists.")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    p_hash = hash_password(password)
    cursor.execute("""
    INSERT INTO users (role, full_name, email, password_hash, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (role, full_name.strip(), email_clean, p_hash, now))
    uid = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        "id": uid,
        "role": role,
        "full_name": full_name.strip(),
        "email": email_clean,
        "created_at": now
    }

def authenticate_user(email: str, password: str, expected_role: Optional[str] = None) -> Optional[Dict[str, Any]]:
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(user["password_hash"], password):
        return None
    if expected_role and user["role"] != expected_role:
        return None
    return {
        "id": user["id"],
        "role": user["role"],
        "full_name": user["full_name"],
        "email": user["email"],
        "created_at": user["created_at"]
    }

