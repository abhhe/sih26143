import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Play,
  Pause,
  RotateCcw,
  ChevronRight,
  ChevronLeft,
  Award,
  Satellite,
  Waves,
  Wind,
  Compass,
  Ship,
  FileCheck2,
  AlertTriangle,
  ExternalLink,
  CheckCircle2,
  XCircle,
} from 'lucide-react';

interface JudgeDemoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApplyScenario: (scenarioId: string) => void;
}

interface DemoStep {
  stepNumber: number;
  title: string;
  stageName: string;
  iconName: string;
  description: string;
  scientificDetails: {
    input: string;
    algorithm: string;
    output: string;
    parameters: string;
  };
  keyFindings: string[];
}

const DEMO_STEPS_SCENARIO_1: DemoStep[] = [
  {
    stepNumber: 1,
    title: 'Satellite SAR Image Ingestion',
    stageName: 'SATELLITE ACQUISITION',
    iconName: 'Satellite',
    description:
      'Sentinel-1 C-band synthetic aperture radar (SAR) Level-1 GRD observation ingested over the North Sea oil corridor. SAR penetrates dense cloud cover and darkness.',
    scientificDetails: {
      input: 'Sentinel-1B IW GRDH SAR Scene (VV + VH polarization)',
      algorithm: 'ESA SNAP Sentinel-1 Toolbox orbit state vector ingestion',
      output: 'Calibrated SAR backscatter matrix (10m pixel spacing)',
      parameters: 'Sub-swath: IW1, Incidence Angle: 38.4°, Polarization: VV',
    },
    keyFindings: [
      'Cloud-penetrating radar acquisition at 06:14 UTC',
      'High backscatter contrast between rough sea and dampened slick',
      'Scene footprint spans major commercial tanker shipping lane',
    ],
  },
  {
    stepNumber: 2,
    title: 'SAR Radiometric Calibration & Speckle Filtering',
    stageName: 'SAR PREPROCESSING',
    iconName: 'Waves',
    description:
      'Conversion of raw digital numbers into normalized radar cross-section (sigma-naught dB) followed by refined Lee speckle filtering to suppress multiplicative speckle noise while preserving edge boundaries.',
    scientificDetails: {
      input: 'Raw 16-bit digital numbers (DN)',
      algorithm: 'Radiometric calibration σ° = (DN² + A)/K, Refined Lee 5x5 window',
      output: 'Speckle-suppressed σ° backscatter image in decibels (dB)',
      parameters: 'Filter Window: 5x5, Noise Variance: 0.28, Damping: 1',
    },
    keyFindings: [
      'Speckle noise reduced by 68% without blurring slick boundary',
      'Clear -4.8 dB backscatter damping observed in candidate anomaly',
      'Signal-to-clutter ratio (SCR) = 11.2 dB',
    ],
  },
  {
    stepNumber: 3,
    title: 'Adaptive Dark Slick Segmentation',
    stageName: 'SLICK DETECTION',
    iconName: 'Waves',
    description:
      'Adaptive constant false alarm rate (CFAR) segmentation combined with Otsu thresholding separates dampened oil slick pixels from ambient sea clutter.',
    scientificDetails: {
      input: 'Calibrated σ° dB image',
      algorithm: 'Bimodal Otsu thresholding + Adaptive CFAR local windowing',
      output: 'Binary oil slick mask [H x W boolean grid]',
      parameters: 'Threshold T_adapt = -22.4 dB, Guard Band: 15px, Clutter Band: 30px',
    },
    keyFindings: [
      'Connected dark patch isolated with zero non-oil false alarms',
      'Look-alike rejection: Low-wind areas and internal waves ruled out',
      'Segmentation confidence: 91.5%',
    ],
  },
  {
    stepNumber: 4,
    title: 'Geometric Characterization & Morphology',
    stageName: 'SLICK GEOMETRY',
    iconName: 'Compass',
    description:
      'Connected-component analysis extracts geometric moments, bounding box, spatial centroid, perimeter, and principal elongation axis of the oil slick.',
    scientificDetails: {
      input: 'Binary slick mask',
      algorithm: 'Green’s theorem polygon extraction & 2nd-order central image moments',
      output: 'SpillDetection object with geo-referenced polygon & centroid',
      parameters: 'Centroid: [56.7800°N, 3.2400°E], Area: 14.8 km², Orientation: 68.2°',
    },
    keyFindings: [
      'Estimated slick surface area: 14.80 km²',
      'Elongated morphology: Length 8.4 km, Mean Width 1.76 km',
      'Orientation axis aligns with combined wind-wave advection vector',
    ],
  },
  {
    stepNumber: 5,
    title: 'Metocean Environmental Forcing Retrieval',
    stageName: 'METOCEAN RETRIEVAL',
    iconName: 'Wind',
    description:
      'Temporal and bilinear spatial interpolation of ERA5 reanalysis 10m atmospheric winds and Copernicus Marine Global Ocean Physics sea surface velocity vectors.',
    scientificDetails: {
      input: 'ERA5 wind grid & CMEMS Global Ocean Physics 1/12° currents',
      algorithm: '4D spatiotemporal bilinear interpolation with quality control flags',
      output: 'EnvironmentalState vector: [wind_u, wind_v, current_u, current_v]',
      parameters: 'Wind: 12.4 kn @ 245° (SW), Surface Current: 0.38 m/s @ 065° (ENE)',
    },
    keyFindings: [
      'Wind forcing: 6.38 m/s from 245° (moderate breeze)',
      'Surface ocean current: 0.38 m/s towards 065° (co-directional push)',
      'Data Quality Flag: VERIFIED_REANALYSIS (no missing data fallbacks)',
    ],
  },
  {
    stepNumber: 6,
    title: 'Backward Lagrangian Particle Hindcasting',
    stageName: 'LAGRANGIAN HINDCAST',
    iconName: 'Waves',
    description:
      'Numerical backward simulation of 100 ensemble particles from the observed slick centroid using Runge-Kutta 2nd-order (RK2) advection, 3.1% wind leeway factor, and random walk diffusion.',
    scientificDetails: {
      input: 'Slick centroid, wind field, current field, simulation duration (6 hours)',
      algorithm: 'Lagrangian RK2 integration with negative timestep dt = -300s',
      output: '100 backward particle trajectories over [T_obs - 6h, T_obs]',
      parameters: 'Leeway: 3.1%, Coriolis deflection: 12° right, Diffusion D: 2.0 m²/s',
    },
    keyFindings: [
      'Reversed surface transport traces slick origin south-southwest',
      'Ensemble spread captures turbulent diffusion & wind gustiness',
      'Zero particles hit shoreline; pure open-water drift physics',
    ],
  },
  {
    stepNumber: 7,
    title: 'Probable Source Envelope & Release Window',
    stageName: 'SOURCE RECONSTRUCTION',
    iconName: 'Compass',
    description:
      'Kernel Density Estimation (KDE) over backward particle positions at optimal hindcast time yields the 50% core credible region and 90% extended uncertainty envelope.',
    scientificDetails: {
      input: 'Particle ensemble endpoints at hindcast convergence time',
      algorithm: 'Bivariate Gaussian KDE + release window variance minimization',
      output: 'DriftResult: source centroid, 50% & 90% polygons, release window',
      parameters: 'Source Centroid: [56.6200°N, 2.9800°E], Uncertainty: ±4.2 km',
    },
    keyFindings: [
      'Probable release window: 00:14 UTC to 03:14 UTC (Peak: 01:45 UTC)',
      '50% Core source zone spans 12.6 km² of high particle convergence',
      'Drift distance: 22.8 km over 4.5 hours hindcast duration',
    ],
  },
  {
    stepNumber: 8,
    title: 'Historical AIS Trajectory Reconstruction',
    stageName: 'AIS INGESTION',
    iconName: 'Ship',
    description:
      'Spatiotemporal bounding box query against historical AIS terrestrial and satellite feeds. Cleans invalid positions, dead-reckons missing pings, and builds continuous trajectories.',
    scientificDetails: {
      input: 'Historical AIS stream covering 2026-09-05 22:00 to 2026-09-06 08:00 UTC',
      algorithm: 'Haversine distance filter + speed spline smoothing',
      output: 'Normalized vessel trajectories with interpolated positions',
      parameters: 'Spatial Radius: 25 km from source centroid, Max allowable speed: 30 kn',
    },
    keyFindings: [
      '3 commercial vessels identified in the broader corridor',
      'Zero AIS spoofing or flag-state dropouts detected',
      'Position temporal resolution: 3 to 10 minutes',
    ],
  },
  {
    stepNumber: 9,
    title: 'Spatial-Temporal Corridor Filtering',
    stageName: 'CANDIDATE FILTERING',
    iconName: 'Ship',
    description:
      'Excludes non-convergent vessels based on Closest Point of Approach (CPA) distance to source centroid and temporal intersection with the estimated release window.',
    scientificDetails: {
      input: 'AIS trajectories + Reconstructed source centroid & release window',
      algorithm: 'CPA geodesic optimization and temporal overlap test',
      output: 'Candidate vessel dossier: MT Nordic Titan, MV Pacific Trader, FV Sea Hunter',
      parameters: 'Max CPA threshold: 20 km, Release Window overlap requirement: > 0 min',
    },
    keyFindings: [
      'MT Nordic Titan passed 0.82 km from source centroid at 01:42 UTC (Dead-on)',
      'MV Pacific Trader CPA was 8.40 km at 04:15 UTC (2h 30m after peak)',
      'FV Sea Hunter CPA was 14.20 km at 05:05 UTC (Stationary fishing)',
    ],
  },
  {
    stepNumber: 10,
    title: 'Multi-Criteria Forensic Consistency Scoring',
    stageName: 'EVIDENCE SCORING',
    iconName: 'FileCheck2',
    description:
      'Calculates the explainable Attribution Evidence Score (0–100) using 5 scientifically weighted dimensions: Spatial (25), Temporal (20), Trajectory (25), Drift (20), Behavioral (10).',
    scientificDetails: {
      input: 'Vessel CPA, crossing geometry, release window overlap, speed profile',
      algorithm: 'Weighted linear combination: Score = S_sp + S_tm + S_tr + S_dr + S_bh',
      output: 'VesselEvidence records with component scores, rank, and classification',
      parameters: 'Weights: Spatial=25, Temporal=20, Trajectory=25, Drift=20, Behavioral=10',
    },
    keyFindings: [
      'MT Nordic Titan: 88.5 / 100 [Strong Candidate]',
      'MV Pacific Trader: 34.0 / 100 [Low Consistency]',
      'FV Sea Hunter: 28.5 / 100 [Low Consistency]',
    ],
  },
  {
    stepNumber: 11,
    title: 'Counterfactual & Exclusion Audit',
    stageName: 'FORENSIC AUDIT',
    iconName: 'AlertTriangle',
    description:
      'Rigorous counterfactual reasoning documents exactly why secondary vessels are excluded from culpability, eliminating false accusations and bias.',
    scientificDetails: {
      input: 'Candidate evidence records and physical drift vectors',
      algorithm: 'Counterfactual hypothesis test: H_0(vessel) = source_consistent',
      output: 'Counterfactual explanations and limiting factors for each vessel',
      parameters: 'Rejection criteria: CPA > 5 km OR time delta > 2 hours',
    },
    keyFindings: [
      'MV Pacific Trader passed 8.4 km to the north well after slick release commenced',
      'FV Sea Hunter was operating 14.2 km downwind; hydrodynamically impossible origin',
      'MT Nordic Titan speed dropped from 14.2 to 11.8 knots during source crossing',
    ],
  },
  {
    stepNumber: 12,
    title: 'Final Evidentiary Attribution Dossier',
    stageName: 'FINAL DOSSIER',
    iconName: 'Award',
    description:
      'Synthesizes complete forensic dossier for maritime authority triage under UNCLOS Article 217. Displays top candidate, component radar breakdown, and mandatory scientific disclaimers.',
    scientificDetails: {
      input: 'All pipeline outputs: SAR, drift envelope, AIS tracks, evidence scores',
      algorithm: 'Automated executive summary generation with chain-of-custody metadata',
      output: 'InvestigationSummary ready for maritime port state control inspection',
      parameters: 'Top Candidate: MT Nordic Titan (MMSI: 257001234), Score: 88.5 / 100',
    },
    keyFindings: [
      'Rank #1: MT Nordic Titan (Crude Oil Tanker, Norway flag)',
      'Attribution Evidence Score: 88.5 / 100 (Strong Candidate)',
      'Legal Disclaimer: Investigative triage metric, not proof of guilt in isolation',
    ],
  },
];

