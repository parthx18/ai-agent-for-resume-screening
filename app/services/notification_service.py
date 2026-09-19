import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from typing import Dict, Any, Tuple
from app.config import settings
from app.database import log_notification

logger = logging.getLogger(__name__)

EMAIL_TEMPLATE_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.06); }}
    .header {{ background: linear-gradient(135deg, #1e293b, #0f172a); color: #ffffff; padding: 32px 28px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }}
    .header p {{ margin: 6px 0 0 0; color: #94a3b8; font-size: 14px; }}
    .content {{ padding: 30px 28px; color: #334155; line-height: 1.6; font-size: 15px; }}
    .status-card {{ border-radius: 8px; padding: 18px 20px; margin: 20px 0; }}
    .status-shortlisted {{ background-color: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; }}
    .status-review {{ background-color: #fffbeb; border: 1px solid #fde68a; color: #92400e; }}
    .status-rejected {{ background-color: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }}
    .status-title {{ font-weight: 700; font-size: 16px; margin-bottom: 4px; display: flex; align-items: center; gap: 8px; }}
    .score-badge {{ display: inline-block; padding: 4px 12px; background: #0f172a; color: #ffffff; border-radius: 9999px; font-size: 13px; font-weight: 600; margin-top: 6px; }}
    .feedback-box {{ background: #f8fafc; border-left: 4px solid #3b82f6; padding: 14px 18px; border-radius: 4px; margin: 20px 0; font-style: italic; font-size: 14px; color: #475569; }}
    .footer {{ background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 18px 28px; text-align: center; font-size: 12px; color: #64748b; }}
    .btn {{ display: inline-block; padding: 10px 22px; background: #2563eb; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 15px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>AI Talent Acquisition Portal</h1>
      <p>Automated Application Screening Update</p>
    </div>
    <div class="content">
      <p>Hello <strong>{candidate_name}</strong>,</p>
      <p>Thank you for submitting your resume for the <strong>{job_title}</strong> role at our organization.</p>
      
      <div class="status-card {status_class}">
        <div class="status-title">Status: {recommendation}</div>
        <div>{status_headline}</div>
        <div class="score-badge">Screening Match Score: {overall_score}/100</div>
      </div>
      
      <div class="feedback-box">
        "{notification_message}"
      </div>
      
      <p>{next_steps}</p>
      
      <p style="margin-top: 25px;">Best regards,<br><strong>Talent Acquisition & Hiring Operations</strong></p>
    </div>
    <div class="footer">
      This is an automated notification dispatched by the AI Resume Screening Agent. All candidate records are synchronized in real-time.
    </div>
  </div>
</body>
</html>
"""

def build_notification_content(candidate: Dict[str, Any], job: Dict[str, Any], report: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """Generates subject, HTML body, plain text body, and SMS body."""
    candidate_name = candidate.get("full_name", "Applicant")
    job_title = job.get("title", "Position")
    recommendation = report.get("recommendation", "Under Review")
    score = report.get("overall_score", 0.0)
    msg = report.get("notification_message") or report.get("summary_feedback") or "Your application has been processed."
    
    if "shortlist" in recommendation.lower():
        status_class = "status-shortlisted"
        status_headline = "Outstanding Profile Match - Shortlisted for Next Stage"
        next_steps = "Our recruitment team has added you to the primary interview schedule. Keep an eye on your inbox for interview date invitations within the next 48 hours."
        subject = f"Congratulations! Application Shortlisted: {job_title}"
    elif "not" in recommendation.lower() or "reject" in recommendation.lower():
        status_class = "status-rejected"
        status_headline = "Application Review Concluded"
        next_steps = "We appreciate your interest and time. While this specific position is not a match for our current opening, your profile will remain in our talent network for future matching roles."
        subject = f"Update regarding your application for {job_title}"
    else:
        status_class = "status-review"
        status_headline = "Application Under Committee Review"
        next_steps = "Your application has successfully cleared preliminary automated screening and is queued for senior team review. We will notify you once final decisions are confirmed."
        subject = f"Application Status Update: {job_title}"

    html_content = EMAIL_TEMPLATE_HTML.format(
        candidate_name=candidate_name,
        job_title=job_title,
        recommendation=recommendation,
        status_class=status_class,
        status_headline=status_headline,
        overall_score=score,
        notification_message=msg,
        next_steps=next_steps
    )
    
    plain_text = f"""Hello {candidate_name},

Thank you for applying for the {job_title} role.
Our AI screening agent has reviewed your application.

Status: {recommendation}
Screening Match Score: {score}/100

{msg}

{next_steps}

Best regards,
Talent Acquisition Team
"""

    sms_text = f"Hi {candidate_name}, your application for {job_title} has been screened! Status: {recommendation} (Score: {score}/100). Check your email for full details."

    return subject, html_content, plain_text, sms_text

def dispatch_candidate_notification(candidate: Dict[str, Any], job: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatches email via SMTP if configured, or records to live simulated outbox.
    Also logs an SMS notification record.
    """
    subject, html_content, plain_text, sms_text = build_notification_content(candidate, job, report)
    
    email_status = "simulated"
    email_error = None
    
    # Check if real SMTP is configured and enabled
    if settings.ENABLE_REAL_EMAIL and settings.SMTP_USER and settings.SMTP_PASSWORD:
        try:
            smtp_user = settings.SMTP_USER.strip()
            smtp_pass = settings.SMTP_PASSWORD.replace(" ", "").strip()
            from_addr = settings.SMTP_FROM_EMAIL.strip() if settings.SMTP_FROM_EMAIL else smtp_user

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = candidate["email"]
            
            part1 = MIMEText(plain_text, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)
            
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=12) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_addr, [candidate["email"]], msg.as_string())
                
            email_status = "sent"
            logger.info(f"Live email dispatched successfully to {candidate['email']}")
        except Exception as e:
            logger.error(f"Failed to send live email via SMTP: {e}")
            email_status = f"failed ({str(e)[:40]})"
            email_error = str(e)
    else:
        # Default: Mock / Automated simulation logged to persistent SQLite outbox
        email_status = "simulated (outbox logged)"

    # Log Email Notification
    email_log_id = log_notification({
        "candidate_id": candidate.get("id"),
        "candidate_name": candidate.get("full_name"),
        "recipient_email": candidate.get("email"),
        "recipient_phone": candidate.get("phone", ""),
        "channel": "email",
        "subject": subject,
        "message_body": html_content,
        "status": email_status
    })
    
    # Log SMS / Message Notification
    sms_status = "simulated (ready)" if candidate.get("phone") else "no phone provided"
    sms_log_id = log_notification({
        "candidate_id": candidate.get("id"),
        "candidate_name": candidate.get("full_name"),
        "recipient_email": candidate.get("email"),
        "recipient_phone": candidate.get("phone", ""),
        "channel": "sms",
        "subject": "Application Update SMS",
        "message_body": sms_text,
        "status": sms_status
    })

    return {
        "email_log_id": email_log_id,
        "email_status": email_status,
        "email_error": email_error,
        "sms_log_id": sms_log_id,
        "sms_status": sms_status,
        "subject": subject,
        "summary": f"Notification triggered for {candidate.get('full_name')} ({email_status})"
    }
