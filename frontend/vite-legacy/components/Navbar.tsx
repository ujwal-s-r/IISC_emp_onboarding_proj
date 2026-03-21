import { Brain, Github, Zap } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '../lib/utils';

export default function Navbar() {
  const { pathname } = useLocation();

  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b border-white/5 bg-surface-900/80 backdrop-blur-xl">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-600 flex items-center justify-center shadow-glow-sm group-hover:shadow-glow transition-shadow duration-300">
            <Brain className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="text-sm font-bold text-white tracking-tight">SkillBridge</span>
            <span className="ml-1.5 text-xs font-medium text-brand-400 bg-brand-400/10 px-1.5 py-0.5 rounded-md border border-brand-400/20">
              AI
            </span>
          </div>
        </Link>

        {/* Nav links */}
        <div className="hidden sm:flex items-center gap-1">
          {[
            { label: 'Analyze', href: '/' },
            { label: 'Dashboard', href: '/dashboard' },
          ].map(({ label, href }) => (
            <Link
              key={href}
              to={href}
              className={cn(
                'px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                pathname === href
                  ? 'text-white bg-surface-500 border border-white/10'
                  : 'text-slate-400 hover:text-white hover:bg-surface-600'
              )}
            >
              {label}
            </Link>
          ))}
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-400/10 px-3 py-1.5 rounded-lg border border-emerald-400/20">
            <Zap className="w-3 h-3" />
            <span>Live Demo</span>
          </div>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-surface-600 transition-colors duration-200"
            aria-label="GitHub"
          >
            <Github className="w-4 h-4" />
          </a>
        </div>
      </nav>
    </header>
  );
}
