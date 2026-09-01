import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.resume import extract_resume_data
from app.services.interview_engine import generate_interview_session_questions


sample_text = """
Bharath Moogi
Email: bharath@example.com | Phone: 1234567890

Applied AI/ML Projects
ApplyRA – AI-Powered Job Application Assistant
• Built an NLP / RAG-style retrieval pipeline that parses job descriptions, extracts required skills, and semantically compares them against a candidate profile using embeddings and information extraction.
• Generated tailored, ATS-optimized resume content via LLM APIs (Groq, OpenRouter), combining prompt engineering with rule-based scoring logic and output validation checks, secured with basic authentication, request logging, and a CI/CD (GitHub Actions) pipeline for automated tests and linting.

VoiceFlow AI (Saarthi) – Voice-First AI Email & Calling Assistant
• Built an end-to-end voice-to-email pipeline: speech transcribed via Whisper, intent parsed and structured using LLMs (Gemini, OpenRouter), and outputs generated and dispatched through a secure API-integrated SMTP workflow.
• Developed an outbound calling agent using the Twilio Voice API, enabling automated, LLM-driven voice interactions and follow-ups triggered directly from parsed intents.
• Applied prompt engineering and structured-output validation to reliably convert unstructured speech into well-formatted, policy-compliant output; backend built with Python, FastAPI, and PostgreSQL, secured with basic authentication/authorization, structured logging, and a CI/CD (GitHub Actions) pipeline for automated testing and build/deploy.

Visibility Enhancement for Intelligent Transportation
• Applying computer vision and deep learning techniques to improve image visibility and object-detection reliability in degraded driving conditions (ongoing).
• Working with image datasets to evaluate and iterate on enhancement models, documenting results as part of an applied deep learning research project.
"""

data = extract_resume_data(sample_text)
print("Candidate Name:", data.get("candidate_name"))
print("Total Projects Extracted:", len(data.get("notable_projects", [])))
for i, p in enumerate(data.get("notable_projects", []), 1):
    print(f"Project {i}: {p.get('name')}")
    print(f"   Tech: {p.get('technologies')}")

print("\n" + "=" * 80)
print("GENERATED SESSION QUESTIONS (CYCLE ACROSS EXACT RESUME PROJECTS):")
print("=" * 80)
questions = generate_interview_session_questions(resume=data, role="Machine Learning Engineer", target_count=5)
for i, q in enumerate(questions, 1):
    print(f"\n[QUESTION #{i}]")
    print(f"Project Reference: {q.project_referenced}")
    print(f"Topic: {q.topic}")
    print(f"Question Text:\n   \"{q.question_text}\"")
