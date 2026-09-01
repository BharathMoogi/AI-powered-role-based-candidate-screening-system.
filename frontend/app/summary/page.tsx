"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Award,
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  FileText,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Printer,
  Sparkles,
  Layers,
  Lightbulb,
} from "lucide-react";
import { getSessionSummary } from "../../lib/api";
import { SessionSummary } from "../../types";


function SummaryContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [expandedQuestionIdx, setExpandedQuestionIdx] = useState<number | null>(null);

  useEffect(() => {
    const urlSessionId = searchParams.get("sessionId");
    const storedSessionId = typeof window !== "undefined" ? localStorage.getItem("current_session_id") : null;
    const resolvedId = urlSessionId || storedSessionId;

    if (!resolvedId) {
      router.push("/");
      return;
    }

    setSessionId(resolvedId);
    fetchSummary(resolvedId);
  }, [searchParams]);

  const fetchSummary = async (id: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await getSessionSummary(id);
      setSummary(data);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load session summary.");
    } finally {
      setIsLoading(false);
    }
  };

  const getRecommendationBadge = (rec: string) => {
    switch (rec.toLowerCase()) {
      case "strong_hire":
        return {
          label: "STRONG HIRE",
          bg: "bg-emerald-950/80 text-emerald-300 border-emerald-700",
          desc: "Exhibits exceptional technical depth and applied system reasoning.",
        };
      case "hire":
        return {
          label: "RECOMMENDED HIRE",
          bg: "bg-teal-950/80 text-teal-300 border-teal-700",
          desc: "Demonstrates solid technical foundations and practical execution ability.",
        };
      case "lean_hire":
        return {
          label: "LEAN HIRE",
          bg: "bg-amber-950/80 text-amber-300 border-amber-700",
          desc: "Adequate core capabilities with growth areas requiring targeted mentorship.",
        };
      case "lean_no_hire":
        return {
          label: "LEAN NO HIRE",
          bg: "bg-orange-950/80 text-orange-300 border-orange-700",
          desc: "Notable gaps in foundational concepts under scenario probing.",
        };
      default:
        return {
          label: "NOT RECOMMENDED",
          bg: "bg-rose-950/80 text-rose-300 border-rose-700",
          desc: "Did not meet the technical bar for the target role.",
        };
    }
  };

  const getRatingColor = (rating: string) => {
    switch (rating.toLowerCase()) {
      case "strong":
        return "bg-emerald-950 text-emerald-300 border-emerald-800";
      case "weak":
        return "bg-rose-950 text-rose-300 border-rose-800";
      default:
        return "bg-amber-950 text-amber-300 border-amber-800";
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="w-10 h-10 border-3 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
        <p className="text-sm font-medium text-slate-400">Synthesizing executive candidate summary report...</p>
      </div>
    );
  }

  if (errorMessage || !summary) {
    return (
      <div className="max-w-xl mx-auto text-center space-y-4 p-8 bg-slate-900 border border-slate-800 rounded-2xl">
        <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Summary Report Unavailable</h2>
        <p className="text-sm text-slate-400">{errorMessage || "Unable to locate session record."}</p>
        <Link
          href="/"
          className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 font-semibold text-white text-sm"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Return to Dashboard</span>
        </Link>
      </div>
    );
  }

  const recBadge = getRecommendationBadge(summary.hiring_recommendation);

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-16">
      {/* Top Action Bar */}
      <div className="flex items-center justify-between">
        <div className="text-xs text-slate-400">
          Session ID: <span className="font-mono text-slate-300">{summary.session_id}</span>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => window.print()}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-xs font-semibold text-slate-300 border border-slate-800 transition-colors"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Print Report</span>
          </button>
          <Link
            href="/"
            onClick={() => {
              if (typeof window !== "undefined") {
                localStorage.removeItem("current_session_id");
              }
            }}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white transition-colors shadow-sm"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>New Screening</span>
          </Link>
        </div>
      </div>

      {/* Executive Hero Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-950 border border-indigo-800 text-xs font-semibold text-indigo-400 mb-2">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Executive Candidate Screening Evaluation</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white">{summary.role}</h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Screened against domain knowledge base • {summary.total_questions} Adaptive Scenario Questions
            </p>
          </div>

          {/* Score & Recommendation Badges */}
          <div className="flex items-center space-x-4">
            <div className="text-center bg-slate-950/80 px-5 py-3 rounded-2xl border border-slate-800">
              <div className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-violet-400">
                {summary.approximate_score_out_of_10.toFixed(1)}
              </div>
              <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Score / 10</div>
            </div>

            <div className={`px-4 py-3 rounded-2xl border ${recBadge.bg} flex flex-col justify-center`}>
              <span className="text-xs font-black uppercase tracking-wider">{recBadge.label}</span>
              <span className="text-[11px] opacity-80 mt-0.5 max-w-[200px] leading-tight">{recBadge.desc}</span>
            </div>
          </div>
        </div>

        {/* Narrative Prose Assessment */}
        <div className="bg-slate-950/80 p-5 sm:p-6 rounded-2xl border border-slate-800/90 space-y-2">
          <div className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center space-x-1.5">
            <FileText className="w-3.5 h-3.5" />
            <span>Overall Assessment Narrative</span>
          </div>
          <p className="text-sm sm:text-base text-slate-200 leading-relaxed font-sans font-normal">
            {summary.overall_assessment}
          </p>
        </div>

        {/* Score Justification */}
        {summary.score_justification && (
          <p className="text-xs text-slate-400 italic px-2">
            <strong>Score Justification: </strong>
            {summary.score_justification}
          </p>
        )}
      </div>

      {/* Per-Topic Breakdown Cards */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-white flex items-center space-x-2">
          <Layers className="w-5 h-5 text-indigo-400" />
          <span>Competency Topic Breakdown</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {summary.topic_breakdown.map((t, idx) => (
            <div
              key={idx}
              className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3.5 shadow-md flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h3 className="text-sm font-bold text-slate-100">{t.topic}</h3>
                  <span className={`text-[10px] uppercase font-black px-2 py-0.5 rounded-md border ${getRatingColor(t.rating)}`}>
                    {t.rating}
                  </span>
                </div>

                {/* Score Bar */}
                <div className="flex items-center space-x-3 mb-3">
                  <div className="flex-1 bg-slate-950 rounded-full h-2 border border-slate-800 overflow-hidden">
                    <div
                      className="bg-indigo-500 h-full rounded-full"
                      style={{ width: `${Math.min(100, Math.round(t.score_out_of_10 * 10))}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono font-bold text-indigo-400">
                    {t.score_out_of_10.toFixed(1)}/10
                  </span>
                </div>

                {/* Strengths & Weaknesses */}
                <div className="space-y-2 text-xs">
                  {t.strengths.length > 0 && (
                    <div>
                      <span className="font-semibold text-emerald-400">Key Strengths:</span>
                      <ul className="list-disc list-inside text-slate-300 mt-1 space-y-0.5">
                        {t.strengths.map((s, sIdx) => (
                          <li key={sIdx}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {t.weaknesses.length > 0 && (
                    <div className="pt-1">
                      <span className="font-semibold text-rose-400">Observed Gaps:</span>
                      <ul className="list-disc list-inside text-slate-400 mt-1 space-y-0.5">
                        {t.weaknesses.map((w, wIdx) => (
                          <li key={wIdx}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Concrete Technical Improvement Suggestions */}
      {summary.concrete_improvements.length > 0 && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-3 shadow-md">
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <Lightbulb className="w-5 h-5 text-amber-400" />
            <span>Targeted Technical Growth Recommendations</span>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-1">
            {summary.concrete_improvements.map((imp, idx) => (
              <div
                key={idx}
                className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 text-xs text-slate-300 leading-relaxed flex items-start space-x-2.5"
              >
                <span className="w-5 h-5 rounded-full bg-amber-950/60 text-amber-400 border border-amber-800/80 flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5">
                  {idx + 1}
                </span>
                <span>{imp}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Question Transcript Accordion */}
      <div className="space-y-3">
        <h2 className="text-base font-bold text-white flex items-center space-x-2">
          <FileText className="w-5 h-5 text-indigo-400" />
          <span>Full Screening Transcript ({summary.questions.length} Questions)</span>
        </h2>

        <div className="space-y-2.5">
          {summary.questions.map((q, idx) => (
            <div
              key={idx}
              className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-sm"
            >
              <button
                onClick={() => setExpandedQuestionIdx(expandedQuestionIdx === idx ? null : idx)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-850 transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <span className="text-xs font-bold text-indigo-400">Q#{q.order_index + 1}</span>
                  <span className="text-sm font-semibold text-slate-200">{q.topic}</span>
                </div>
                <div className="flex items-center space-x-3">
                  <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded border ${getRatingColor(q.rating)}`}>
                    {q.rating} ({q.score}/100)
                  </span>
                  {expandedQuestionIdx === idx ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </div>
              </button>

              {expandedQuestionIdx === idx && (
                <div className="p-4 bg-slate-950/70 border-t border-slate-800 space-y-3 text-xs">
                  <div>
                    <span className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Question:</span>
                    <p className="text-slate-200 mt-1 font-medium">{q.question_text}</p>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Candidate Answer:</span>
                    <p className="text-slate-300 mt-1 font-mono bg-slate-900 p-3 rounded-lg border border-slate-800 leading-relaxed">
                      {q.answer_text}
                    </p>
                  </div>
                  <div>
                    <span className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Evaluation Diagnostic:</span>
                    <p className="text-slate-400 mt-1 italic">"{q.rationale}"</p>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function SummaryPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        </div>
      }
    >
      <SummaryContent />
    </Suspense>
  );
}
