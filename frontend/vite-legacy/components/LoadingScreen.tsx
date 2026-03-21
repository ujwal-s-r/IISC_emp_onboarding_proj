import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Check } from 'lucide-react';
import { cn } from '../lib/utils';

interface LoadingScreenProps {
  currentStep: string;
  progress: number;
}

const ALL_STEPS = [
  'Parsing resume document…',
  'Extracting skills and experience…',
  'Analyzing job description…',
  'Running skill gap detection…',
  'Generating adaptive roadmap…',
  'Mapping learning resources…',
  'Finalizing AI reasoning trace…',
];

export default function LoadingScreen({ currentStep, progress }: LoadingScreenProps) {
  const currentIdx = ALL_STEPS.indexOf(currentStep);

  return (
    <div className="fixed inset-0 z-50 bg-surface-900 flex items-center justify-center p-4">
      {/* Background glow */}
      <div className="absolute inset-0 bg-hero-glow pointer-events-none" />

      <div className="relative w-full max-w-md">
        {/* Icon */}
        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, type: 'spring' }}
          className="flex justify-center mb-8"
        >
          <div className="relative">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-brand-500 to-violet-600 flex items-center justify-center shadow-glow">
              <Brain className="w-10 h-10 text-white" />
            </div>
            {/* Rotating ring */}
            <div className="absolute inset-0 rounded-2xl border-2 border-brand-400/30 animate-spin-slow" />
            <div className="absolute -inset-2 rounded-[20px] border border-brand-500/10 animate-pulse-slow" />
          </div>
        </motion.div>

        {/* Title */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="text-center mb-8"
        >
          <h2 className="text-2xl font-bold text-white">Analyzing Your Profile</h2>
          <p className="mt-1 text-sm text-slate-400">AI agents are working in parallel…</p>
        </motion.div>

        {/* Progress bar */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mb-8"
        >
          <div className="flex justify-between text-xs font-medium mb-2">
            <span className="text-slate-400">Progress</span>
            <span className="text-brand-400">{progress}%</span>
          </div>
          <div className="h-2 rounded-full bg-surface-500 overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500"
              initial={{ width: '0%' }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>
        </motion.div>

        {/* Steps */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="space-y-3"
        >
          {ALL_STEPS.map((step, idx) => {
            const isDone = idx < currentIdx;
            const isActive = idx === currentIdx;
            const isPending = idx > currentIdx;

            return (
              <motion.div
                key={step}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4 + idx * 0.06 }}
                className={cn(
                  'flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300',
                  isActive && 'bg-brand-500/10 border border-brand-500/20',
                  isDone && 'opacity-60',
                  isPending && 'opacity-30'
                )}
              >
                {/* Status icon */}
                <div
                  className={cn(
                    'w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-all duration-300',
                    isDone && 'bg-emerald-500',
                    isActive && 'bg-brand-500',
                    isPending && 'bg-surface-500'
                  )}
                >
                  {isDone ? (
                    <Check className="w-3 h-3 text-white" />
                  ) : isActive ? (
                    <motion.div
                      className="w-2 h-2 rounded-full bg-white"
                      animate={{ scale: [1, 1.3, 1] }}
                      transition={{ duration: 1, repeat: Infinity }}
                    />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-slate-600" />
                  )}
                </div>

                {/* Label */}
                <span
                  className={cn(
                    'text-sm font-medium',
                    isActive && 'text-white',
                    isDone && 'text-slate-400',
                    isPending && 'text-slate-600'
                  )}
                >
                  {step}
                </span>

                {/* Active shimmer */}
                <AnimatePresence>
                  {isActive && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="ml-auto"
                    >
                      <div className="flex gap-1">
                        {[0, 1, 2].map((i) => (
                          <motion.div
                            key={i}
                            className="w-1 h-1 rounded-full bg-brand-400"
                            animate={{ opacity: [0.3, 1, 0.3] }}
                            transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.2 }}
                          />
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </motion.div>

        {/* Footer note */}
        <p className="mt-6 text-center text-xs text-slate-600">
          Powered by BAAI/bge-small-en-v1.5 · Multi-Agent Architecture
        </p>
      </div>
    </div>
  );
}
