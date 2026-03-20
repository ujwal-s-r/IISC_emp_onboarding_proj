import type { AnalysisResult } from '../types';
import { MOCK_ANALYSIS_RESULT } from './mockData';

const BASE_URL = '/api';
const USE_MOCK = true; // Set to false when backend is running

export interface AnalyzePayload {
  resumeFile: File;
  jobDescriptionFile?: File;
  jobDescriptionText?: string;
}

async function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function analyzeCandidate(
  payload: AnalyzePayload,
  onProgress?: (step: string, percent: number) => void
): Promise<AnalysisResult> {
  if (USE_MOCK) {
    const steps = [
      ['Parsing resume document…', 15],
      ['Extracting skills and experience…', 30],
      ['Analyzing job description…', 50],
      ['Running skill gap detection…', 65],
      ['Generating adaptive roadmap…', 80],
      ['Mapping learning resources…', 92],
      ['Finalizing AI reasoning trace…', 100],
    ] as const;

    for (const [step, percent] of steps) {
      await delay(600 + Math.random() * 400);
      onProgress?.(step, percent);
    }

    await delay(300);
    return { ...MOCK_ANALYSIS_RESULT, timestamp: new Date().toISOString() };
  }

  const formData = new FormData();
  formData.append('resume', payload.resumeFile);

  if (payload.jobDescriptionFile) {
    formData.append('job_description', payload.jobDescriptionFile);
  } else if (payload.jobDescriptionText) {
    formData.append('job_description_text', payload.jobDescriptionText);
  }

  const response = await fetch(`${BASE_URL}/analyze`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail ?? `HTTP ${response.status}`);
  }

  return response.json() as Promise<AnalysisResult>;
}

export async function uploadResume(file: File): Promise<{ resumeId: string }> {
  if (USE_MOCK) {
    await delay(500);
    return { resumeId: 'resume_mock_001' };
  }

  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${BASE_URL}/upload-resume`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) throw new Error(`Upload failed: HTTP ${response.status}`);
  return response.json();
}

export async function generateRoadmap(resumeId: string, jdText: string) {
  if (USE_MOCK) {
    await delay(800);
    return MOCK_ANALYSIS_RESULT.learningRoadmap;
  }

  const response = await fetch(`${BASE_URL}/generate-roadmap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_id: resumeId, jd_text: jdText }),
  });

  if (!response.ok) throw new Error(`Roadmap generation failed: HTTP ${response.status}`);
  return response.json();
}
