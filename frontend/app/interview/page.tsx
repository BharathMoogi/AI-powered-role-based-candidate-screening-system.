"use client";

import React, { useState, useEffect, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  MessageSquare,
  Send,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Clock,
  BookOpen,
  ArrowRight,
  TrendingUp,
  Award,
  RefreshCw,
} from "lucide-react";
import {
  getCurrentQuestion,
  submitCandidateAnswer,
  completeScreeningSession,
} from "@/lib/api";
import { Question, AnswerEvaluation } from "@/types";

interface TranscriptItem {
  question: Question;
  answerText: string;
  evaluation?: AnswerEvaluation;
}

function InterviewContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [answerInput, setAnswerInput] = useState<string>("");
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [isFinished, setIsFinished] = useState<boolean>(false);
  const [totalAnswered, setTotalAnswered] = useState<number>(0);

  // Loading & Error States
  const [isLoadingSession, setIsLoadingSession] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isCompleting, setIsCompleting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Initialize Session ID from URL or LocalStorage
  useEffect(() => {
    const urlSessionId = searchParams.get("sessionId");
    const storedSessionId = typeof window !== "undefined" ? localStorage.getItem("current_session_id") : null;
    const resolvedId = urlSessionId || storedSessionId;

    if (!resolvedId) {
      router.push("/");
      return;
    }

    setSessionId(resolvedId);
    if (!urlSessionId) {
      router.replace(`/interview?sessionId=${resolvedId}`);
    }

    fetchActiveQuestion(resolvedId);
  }, [searchParams]);

  // Scroll to latest question
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript, currentQuestion, isSubmitting]);

  const fetchActiveQuestion = async (id: string) => {
    setIsLoadingSession(true);
    setErrorMessage(null);
    try {
      const data = await getCurrentQuestion(id);
      setCurrentQuestion(data.question);
      setIsFinished(data.is_finished);
      setTotalAnswered(data.total_answered);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load current interview state.");
    } finally {
      setIsLoadingSession(false);
    }
  };

  // Submit Answer
  const handleSubmitAnswer = async () => {
    if (!sessionId || !currentQuestion) return;
    if (answerInput.trim().length < 5) {
      setErrorMessage("Please type a detailed answer before submitting.");
      return;
    }

    const questionToAnswer = currentQuestion;
    const submittedText = answerInput.trim();

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await submitCandidateAnswer(sessionId, submittedText);

      // Append to transcript
      setTranscript((prev) => [
        ...prev,
        {
          question: questionToAnswer,
          answerText: submittedText,
          evaluation: response.evaluation,
        },
      ]);

      // Clear input
      setAnswerInput("");

      // Update next question state
      if (response.next_question) {
        setCurrentQuestion(response.next_question);
        setTotalAnswered((prev) => prev + 1);
      } else {
        setCurrentQuestion(null);
        setIsFinished(true);
        setTotalAnswered((prev) => prev + 1);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to evaluate answer. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Ctrl+Enter / Cmd+Enter
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !isSubmitting) {
      e.preventDefault();
      handleSubmitAnswer();
    }
  };

  // Complete Session & Navigate to Summary
  const handleCompleteSession = async () => {
    if (!sessionId) return;
    setIsCompleting(true);
    setErrorMessage(null);
    try {
      await completeScreeningSession(sessionId);
      router.push(`/summary?sessionId=${sessionId}`);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to finalize session.");
      setIsCompleting(false);
    }
  };

  const getDifficultyBadgeColor = (difficulty: string) => {
    switch (difficulty.toLowerCase()) {
      case "hard":
        return "bg-rose-950/80 text-rose-300 border-rose-800/80";
      case "easy":
        return "bg-emerald-950/80 text-emerald-300 border-emerald-800/80";
      default:
        return "bg-amber-950/80 text-amber-300 border-amber-800/80";
    }
  };

  const getRatingBadgeColor = (rating: string) => {
    switch (rating.toLowerCase()) {
      case "strong":
        return "bg-emerald-950 text-emerald-400 border-emerald-800";
      case "weak":
        return "bg-rose-950 text-rose-400 border-rose-800";
      default:
        return "bg-amber-950 text-amber-400 border-amber-800";
    }
  };

  if (isLoadingSession) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="w-10 h-10 border-3 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
        <p className="text-sm font-medium text-slate-400">Loading interview session state...</p>
      </div>
    );
  }

  const currentOrder = currentQuestion ? currentQuestion.order_index + 1 : totalAnswered;
  const progressPercent = Math.min(100, Math.round((totalAnswered / 5) * 100));

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-12">
      {/* Session Progress Header */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Live Screening Assessment
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Question <span className="text-white font-semibold">{currentOrder}</span> of{" "}
            <span className="text-white font-semibold">5</span> (Adaptive Difficulty)
          </p>
        </div>

        {/* Progress Meter */}
        <div className="flex items-center space-x-3 sm:w-64">
          <div className="flex-1 bg-slate-950 rounded-full h-2.5 border border-slate-800 overflow-hidden">
            <div
              className="bg-gradient-to-r from-indigo-500 to-violet-500 h-full rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="text-xs font-mono font-bold text-indigo-400">{progressPercent}%</span>
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="flex items-start space-x-3 p-4 rounded-xl bg-red-950/50 border border-red-800 text-red-300 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold">Error: </span>
            {errorMessage}
          </div>
        </div>
      )}

      {/* Transcript History */}
      <div className="space-y-6">
        {transcript.map((item, idx) => (
          <div key={idx} className="space-y-3">
            {/* Question Card */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 shadow-md">
              <div className="flex items-center justify-between gap-2 mb-2.5">
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center space-x-1.5">
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>Question #{item.question.order_index + 1} • {item.question.topic}</span>
                </span>
                <span className={`text-[10px] uppercase font-extrabold px-2.5 py-0.5 rounded-full border ${getDifficultyBadgeColor(item.question.difficulty)}`}>
                  {item.question.difficulty}
                </span>
              </div>
              <p className="text-slate-200 text-sm sm:text-base leading-relaxed">
                {item.question.question_text}
              </p>
            </div>

            {/* Candidate Answer & Evaluation Box */}
            <div className="ml-4 sm:ml-8 bg-indigo-950/20 border border-indigo-900/40 rounded-2xl p-5 space-y-3">
              <div className="text-xs font-semibold text-slate-400 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-400" />
                <span>Your Submitted Answer:</span>
              </div>
              <p className="text-sm text-slate-200 leading-relaxed font-mono bg-slate-950/70 p-3.5 rounded-xl border border-slate-800/60">
                {item.answerText}
              </p>

              {/* Evaluation Card */}
              {item.evaluation && (
                <div className="pt-2 border-t border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className={`text-[11px] uppercase font-black px-2.5 py-0.5 rounded-md border ${getRatingBadgeColor(item.evaluation.rating)}`}>
                        {item.evaluation.rating}
                      </span>
                      <span className="text-xs font-bold text-slate-300">
                        Score: <span className="text-white">{item.evaluation.score}/100</span>
                      </span>
                    </div>
                    <span className="text-[11px] text-slate-400 flex items-center space-x-1">
                      <TrendingUp className="w-3 h-3 text-indigo-400" />
                      <span>Next Difficulty Adapted: <strong className="text-indigo-300 uppercase">{item.evaluation.next_difficulty}</strong></span>
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed italic">
                    "{item.evaluation.rationale}"
                  </p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Active Question Box */}
      {currentQuestion && !isFinished && (
        <div className="bg-gradient-to-b from-slate-900 to-slate-950 border-2 border-indigo-500/40 rounded-2xl p-6 sm:p-7 shadow-2xl space-y-5">
          {/* Header */}
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-black uppercase tracking-wider text-indigo-400 flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span>Active Scenario Probing • {currentQuestion.topic}</span>
            </span>
            <span className={`text-[11px] uppercase font-black px-3 py-1 rounded-full border shadow-sm ${getDifficultyBadgeColor(currentQuestion.difficulty)}`}>
              {currentQuestion.difficulty} DIFFICULTY
            </span>
          </div>

          {/* Question Text */}
          <div className="p-4 sm:p-5 rounded-xl bg-slate-950/90 border border-slate-800">
            <p className="text-base sm:text-lg font-medium text-slate-100 leading-relaxed">
              "{currentQuestion.question_text}"
            </p>
          </div>

          {/* Answer Textarea */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
              <span>Your Technical Response & Architectural Reasoning:</span>
              <span className="text-slate-500 text-[11px]">
                {answerInput.length} chars • Ctrl+Enter to submit
              </span>
            </label>
            <textarea
              ref={textareaRef}
              rows={6}
              disabled={isSubmitting}
              placeholder="Structure your answer addressing theoretical root causes, trade-off considerations, and applied engineering mitigations..."
              value={answerInput}
              onChange={(e) => setAnswerInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-4 py-3.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:outline-none text-sm text-slate-200 placeholder-slate-600 transition-colors font-mono leading-relaxed resize-y"
            />
          </div>

          {/* Submit Button */}
          <button
            type="button"
            disabled={isSubmitting || answerInput.trim().length < 5}
            onClick={handleSubmitAnswer}
            className="w-full py-3.5 px-6 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 font-bold text-white shadow-lg shadow-indigo-600/30 flex items-center justify-center space-x-2 transition-all text-sm"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Evaluating Response & Adapting Next Difficulty...</span>
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                <span>Submit Technical Answer</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Completion Banner */}
      {isFinished && (
        <div className="bg-gradient-to-r from-emerald-950/60 via-slate-900 to-indigo-950/60 border border-emerald-800/80 rounded-2xl p-8 text-center space-y-4 shadow-2xl">
          <div className="w-12 h-12 rounded-full bg-emerald-900/50 border border-emerald-600 flex items-center justify-center mx-auto text-emerald-400">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold text-white">All Screening Questions Completed</h2>
          <p className="text-sm text-slate-300 max-w-lg mx-auto">
            You have answered all scenario questions. Synthesize the final candidate evaluation report with overall scoring, topic breakdowns, and hiring recommendations.
          </p>
          <button
            type="button"
            disabled={isCompleting}
            onClick={handleCompleteSession}
            className="py-3.5 px-8 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 font-bold text-white shadow-lg shadow-emerald-600/25 flex items-center justify-center space-x-2 mx-auto text-sm transition-all"
          >
            {isCompleting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Synthesizing Executive Evaluation Report...</span>
              </>
            ) : (
              <>
                <span>View Full Executive Summary</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}

export default function InterviewPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      }
    >
      <InterviewContent />
    </Suspense>
  );
}
