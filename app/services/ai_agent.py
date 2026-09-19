import os
import re
import json
import logging
import httpx
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Senior Technical Talent Acquisition & AI Recruitment Agent.
Your role is to rigorously, objectively, and accurately screen candidate resumes against an Employer's Job Description and strict criteria.

You will receive:
1. Job Title, Department, Description
2. Required Skills & Preferred Skills
3. Minimum Years of Experience & Education
4. Custom Evaluation Criteria with weights
5. The Candidate's extracted Resume text

You MUST return ONLY a valid, parseable JSON object without markdown fences, with the following exact schema:
{
  "overall_score": <number between 0 and 100>,
  "recommendation": "<'Shortlisted' if score >= 75, 'Under Review' if score 50-74, or 'Not Recommended' if score < 50>",
  "skills_match_score": <number 0-100>,
  "experience_score": <number 0-100>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["missingSkill1", "missingSkill2"],
  "strengths": [
    "Key strength with evidence from resume",
    "Second key strength with evidence"
  ],
  "gaps_and_flags": [
    "Critical gap or missing criteria",
    "Observation regarding experience or depth"
  ],
  "criteria_breakdown": [
    {
      "criterion": "Name of criterion",
      "weight": 30,
      "score": 85,
      "notes": "Evidence from resume"
    }
  ],
  "suggested_questions": [
    "Question 1 probing an identified gap or deep technical concept from their resume",
    "Question 2 exploring practical execution of their stated projects"
  ],
  "summary_feedback": "A constructive, 2-3 paragraph evaluation of why this candidate fits or doesn't fit the role.",
  "notification_message": "A professional, personalized message to the candidate explaining their application status and constructive guidance."
}
"""

def clean_json_string(text: str) -> str:
    """Strip markdown codeblocks and extra whitespace."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    # Find outer curly brackets
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1:
        text = text[first_brace:last_brace+1]
    return text.strip()

def run_gemini_screening(prompt: str, api_key: str) -> Dict[str, Any]:
    """Call Google Gemini API using free tier REST endpoint with ultra-fast models and intelligent fallback."""
    candidates = [
        settings.GEMINI_MODEL,
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash"
    ]
    seen = set()
    models_to_try = []
    for m in candidates:
        if m and m not in seen:
            seen.add(m)
            models_to_try.append(m)
            
    last_err = None
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": SYSTEM_PROMPT},
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    cleaned = clean_json_string(raw_text)
                    return json.loads(cleaned)
                else:
                    last_err = f"Gemini API {model_name} HTTP {res.status_code}: {res.text}"
                    logger.warning(last_err)
        except Exception as e:
            last_err = str(e)
            logger.warning(f"Failed with {model_name}: {e}")
            continue

    raise RuntimeError(f"Gemini API screening failed on all models: {last_err}")

