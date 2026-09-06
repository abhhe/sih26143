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
import { ScenarioPreset, InvestigationInput } from './services/adapterInterface';
import { InvestigationSummary, VesselEvidence } from './types/contracts';

export const App: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioPreset[]>([]);
  const [activeScenarioId, setActiveScenarioId] = useState<string>('scenario-1');
  const [investigation, setInvestigation] = useState<InvestigationSummary | null>(null);
  const [selectedVesselMmsi, setSelectedVesselMmsi] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Modals state
  const [isValidationModalOpen, setIsValidationModalOpen] = useState<boolean>(false);
  const [isJudgeDemoModalOpen, setIsJudgeDemoModalOpen] = useState<boolean>(false);

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

  // Handle scenario switch
  const handleSelectScenario = async (id: string) => {
    setActiveScenarioId(id);
    setIsLoading(true);
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
    try {
      const summary = await investigationService.runInvestigation({
        ...input,
        scenarioId: activeScenarioId,
      });
      setInvestigation(summary);
      if (summary.candidate_vessels.length > 0) {
        setSelectedVesselMmsi(summary.candidate_vessels[0].mmsi);
      }
    } finally {
      setIsLoading(false);
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
      {/* 1. Header with SIH branding, quick action buttons, scenario switcher & workflow breadcrumbs */}
      <Header
        investigationId={investigation.investigation_id}
        activeScenarioId={activeScenarioId}
        scenarios={scenarios}
        onSelectScenario={handleSelectScenario}
        activeStepIndex={isInsufficientEvidence ? 4 : 5}
        onOpenJudgeDemo={() => setIsJudgeDemoModalOpen(true)}
        onOpenValidation={() => setIsValidationModalOpen(true)}
      />

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
