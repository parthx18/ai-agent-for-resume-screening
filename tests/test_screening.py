import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, get_all_jobs, get_candidates_with_reports
from app.services.parser import parse_resume_content
from app.services.ai_agent import run_heuristic_screening
from app.services.excel_service import sync_candidate_to_excel
from app.services.notification_service import build_notification_content

client = TestClient(app)

def test_system_initialization():
    print("Testing system initialization and database...")
    init_db()
    jobs = get_all_jobs()
    assert len(jobs) >= 1, "Starter job should be pre-seeded in SQLite database"
    print(f"PASS: Found {len(jobs)} active jobs in database.")

def test_resume_parser():
    print("Testing resume document parser...")
    sample_txt = "John Doe\nSoftware Engineer with 4 years experience in Python and FastAPI."
    parsed = parse_resume_content("resume.txt", sample_txt.encode("utf-8"))
    assert "Software Engineer" in parsed
    print("PASS: Resume text parser successfully parsed document.")

def test_ai_screening_engine():
    print("Testing AI screening agent with criteria evaluation...")
    job = {
        "title": "AI Backend Engineer",
        "department": "AI",
        "description": "Building agentic systems",
        "required_skills": ["Python", "FastAPI", "Docker", "LLMs"],
        "preferred_skills": ["PostgreSQL", "LangChain"],
        "min_experience_years": 3,
        "custom_criteria": [
            {"name": "Agentic Architecture", "weight": 50, "description": "LLM agent design"},
            {"name": "Python Mastery", "weight": 50, "description": "FastAPI async backend"}
        ]
    }
    
    sample_resume = """
    Jane Smith
    Senior Software Engineer
    5 years of experience building Python and FastAPI backend microservices.
    Proficient in Docker, LLMs, LangChain, REST APIs, and PostgreSQL.
    Architected autonomous agent pipelines and production web applications.
    """
    
    result = run_heuristic_screening(job, sample_resume, "Jane Smith")
    assert 0 <= result["overall_score"] <= 100
    assert result["recommendation"] in ["Shortlisted", "Under Review", "Not Recommended"]
    assert "Python" in result["matched_skills"]
    assert len(result["strengths"]) > 0
    assert len(result["suggested_questions"]) > 0
    print(f"PASS: AI screening completed successfully. Score: {result['overall_score']}, Tier: {result['recommendation']}")

def test_excel_sync():
    print("Testing live Excel generation & styling...")
    test_excel_path = str(BASE_DIR / "records" / "test_screened_candidates.xlsx")
    record = {
        "id": 101,
        "full_name": "Test Candidate",
        "email": "test@example.com",
        "phone": "+1 555 1234",
        "job_title": "AI Backend Engineer",
        "overall_score": 88.5,
        "recommendation": "Shortlisted",
        "skills_match_score": 90.0,
        "experience_score": 85.0,
        "matched_skills": ["Python", "FastAPI"],
        "missing_skills": [],
        "strengths": ["Strong Python experience"],
        "gaps_and_flags": ["None"],
        "summary_feedback": "Excellent match.",
        "notification_status": "Sent"
    }
    out_path = sync_candidate_to_excel(record, filepath=test_excel_path)
    assert os.path.exists(out_path), "Excel file must exist after sync"
    print(f"PASS: Live Excel synchronized cleanly at {out_path}")
    # Cleanup test file
    if os.path.exists(test_excel_path):
        os.remove(test_excel_path)

def test_notification_generation():
    print("Testing candidate automated notification builder...")
    candidate = {"full_name": "John Doe", "email": "john@example.com", "phone": "+1234567890"}
    job = {"title": "Senior AI Engineer"}
    report = {"recommendation": "Shortlisted", "overall_score": 92.0, "notification_message": "Welcome aboard!"}
    
    subject, html, plain, sms = build_notification_content(candidate, job, report)
    assert "Shortlisted" in subject
    assert "John Doe" in html
    assert "92" in html
    assert "Shortlisted" in sms
    print("PASS: Notification builder generated verified HTML email and SMS alert.")

def test_api_endpoints():
    print("Testing FastAPI endpoints via TestClient...")
    # Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
    
    # Jobs list
    res = client.get("/api/jobs")
    assert res.status_code == 200
    jobs = res.json()["jobs"]
    assert len(jobs) >= 1
    
    # Apply and screen
    job_id = jobs[0]["id"]
    resume_file_content = b"Alex Developer\n3 years experience in Python, FastAPI, Docker, and REST APIs."
    files = {"resume_file": ("resume.txt", resume_file_content, "text/plain")}
    data = {
        "job_id": job_id,
        "full_name": "Alex Developer",
        "email": "alex.dev@testdomain.com",
        "phone": "+1 555 9876",
        "linkedin_or_portfolio": "https://linkedin.com/in/alexdev"
    }
    res = client.post("/api/apply", data=data, files=files)
    assert res.status_code == 200
    resp_data = res.json()
    assert resp_data["success"] is True
    assert "overall_score" in resp_data
    assert "recommendation" in resp_data
    print(f"PASS: Full application & screening API executed successfully! Score: {resp_data['overall_score']}")

    # Candidates list
    res = client.get("/api/candidates")
    assert res.status_code == 200
    candidates = res.json()["candidates"]
    assert len(candidates) >= 1
    print(f"PASS: Verified candidates API returned {len(candidates)} records.")

    # Excel Download
    res = client.get("/api/excel/download")
    assert res.status_code == 200
    assert len(res.content) > 1000
    print("PASS: Verified Excel live download endpoint returns binary xlsx file.")

    # Notifications outbox
    res = client.get("/api/notifications")
    assert res.status_code == 200
    notifs = res.json()["notifications"]
    assert len(notifs) >= 1
    print(f"PASS: Verified notification outbox logged {len(notifs)} records.")

if __name__ == "__main__":
    test_system_initialization()
    test_resume_parser()
    test_ai_screening_engine()
    test_excel_sync()
    test_notification_generation()
    test_api_endpoints()
    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
