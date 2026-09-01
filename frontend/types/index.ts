export interface ExtractedSkillsData {
  candidate_name?: string | null;
  summary?: string | null;
  skills: string[];
  technologies: string[];
  domains: string[];
  apparent_experience_level: "junior" | "mid" | "senior";
  notable_projects?: Array<{
    name: string;
    description: string;
    technologies: string[];
    highlights?: string | null;
  }>;
}

export interface CandidateProfile {
  id: string;
  target_role: string;
  resume_summary?: string | null;
  extracted_data: ExtractedSkillsData;
  created_at: string;
}

export interface Question {
  id: string;
  session_id: string;
  question_text: string;
  topic: string;
  difficulty: "easy" | "medium" | "hard";
  order_index: number;
  source_chunk_ids?: string[];
}

export interface SessionStartResponse {
  session_id: string;
  candidate_id: string;
  role: string;
  status: string;
  first_question: Question;
}

export interface CurrentQuestionData {
  session_id: string;
  status: string;
  question: Question | null;
  is_finished: boolean;
  total_answered: number;
}

export interface AnswerEvaluation {
  rating: "weak" | "adequate" | "strong";
  score: number;
  rationale: string;
  strengths: string[];
  improvement_areas: string[];
  next_difficulty: "easy" | "medium" | "hard";
}

export interface AnswerSubmissionResponse {
  answer_id: string;
  question_id: string;
  evaluation: AnswerEvaluation;
  next_question: Question | null;
  session_status: string;
}

export interface TopicAssessment {
  topic: string;
  rating: "weak" | "adequate" | "strong";
  score_out_of_10: number;
  strengths: string[];
  weaknesses: string[];
}

export interface QuestionSummaryItem {
  order_index: number;
  topic: string;
  difficulty: string;
  question_text: string;
  answer_text: string;
  rating: string;
  score: number;
  rationale: string;
}

export interface SessionSummary {
  session_id: string;
  candidate_id: string;
  role: string;
  status: string;
  total_questions: number;
  overall_assessment: string;
  approximate_score_out_of_10: number;
  score_justification: string;
  hiring_recommendation: "strong_hire" | "hire" | "lean_hire" | "lean_no_hire" | "no_hire";
  topic_breakdown: TopicAssessment[];
  concrete_improvements: string[];
  questions: QuestionSummaryItem[];
}