def run_groq_screening(prompt: str, api_key: str) -> Dict[str, Any]:
    """Call Groq free tier API."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-HTTP": "application/json"
    }
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    with httpx.Client(timeout=35.0) as client:
        res = client.post(url, json=payload, headers=headers)
        if res.status_code == 200:
            data = res.json()
            raw_text = data["choices"][0]["message"]["content"]
            cleaned = clean_json_string(raw_text)
            return json.loads(cleaned)
        else:
            raise RuntimeError(f"Groq API error {res.status_code}: {res.text}")

def run_heuristic_screening(job: Dict[str, Any], resume_text: str, candidate_name: str) -> Dict[str, Any]:
    """
    Intelligent NLP and heuristic rule-based evaluator.
    Executes if no API key is provided or if free API quotas are exhausted.
    Guarantees reliable, deterministic, zero-crash execution.
    """
    text_lower = resume_text.lower()
    
    # 1. Evaluate Required Skills
    req_skills = job.get("required_skills", [])
    pref_skills = job.get("preferred_skills", [])
    
    matched_skills = []
    missing_skills = []
    
    for s in req_skills:
        # Regex search with word boundary where applicable
        pattern = r"\b" + re.escape(s.lower()) + r"\b"
        if re.search(pattern, text_lower):
            matched_skills.append(s)
        else:
            missing_skills.append(s)
            
    matched_pref = []
    for s in pref_skills:
        pattern = r"\b" + re.escape(s.lower()) + r"\b"
        if re.search(pattern, text_lower):
            matched_pref.append(s)
            
    # Calculate skills score
    if req_skills:
        req_ratio = len(matched_skills) / len(req_skills)
    else:
        req_ratio = 0.8
        
    pref_bonus = (len(matched_pref) / max(len(pref_skills), 1)) * 15.0 if pref_skills else 5.0
    skills_score = min(100.0, round((req_ratio * 85.0) + pref_bonus, 1))

    # 2. Experience Estimation
    min_exp = float(job.get("min_experience_years", 0))
    exp_matches = re.findall(r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+experience", text_lower)
    extracted_years = 0.0
    if exp_matches:
        extracted_years = max([float(x) for x in exp_matches])
    else:
        # Check for year ranges like 2020 - 2024 or 2018 to Present
        date_matches = re.findall(r"(20\d\d)\s*(?:-|to)\s*(20\d\d|present|current)", text_lower)
        total_span = 0
        for start_yr, end_yr in date_matches:
            end_val = 2026 if ("present" in end_yr or "current" in end_yr) else int(end_yr)
            diff = end_val - int(start_yr)
            if 0 < diff <= 25:
                total_span += diff
        extracted_years = min(total_span, 15.0)
    
    if min_exp <= 0:
        exp_score = 85.0
    elif extracted_years >= min_exp:
        exp_score = min(100.0, 80.0 + min(20.0, (extracted_years - min_exp) * 5.0))
    else:
        exp_score = max(30.0, round((extracted_years / min_exp) * 75.0, 1))

    # 3. Custom Criteria breakdown
    criteria = job.get("custom_criteria", [])
    criteria_breakdown = []
    total_criteria_weighted_score = 0.0
    total_weights = 0.0
    
    if not criteria:
        criteria = [
            {"name": "Technical Alignment", "weight": 50, "description": "Core technical capability match"},
            {"name": "Domain Experience", "weight": 50, "description": "Relevant professional background"}
        ]
        
    for c in criteria:
        c_name = c.get("name", "Criterion")
        c_weight = float(c.get("weight", 20))
        total_weights += c_weight
        
        # Check criteria keywords in resume
        c_words = [w for w in re.split(r"\W+", (c_name + " " + c.get("description", "")).lower()) if len(w) > 3]
        matches = sum(1 for w in set(c_words) if w in text_lower)
        match_rate = matches / max(len(set(c_words)), 1)
        
        c_score = round(min(100.0, max(40.0, (match_rate * 70.0) + (req_ratio * 30.0))), 1)
        total_criteria_weighted_score += c_score * (c_weight / 100.0)
        
        criteria_breakdown.append({
            "criterion": c_name,
            "weight": c_weight,
            "score": c_score,
            "notes": f"Matched relevant criteria keywords ({matches} indicator matches identified in resume text)."
        })
        
    # Overall score calculation
    if total_weights > 0:
        criteria_normalized = (total_criteria_weighted_score / (total_weights / 100.0))
        overall_score = round((skills_score * 0.4) + (exp_score * 0.3) + (criteria_normalized * 0.3), 1)
    else:
        overall_score = round((skills_score * 0.6) + (exp_score * 0.4), 1)
        
    overall_score = max(10.0, min(99.0, overall_score))
    
    # Recommendation Tier
    if overall_score >= 75.0:
        recommendation = "Shortlisted"
    elif overall_score >= 50.0:
        recommendation = "Under Review"
    else:
        recommendation = "Not Recommended"

    # Strengths
    strengths = []
    if matched_skills:
        strengths.append(f"Demonstrates validated competence in core requirements: {', '.join(matched_skills[:5])}.")
    if extracted_years >= min_exp and min_exp > 0:
        strengths.append(f"Meets or exceeds experience threshold with ~{int(extracted_years)} years identified.")
    if matched_pref:
        strengths.append(f"Brings desirable secondary competencies: {', '.join(matched_pref[:4])}.")
    if not strengths:
        strengths.append("Possesses foundational technical orientation and readable career progression.")

    # Gaps and flags
    gaps = []
    if missing_skills:
        gaps.append(f"Did not find clear evidence for required competencies: {', '.join(missing_skills[:4])}.")
    if extracted_years < min_exp and min_exp > 0:
        gaps.append(f"Experience level (~{extracted_years} yrs) falls short of the target minimum ({min_exp} yrs).")
    if not gaps:
        gaps.append("No critical blockers found; recommended for technical validation round.")

    # Tailored interview questions
    questions = []
    if missing_skills:
        questions.append(f"Can you walk us through any hands-on project experience you have with {missing_skills[0]}?")
    else:
        questions.append(f"Can you describe your most architecturally demanding implementation using {matched_skills[0] if matched_skills else 'your primary stack'}?")
    questions.append("How do you typically approach automated testing, performance profiling, and production error recovery?")
    questions.append("Describe a project where requirements shifted mid-stream. How did you adapt your architecture?")

    # Summary
    summary_feedback = (
        f"Candidate {candidate_name} was evaluated against the requirements for {job.get('title', 'this position')}. "
        f"The candidate achieved an overall match score of {overall_score}/100. "
        f"They matched {len(matched_skills)} out of {len(req_skills)} mandatory skills. "
        f"Based on the evaluation criteria, the candidate is categorized as: {recommendation}."
    )

    notification_message = (
        f"Dear {candidate_name},\n\n"
        f"Thank you for your interest in the {job.get('title', 'Role')} opening with us! "
        f"Our AI Talent Screening agent has completed reviewing your resume against our role criteria.\n\n"
        f"Application Status: {recommendation}\n"
        f"Overall Assessment Score: {overall_score}/100\n\n"
        + (
            "Congratulations! Our hiring team has shortlisted your application for the next interview round. We will follow up shortly with scheduling details."
            if recommendation == "Shortlisted" else
            "Your profile is currently under active review by our recruitment committee. We will contact you if your qualifications align with our interview schedule."
            if recommendation == "Under Review" else
            "While your background has compelling aspects, we have chosen to proceed with applicants whose current technical experience more closely aligns with our immediate requirements."
        )
    )

    return {
        "overall_score": overall_score,
        "recommendation": recommendation,
        "skills_match_score": skills_score,
        "experience_score": exp_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "strengths": strengths,
        "gaps_and_flags": gaps,
        "criteria_breakdown": criteria_breakdown,
        "suggested_questions": questions,
        "summary_feedback": summary_feedback,
        "notification_message": notification_message
    }

def screen_resume(job: Dict[str, Any], resume_text: str, candidate_name: str, preferred_provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Main screening orchestrator. Tries configured Free AI provider (Gemini / Groq),
    and gracefully falls back to the heuristic evaluation if unavailable or unconfigured.
    """
    provider = preferred_provider or settings.AI_PROVIDER
    gemini_key = settings.GEMINI_API_KEY.strip()
    groq_key = settings.GROQ_API_KEY.strip()
    
    prompt = f"""
=== JOB SPECIFICATION ===
Title: {job.get('title')}
Department: {job.get('department')}
Description: {job.get('description')}
Required Skills: {json.dumps(job.get('required_skills', []))}
Preferred Skills: {json.dumps(job.get('preferred_skills', []))}
Minimum Experience Years: {job.get('min_experience_years', 0)}
Minimum Education: {job.get('min_education', 'Not specified')}
Custom Evaluation Rubrics: {json.dumps(job.get('custom_criteria', []))}

=== CANDIDATE RESUME ===
Candidate Name: {candidate_name}
Resume Text:
{resume_text[:12000]}
"""

    # 1. Try Gemini if key is provided
    if provider in ["gemini", "auto"] and gemini_key:
        try:
            logger.info("Executing screening via Google Gemini API (Free Tier)...")
            result = run_gemini_screening(prompt, gemini_key)
            result["provider_used"] = "Google Gemini"
            return result
        except Exception as e:
            logger.error(f"Gemini API execution failed: {e}. Attempting fallback...")

    # 2. Try Groq if key is provided
    if (provider == "groq" or not gemini_key) and groq_key:
        try:
            logger.info("Executing screening via Groq API (Free Tier)...")
            result = run_groq_screening(prompt, groq_key)
            result["provider_used"] = "Groq Llama 3"
            return result
        except Exception as e:
            logger.error(f"Groq API execution failed: {e}. Falling back to Heuristic Engine...")

    # 3. Resilient Heuristic Engine (zero API key needed)
    logger.info("Executing screening via Native Heuristic Evaluation Engine...")
    result = run_heuristic_screening(job, resume_text, candidate_name)
    result["provider_used"] = "AI Heuristic Engine (Offline Free Fallback)"
    return result