export const JudgeDemoModal: React.FC<JudgeDemoModalProps> = ({
  isOpen,
  onClose,
  onApplyScenario,
}) => {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('scenario-1');
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const timerRef = useRef<any>(null);

  const steps = DEMO_STEPS_SCENARIO_1;
  const currentStep = steps[currentStepIndex];
  const isLastStep = currentStepIndex === steps.length - 1;
  const isFirstStep = currentStepIndex === 0;

  // Auto-play timer effect (5 seconds per step)
  useEffect(() => {
    if (isPlaying) {
      timerRef.current = setInterval(() => {
        setCurrentStepIndex((prev) => {
          if (prev < steps.length - 1) {
            return prev + 1;
          } else {
            setIsPlaying(false);
            return prev;
          }
        });
      }, 5000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, steps.length]);

  if (!isOpen) return null;

  const handleScenarioChange = (id: string) => {
    setSelectedScenarioId(id);
    setCurrentStepIndex(0);
    setIsPlaying(false);
  };

  const handleApplyAndClose = () => {
    onApplyScenario(selectedScenarioId);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container modal-xlarge" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header demo-header">
          <div className="modal-title-wrap">
            <div className="demo-badge-icon">
              <Award size={22} className="text-amber" />
            </div>
            <div>
              <div className="demo-header-tag-row">
                <h2 className="modal-title">SIH 2026 Judge Demonstration Mode</h2>
                <span className="badge-sih">PS-26143</span>
                <span className="demo-time-badge font-mono">60–90 SEC WALKTHROUGH</span>
              </div>
              <p className="modal-subtitle">
                Autonomous 12-Step Scientific Verification: Satellite SAR &rarr; Drift Hindcast &rarr; Source KDE &rarr; AIS Attribution
              </p>
            </div>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose} title="Close Demo">
            <X size={18} />
          </button>
        </div>

        {/* Demo Scenario Switcher & Playbar */}
        <div className="demo-control-strip">
          <div className="demo-scenario-pills">
            <button
              type="button"
              className={`scenario-pill-btn ${selectedScenarioId === 'scenario-1' ? 'active' : ''}`}
              onClick={() => handleScenarioChange('scenario-1')}
            >
              <CheckCircle2 size={14} className="text-emerald" />
              <span>Scenario A: High Evidence Tanker (North Sea)</span>
            </button>
            <button
              type="button"
              className={`scenario-pill-btn ${selectedScenarioId === 'scenario-3' ? 'active' : ''}`}
              onClick={() => handleScenarioChange('scenario-3')}
            >
              <XCircle size={14} className="text-amber" />
              <span>Scenario B: Insufficient Evidence (Malacca Strait)</span>
            </button>
          </div>

          <div className="demo-player-controls">
            <button
              type="button"
              className="demo-playback-btn"
              onClick={() => {
                setIsPlaying(false);
                setCurrentStepIndex(0);
              }}
              title="Reset to Step 1"
            >
              <RotateCcw size={14} />
            </button>

            <button
              type="button"
              className={`demo-playback-btn demo-play-btn ${isPlaying ? 'playing' : ''}`}
              onClick={() => setIsPlaying(!isPlaying)}
              title={isPlaying ? 'Pause Auto-Play' : 'Auto-Play Walkthrough (60s)'}
            >
              {isPlaying ? <Pause size={15} /> : <Play size={15} />}
              <span>{isPlaying ? 'Pause Demo' : 'Auto-Play Walkthrough'}</span>
            </button>

            <button
              type="button"
              className="demo-playback-btn"
              onClick={() => {
                setIsPlaying(false);
                if (!isFirstStep) setCurrentStepIndex((p) => p - 1);
              }}
              disabled={isFirstStep}
              title="Previous Step"
            >
              <ChevronLeft size={16} />
              <span>Prev</span>
            </button>

            <span className="demo-step-counter font-mono">
              Step {currentStepIndex + 1} / {steps.length}
            </span>

            <button
              type="button"
              className="demo-playback-btn"
              onClick={() => {
                setIsPlaying(false);
                if (!isLastStep) setCurrentStepIndex((p) => p + 1);
              }}
              disabled={isLastStep}
              title="Next Step"
            >
              <span>Next</span>
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {/* 12-Step Progress Stepper Ribbon */}
        <div className="demo-stepper-ribbon">
          {steps.map((step, idx) => {
            const isDone = idx < currentStepIndex;
            const isCurrent = idx === currentStepIndex;
            return (
              <div
                key={step.stepNumber}
                className={`stepper-node ${isDone ? 'done' : ''} ${isCurrent ? 'current' : ''}`}
                onClick={() => {
                  setIsPlaying(false);
                  setCurrentStepIndex(idx);
                }}
                title={`Jump to Step ${step.stepNumber}: ${step.title}`}
              >
                <div className="stepper-dot font-mono">{step.stepNumber}</div>
                <span className="stepper-label">{step.stageName}</span>
              </div>
            );
          })}
        </div>

        {/* Demo Content Canvas */}
        <div className="modal-body demo-body">
          {selectedScenarioId === 'scenario-3' ? (
            /* Scenario B: Insufficient Evidence Display */
            <div className="demo-insufficient-view">
              <div className="insufficient-alert-card">
                <AlertTriangle size={32} className="text-amber" />
                <div className="insufficient-text-wrap">
                  <h3 className="insufficient-title">
                    SYSTEM DETERMINATION: INSUFFICIENT EVIDENCE
                  </h3>
                  <p className="insufficient-reason">
                    No vessel in the Strait of Malacca transit corridor crossed the minimum Attribution Evidence Threshold of 50.0 / 100.
                  </p>
                  <div className="insufficient-meta-grid">
                    <div className="meta-box">
                      <span className="meta-lbl">TOP SCORING VESSEL</span>
                      <span className="meta-val">KM Nusantara (38.5 / 100)</span>
                    </div>
                    <div className="meta-box">
                      <span className="meta-lbl">PRIMARY DISQUALIFIER</span>
                      <span className="meta-val">Temporal offset +2.8 hrs outside release window</span>
                    </div>
                    <div className="meta-box">
                      <span className="meta-lbl">ETHICAL AI SAFEGUARD</span>
                      <span className="meta-val text-emerald">Active — Presumption of Innocence Upheld</span>
                    </div>
                  </div>
                  <p className="insufficient-legal-note">
                    <strong>Rule PS-26143-R3:</strong> The attribution engine strictly rejects false-positive force-matching. When spatial-temporal evidence is ambiguous or non-convergent, the system issues an explicit "Insufficient Evidence" finding to prevent maritime wrongful detention.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            /* Scenario A: 12-Step Scientific Walkthrough */
            <div className="demo-step-layout">
              {/* Step Header */}
              <div className="demo-step-banner">
                <div className="step-banner-left">
                  <span className="step-badge font-mono">STAGE {currentStep.stepNumber} OF 12</span>
                  <h3 className="step-banner-title">{currentStep.title}</h3>
                </div>
                <span className="step-stage-pill font-mono">{currentStep.stageName}</span>
              </div>

              {/* Main Step Description */}
              <p className="demo-step-description">{currentStep.description}</p>

              {/* Technical Specifications Grid */}
              <div className="demo-tech-specs-grid">
                <div className="spec-card">
                  <span className="spec-label">INPUT DATASET</span>
                  <span className="spec-val font-mono">{currentStep.scientificDetails.input}</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">GOVERNING ALGORITHM / METHOD</span>
                  <span className="spec-val font-mono">{currentStep.scientificDetails.algorithm}</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">PHYSICAL PARAMETERS</span>
                  <span className="spec-val font-mono">{currentStep.scientificDetails.parameters}</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">DERIVED SCIENTIFIC OUTPUT</span>
                  <span className="spec-val font-mono text-cyan">{currentStep.scientificDetails.output}</span>
                </div>
              </div>

              {/* Key Findings Checklist */}
              <div className="demo-findings-panel">
                <h4 className="findings-title">Key Scientific Observations at this Stage:</h4>
                <div className="findings-list">
                  {currentStep.keyFindings.map((finding, idx) => (
                    <div key={idx} className="finding-item">
                      <CheckCircle2 size={14} className="text-cyan flex-shrink-0" />
                      <span>{finding}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* If on final step (Step 12), show final score breakdown card */}
              {isLastStep && (
                <div className="final-attribution-hero-card">
                  <div className="hero-top-row">
                    <div>
                      <span className="hero-eyebrow">IDENTIFIED TOP CANDIDATE</span>
                      <h3 className="hero-ship-name">MT NORDIC TITAN</h3>
                      <span className="hero-ship-meta">Crude Oil Tanker &bull; MMSI: 257001234 &bull; Flag: Norway [NO]</span>
                    </div>
                    <div className="hero-score-badge">
                      <span className="score-lbl">ATTRIBUTION EVIDENCE SCORE</span>
                      <div className="score-num-wrap">
                        <span className="score-num text-cyan">88.5</span>
                        <span className="score-den">/ 100</span>
                      </div>
                      <span className="score-class-badge class-strong">Strong Candidate</span>
                    </div>
                  </div>

                  <div className="hero-criteria-breakdown">
                    <div className="criterion-mini">
                      <span className="crit-name">Spatial Consistency (25%)</span>
                      <span className="crit-score text-cyan">25.0 / 25</span>
                    </div>
                    <div className="criterion-mini">
                      <span className="crit-name">Temporal Consistency (20%)</span>
                      <span className="crit-score text-cyan">19.0 / 20</span>
                    </div>
                    <div className="criterion-mini">
                      <span className="crit-name">Trajectory Corridor (25%)</span>
                      <span className="crit-score text-cyan">22.5 / 25</span>
                    </div>
                    <div className="criterion-mini">
                      <span className="crit-name">Drift Physics (20%)</span>
                      <span className="crit-score text-cyan">17.0 / 20</span>
                    </div>
                    <div className="criterion-mini">
                      <span className="crit-name">Speed Behavioral (10%)</span>
                      <span className="crit-score text-amber">5.0 / 10</span>
                    </div>
                  </div>

                  <div className="hero-disclaimer-alert">
                    <AlertTriangle size={16} className="text-amber flex-shrink-0" />
                    <span>
                      <strong>Mandatory Evidentiary Disclaimer:</strong> The Attribution Evidence Score indicates forensic consistency between satellite observations, oceanographic drift physics, and historical AIS trajectories. It does NOT constitute definitive legal proof of guilt in isolation and is intended for port state control maritime investigative triage under UNCLOS Article 217.
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="modal-footer demo-footer">
          <div className="demo-footer-info">
            <Award size={14} className="text-amber" />
            <span>SIH 2026 PS-26143 &bull; Ministry of Earth Sciences / Indian Coast Guard Forensic Prototype</span>
          </div>

          <div className="demo-footer-actions">
            <button
              type="button"
              className="btn-apply-dashboard"
              onClick={handleApplyAndClose}
            >
              <ExternalLink size={14} />
              <span>Apply & View on Interactive Map</span>
            </button>
            <button type="button" className="btn-modal-close" onClick={onClose}>
              Exit Demo
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
