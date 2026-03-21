import { ExternalLink, Clock, Star } from 'lucide-react';
import { motion } from 'framer-motion';
import type { Resource } from '../types';
import { cn, getDifficultyColor, getPlatformIcon } from '../lib/utils';

interface ResourceCardProps {
  resource: Resource;
  index?: number;
}

const PLATFORM_COLORS: Record<string, string> = {
  Coursera: 'text-blue-400 bg-blue-400/10 border-blue-400/20',
  YouTube: 'text-red-400 bg-red-400/10 border-red-400/20',
  FreeCodeCamp: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
  Documentation: 'text-slate-400 bg-slate-400/10 border-slate-400/20',
  'Official Docs': 'text-slate-400 bg-slate-400/10 border-slate-400/20',
  GitHub: 'text-violet-400 bg-violet-400/10 border-violet-400/20',
  Udemy: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
  edX: 'text-rose-400 bg-rose-400/10 border-rose-400/20',
};

export default function ResourceCard({ resource, index = 0 }: ResourceCardProps) {
  const platformColor = PLATFORM_COLORS[resource.platform] ?? 'text-brand-400 bg-brand-400/10 border-brand-400/20';
  const diffColor = getDifficultyColor(resource.difficulty);
  const icon = getPlatformIcon(resource.platform);

  return (
    <motion.a
      href={resource.url}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06 }}
      className="glass-card p-4 flex flex-col gap-3 hover:border-white/10 hover:-translate-y-1 hover:shadow-card-hover transition-all duration-300 group cursor-pointer"
    >
      {/* Platform + Free badge */}
      <div className="flex items-center justify-between">
        <span className={cn('badge border', platformColor)}>
          <span>{icon}</span>
          <span>{resource.platform}</span>
        </span>
        {resource.free ? (
          <span className="badge text-emerald-400 bg-emerald-400/10 border-emerald-400/20">
            Free
          </span>
        ) : (
          <span className="badge text-slate-400 bg-slate-400/10 border-slate-400/20">
            Paid
          </span>
        )}
      </div>

      {/* Title */}
      <div>
        <h4 className="text-sm font-semibold text-white leading-snug group-hover:text-brand-400 transition-colors duration-200 line-clamp-2">
          {resource.title}
        </h4>
      </div>

      {/* Meta */}
      <div className="flex items-center justify-between mt-auto pt-1 border-t border-white/5">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-xs text-slate-500">
            <Clock className="w-3 h-3" />
            <span>{resource.duration}</span>
          </div>
          <span className={cn('text-xs font-medium capitalize', diffColor)}>
            {resource.difficulty}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {resource.rating && (
            <div className="flex items-center gap-1 text-xs text-amber-400">
              <Star className="w-3 h-3 fill-amber-400" />
              <span>{resource.rating}</span>
            </div>
          )}
          <ExternalLink className="w-3.5 h-3.5 text-slate-500 group-hover:text-brand-400 transition-colors duration-200" />
        </div>
      </div>
    </motion.a>
  );
}
