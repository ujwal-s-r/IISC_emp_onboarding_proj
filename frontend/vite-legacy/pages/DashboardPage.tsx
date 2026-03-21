import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Target,
  Clock,
  TrendingDown,
  Cpu,
  ArrowLeft,
  Download,
  BookOpen,
  Brain,
  BarChart3,
  Lightbulb,
  User,
  Briefcase,
} from 'lucide-react';
import type { AnalysisResult } from '../types';
import MetricCard from '../components/MetricCard';
import SkillMatchGauge from '../components/SkillMatchGauge';
import SkillRadarChart from '../components/SkillRadarChart';
import SkillGapList from '../components/SkillGapList';
import LearningRoadmap from '../components/LearningRoadmap';
import ReasoningTrace from '../components/ReasoningTrace';
import ResourceCard from '../components/ResourceCard';
import { formatPercent } from '../lib/utils';

interface DashboardPageProps {
  result: AnalysisResult | null;
}

function SectionHeader({ icon: Icon, title, subtitle }: {
  icon: React.ElementType;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="flex items-start gap-3 mb-6">
      <div className="w-9 h-9 rounded-xl bg-brand-500/10 flex items-center justify-center shrink-0">
        <Icon className="w-4.5 h-4.5 text-brand-400" />
      </div>
      <div>
        <h2 className="text-lg font-bold text-white">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

export default function DashboardPage({ result }: DashboardPageProps) {
  const navigate = useNavigate();

  if (!result) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="text-center space-y-4">
          <p className="text-slate-400">No analysis results found.</p>
          <button onClick={() => navigate('/')} className="btn-primary">
            <ArrowLeft className="w-4 h-4" />
            Start New Analysis
          </button>
        </div>
      </div>
    );
  }

  const { metrics } = result;

  return (
    <div className="min-h-screen pb-24">
      {/* Background */}
      <div className="fixed inset-0 bg-hero-glow pointer-events-none opacity-50" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-24">

        {/* Page header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start justify-between gap-4 mb-8 flex-wrap"
        >
          <div>
            <button
              onClick={() => navigate('/')}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 mb-3 transition-colors duration-200"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              New Analysis
            </button>
            <div className="flex items-center gap-3 flex-wrap">
              {result.candidateName && (
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand-500 to-violet-600 flex items-center justify-center text-xs font-bold text-white">
                    {result.candidateName.charAt(0)}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-white">{result.candidateName}</span>
                    <User className="w-3 h-3 text-slate-500" />
                  </div>
                </div>
              )}
              <div className="flex items-center gap-1.5 text-sm text-slate-400">
                <Briefcase className="w-3.5 h-3.5 text-violet-400" />
                <span>{result.targetRole}</span>
              </div>
            </div>
            <h1 className="text-2xl font-black text-white mt-2">
              Skill Gap Analysis & Learning Roadmap
            </h1>
          </div>

          <button className="btn-secondary">
            <Download className="w-4 h-4" />
            Export PDF
          </button>
        </motion.div>

        {/* Metrics row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <MetricCard
            label="Skill Match"
            value={result.skillMatchScore}
            suffix="%"
            icon={Target}
            iconColor="text-brand-400"
            iconBg="bg-brand-400/10"
            trend={{ value: `${result.matchedSkills.length} of ${result.requiredSkills.length} required`, positive: result.skillMatchScore >= 60 }}
            delay={0.05}
          />
          <MetricCard
            label="Career Readiness"
            value={result.careerReadinessScore}
            suffix="%"
            icon={Cpu}
            iconColor="text-violet-400"
            iconBg="bg-violet-400/10"
            description="Overall role fit score"
            delay={0.1}
          />
          <MetricCard
            label="Training Reduction"
            value={metrics.trainingReductionPercent}
            suffix="%"
            icon={TrendingDown}
            iconColor="text-emerald-400"
            iconBg="bg-emerald-400/10"
            trend={{ value: 'vs. full training program', positive: true }}
            delay={0.15}
          />
          <MetricCard
            label="Estimated Timeline"
            value={metrics.estimatedLearningWeeks}
            suffix=" wks"
            icon={Clock}
            iconColor="text-accent-400"
            iconBg="bg-accent-400/10"
            description={metrics.pathCompletionEstimate}
            delay={0.2}
          />
        </div>

        {/* Main content: Gauge + Radar + Gap list */}
        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          {/* Left: Score gauge */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.25 }}
            className="glass-card p-6 flex flex-col items-center gap-6"
          >
            <div className="section-title w-full">
              <Target className="w-4 h-4 text-brand-400" />
              <span>Match Score</span>
            </div>

            <SkillMatchGauge score={result.skillMatchScore} size="md" />

            {/* Score breakdown */}
            <div className="w-full space-y-2.5">
              {[
                { label: 'Matched Skills', value: result.matchedSkills.length, total: result.requiredSkills.length, color: 'bg-emerald-500' },
                { label: 'Missing Skills', value: result.missingSkills.length, total: result.requiredSkills.length + result.missingSkills.length, color: 'bg-red-500' },
                { label: 'AI Accuracy', value: metrics.skillExtractionAccuracy, total: 100, color: 'bg-brand-500' },
              ].map(({ label, value, total, color }) => (
                <div key={label}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">{label}</span>
                    <span className="text-white font-semibold">{typeof value === 'number' && value > 10 ? formatPercent(value, 1) : value}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-500 overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${color}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${(Number(value) / total) * 100}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut', delay: 0.5 }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Center: Radar chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="glass-card p-6 lg:col-span-1"
          >
            <div className="section-title mb-4">
              <BarChart3 className="w-4 h-4 text-violet-400" />
              <span>Skill Profile Radar</span>
            </div>
            <div className="h-[300px]">
              <SkillRadarChart data={result.radarData} />
            </div>
          </motion.div>

          {/* Right: Skill gap list (scrollable) */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.35 }}
            className="glass-card p-6 max-h-[480px] overflow-y-auto"
          >
            <SkillGapList
              missing={result.missingSkills}
              matched={result.matchedSkills}
            />
          </motion.div>
        </div>

        {/* Learning Roadmap */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="mb-8"
        >
          <SectionHeader
            icon={BookOpen}
            title="Adaptive Learning Roadmap"
            subtitle={`Personalized 4-phase plan • ${metrics.pathCompletionEstimate} • ${result.missingSkills.length} skills to acquire`}
          />
          <LearningRoadmap phases={result.learningRoadmap} />
        </motion.section>

        {/* AI Reasoning Trace */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.45 }}
          className="mb-8"
        >
          <SectionHeader
            icon={Brain}
            title="AI Reasoning Trace"
            subtitle="Why each skill was flagged · confidence scores · data sources"
          />
          <div className="glass-card p-6">
            <ReasoningTrace items={result.reasoningTrace} />
          </div>
        </motion.section>

        {/* Top Resources */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <SectionHeader
            icon={Lightbulb}
            title="Top Learning Resources"
            subtitle="Curated courses and documentation for your highest-priority gaps"
          />
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {result.topResources.map((resource, i) => (
              <ResourceCard key={resource.title} resource={resource} index={i} />
            ))}
          </div>
        </motion.section>

        {/* Footer metrics */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="mt-12 p-5 glass-card flex items-center justify-between flex-wrap gap-4"
        >
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-brand-400" />
            <span className="text-xs font-semibold text-brand-400">SkillBridge AI</span>
          </div>
          <div className="flex items-center gap-6 text-xs text-slate-500 flex-wrap">
            <span>Session: <span className="text-slate-400 font-mono">{result.sessionId}</span></span>
            <span>Extraction accuracy: <span className="text-emerald-400 font-semibold">{formatPercent(metrics.skillExtractionAccuracy, 1)}</span></span>
            <span>Gap precision: <span className="text-emerald-400 font-semibold">{formatPercent(metrics.gapDetectionPrecision, 1)}</span></span>
            <span>Model: <span className="text-slate-400 font-mono">BAAI/bge-small-en-v1.5</span></span>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
