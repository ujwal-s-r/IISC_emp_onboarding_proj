export type Priority = 'high' | 'medium' | 'low';
export type Proficiency = 'beginner' | 'intermediate' | 'advanced';
export type Platform =
  | 'Coursera'
  | 'YouTube'
  | 'FreeCodeCamp'
  | 'Documentation'
  | 'GitHub'
  | 'Udemy'
  | 'edX'
  | 'Official Docs';

export interface Skill {
  name: string;
  priority: Priority;
  proficiency?: Proficiency;
  confidence: number;
  category?: string;
  similarity?: number;
}

export interface Resource {
  title: string;
  url: string;
  platform: Platform | string;
  difficulty: Proficiency;
  duration: string;
  free: boolean;
  rating?: number;
}

export interface PhaseSkill {
  name: string;
  duration: string;
  resources: Resource[];
  reason: string;
  confidence: number;
  difficulty: Proficiency;
}

export interface Phase {
  phase: number;
  title: string;
  description: string;
  duration: string;
  skills: PhaseSkill[];
  difficulty: Proficiency;
}

export interface ReasoningItem {
  skill: string;
  missing: boolean;
  reason: string;
  priority: 'High' | 'Medium' | 'Low';
  confidence: number;
  source: string;
  category?: string;
}

export interface RadarDataPoint {
  skill: string;
  candidate: number;
  required: number;
  fullMark: number;
}

export interface Metrics {
  skillExtractionAccuracy: number;
  gapDetectionPrecision: number;
  pathCompletionEstimate: string;
  estimatedLearningWeeks: number;
  trainingReductionPercent: number;
}

export interface AnalysisResult {
  sessionId: string;
  timestamp: string;
  skillMatchScore: number;
  careerReadinessScore: number;
  candidateName?: string;
  targetRole: string;
  matchedSkills: Skill[];
  missingSkills: Skill[];
  candidateSkills: Skill[];
  requiredSkills: Skill[];
  radarData: RadarDataPoint[];
  learningRoadmap: Phase[];
  reasoningTrace: ReasoningItem[];
  topResources: Resource[];
  metrics: Metrics;
}

export interface UploadState {
  resume: File | null;
  jobDescription: File | null;
  jdText: string;
}

export type AnalysisStatus =
  | 'idle'
  | 'uploading'
  | 'analyzing'
  | 'complete'
  | 'error';
