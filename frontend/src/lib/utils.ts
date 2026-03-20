import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import type { Priority, Proficiency } from '../types';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPercent(value: number, decimals = 0): string {
  return `${value.toFixed(decimals)}%`;
}

export function getPriorityColor(priority: Priority): string {
  const map: Record<Priority, string> = {
    high: 'text-red-400 bg-red-400/10 border-red-400/20',
    medium: 'text-amber-400 bg-amber-400/10 border-amber-400/20',
    low: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
  };
  return map[priority];
}

export function getPriorityDot(priority: Priority): string {
  const map: Record<Priority, string> = {
    high: 'bg-red-400',
    medium: 'bg-amber-400',
    low: 'bg-emerald-400',
  };
  return map[priority];
}

export function getDifficultyColor(difficulty: Proficiency): string {
  const map: Record<Proficiency, string> = {
    beginner: 'text-emerald-400',
    intermediate: 'text-amber-400',
    advanced: 'text-red-400',
  };
  return map[difficulty];
}

export function getScoreColor(score: number): string {
  if (score >= 80) return 'text-emerald-400';
  if (score >= 60) return 'text-amber-400';
  if (score >= 40) return 'text-orange-400';
  return 'text-red-400';
}

export function getScoreGradient(score: number): string {
  if (score >= 80) return 'from-emerald-500 to-teal-500';
  if (score >= 60) return 'from-amber-500 to-orange-500';
  if (score >= 40) return 'from-orange-500 to-red-500';
  return 'from-red-500 to-rose-600';
}

export function getPlatformIcon(platform: string): string {
  const map: Record<string, string> = {
    Coursera: '🎓',
    YouTube: '▶️',
    FreeCodeCamp: '💻',
    Documentation: '📄',
    'Official Docs': '📄',
    GitHub: '🐙',
    Udemy: '🎯',
    edX: '🏫',
  };
  return map[platform] ?? '🔗';
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return `${str.slice(0, maxLength)}…`;
}
