import { type LucideIcon } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '../lib/utils';

interface MetricCardProps {
  label: string;
  value: string | number;
  suffix?: string;
  icon: LucideIcon;
  iconColor?: string;
  iconBg?: string;
  trend?: { value: string; positive: boolean };
  description?: string;
  delay?: number;
}

export default function MetricCard({
  label,
  value,
  suffix,
  icon: Icon,
  iconColor = 'text-brand-400',
  iconBg = 'bg-brand-400/10',
  trend,
  description,
  delay = 0,
}: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className="glass-card p-5 flex items-start gap-4 hover:border-white/10 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-card"
    >
      <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center shrink-0', iconBg)}>
        <Icon className={cn('w-5 h-5', iconColor)} />
      </div>

      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
        <div className="mt-1 flex items-baseline gap-1">
          <span className="text-2xl font-bold text-white tabular-nums">
            {value}
          </span>
          {suffix && (
            <span className="text-sm font-semibold text-slate-400">{suffix}</span>
          )}
        </div>

        {trend && (
          <p className={cn('mt-1 text-xs font-medium', trend.positive ? 'text-emerald-400' : 'text-red-400')}>
            {trend.positive ? '↑' : '↓'} {trend.value}
          </p>
        )}

        {description && !trend && (
          <p className="mt-1 text-xs text-slate-500">{description}</p>
        )}
      </div>
    </motion.div>
  );
}
