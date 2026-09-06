import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { InputPanel } from './components/InputPanel';
import { MapView } from './components/MapView';
import { SpillCard } from './components/SpillCard';
import { SourceCard } from './components/SourceCard';
import { CandidateTable } from './components/CandidateTable';
import { EvidencePanel } from './components/EvidencePanel';
import { InsufficientEvidenceBanner } from './components/InsufficientEvidenceBanner';
import { ValidationModal } from './components/ValidationModal';
import { JudgeDemoModal } from './components/JudgeDemoModal';
import { investigationService } from './services/investigationAdapter';
import { apiClient } from './services/apiClient';
import { ScenarioPreset, InvestigationInput } from './services/adapterInterface';
import { InvestigationSummary, VesselEvidence, DriftResult, EnvironmentalState } from './types/contracts';

export const App: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioPreset[]>([]);
  const [activeScenarioId, setActiveScenarioId] = useState<string>('scenario-1');
  const [investigation, setInvestigation] = useState<InvestigationSummary | null>(null);
  const [selectedVesselMmsi, setSelectedVesselMmsi] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [appMode, setAppMode] = useState<'demo' | 'real'>('demo');
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modals state
  const [isValidationModalOpen, setIsValidationModalOpen] = useState<boolean>(false);
  const [isJudgeDemoModalOpen, setIsJudgeDemoModalOpen] = useState<boolean>(false);

  // Periodic health check to monitor FastAPI backend connectivity
  useEffect(() => {
    let isMounted = true;
    async function checkHealth() {
      try {
        await apiClient.checkHealth(3000);
        if (isMounted) setBackendOnline(true);
      } catch {
        if (isMounted) setBackendOnline(false);
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Load preset scenarios on mount
  useEffect(() => {
    async function init() {
      const list = await investigationService.listScenarios();
      setScenarios(list);
      if (list.length > 0) {
        const defaultScenario = list[0];
        setInvestigation(defaultScenario.data);
        if (defaultScenario.data.candidate_vessels.length > 0) {
          setSelectedVesselMmsi(defaultScenario.data.candidate_vessels[0].mmsi);
        }
      }
    }
    init();
  }, []);

  // Handle mode toggle (DEMO MODE vs REAL DATA MODE)
  const handleToggleMode = async (newMode: 'demo' | 'real') => {
    setAppMode(newMode);
    setErrorMessage(null);
    if (newMode === 'demo') {
      const scenario = await investigationService.getScenarioById(activeScenarioId);
      if (scenario) {
        setInvestigation(scenario.data);
        setSelectedVesselMmsi(scenario.data.candidate_vessels[0]?.mmsi || null);
      }
    }
  };

  // Handle scenario switch (in Demo Mode)
  const handleSelectScenario = async (id: string) => {
    setActiveScenarioId(id);
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const summary = await investigationService.runInvestigation({
        scenarioId: id,
        latitude: 0,
        longitude: 0,
        observationDate: '',
        observationTime: '',
      });
      setInvestigation(summary);
      if (summary.candidate_vessels.length > 0) {
        setSelectedVesselMmsi(summary.candidate_vessels[0].mmsi);
      } else {
        setSelectedVesselMmsi(null);
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Handle form submission / manual re-run
  const handleRunAnalysis = async (input: InvestigationInput) => {
    setIsLoading(true);
    setErrorMessage(null);

    if (appMode === 'real') {
      // REAL DATA MODE: Send uploaded SAR file to FastAPI endpoint
      if (!input.imageFile) {
        setErrorMessage('Please select a valid SAR image (.tiff, .png, .jpg) to analyze in Real Data Mode.');
        setIsLoading(false);
        return;
      }

      try {
        const formData = new FormData();
        formData.append('file', input.imageFile);
        formData.append('latitude', input.latitude.toString());
        formData.append('longitude', input.longitude.toString());
        formData.append('confidence_threshold', (input.confidenceThreshold ?? 0.50).toString());
        formData.append('resolution', '10.0');

        const detection = await apiClient.analyzeSarImage(formData);

        // Map real detection into InvestigationSummary structure
        const timestampIso = `${input.observationDate}T${input.observationTime}:00Z`;

        let driftResult: DriftResult = {
          source_centroid: detection.centroid,
          particle_count: 0,
          drift_duration_hours: 0,
          release_time_window: {
            earliest: timestampIso,
            most_probable: timestampIso,
            latest: timestampIso,
            slick_age_hours_range: [0, 0] as [number, number],
          },
          source_region: { type: 'Polygon' as const, coordinates: [] },
          particle_trajectories: [],
          uncertainty: {
            spatial_radius_km: 0,
            major_semi_axis_km: 0,
            minor_semi_axis_km: 0,
            diffusion_coefficient: 0,
            confidence_level: 0,
          },
        };

        let envSnapshot: EnvironmentalState = {
          timestamp: timestampIso,
          latitude: detection.centroid.latitude,
          longitude: detection.centroid.longitude,
          wind_u: 0,
          wind_v: 0,
          current_u: 0,
          current_v: 0,
        };

        // Phase 3: If an oil spill is confirmed, advect particles backward using numerical Lagrangian RK2 drift engine
        if (detection.detected) {
          try {
            const driftSim = await apiClient.simulateDrift({
              spill: detection,
              observation_time: timestampIso,
              max_hindcast_hours: 18.0,
              forecast_hours: 12.0,
              particle_count: 100,
              timestep_minutes: 30.0,
              wind_speed_ms: input.windSpeedMs,
              wind_direction_deg: input.windDirectionDeg,
              current_speed_ms: input.currentSpeedMs,
              current_direction_deg: input.currentDirectionDeg,
            });
            driftResult = driftSim.drift_result;
            envSnapshot = driftSim.environmental_snapshot;
          } catch (driftErr) {
            console.warn('Drift simulation error:', driftErr);
            // Fallback to point metocean snapshot if full drift simulation fails
            try {
              envSnapshot = await apiClient.getMetoceanPoint({
                latitude: detection.centroid.latitude,
                longitude: detection.centroid.longitude,
                timestamp: timestampIso,
                wind_speed_ms: input.windSpeedMs,
                wind_direction_deg: input.windDirectionDeg,
                current_speed_ms: input.currentSpeedMs,
                current_direction_deg: input.currentDirectionDeg,
              });
            } catch {
              // ignore fallback error
            }
          }
        }

        const realSummary: InvestigationSummary = {
          investigation_id: `REAL-${Date.now().toString(36).toUpperCase()}`,
          status: 'completed',
          created_at: new Date().toISOString(),
          satellite_observation: {
            image_id: input.imageFile.name,
            timestamp: timestampIso,
            latitude: detection.centroid.latitude,
            longitude: detection.centroid.longitude,
            image_path: input.imageFile.name,
            sensor: 'Sentinel-1A C-SAR',
            resolution: 10.0,
          },
          spill_detection: detection,
          environmental_snapshot: envSnapshot,
          drift_result: driftResult,
          candidate_vessels: [],
          top_candidate: null,
          insufficient_evidence_reason: detection.detected
            ? null
            : 'No oil spill detected in the uploaded SAR scene above the confidence threshold.',
        };

        setInvestigation(realSummary);
        setSelectedVesselMmsi(null);
      } catch (err: unknown) {
        const msg = (err as Error).message || 'SAR analysis request failed.';
        setErrorMessage(msg);
      } finally {
        setIsLoading(false);
      }
    } else {
      // DEMO MODE: Run existing MockInvestigationAdapter
      try {
        const summary = await investigationService.runInvestigation({
          ...input,
          scenarioId: activeScenarioId,
        });

        // If user specified environmental overrides in demo mode and backend is online,
        // dynamically re-run drift simulation with the real Lagrangian engine to demonstrate sensitivity
        if (
          backendOnline &&
          (input.windSpeedMs !== undefined ||
            input.windDirectionDeg !== undefined ||
            input.currentSpeedMs !== undefined ||
            input.currentDirectionDeg !== undefined)
        ) {
          try {
            const timestampIso = `${input.observationDate}T${input.observationTime}:00Z`;
            const driftSim = await apiClient.simulateDrift({
              spill: summary.spill_detection,
              observation_time: timestampIso,
              max_hindcast_hours: summary.drift_result.drift_duration_hours || 18.0,
              forecast_hours: 12.0,
              particle_count: summary.drift_result.particle_count || 100,
              wind_speed_ms: input.windSpeedMs,
              wind_direction_deg: input.windDirectionDeg,
              current_speed_ms: input.currentSpeedMs,
              current_direction_deg: input.currentDirectionDeg,
            });
            summary.drift_result = driftSim.drift_result;
            summary.environmental_snapshot = driftSim.environmental_snapshot;
          } catch (driftErr) {
            console.warn('Custom drift simulation in demo mode failed, using preset:', driftErr);
          }
        }

        setInvestigation(summary);
        if (summary.candidate_vessels.length > 0) {
          setSelectedVesselMmsi(summary.candidate_vessels[0].mmsi);
        }
      } finally {
        setIsLoading(false);
      }
    }
  };

  if (!investigation) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <p>Initializing SIH PS-26143 Attribution System...</p>
      </div>
    );
  }

  // Find currently selected candidate vessel
  const selectedVessel: VesselEvidence | null =
    investigation.candidate_vessels.find((v) => v.mmsi === selectedVesselMmsi) || null;

  // Check if Insufficient Evidence state is active
  const isInsufficientEvidence =
    Boolean(investigation.insufficient_evidence_reason) ||
    investigation.top_candidate === null ||
    (investigation.candidate_vessels.length > 0 &&
      investigation.candidate_vessels.every(
        (v) => v.classification === 'Insufficient Evidence'
      ));

  const highestScore =
    investigation.candidate_vessels.length > 0
      ? Math.max(...investigation.candidate_vessels.map((v) => v.overall_evidence_score))
      : 0;

  return (
    <div className="app-container">
      {/* 1. Header with SIH branding, quick action buttons, scenario switcher, mode toggle & workflow breadcrumbs */}
      <Header
        investigationId={investigation.investigation_id}
        activeScenarioId={activeScenarioId}
        scenarios={scenarios}
        onSelectScenario={handleSelectScenario}
        activeStepIndex={appMode === 'real' ? (investigation.drift_result.particle_count > 0 ? 3 : 1) : isInsufficientEvidence ? 4 : 5}
        onOpenJudgeDemo={() => setIsJudgeDemoModalOpen(true)}
        onOpenValidation={() => setIsValidationModalOpen(true)}
        appMode={appMode}
        onToggleMode={handleToggleMode}
        backendOnline={backendOnline}
      />

      {/* Error Alert Banner */}
      {errorMessage && (
        <div
          className="error-alert-banner"
          style={{
            background: '#450a0a',
            border: '1px solid #ef4444',
            borderRadius: '6px',
            padding: '0.85rem 1.25rem',
            margin: '0.75rem 1.5rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            color: '#fca5a5',
            fontSize: '0.88rem',
          }}
        >
          <div>
            <strong style={{ color: '#ffffff', marginRight: '0.5rem' }}>Analysis Error:</strong>
            <span>{errorMessage}</span>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            {appMode === 'real' && (
              <button
                type="button"
                onClick={() => handleToggleMode('demo')}
                style={{
                  background: '#1e293b',
                  color: '#38bdf8',
                  border: '1px solid #38bdf8',
                  borderRadius: 4,
                  padding: '3px 8px',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                }}
              >
                Switch to Demo Mode
              </button>
            )}
            <button
              type="button"
              onClick={() => setErrorMessage(null)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#fca5a5',
                cursor: 'pointer',
                fontSize: '1.2rem',
                lineHeight: 1,
              }}
            >
              &times;
            </button>
          </div>
        </div>
      )}

      {/* 8. Insufficient Evidence State Alert (if triggered) */}
      {isInsufficientEvidence && investigation.insufficient_evidence_reason && (
        <InsufficientEvidenceBanner
          reason={investigation.insufficient_evidence_reason}
          threshold={50.0}
          highestCandidateScore={highestScore}
        />
      )}

      {/* Main Workspace Layout */}
      <main className="dashboard-grid">
        {/* Left Column: Input Panel + Physical Characterization Cards */}
        <div className="left-sidebar">
          {/* 2. Investigation Input Panel */}
          <InputPanel
            initialLatitude={investigation.satellite_observation.latitude}
            initialLongitude={investigation.satellite_observation.longitude}
            initialTimestamp={investigation.satellite_observation.timestamp}
            initialWindU={investigation.environmental_snapshot.wind_u}
            initialWindV={investigation.environmental_snapshot.wind_v}
            initialCurrentU={investigation.environmental_snapshot.current_u}
            initialCurrentV={investigation.environmental_snapshot.current_v}
            onRunAnalysis={handleRunAnalysis}
            isLoading={isLoading}
            appMode={appMode}
          />

          {/* 4. Spill Characterization Card */}
          <SpillCard
            spill={investigation.spill_detection}
            observation={investigation.satellite_observation}
          />

          {/* 5. Source Reconstruction Card */}
          <SourceCard
            drift={investigation.drift_result}
            metocean={investigation.environmental_snapshot}
          />
        </div>

        {/* Center / Right Column: Interactive Map & Attribution Analytics */}
        <div className="main-content">
          {/* 3. Main Interactive Map with Timeline Scrubber & Forensic Legend */}
          <div className="map-section-container">
            <MapView
              spill={investigation.spill_detection}
              drift={investigation.drift_result}
              candidateVessels={investigation.candidate_vessels}
              selectedVesselMmsi={selectedVesselMmsi}
              onSelectVessel={(mmsi) => setSelectedVesselMmsi(mmsi)}
            />
          </div>

          {/* Bottom Analytics Split: 6. Candidate Vessels Table + 7. Evidence Panel */}
          <div className="attribution-split">
            {/* 6. Candidate Vessels Table */}
            <CandidateTable
              candidates={investigation.candidate_vessels}
              selectedMmsi={selectedVesselMmsi}
              onSelectVessel={(mmsi) => setSelectedVesselMmsi(mmsi)}
            />

            {/* 7. Evidence Dossier Panel */}
            <EvidencePanel vessel={selectedVessel} />
          </div>
        </div>
      </main>

      {/* Modals */}
      <ValidationModal
        isOpen={isValidationModalOpen}
        onClose={() => setIsValidationModalOpen(false)}
      />

      <JudgeDemoModal
        isOpen={isJudgeDemoModalOpen}
        onClose={() => setIsJudgeDemoModalOpen(false)}
        onApplyScenario={(scenarioId) => handleSelectScenario(scenarioId)}
      />
    </div>
  );
};
