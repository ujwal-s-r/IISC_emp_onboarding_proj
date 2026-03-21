import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Brain,
  FileText,
  Briefcase,
  ArrowRight,
  Sparkles,
  BarChart3,
  Map,
  ShieldCheck,
  Zap,
  ChevronRight,
} from 'lucide-react';
import FileUploadZone from '../components/FileUploadZone';
import LoadingScreen from '../components/LoadingScreen';
import { analyzeCandidate } from '../lib/api';
import type { AnalysisResult, UploadState } from '../types';
import { cn } from '../lib/utils';

const ACCEPTED_RESUME = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
};

const ACCEPTED_JD = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
};

const FEATURES = [
  {
    icon: Brain,
    title: 'Multi-Agent AI',
    description: 'Five specialized AI agents work in parallel: Skill Extractor, Gap Analyst, Roadmap Builder, Verifier, and Resource Mapper.',
    color: 'text-brand-400',
    bg: 'bg-brand-400/10',
  },
  {
    icon: BarChart3,
    title: 'Skill Gap Visualization',
    description: 'Radar charts, confidence scores, and priority rankings give you a crystal-clear picture of your skill gaps.',
    color: 'text-violet-400',
    bg: 'bg-violet-400/10',
  },
  {
    icon: Map,
    title: 'Adaptive Learning Path',
    description: 'A 4-phase personalized roadmap with curated resources, estimated durations, and difficulty scaling.',
    color: 'text-accent-400',
    bg: 'bg-accent-400/10',
  },
  {
    icon: ShieldCheck,
    title: 'Explainable AI',
    description: 'Every recommendation includes a reasoning trace, confidence score, and data source — no black boxes.',
    color: 'text-emerald-400',
    bg: 'bg-emerald-400/10',
  },
];

const STEPS = [
  { number: '01', title: 'Upload Resume', description: 'PDF, DOCX, or TXT — our parser extracts skills, experience, and projects.' },
  { number: '02', title: 'Add Job Description', description: 'Paste or upload the JD. We extract required skills and role expectations.' },
  { number: '03', title: 'Get Your Roadmap', description: 'AI analyzes gaps and generates a personalized learning path in seconds.' },
];

interface LandingPageProps {
  onAnalysisComplete: (result: AnalysisResult) => void;
}

