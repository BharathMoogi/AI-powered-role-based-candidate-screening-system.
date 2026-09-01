"use client";

import React, { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Sparkles,
  Briefcase,
  Layers,
  Code2,
  Cpu,
} from "lucide-react";
import { uploadCandidateResume, startScreeningSession } from "@/lib/api";
import { CandidateProfile } from "@/types";

const POPULAR_ROLES = [
  "Machine Learning Engineer",
  "Senior Backend Engineer",
  "Distributed Systems Engineer",
  "Full Stack Engineer",
  "Cloud & DevOps Architect",
  "Data Scientist",
];

export default function LandingPage() {
  const router = useRouter();

  // Form State
  const [selectedRole, setSelectedRole] = useState<string>(POPULAR_ROLES[0]);
  const [customRole, setCustomRole] = useState<string>("");
  const [inputMode, setInputMode] = useState<"file" | "text">("file");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [resumeText, setResumeText] = useState<string>("");

  // Workflow State
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isStartingSession, setIsStartingSession] = useState<boolean>(false);
  const [candidateProfile, setCandidateProfile] = useState<CandidateProfile | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const activeRole = customRole.trim() ? customRole.trim() : selectedRole;

  // Handle Drag & Drop
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
      setCandidateProfile(null);
      setErrorMessage(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setCandidateProfile(null);
      setErrorMessage(null);
    }
  };

  // Upload & Extract Candidate Resume
  const handleParseResume = async () => {
    setErrorMessage(null);
    if (inputMode === "file" && !selectedFile) {
      setErrorMessage("Please select or drop a PDF/text resume file.");
      return;
    }
    if (inputMode === "text" && resumeText.trim().length < 40) {
      setErrorMessage("Please paste a resume text with at least 40 characters.");
      return;
    }

    setIsUploading(true);
    try {
      const source = inputMode === "file" ? selectedFile! : resumeText;
      const profile = await uploadCandidateResume(activeRole, source);
      setCandidateProfile(profile);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to analyze resume. Please verify backend is active.");
    } finally {
      setIsUploading(false);
    }
  };

  // Launch Screening Interview Session
  const handleStartInterview = async () => {
    if (!candidateProfile) return;

    setIsStartingSession(true);
    setErrorMessage(null);
    try {
      const sessionData = await startScreeningSession(candidateProfile.id, activeRole);
      // Persist in localStorage
      localStorage.setItem("current_session_id", sessionData.session_id);
      localStorage.setItem("candidate_role", activeRole);
      router.push(`/interview?sessionId=${sessionData.session_id}`);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to start interview session.");
      setIsStartingSession(false);
    }
  };

  return (
    <div className="space-y-10 max-w-4xl mx-auto">
      {/* Hero Banner */}
      <div className="text-center space-y-3 pt-4">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-950/80 border border-indigo-800/60 text-xs font-semibold text-indigo-400">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>AI-Powered RAG Screening Pipeline</span>
        </div>
        <h1 className="text-4xl sm:text-5xl font-black tracking-tight text-white">
          Role-Grounded Candidate Evaluation
        </h1>
        <p className="text-base sm:text-lg text-slate-400 max-w-2xl mx-auto">
          Upload a resume to automatically extract candidate competencies, synthesize conceptual retrieval queries, and begin an adaptive technical screening session.
        </p>
      </div>

      {/* Main Configuration Card */}
      <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-sm space-y-8">
        {/* Error Alert */}
        {errorMessage && (
          <div className="flex items-start space-x-3 p-4 rounded-xl bg-red-950/50 border border-red-800/80 text-red-300 text-sm">
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-red-400 mt-0.5" />
            <div className="flex-1">
              <span className="font-semibold">Error: </span>
              {errorMessage}
            </div>
          </div>
        )}

        {/* Step 1: Role Selection */}
        <div className="space-y-3">
          <label className="flex items-center space-x-2 text-sm font-semibold text-slate-200">
            <Briefcase className="w-4 h-4 text-indigo-400" />
            <span>1. Select Target Job Role</span>
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {POPULAR_ROLES.map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => {
                  setSelectedRole(role);
                  setCustomRole("");
                  setCandidateProfile(null);
                }}
                className={`flex items-center justify-between p-3.5 rounded-xl border text-sm font-medium transition-all text-left ${
                  selectedRole === role && !customRole
                    ? "bg-indigo-600/15 border-indigo-500 text-indigo-200 shadow-md shadow-indigo-500/10"
                    : "bg-slate-950/60 border-slate-800 hover:border-slate-700 text-slate-300"
                }`}
              >
                <span>{role}</span>
                {selectedRole === role && !customRole && (
                  <CheckCircle2 className="w-4 h-4 text-indigo-400" />
                )}
              </button>
            ))}
          </div>

          <div className="pt-1">
            <input
              type="text"
              placeholder="Or type a custom role title (e.g. Lead SRE / Platform Engineer)..."
              value={customRole}
              onChange={(e) => {
                setCustomRole(e.target.value);
                setCandidateProfile(null);
              }}
              className="w-full px-4 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 focus:border-indigo-500 focus:outline-none text-sm text-slate-200 placeholder-slate-500 transition-colors"
            />
          </div>
        </div>

        {/* Step 2: Resume Input (File vs Text Tabs) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <label className="flex items-center space-x-2 text-sm font-semibold text-slate-200">
              <FileText className="w-4 h-4 text-indigo-400" />
              <span>2. Upload Candidate Resume</span>
            </label>
            <div className="flex items-center rounded-lg bg-slate-950 p-1 border border-slate-800">
              <button
                type="button"
                onClick={() => setInputMode("file")}
                className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                  inputMode === "file"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                PDF / File
              </button>
              <button
                type="button"
                onClick={() => setInputMode("text")}
                className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                  inputMode === "text"
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Paste Text
              </button>
            </div>
          </div>

          {inputMode === "file" ? (
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
                dragActive
                  ? "border-indigo-500 bg-indigo-950/20"
                  : selectedFile
                  ? "border-emerald-600/80 bg-emerald-950/10"
                  : "border-slate-800 hover:border-slate-700 bg-slate-950/40 hover:bg-slate-950/60"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt"
                onChange={handleFileChange}
                className="hidden"
              />
              <div className="flex flex-col items-center justify-center space-y-3">
                {selectedFile ? (
                  <>
                    <div className="w-12 h-12 rounded-xl bg-emerald-900/40 border border-emerald-700 flex items-center justify-center text-emerald-400">
                      <FileText className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-emerald-300">{selectedFile.name}</p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {(selectedFile.size / 1024).toFixed(1)} KB • Ready to extract
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="w-12 h-12 rounded-xl bg-slate-800/80 flex items-center justify-center text-indigo-400">
                      <UploadCloud className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-200">
                        Drag and drop candidate resume PDF here
                      </p>
                      <p className="text-xs text-slate-500 mt-1">or click to browse local files (.pdf, .txt)</p>
                    </div>
                  </>
                )}
              </div>
            </div>
          ) : (
            <textarea
              rows={6}
              placeholder="Paste candidate resume text, bio, or technical project highlights here..."
              value={resumeText}
              onChange={(e) => {
                setResumeText(e.target.value);
                setCandidateProfile(null);
              }}
              className="w-full px-4 py-3 rounded-xl bg-slate-950/80 border border-slate-800 focus:border-indigo-500 focus:outline-none text-sm text-slate-200 placeholder-slate-600 transition-colors font-mono leading-relaxed"
            />
          )}
        </div>

        {/* Action Button: Parse Resume */}
        {!candidateProfile && (
          <button
            type="button"
            disabled={isUploading}
            onClick={handleParseResume}
            className="w-full py-3.5 px-6 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 font-semibold text-white shadow-lg shadow-indigo-600/25 flex items-center justify-center space-x-2 transition-all"
          >
            {isUploading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Analyzing Resume with LLM...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Extract Candidate Profile</span>
              </>
            )}
          </button>
        )}

        {/* Step 3: Extracted Profile Review & Launch Session */}
        {candidateProfile && (
          <div className="space-y-6 pt-4 border-t border-slate-800">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span>Profile Extracted Successfully</span>
              </h3>
              <span className="text-xs uppercase tracking-wider font-extrabold px-3 py-1 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800">
                {candidateProfile.extracted_data.apparent_experience_level.toUpperCase()} LEVEL
              </span>
            </div>

            {candidateProfile.resume_summary && (
              <p className="text-sm text-slate-300 bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 leading-relaxed">
                {candidateProfile.resume_summary}
              </p>
            )}

            {/* Skills & Technologies Badges */}
            <div className="space-y-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5 mb-2">
                  <Code2 className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Key Technologies:</span>
                </span>
                <div className="flex flex-wrap gap-2">
                  {candidateProfile.extracted_data.technologies.map((t, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-950 text-slate-200 border border-slate-800"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5 mb-2">
                  <Layers className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Technical Competencies:</span>
                </span>
                <div className="flex flex-wrap gap-2">
                  {candidateProfile.extracted_data.skills.map((s, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded-lg text-xs font-medium bg-emerald-950/40 text-emerald-300 border border-emerald-900/60"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Start Screening Button */}
            <button
              type="button"
              disabled={isStartingSession}
              onClick={handleStartInterview}
              className="w-full py-4 px-6 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 font-bold text-white shadow-xl shadow-indigo-600/30 flex items-center justify-center space-x-2 text-base transition-all"
            >
              {isStartingSession ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Grounding ChromaDB Knowledge Base & Generating Q1...</span>
                </>
              ) : (
                <>
                  <span>Launch Screening Interview</span>
                  <ArrowRight className="w-5 h-5" />
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
