import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown,
  Clock,
  BookOpen,
  ExternalLink,
  Layers,
  Zap,
  Target,
  Trophy,
} from 'lucide-react';
import type { Phase } from '../types';
import { cn, getDifficultyColor } from '../lib/utils';

interface LearningRoadmapProps {
  phases: Phase[];
}

const PHASE_ICONS = [Layers, Zap, Target, Trophy];
const PHASE_GRADIENTS = [
  'from-emerald-500 to-teal-600',
  'from-brand-500 to-violet-600',
  'from-amber-500 to-orange-600',
  'from-rose-500 to-pink-600',
];
const PHASE_GLOW = [
  'shadow-[0_0_20px_rgba(16,185,129,0.3)]',
  'shadow-[0_0_20px_rgba(99,102,241,0.3)]',
  'shadow-[0_0_20px_rgba(245,158,11,0.3)]',
  'shadow-[0_0_20px_rgba(244,63,94,0.3)]',
];

function PhaseCard({ phase, index, isExpanded, onToggle }: {
  phase: Phase;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const Icon = PHASE_ICONS[index % PHASE_ICONS.length];
  const gradient = PHASE_GRADIENTS[index % PHASE_GRADIENTS.length];
  const glow = PHASE_GLOW[index % PHASE_GLOW.length];
  const diffColor = getDifficultyColor(phase.difficulty);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1 }}
    >
      <div
        className={cn(
          'glass-card overflow-hidden transition-all duration-300',
          isExpanded && 'border-white/10'
        )}
      >
        {/* Phase header */}
        <button
          onClick={onToggle}
          className="w-full flex items-start gap-4 p-5 text-left hover:bg-white/2 transition-colors duration-200"
        >
          {/* Phase icon */}
          <div
            className={cn(
              'w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-gradient-to-br',
              gradient,
              isExpanded && glow
            )}
          >
            <Icon className="w-6 h-6 text-white" />
          </div>

          {/* Phase info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Phase {phase.phase}
              </span>
              <span className={cn('text-xs font-semibold capitalize', diffColor)}>
                · {phase.difficulty}
              </span>
            </div>
            <h3 className="text-base font-bold text-white mt-0.5">{phase.title}</h3>
            <p className="text-xs text-slate-400 mt-1 line-clamp-1">{phase.description}</p>

            <div className="flex items-center gap-4 mt-2">
              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <Clock className="w-3 h-3" />
                <span>{phase.duration}</span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <BookOpen className="w-3 h-3" />
                <span>{phase.skills.length} skills</span>
              </div>
            </div>
          </div>

          {/* Expand icon */}
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="shrink-0 mt-1"
          >
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </motion.div>
        </button>

        {/* Skill list (expanded) */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: 'easeInOut' }}
              className="overflow-hidden"
            >
              <div className="px-5 pb-5 space-y-3 border-t border-white/5 pt-4">
                {phase.skills.map((skill, si) => (
                  <motion.div
                    key={skill.name}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: si * 0.05 }}
                    className="bg-surface-600/40 rounded-xl p-4 border border-white/5"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-white">{skill.name}</span>
                          <span className={cn('text-xs font-medium capitalize', getDifficultyColor(skill.difficulty))}>
                            {skill.difficulty}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1 leading-relaxed">{skill.reason}</p>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-slate-500 shrink-0">
                        <Clock className="w-3 h-3" />
                        <span>{skill.duration}</span>
                      </div>
                    </div>

                    {/* Resources */}
                    {skill.resources.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {skill.resources.map((res) => (
                          <a
                            key={res.title}
                            href={res.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-brand-500/10 text-brand-400 border border-brand-500/20 hover:bg-brand-500/20 hover:border-brand-500/40 transition-all duration-200"
                          >
                            <span>{res.platform}</span>
                            <span className="text-slate-500">·</span>
                            <span>{res.duration}</span>
                            {res.free ? (
                              <span className="text-emerald-400 font-semibold">Free</span>
                            ) : null}
                            <ExternalLink className="w-3 h-3 opacity-60" />
                          </a>
                        ))}
                      </div>
                    )}

                    {/* Confidence */}
                    <div className="mt-3 flex items-center gap-2">
                      <span className="text-[10px] text-slate-600 uppercase tracking-wider">AI Confidence</span>
                      <div className="flex-1 h-1 rounded-full bg-surface-500 max-w-24">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500"
                          style={{ width: `${Math.round(skill.confidence * 100)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-slate-500">{Math.round(skill.confidence * 100)}%</span>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export default function LearningRoadmap({ phases }: LearningRoadmapProps) {
  const [expandedPhase, setExpandedPhase] = useState<number>(1);

  const totalWeeks = phases.reduce((acc, phase) => {
    const match = phase.duration.match(/(\d+)/);
    return acc + (match ? parseInt(match[1]) : 0);
  }, 0);

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center gap-6 p-4 bg-surface-700/50 rounded-xl border border-white/5">
        <div className="flex items-center gap-4 flex-wrap">
          {phases.map((phase, i) => {
            const gradient = PHASE_GRADIENTS[i % PHASE_GRADIENTS.length];
            return (
              <div key={phase.phase} className="flex items-center gap-2">
                <div className={cn('w-3 h-3 rounded-full bg-gradient-to-r', gradient)} />
                <span className="text-xs text-slate-400 font-medium">Phase {phase.phase}: {phase.title}</span>
              </div>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-1.5 text-xs text-slate-400 shrink-0">
          <Clock className="w-3 h-3" />
          <span>~{totalWeeks}–{totalWeeks + 4} weeks total</span>
        </div>
      </div>

      {/* Phase cards */}
      <div className="space-y-3">
        {phases.map((phase, i) => (
          <PhaseCard
            key={phase.phase}
            phase={phase}
            index={i}
            isExpanded={expandedPhase === phase.phase}
            onToggle={() => setExpandedPhase(expandedPhase === phase.phase ? -1 : phase.phase)}
          />
        ))}
      </div>
    </div>
  );
}
