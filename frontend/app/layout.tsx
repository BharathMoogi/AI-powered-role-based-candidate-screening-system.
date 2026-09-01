import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Candidate Screening Platform",
  description: "Role-grounded candidate evaluation powered by RAG and dynamic rubric assessment.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 min-h-screen antialiased selection:bg-indigo-500 selection:text-white">
        {/* Navigation Bar */}
        <header className="border-b border-slate-800/80 bg-slate-900/70 backdrop-blur-md sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center space-x-3 group">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center font-black text-white text-sm shadow-md shadow-indigo-500/20 group-hover:scale-105 transition-transform">
                AI
              </div>
              <div>
                <span className="font-bold text-base tracking-tight text-white group-hover:text-indigo-300 transition-colors">
                  RoleScreener
                </span>
                <span className="ml-2 text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-400 border border-indigo-800/60">
                  RAG Core
                </span>
              </div>
            </Link>

            <nav className="flex items-center space-x-6 text-sm font-medium text-slate-400">
              <Link href="/" className="hover:text-white transition-colors">
                New Screening
              </Link>
              <Link href="/interview" className="hover:text-white transition-colors">
                Active Session
              </Link>
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noreferrer"
                className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700/80 transition-colors"
              >
                API Docs ↗
              </a>
            </nav>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
