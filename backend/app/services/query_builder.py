"""
Dynamic Retrieval Query Builder Service

Constructs targeted conceptual retrieval queries from parsed candidate resume data and the target screening role.
Translates practical skills and tooling into deep foundational concepts from the knowledge base,
ensuring every resume project and core skill is systematically covered.
"""

import json
import os
import re
import logging
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.services.resume import ParsedResume

logger = logging.getLogger("query_builder_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ============================================================================
# Schemas
# ============================================================================

class RetrievalQueryItem(BaseModel):
    query: str = Field(
        ...,
        description="Foundational conceptual retrieval query to search against ChromaDB knowledge base"
    )
    source_skill: str = Field(
        ...,
        description="The candidate skill, technology, or domain from the resume that motivated this query"
    )
    rationale: str = Field(
        ...,
        description="Explanation of why this concept should be probed and how it connects the candidate's claim to role foundations"
    )
    project_name: Optional[str] = Field(
        None,
        description="Exact project name from candidate resume if tied to a project"
    )
    project_tech: List[str] = Field(
        default_factory=list,
        description="Tech stack of the associated project"
    )
    project_description: Optional[str] = Field(
        None,
        description="Description of the associated project"
    )


class RetrievalQueryPlan(BaseModel):
    role: str = Field(..., description="Target candidate role")
    queries: List[RetrievalQueryItem] = Field(
        ...,
        min_length=3,
        max_length=10,
        description="List of targeted conceptual retrieval queries covering all projects and skills"
    )


# ============================================================================
# Conceptual Translation Prompt
# ============================================================================

SYSTEM_PROMPT = """You are a Principal Technical Interviewer and Knowledge Base Architect.
Your task is to review a candidate's extracted resume profile and target role, then generate 5 to 8 targeted retrieval queries to probe their foundational competency.

CRITICAL INSTRUCTIONS:
1. CYCLE THROUGH ALL NOTABLE PROJECTS: You MUST generate at least one dedicated conceptual query for EACH project listed in the resume.
2. DO NOT simply echo candidate resume keywords as queries:
   - WRONG: "FastAPI Twilio experience"
   - RIGHT: "asynchronous webhook dispatch, rate-limiting backpressure, and non-blocking I/O event loops"
   - WRONG: "Spark ETL pipeline"
   - RIGHT: "distributed dataset partitioning, shuffle memory management, and stream-table joins"
   - WRONG: "PyTorch NLP classifier"
   - RIGHT: "multi-head self-attention mechanisms, cross-entropy loss convergence, and sequence embedding representations"
3. STRICT TECH-STACK ISOLATION: For each project query, include only concepts relevant to that project's actual technologies. Do not blend unrelated domains (e.g. do not ask GPU/CNN questions for a web/API project).
4. Return between 5 and 8 queries with strict traceability: { "query", "source_skill", "rationale", "project_name", "project_tech" }.

Return ONLY valid JSON matching this schema:
{
  "role": "Target role name",
  "queries": [
    {
      "query": "Theoretical/foundational concept query",
      "source_skill": "Candidate skill/tool/project referenced",
      "rationale": "Clear justification of why probing this concept tests depth",
      "project_name": "Project Name if applicable or null",
      "project_tech": ["Tool1", "Tool2"]
    }
  ]
}
"""


# ============================================================================
# Domain Knowledge Conceptual Bridge Table
# ============================================================================

CONCEPT_BRIDGES = {
    # Backend / Web / APIs
    "twilio": ("asynchronous webhook dispatch, rate limiting backpressure, and fault-tolerant third-party API integration", "Probe resilience and async reliability in communications and external API integration"),
    "fastapi": ("asynchronous concurrency, non-blocking I/O event loops and ASGI architecture", "Probe understanding of asynchronous runtime mechanics beyond framework routing"),
    "flask": ("WSGI application concurrency, synchronous threadpool execution and request context lifecycle", "Assess core web runtime architectures and request handling"),
    "django": ("ORM query optimization, database transaction management and middleware request processing", "Evaluate web framework architecture and data access patterns"),
    "redis": ("in-memory key-value eviction policies, distributed caching coherence and atomic operations", "Test caching strategies, lock contention and volatile memory management"),
    "postgresql": ("ACID isolation anomalies, WAL write-ahead logging and B-Tree indexing access paths", "Probe relational data safety and query planner execution internals"),
    "postgres": ("ACID transaction isolation guarantees, lock contention and indexing strategies", "Evaluate transactional consistency knowledge under load"),
    "sql": ("relational schema normalization, execution plan index scans and join algorithms", "Test database fundamentals and query optimization"),
    
    # Data Engineering / Distributed Processing
    "spark": ("distributed dataset partitioning, shuffle spill memory management and DAG execution stages", "Assess understanding of distributed compute bottlenecks and memory layouts"),
    "apache spark": ("distributed dataset partitioning, shuffle memory management and lazy DAG execution", "Probe distributed data processing mechanics"),
    "airflow": ("DAG task dependency scheduling, idempotent pipeline retries and distributed executor coordination", "Evaluate workflow orchestration and data pipeline reliability"),
    "kafka": ("distributed partition logs, consumer group offset commits and at-least-once delivery semantics", "Probe event streaming durability and distributed messaging guarantees"),
    
    # Machine Learning / AI
    "pytorch": ("automatic differentiation computational graphs and backpropagation gradient calculation", "Verify deep understanding of gradient mechanics behind deep learning framework usage"),
    "tensorflow": ("computational graph execution, backpropagation and tensor memory management", "Probe underlying mechanics of tensor execution engines"),
    "transformers": ("multi-head self-attention mechanisms, positional encodings and transformer sequence modeling", "Assess theoretical comprehension of modern language modeling architectures"),
    "hugging face": ("transformer attention computation, tokenization schemes and transfer learning fine-tuning", "Evaluate fine-tuning methodology and language representation structures"),
    "nlp": ("self-attention mechanisms, token embedding representations and loss convergence", "Assess language modeling fundamentals"),
    "scikit-learn": ("bias-variance tradeoff, cross-validation methodology and regularization penalties", "Assess fundamental statistical learning and validation rigor"),
    "computer vision": ("convolutional spatial invariance, receptive fields and feature map representations", "Check core architectural principles of image feature extraction"),
    "cnn": ("convolutional kernel operations, spatial downsampling and receptive field expansion", "Probe deep convolutional network mechanics"),
    "machine learning": ("inductive bias, hypothesis space search and generalization bounds", "Test understanding of foundational learning theory and overfitting"),
    "deep learning": ("gradient degradation, vanishing gradients and residual learning representations", "Evaluate architecture intuition and optimization challenges"),

    # Infrastructure / Cloud
    "docker": ("Linux namespaces, cgroups resource isolation and layered copy-on-write filesystem internals", "Assess OS-level virtualization concepts behind containerization"),
    "kubernetes": ("control plane reconciliation loops, distributed consensus and stateful workload scheduling", "Evaluate distributed systems coordination and orchestration theory"),
    "distributed systems": ("CAP theorem trade-offs, consensus algorithms (Raft/Paxos) and eventual consistency", "Test architectural mastery of network partitions and node failures"),
    "system design": ("horizontal scalability, database sharding, fault tolerance and load balancing algorithms", "Assess high-level architectural decomposition and bottleneck mitigation"),
    "python": ("global interpreter lock (GIL), memory reference counting and generator iteration protocols", "Examine core runtime execution characteristics of Python"),
}


class DynamicQueryBuilder:
    """Service to generate conceptual retrieval queries from resume analysis."""

    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        self.gemini_api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    def _call_llm(self, user_content: str) -> str:
        # 1. Try OpenAI
        if self.openai_api_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                return response.choices[0].message.content or "{}"
            except Exception as e:
                logger.warning(f"OpenAI query builder failed: {e}")

        # 2. Try Gemini
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    generation_config={"response_mime_type": "application/json"}
                )
                full_prompt = f"{SYSTEM_PROMPT}\n\nCandidate & Role Info:\n{user_content}"
                response = model.generate_content(full_prompt)
                return response.text or "{}"
            except Exception as e:
                logger.warning(f"Gemini query builder failed: {e}")

        # 3. Fallback deterministic conceptual mapper cycling through all projects
        return self._heuristic_query_builder(user_content)

    def _heuristic_query_builder(self, user_content: str) -> str:
        """
        Deterministic knowledge-bridge generator that guarantees EVERY project in the resume
        receives dedicated conceptual queries strictly matching its own tech stack.
        """
        items: List[Dict[str, Any]] = []

        # Parse notable projects from user_content if formatted as JSON
        projects = []
        try:
            p_match = re.search(r"Notable Projects:\s*(\[[\s\S]*?\])\s*(?:Candidate|$)", user_content)
            if p_match:
                projects = json.loads(p_match.group(1))
        except Exception:
            projects = []

        # 1. First Pass: Generate at least 1-2 targeted queries for EACH notable project
        for p in projects:
            p_name = p.get("name", "Project")
            p_techs = p.get("technologies", [])
            p_desc = p.get("description", "")
            combined_p_text = f"{p_name} {' '.join(p_techs)} {p_desc}".lower()

            # Find matching concept for this specific project
            project_matched = False
            for tech in p_techs:
                tech_lower = tech.lower()
                for keyword, (concept_query, rationale) in CONCEPT_BRIDGES.items():
                    if keyword in tech_lower:
                        items.append({
                            "query": concept_query,
                            "source_skill": tech,
                            "rationale": f"For project '{p_name}': {rationale}",
                            "project_name": p_name,
                            "project_tech": p_techs,
                            "project_description": p_desc
                        })
                        project_matched = True
                        break
                if project_matched:
                    break

            if not project_matched:
                # Build tailored query from project description/tech
                primary_tech = p_techs[0] if p_techs else "System Engineering"
                items.append({
                    "query": f"architectural design, fault-tolerance and implementation patterns for {primary_tech}",
                    "source_skill": primary_tech,
                    "rationale": f"Probe candidate design and execution in project '{p_name}'",
                    "project_name": p_name,
                    "project_tech": p_techs,
                    "project_description": p_desc
                })

        # 2. Second Pass: Add queries for candidate's other technologies/skills
        content_lower = user_content.lower()
        for keyword, (concept_query, rationale) in CONCEPT_BRIDGES.items():
            if keyword in content_lower and not any(it["query"] == concept_query for it in items):
                items.append({
                    "query": concept_query,
                    "source_skill": keyword.capitalize(),
                    "rationale": rationale,
                    "project_name": None,
                    "project_tech": [keyword.capitalize()]
                })
            if len(items) >= 7:
                break

        # 3. Fill fallback queries if needed
        generic_fallbacks = [
            ("concurrency models, asynchronous non-blocking I/O and race condition prevention", "System Architecture", "Probe candidate capability in concurrent execution"),
            ("database transaction isolation levels, indexing access paths and data normalization", "Database Architecture", "Assess database internals and data modeling lifecycle"),
            ("system resilience, error handling paradigms and observability monitoring", "Production Engineering", "Ensure candidate designs systems with fault-tolerance")
        ]

        for q, skill, rat in generic_fallbacks:
            if len(items) >= 5:
                break
            if not any(it["query"] == q for it in items):
                items.append({
                    "query": q,
                    "source_skill": skill,
                    "rationale": rat,
                    "project_name": None,
                    "project_tech": [skill]
                })

        items = items[:8]
        return json.dumps({
            "role": "Candidate Screening Role",
            "queries": items
        })

    def build_queries(
        self,
        resume: Union[ParsedResume, Dict[str, Any]],
        role: str
    ) -> List[RetrievalQueryItem]:
        """
        Builds 5-8 targeted conceptual retrieval queries systematically covering all resume projects.
        """
        if isinstance(resume, dict):
            resume_data = resume
        else:
            resume_data = resume.model_dump()

        user_content = (
            f"Target Role: {role}\n"
            f"Candidate Experience Level: {resume_data.get('apparent_experience_level', 'mid')}\n"
            f"Skills: {', '.join(resume_data.get('skills', []))}\n"
            f"Technologies: {', '.join(resume_data.get('technologies', []))}\n"
            f"Domains: {', '.join(resume_data.get('domains', []))}\n"
            f"Notable Projects: {json.dumps(resume_data.get('notable_projects', []))}\n"
        )

        response_str = self._call_llm(user_content)
        
        try:
            cleaned = self._clean_json(response_str)
            data = json.loads(cleaned)
            if "role" not in data:
                data["role"] = role

            queries_raw = data.get("queries", [])
            if len(queries_raw) > 8:
                data["queries"] = queries_raw[:8]
            elif len(queries_raw) < 3:
                fallback_json = self._heuristic_query_builder(user_content)
                data = json.loads(fallback_json)
                data["role"] = role

            plan = RetrievalQueryPlan.model_validate(data)
            return plan.queries

        except Exception as e:
            logger.warning(f"Error validating query plan ({e}), generating heuristic plan covering all projects...")
            fallback_json = self._heuristic_query_builder(user_content)
            fallback_data = json.loads(fallback_json)
            fallback_data["role"] = role
            plan = RetrievalQueryPlan.model_validate(fallback_data)
            return plan.queries

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text


# Module-level convenience functions
def build_retrieval_queries(
    resume: Union[ParsedResume, Dict[str, Any]],
    role: str
) -> List[RetrievalQueryItem]:
    """Convenience function to generate conceptual retrieval queries covering all projects."""
    builder = DynamicQueryBuilder()
    return builder.build_queries(resume=resume, role=role)

build_queries = build_retrieval_queries
