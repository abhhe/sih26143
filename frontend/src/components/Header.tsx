import React from 'react';
import { Satellite, Activity, Award, ShieldCheck } from 'lucide-react';
import { ScenarioPreset } from '../services/adapterInterface';

interface HeaderProps {
  investigationId: string;
  activeScenarioId: string;
  scenarios: ScenarioPreset[];
  onSelectScenario: (scenarioId: string) => void;
  activeStepIndex?: number;
  onOpenJudgeDemo: () => void;
  onOpenValidation: () => void;
}

const WORKFLOW_STEPS = [
  { label: 'SATELLITE', desc: 'Sentinel-1 SAR' },
  { label: 'SPILL', desc: 'Detection & Mask' },
  { label: 'DRIFT', desc: 'MetOcean Forcing' },
  { label: 'SOURCE', desc: 'Hindcast Envelope' },
  { label: 'AIS', desc: 'Corridor Tracks' },
  { label: 'ATTRIBUTION', desc: 'Evidence Scoring' },
];

export const Header: React.FC<HeaderProps> = ({
  investigationId,
  activeScenarioId,
  scenarios,
  onSelectScenario,
  activeStepIndex = 5,
  onOpenJudgeDemo,
  onOpenValidation,
}) => {
  return (
    <header className="app-header">
      {/* Top Banner */}
      <div className="header-top">
        <div className="header-title-group">
          <div className="header-icon-box">
            <Satellite className="header-icon" size={24} />
          </div>
          <div>
            <div className="title-row">
              <h1 className="header-title">Oil Spill Source Attribution System</h1>
              <span className="badge-sih">SIH PS-26143</span>
            </div>
            <p className="header-subtitle">
              Satellite SAR Observation &bull; Backward Lagrangian Drift Hindcasting &bull; AIS Spatiotemporal Correlation
            </p>
          </div>
        </div>

        <div className="header-controls">
          {/* Quick Action Buttons: Judge Demo & Scientific Benchmarks */}
          <div className="header-action-buttons">
            <button
              type="button"
              className="btn-header-action btn-judge-demo"
              onClick={onOpenJudgeDemo}
              title="Launch 60-90s Automated Judge Demonstration"
            >
              <Award size={15} className="text-amber" />
              <span>Run Demo Investigation</span>
            </button>

            <button
              type="button"
              className="btn-header-action btn-validation-benchmarks"
              onClick={onOpenValidation}
              title="Open Scientific Validation & Sensitivity Benchmarks"
            >
              <ShieldCheck size={15} className="text-cyan" />
              <span>Validation Benchmarks</span>
            </button>
          </div>

          {/* Investigation ID */}
          <div className="header-meta-pill">
            <span className="pill-label">INVESTIGATION ID</span>
            <span className="pill-value font-mono">{investigationId}</span>
          </div>

          {/* Demo Mode & Scenario Selector */}
          <div className="header-scenario-selector">
            <div className="demo-indicator">
              <span className="demo-pulse-dot"></span>
              <span className="demo-label">DEMO MODE ACTIVE</span>
            </div>
            <select
              className="scenario-select"
              value={activeScenarioId}
              onChange={(e) => onSelectScenario(e.target.value)}
              title="Select demo scenario"
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.expectedOutcome})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Scientific Workflow Chain */}
      <div className="workflow-bar">
        <div className="workflow-title">
          <Activity size={14} className="text-cyan" />
          <span>SCIENTIFIC CHAIN</span>
        </div>
        <div className="workflow-steps">
          {WORKFLOW_STEPS.map((step, idx) => {
            const isActive = idx <= activeStepIndex;
            const isCurrent = idx === activeStepIndex;
            return (
              <React.Fragment key={step.label}>
                <div className={`workflow-step ${isActive ? 'active' : ''} ${isCurrent ? 'current' : ''}`}>
                  <span className="step-num">{idx + 1}</span>
                  <div className="step-text">
                    <span className="step-label">{step.label}</span>
                    <span className="step-desc">{step.desc}</span>
                  </div>
                </div>
                {idx < WORKFLOW_STEPS.length - 1 && <span className="step-arrow">&rarr;</span>}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </header>
  );
};
