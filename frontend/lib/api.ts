import {
  CandidateProfile,
  SessionStartResponse,
  CurrentQuestionData,
  AnswerSubmissionResponse,
  SessionSummary,
} from "../types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errorJson = await res.json();
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === "string" 
          ? errorJson.detail 
          : JSON.stringify(errorJson.detail);
      }
    } catch {
      // ignore
    }
    throw new ApiError(errorDetail, res.status);
  }
  return res.json() as Promise<T>;
}

export async function uploadCandidateResume(
  targetRole: string,
  resumeSource: File | string
): Promise<CandidateProfile> {
  if (resumeSource instanceof File) {
    const formData = new FormData();
    formData.append("target_role", targetRole);
    formData.append("file", resumeSource);
    const res = await fetch(`${API_BASE_URL}/candidates`, {
      method: "POST",
      body: formData,
    });
    return handleResponse<CandidateProfile>(res);
  } else {
    const res = await fetch(`${API_BASE_URL}/candidates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_role: targetRole,
        resume_text: resumeSource,
      }),
    });
    return handleResponse<CandidateProfile>(res);
  }
}

export async function startScreeningSession(
  candidateId: string,
  role?: string
): Promise<SessionStartResponse> {
  const res = await fetch(`${API_BASE_URL}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_id: candidateId,
      role: role || undefined,
    }),
  });
  return handleResponse<SessionStartResponse>(res);
}

export async function getCurrentQuestion(sessionId: string): Promise<CurrentQuestionData> {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/current-question`);
  return handleResponse<CurrentQuestionData>(res);
}

export async function submitCandidateAnswer(
  sessionId: string,
  answerText: string
): Promise<AnswerSubmissionResponse> {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer_text: answerText }),
  });
  return handleResponse<AnswerSubmissionResponse>(res);
}

export async function completeScreeningSession(sessionId: string): Promise<SessionSummary> {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return handleResponse<SessionSummary>(res);
}

export async function getSessionSummary(sessionId: string): Promise<SessionSummary> {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/summary`);
  return handleResponse<SessionSummary>(res);
}
