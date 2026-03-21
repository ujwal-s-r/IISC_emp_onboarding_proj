import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown,
  Brain,
  CheckCircle2,
  XCircle,
  Database,
  Cpu,
} from 'lucide-react';
import type { ReasoningItem } from '../types';
import { cn } from '../lib/utils';

interface ReasoningTraceProps {
  items: ReasoningItem[];
}

const PRIORITY_CONFIG = {
  High: {
    badge: 'text-red-400 bg-red-400/10 border-red-400/20',
    dot: 'bg-red-400',
    bar: 'bg-red-500',
  },
  Medium: {
    badge: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
    dot: 'bg-amber-400',
    bar: 'bg-amber-500',
  },
  Low: {
    badge: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
    dot: 'bg-emerald-400',
    bar: 'bg-emerald-500',
  },
};

function ReasoningRow({ item, index }: { item: ReasoningItem; index: number }) {
  const [open, setOpen] = useState(false);
  const config = PRIORITY_CONFIG[item.priority];
  const confidence = Math.round(item.confidence * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.06 }}
      className={cn(
        'rounded-xl border transition-all duration-200 overflow-hidden',
        open ? 'border-white/10 bg-surface-600/40' : 'border-white/5 bg-surface-700/30',
        !open && 'hover:border-white/8 hover:bg-surface-700/50'
      )}
    >
      {/* Header row */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 p-4 text-left"
      >
        {/* Status icon */}
        <div className="shrink-0">
          {item.missing ? (
            <XCircle className="w-4 h-4 text-red-400" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          )}
        </div>

        {/* Skill name */}
        <span className="text-sm font-semibold text-white flex-1">{item.skill}</span>

        {/* Category */}
        {item.category && (
          <span className="hidden sm:block text-xs text-slate-600 bg-surface-500 px-2 py-0.5 rounded">
            {item.category}
          </span>
        )}

        {/* Priority badge */}
        <span className={cn('badge border shrink-0', config.badge)}>
          {item.priority}
        </span>

        {/* Confidence */}
        <span className="text-xs font-mono text-slate-500 shrink-0 w-10 text-right">
          {confidence}%
        </span>

        {/* Expand icon */}
        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="w-4 h-4 text-slate-500" />
        </motion.div>
      </button>

      {/* Expanded details */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 border-t border-white/5 pt-3 space-y-4">
              {/* Reason */}
              <div className="flex gap-3">
                <Brain className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1.5">AI Reasoning</p>
                  <p className="text-sm text-slate-300 leading-relaxed">{item.reason}</p>
                </div>
              </div>

              {/* Source */}
              <div className="flex gap-3">
                <Database className="w-4 h-4 text-accent-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1.5">Data Source</p>
                  <p className="text-sm text-slate-400 font-mono">{item.source}</p>
                </div>
              </div>

              {/* Confidence bar */}
              <div className="flex gap-3">
                <Cpu className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-1.5">
                    Confidence Score
                  </p>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 rounded-full bg-surface-500 overflow-hidden">
                      <motion.div
                        className={cn('h-full rounded-full', config.bar)}
                        initial={{ width: 0 }}
                        animate={{ width: `${confidence}%` }}
                        transition={{ duration: 0.6, ease: 'easeOut' }}
                      />
                    </div>
                    <span className="text-sm font-bold text-white tabular-nums">
                      {confidence}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function ReasoningTrace({ items }: ReasoningTraceProps) {
  const missing = items.filter((i) => i.missing);
  const matched = items.filter((i) => !i.missing);

  return (
    <div className="space-y-6">
      {/* Explainability note */}
      <div className="flex items-start gap-3 p-4 bg-brand-500/5 rounded-xl border border-brand-500/15">
        <Brain className="w-4 h-4 text-brand-400 mt-0.5 shrink-0" />
        <div>
          <p className="text-xs font-semibold text-brand-400 mb-1">Explainable AI Output</p>
          <p className="text-xs text-slate-400 leading-relaxed">
            Every recommendation includes AI-generated reasoning, confidence scores, and data source attribution.
            Expand any item to view the full explanation.
          </p>
        </div>
      </div>

      {/* Missing skills */}
      {missing.length > 0 && (
        <div>
          <div className="section-title mb-3">
            <XCircle className="w-4 h-4 text-red-400" />
            <span>Gap Reasoning</span>
            <span className="ml-1 text-xs text-slate-500 bg-surface-500 px-2 py-0.5 rounded-md">{missing.length}</span>
          </div>
          <div className="space-y-2">
            {missing.map((item, i) => (
              <ReasoningRow key={item.skill} item={item} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* Matched skills */}
      {matched.length > 0 && (
        <div>
          <div className="section-title mb-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Match Reasoning</span>
            <span className="ml-1 text-xs text-slate-500 bg-surface-500 px-2 py-0.5 rounded-md">{matched.length}</span>
          </div>
          <div className="space-y-2">
            {matched.map((item, i) => (
              <ReasoningRow key={item.skill} item={item} index={i} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
