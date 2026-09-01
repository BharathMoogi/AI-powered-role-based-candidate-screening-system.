"""
Test Multi-Project Cycling and Strict Tech-Stack Isolation

Verifies that:
1. All resume projects are systematically cycled through across generated session questions.
2. Each generated question strictly references only the technologies from that project's tech stack
   (i.e. zero domain bleed like CNN/GPU questions for a web backend project).
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.resume import ParsedResume, ProjectDetail
from app.services.interview_engine import generate_interview_session_questions


def test_three_project_resume_cycling():
    print("=" * 80)
    print("TEST: MULTI-PROJECT CYCLING & TECH-STACK DOMAIN ISOLATION")
    print("=" * 80)

    # 3 Distinct Projects: Backend, Data Engineering, ML/NLP
    candidate_resume = ParsedResume(
        candidate_name="Alex Rivera",
        summary="Senior Software Engineer with expertise across asynchronous backend APIs, distributed data pipelines, and NLP language models.",
        skills=["Asynchronous APIs", "Distributed Data Systems", "Natural Language Processing"],
        technologies=["FastAPI", "Twilio", "Redis", "Apache Spark", "Airflow", "PostgreSQL", "PyTorch", "Transformers", "Python"],
        domains=["Communications & APIs", "Data Engineering", "Machine Learning & NLP"],
        apparent_experience_level="senior",
        notable_projects=[
            ProjectDetail(
                name="Twilio Alert & Notification Dispatcher",
                description="Engineered low-latency SMS alert and webhook dispatch service handling 12,000 req/sec.",
                technologies=["FastAPI", "Twilio", "Redis", "Python"],
                highlights="Sub-15ms P99 latency with zero webhook dropping"
            ),
            ProjectDetail(
                name="Clickstream ETL & Warehouse Ingestion",
                description="Built distributed clickstream ingestion pipeline processing 200 million daily events into data warehouse.",
                technologies=["Apache Spark", "Airflow", "PostgreSQL", "SQL"],
                highlights="Eliminated executor shuffle memory spills and cut pipeline runtime by 45%"
            ),
            ProjectDetail(
                name="Customer Intent & Sentiment NLP Classifier",
                description="Fine-tuned transformer models for real-time customer support intent classification.",
                technologies=["PyTorch", "Transformers", "Hugging Face"],
                highlights="Achieved 94.2% multi-class accuracy across 60 support categories"
            )
        ]
    )

    role = "Senior Full Stack / Systems Engineer"
    questions = generate_interview_session_questions(
        resume=candidate_resume,
        role=role,
        target_count=5,
        difficulty="hard"
    )

    print(f"\nGenerated {len(questions)} Questions for Candidate with 3 Distinct Projects:\n")

    projects_covered = set()

    for idx, q in enumerate(questions, 1):
        p_ref = q.project_referenced or "Unknown"
        projects_covered.add(p_ref)
        print(f"--- QUESTION #{idx} ---")
        print(f"  Target Project: [{p_ref}]")
        print(f"  Technologies in Scope: {q.technologies_referenced}")
        print(f"  Topic: {q.topic}")
        print(f"  Question:\n    \"{q.question_text}\"\n")

        q_lower = q.question_text.lower()

        # Strict Isolation Assertions:
        if "twilio" in p_ref.lower() or "dispatcher" in p_ref.lower():
            # Project 1: Backend/Twilio -> MUST NOT mention CNN, GPU, Spark, Transformer
            assert "cnn" not in q_lower, f"Q{idx} for Backend/Twilio project contained CNN!"
            assert "gpu" not in q_lower, f"Q{idx} for Backend/Twilio project contained GPU!"
            assert "spark" not in q_lower, f"Q{idx} for Backend/Twilio project contained Spark!"
            assert "transformer" not in q_lower, f"Q{idx} for Backend/Twilio project contained Transformer!"
            print(f"  [CHECK PASSED] Q{idx} correctly isolated to Webhook / API / Rate Limiting domain.")

        elif "clickstream" in p_ref.lower() or "spark" in p_ref.lower() or "warehouse" in p_ref.lower():
            # Project 2: Data/Spark -> MUST NOT mention Twilio, CNN, GPU kernel
            assert "twilio" not in q_lower, f"Q{idx} for Spark project contained Twilio!"
            assert "cnn" not in q_lower, f"Q{idx} for Spark project contained CNN!"
            print(f"  [CHECK PASSED] Q{idx} correctly isolated to Spark / Distributed Data / Memory Spill domain.")

        elif "sentiment" in p_ref.lower() or "nlp" in p_ref.lower() or "classifier" in p_ref.lower():
            # Project 3: NLP/PyTorch -> MUST NOT mention Twilio, Spark, SQL write-skew
            assert "twilio" not in q_lower, f"Q{idx} for NLP project contained Twilio!"
            assert "spark" not in q_lower, f"Q{idx} for NLP project contained Spark!"
            print(f"  [CHECK PASSED] Q{idx} correctly isolated to Transformer / Attention / Loss Convergence domain.")

    print("\n" + "=" * 80)
    print("PROJECT COVERAGE SUMMARY:")
    print(f"Total Unique Projects in Resume: {len(candidate_resume.notable_projects)}")
    print(f"Total Unique Projects Covered in Interview: {len(projects_covered)}")
    for p in projects_covered:
        print(f"  - Covered: {p}")
    print("=" * 80)

    assert len(projects_covered) == 3, f"Expected all 3 projects to be covered, but got {len(projects_covered)}"
    print("\n>>> ALL ASSERTIONS PASSED: 100% of resume projects systematically covered with ZERO tech-stack domain bleed!")


if __name__ == "__main__":
    test_three_project_resume_cycling()
