import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import LandingPage from './pages/LandingPage';
import DashboardPage from './pages/DashboardPage';
import type { AnalysisResult } from './types';

export default function App() {
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);

  return (
    <div className="min-h-screen bg-surface-900">
      <Navbar />
      <main>
        <Routes>
          <Route
            path="/"
            element={<LandingPage onAnalysisComplete={setAnalysisResult} />}
          />
          <Route
            path="/dashboard"
            element={<DashboardPage result={analysisResult} />}
          />
        </Routes>
      </main>
    </div>
  );
}
