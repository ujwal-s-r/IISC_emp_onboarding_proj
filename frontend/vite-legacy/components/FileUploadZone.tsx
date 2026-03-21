import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, X, CheckCircle2, AlertCircle } from 'lucide-react';
import { cn, formatFileSize } from '../lib/utils';

interface FileUploadZoneProps {
  label: string;
  description: string;
  accept: Record<string, string[]>;
  file: File | null;
  onFileChange: (file: File | null) => void;
  icon?: React.ReactNode;
  accentColor?: 'brand' | 'violet' | 'accent';
  maxSizeMB?: number;
}

const ACCENT_STYLES = {
  brand: {
    active: 'border-brand-500/60 bg-brand-500/5',
    idle: 'border-white/10 hover:border-brand-500/30 hover:bg-brand-500/3',
    icon: 'text-brand-400',
    badge: 'bg-brand-500/10 text-brand-400 border-brand-500/20',
    glow: 'shadow-glow',
  },
  violet: {
    active: 'border-violet-500/60 bg-violet-500/5',
    idle: 'border-white/10 hover:border-violet-500/30 hover:bg-violet-500/3',
    icon: 'text-violet-400',
    badge: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
    glow: 'shadow-glow-violet',
  },
  accent: {
    active: 'border-accent-500/60 bg-accent-500/5',
    idle: 'border-white/10 hover:border-accent-500/30 hover:bg-accent-500/3',
    icon: 'text-accent-400',
    badge: 'bg-accent-500/10 text-accent-400 border-accent-500/20',
    glow: 'shadow-glow-cyan',
  },
};

export default function FileUploadZone({
  label,
  description,
  accept,
  file,
  onFileChange,
  icon,
  accentColor = 'brand',
  maxSizeMB = 10,
}: FileUploadZoneProps) {
  const maxSize = maxSizeMB * 1024 * 1024;
  const styles = ACCENT_STYLES[accentColor];

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) onFileChange(accepted[0]);
    },
    [onFileChange]
  );

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept,
    maxFiles: 1,
    maxSize,
  });

  const hasError = fileRejections.length > 0;
  const acceptedExtensions = Object.values(accept).flat().join(', ');

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-semibold text-slate-200">{label}</label>
        {file && (
          <button
            onClick={() => onFileChange(null)}
            className="text-xs text-slate-500 hover:text-red-400 flex items-center gap-1 transition-colors duration-200"
          >
            <X className="w-3 h-3" />
            Remove
          </button>
        )}
      </div>

      <div
        {...getRootProps()}
        className={cn(
          'relative rounded-2xl border-2 border-dashed transition-all duration-300 cursor-pointer overflow-hidden',
          file
            ? 'border-emerald-500/40 bg-emerald-500/5'
            : isDragActive
            ? cn('border-solid', styles.active)
            : hasError
            ? 'border-red-500/40 bg-red-500/5'
            : styles.idle,
          file && styles.glow
        )}
      >
        <input {...getInputProps()} />

        <AnimatePresence mode="wait">
          {file ? (
            /* File selected state */
            <motion.div
              key="file"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex items-center gap-4 p-5"
            >
              <div className="w-12 h-12 rounded-xl bg-emerald-500/15 flex items-center justify-center shrink-0">
                <FileText className="w-6 h-6 text-emerald-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-white truncate">{file.name}</p>
                <p className="text-xs text-slate-400 mt-0.5">{formatFileSize(file.size)}</p>
              </div>
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            </motion.div>
          ) : isDragActive ? (
            /* Drag active state */
            <motion.div
              key="drag"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-2 py-10 px-4"
            >
              <motion.div
                animate={{ y: [-4, 4, -4] }}
                transition={{ duration: 1, repeat: Infinity }}
              >
                <Upload className={cn('w-10 h-10', styles.icon)} />
              </motion.div>
              <p className="text-sm font-semibold text-white">Drop it here!</p>
            </motion.div>
          ) : (
            /* Default idle state */
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-4 py-8 px-4"
            >
              <div className={cn('w-14 h-14 rounded-2xl flex items-center justify-center', styles.badge, 'border')}>
                {icon ?? <Upload className={cn('w-6 h-6', styles.icon)} />}
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-white">
                  Drag & drop or{' '}
                  <span className={cn('underline underline-offset-2', styles.icon)}>browse</span>
                </p>
                <p className="text-xs text-slate-500 mt-1.5">{description}</p>
                <p className="text-xs text-slate-600 mt-1">
                  {acceptedExtensions} · max {maxSizeMB}MB
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error state */}
        {hasError && !file && (
          <div className="absolute bottom-0 inset-x-0 flex items-center gap-2 px-4 py-2 bg-red-500/10 border-t border-red-500/20">
            <AlertCircle className="w-3 h-3 text-red-400 shrink-0" />
            <p className="text-xs text-red-400">
              {fileRejections[0]?.errors[0]?.message ?? 'Invalid file'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
