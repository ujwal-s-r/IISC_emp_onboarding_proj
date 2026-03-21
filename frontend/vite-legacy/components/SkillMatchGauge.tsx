import { motion } from 'framer-motion';
import { getScoreColor } from '../lib/utils';

interface SkillMatchGaugeProps {
  score: number;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

const SIZE_CONFIG = {
  sm: { viewBox: 120, cx: 60, cy: 60, r: 46, stroke: 8, fontSize: 'text-xl', labelSize: 'text-xs' },
  md: { viewBox: 180, cx: 90, cy: 90, r: 70, stroke: 10, fontSize: 'text-3xl', labelSize: 'text-sm' },
  lg: { viewBox: 240, cx: 120, cy: 120, r: 95, stroke: 12, fontSize: 'text-5xl', labelSize: 'text-base' },
};

function getArcColor(score: number): { stroke: string; glow: string } {
  if (score >= 80) return { stroke: '#10b981', glow: 'rgba(16,185,129,0.4)' };
  if (score >= 60) return { stroke: '#f59e0b', glow: 'rgba(245,158,11,0.4)' };
  if (score >= 40) return { stroke: '#f97316', glow: 'rgba(249,115,22,0.4)' };
  return { stroke: '#ef4444', glow: 'rgba(239,68,68,0.4)' };
}

export default function SkillMatchGauge({
  score,
  label = 'Skill Match Score',
  size = 'md',
  showLabel = true,
}: SkillMatchGaugeProps) {
  const { viewBox, cx, cy, r, stroke, fontSize, labelSize } = SIZE_CONFIG[size];
  const { stroke: arcColor, glow } = getArcColor(score);
  const textColor = getScoreColor(score);

  // Arc math — we use a 270° arc (from 135° to 405°)
  const startAngleDeg = 135;
  const endAngleDeg = 405;
  const totalAngle = endAngleDeg - startAngleDeg; // 270
  function polarToCartesian(angle: number) {
    const rad = ((angle - 90) * Math.PI) / 180;
    return {
      x: cx + r * Math.cos(rad),
      y: cy + r * Math.sin(rad),
    };
  }

  function describeArc(startDeg: number, endDeg: number) {
    const start = polarToCartesian(startDeg);
    const end = polarToCartesian(endDeg);
    const largeArc = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
  }

  const bgPath = describeArc(startAngleDeg, endAngleDeg);

  // Filled arc end angle
  const filledEndDeg = startAngleDeg + (score / 100) * totalAngle;
  const filledPath = score > 0 ? describeArc(startAngleDeg, filledEndDeg) : '';

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: viewBox, height: viewBox }}>
        {/* SVG gauge */}
        <svg
          width={viewBox}
          height={viewBox}
          viewBox={`0 0 ${viewBox} ${viewBox}`}
          className="overflow-visible"
        >
          <defs>
            <filter id="glow-gauge" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Background track */}
          <path
            d={bgPath}
            fill="none"
            stroke="#1e1e35"
            strokeWidth={stroke}
            strokeLinecap="round"
          />

          {/* Filled arc */}
          {score > 0 && (
            <motion.path
              d={filledPath}
              fill="none"
              stroke={arcColor}
              strokeWidth={stroke}
              strokeLinecap="round"
              filter="url(#glow-gauge)"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1.2, ease: 'easeOut', delay: 0.3 }}
              style={{
                filter: `drop-shadow(0 0 6px ${glow})`,
              }}
            />
          )}

          {/* Center tick marks */}
          {[0, 25, 50, 75, 100].map((tick) => {
            const angleDeg = startAngleDeg + (tick / 100) * totalAngle;
            const inner = polarToCartesian(angleDeg);
            const rOuter = r + stroke / 2 + 2;
            const rInner = r - stroke / 2 - 2;
            const outerPt = {
              x: cx + rOuter * Math.cos(((angleDeg - 90) * Math.PI) / 180),
              y: cy + rOuter * Math.sin(((angleDeg - 90) * Math.PI) / 180),
            };
            const innerPt = {
              x: cx + rInner * Math.cos(((angleDeg - 90) * Math.PI) / 180),
              y: cy + rInner * Math.sin(((angleDeg - 90) * Math.PI) / 180),
            };
            void inner;
            return (
              <line
                key={tick}
                x1={innerPt.x}
                y1={innerPt.y}
                x2={outerPt.x}
                y2={outerPt.y}
                stroke="#2a2a45"
                strokeWidth={1.5}
              />
            );
          })}
        </svg>

        {/* Center text overlay */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span
            className={`font-black tabular-nums ${fontSize} ${textColor}`}
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.8, type: 'spring' }}
          >
            {score}
            <span className="text-slate-400" style={{ fontSize: '0.5em' }}>%</span>
          </motion.span>
          {showLabel && (
            <motion.span
              className={`text-slate-500 font-medium ${labelSize} mt-0.5`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1 }}
            >
              Match
            </motion.span>
          )}
        </div>
      </div>

      {label && (
        <p className="text-sm font-semibold text-slate-300 text-center">{label}</p>
      )}
    </div>
  );
}
