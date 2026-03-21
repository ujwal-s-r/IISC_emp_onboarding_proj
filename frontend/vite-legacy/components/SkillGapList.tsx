import { motion } from 'framer-motion';
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import type { Skill } from '../types';
import { getPriorityColor, getPriorityDot, cn } from '../lib/utils';

interface SkillGapListProps {
  missing: Skill[];
  matched: Skill[];
}

function ConfidenceBar({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2 mt-1.5">
      <div className="flex-1 h-1 rounded-full bg-surface-500 overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500"
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </div>
      <span className="text-[10px] text-slate-500 tabular-nums w-8 text-right">{percent}%</span>
    </div>
  );
}

function SkillItem({ skill, index, isMissing }: { skill: Skill; index: number; isMissing: boolean }) {
  const priorityClass = getPriorityColor(skill.priority);
  const dotClass = getPriorityDot(skill.priority);

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={cn(
        'px-3.5 py-3 rounded-xl border transition-all duration-200 hover:-translate-y-0.5',
        isMissing
          ? 'bg-red-500/5 border-red-500/10 hover:border-red-500/20'
          : 'bg-emerald-500/5 border-emerald-500/10 hover:border-emerald-500/20'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className={cn('w-2 h-2 rounded-full shrink-0 mt-0.5', dotClass)} />
          <span className="text-sm font-semibold text-white truncate">{skill.name}</span>
        </div>
        <span className={cn('badge shrink-0', priorityClass)}>
          {skill.priority.toUpperCase()}
        </span>
      </div>

      {skill.category && (
        <p className="text-xs text-slate-500 mt-1 ml-4">{skill.category}</p>
      )}

      <div className="ml-4">
        <ConfidenceBar value={skill.confidence} />
      </div>
    </motion.div>
  );
}

export default function SkillGapList({ missing, matched }: SkillGapListProps) {
  const highMissing = missing.filter((s) => s.priority === 'high');

  return (
    <div className="space-y-6">
      {/* Missing skills */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="section-title">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span>Missing Skills</span>
            <span className="ml-1 text-xs font-medium text-slate-500 bg-surface-500 px-2 py-0.5 rounded-md">
              {missing.length}
            </span>
          </div>
          {highMissing.length > 0 && (
            <span className="text-xs text-red-400 font-medium">
              {highMissing.length} critical
            </span>
          )}
        </div>

        <div className="space-y-2">
          {missing.map((skill, i) => (
            <SkillItem key={skill.name} skill={skill} index={i} isMissing={true} />
          ))}
        </div>

        {missing.length === 0 && (
          <div className="flex items-center gap-2 p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/15">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <p className="text-sm text-emerald-400">No critical skill gaps detected!</p>
          </div>
        )}

      </div>

      {/* Matched skills */}
      <div>
        <div className="section-title mb-3">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>Matched Skills</span>
          <span className="ml-1 text-xs font-medium text-slate-500 bg-surface-500 px-2 py-0.5 rounded-md">
            {matched.length}
          </span>
        </div>

        <div className="space-y-2">
          {matched.slice(0, 6).map((skill, i) => (
            <SkillItem key={skill.name} skill={skill} index={i} isMissing={false} />
          ))}
        </div>

        {matched.length > 6 && (
          <div className="flex items-center gap-1.5 mt-3 text-xs text-slate-500">
            <Info className="w-3 h-3" />
            <span>+{matched.length - 6} more matched skills</span>
          </div>
        )}
      </div>
    </div>
  );
}