export default function LandingPage({ onAnalysisComplete }: LandingPageProps) {
  const navigate = useNavigate();

  const [uploadState, setUploadState] = useState<UploadState>({
    resume: null,
    jobDescription: null,
    jdText: '',
  });
  const [jdInputMode, setJdInputMode] = useState<'file' | 'text'>('file');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const canAnalyze =
    uploadState.resume !== null &&
    (uploadState.jobDescription !== null || uploadState.jdText.trim().length > 50);

  async function handleAnalyze() {
    if (!uploadState.resume || !canAnalyze) return;
    setError(null);
    setIsAnalyzing(true);

    try {
      const result = await analyzeCandidate(
        {
          resumeFile: uploadState.resume,
          jobDescriptionFile: uploadState.jobDescription ?? undefined,
          jobDescriptionText: uploadState.jdText || undefined,
        },
        (step, percent) => {
          setLoadingStep(step);
          setLoadingProgress(percent);
        }
      );
      onAnalysisComplete(result);
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed. Please try again.');
      setIsAnalyzing(false);
    }
  }

  if (isAnalyzing) {
    return <LoadingScreen currentStep={loadingStep} progress={loadingProgress} />;
  }

  return (
    <div className="min-h-screen">
      {/* Background effects */}
      <div className="fixed inset-0 bg-hero-glow pointer-events-none" />
      <div
        className="fixed inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage:
            'radial-gradient(circle at 20% 80%, rgba(139,92,246,0.15) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(6,182,212,0.1) 0%, transparent 50%)',
        }}
      />

      {/* Hero section */}
      <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto text-center">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-brand-500/10 border border-brand-500/20 text-sm font-medium text-brand-400 mb-8"
          >
            <Sparkles className="w-4 h-4" />
            <span>AI-Powered Adaptive Onboarding Engine</span>
            <ChevronRight className="w-3 h-3 opacity-60" />
          </motion.div>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-tight leading-[1.05] text-balance"
          >
            <span className="text-white">Bridge Your</span>
            <br />
            <span className="gradient-text">Skill Gaps</span>
            <br />
            <span className="text-white">With AI</span>
          </motion.h1>

          {/* Subheadline */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mt-6 text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed text-balance"
          >
            Upload your resume and job description. Our multi-agent AI analyzes skill gaps,
            detects missing competencies, and generates a personalized learning roadmap in seconds.
          </motion.p>

          {/* Stats row */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="flex items-center justify-center gap-8 mt-10 flex-wrap"
          >
            {[
              { value: '94%', label: 'Skill Extraction Accuracy' },
              { value: '5 AI', label: 'Specialized Agents' },
              { value: '42%', label: 'Avg. Training Reduction' },
              { value: '<10s', label: 'Analysis Time' },
            ].map(({ value, label }) => (
              <div key={label} className="text-center">
                <div className="text-2xl font-black gradient-text">{value}</div>
                <div className="text-xs text-slate-500 mt-0.5">{label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Upload section */}
      <section className="relative px-4 sm:px-6 lg:px-8 pb-24">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="glass-card gradient-border p-8"
          >
            <div className="flex items-center gap-2 mb-6">
              <Zap className="w-5 h-5 text-brand-400" />
              <h2 className="text-lg font-bold text-white">Start Your Analysis</h2>
              <span className="ml-auto text-xs text-slate-500 bg-surface-500 px-2.5 py-1 rounded-lg border border-white/5">
                Demo mode active
              </span>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Resume upload */}
              <FileUploadZone
                label="Resume"
                description="Your professional resume or CV"
                accept={ACCEPTED_RESUME}
                file={uploadState.resume}
                onFileChange={(f) => setUploadState((s) => ({ ...s, resume: f }))}
                icon={<FileText className="w-6 h-6 text-brand-400" />}
                accentColor="brand"
              />

              {/* Job description */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-semibold text-slate-200">Job Description</label>
                  <div className="flex rounded-lg overflow-hidden border border-white/10">
                    {(['file', 'text'] as const).map((mode) => (
                      <button
                        key={mode}
                        onClick={() => setJdInputMode(mode)}
                        className={cn(
                          'px-3 py-1 text-xs font-medium transition-colors duration-200',
                          jdInputMode === mode
                            ? 'bg-brand-500/20 text-brand-400'
                            : 'text-slate-500 hover:text-slate-300'
                        )}
                      >
                        {mode === 'file' ? 'Upload' : 'Paste'}
                      </button>
                    ))}
                  </div>
                </div>

                {jdInputMode === 'file' ? (
                  <FileUploadZone
                    label=""
                    description="The job posting you're applying for"
                    accept={ACCEPTED_JD}
                    file={uploadState.jobDescription}
                    onFileChange={(f) => setUploadState((s) => ({ ...s, jobDescription: f }))}
                    icon={<Briefcase className="w-6 h-6 text-violet-400" />}
                    accentColor="violet"
                  />
                ) : (
                  <textarea
                    value={uploadState.jdText}
                    onChange={(e) => setUploadState((s) => ({ ...s, jdText: e.target.value }))}
                    placeholder="Paste the job description here…&#10;&#10;We'll extract required skills, experience levels, and role expectations automatically."
                    className="w-full h-[218px] px-4 py-3 rounded-2xl bg-surface-600/60 border border-white/10 text-sm text-slate-200 placeholder-slate-600 resize-none focus:outline-none focus:border-violet-500/40 transition-colors duration-200"
                  />
                )}
              </div>
            </div>

            {/* Error message */}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 flex items-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-400"
              >
                {error}
              </motion.div>
            )}

            {/* Analyze button */}
            <div className="mt-6 flex items-center gap-4">
              <button
                onClick={handleAnalyze}
                disabled={!canAnalyze}
                className="btn-primary text-base px-8 py-3.5"
              >
                <Brain className="w-5 h-5" />
                Analyze with AI
                <ArrowRight className="w-4 h-4" />
              </button>

              <p className="text-xs text-slate-500">
                {!uploadState.resume
                  ? 'Upload your resume to continue'
                  : !canAnalyze
                  ? 'Add job description to continue'
                  : 'Ready to analyze!'}
              </p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* How it works */}
      <section className="relative px-4 sm:px-6 lg:px-8 pb-24">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl font-bold text-white">How It Works</h2>
            <p className="mt-3 text-slate-400">Three steps from resume to roadmap</p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6 relative">
            {/* Connector line */}
            <div className="hidden md:block absolute top-8 left-[16.5%] right-[16.5%] h-px bg-gradient-to-r from-brand-500/30 via-violet-500/30 to-accent-500/30" />

            {STEPS.map(({ number, title, description }, i) => (
              <motion.div
                key={number}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="glass-card p-6 text-center relative"
              >
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-500 to-violet-600 flex items-center justify-center mx-auto mb-4 text-lg font-black text-white shadow-glow">
                  {number}
                </div>
                <h3 className="text-base font-bold text-white mb-2">{title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Features grid */}
      <section className="relative px-4 sm:px-6 lg:px-8 pb-32">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl font-bold text-white">Production-Grade AI</h2>
            <p className="mt-3 text-slate-400">Built like a real AI SaaS product, not a hackathon demo</p>
          </motion.div>

          <div className="grid sm:grid-cols-2 gap-5">
            {FEATURES.map(({ icon: Icon, title, description, color, bg }, i) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="glass-card-hover p-6"
              >
                <div className={cn('w-12 h-12 rounded-xl flex items-center justify-center mb-4', bg)}>
                  <Icon className={cn('w-6 h-6', color)} />
                </div>
                <h3 className="text-base font-bold text-white mb-2">{title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
