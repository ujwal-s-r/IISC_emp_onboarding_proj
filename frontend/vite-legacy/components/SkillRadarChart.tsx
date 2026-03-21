import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { motion } from 'framer-motion';
import type { RadarDataPoint } from '../types';

interface SkillRadarChartProps {
  data: RadarDataPoint[];
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-surface-600 border border-white/10 rounded-xl p-3 shadow-card">
      <p className="text-xs font-semibold text-white mb-2">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 text-xs">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-slate-400">{entry.name}:</span>
          <span className="font-semibold text-white">{entry.value}%</span>
        </div>
      ))}
    </div>
  );
}

function CustomAngleAxis({ x, y, payload }: { x?: number; y?: number; payload?: { value: string } }) {
  return (
    <text
      x={x ?? 0}
      y={y ?? 0}
      textAnchor="middle"
      dominantBaseline="middle"
      fill="#94a3b8"
      fontSize={11}
      fontFamily="Inter, sans-serif"
    >
      {payload?.value ?? ''}
    </text>
  );
}

export default function SkillRadarChart({ data }: SkillRadarChartProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="w-full h-full"
    >
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
          <defs>
            <linearGradient id="candidateGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#6366f1" stopOpacity={0.8} />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.4} />
            </linearGradient>
            <linearGradient id="requiredGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.6} />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.2} />
            </linearGradient>
          </defs>

          <PolarGrid
            stroke="#1e1e35"
            strokeDasharray="3 3"
          />

          <PolarAngleAxis
            dataKey="skill"
            tick={CustomAngleAxis}
          />

          <Radar
            name="Required"
            dataKey="required"
            stroke="#06b6d4"
            fill="url(#requiredGrad)"
            strokeWidth={1.5}
            strokeDasharray="4 2"
          />

          <Radar
            name="Your Profile"
            dataKey="candidate"
            stroke="#6366f1"
            fill="url(#candidateGrad)"
            strokeWidth={2}
          />

          <Tooltip content={<CustomTooltip />} />

          <Legend
            iconType="circle"
            iconSize={8}
            wrapperStyle={{
              fontSize: '12px',
              color: '#94a3b8',
              paddingTop: '8px',
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
