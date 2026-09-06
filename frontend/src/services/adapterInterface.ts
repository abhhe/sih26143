import {
  InvestigationSummary,
} from '../types/contracts';

export interface InvestigationInput {
  scenarioId?: string;
  imageFile?: File | null;
  latitude: number;
  longitude: number;
  observationDate: string;
  observationTime: string;
  confidenceThreshold?: number;
  // Optional Metocean manual overrides for demo mode
  windSpeedMs?: number;
  windDirectionDeg?: number;
  currentSpeedMs?: number;
  currentDirectionDeg?: number;
  evidenceThreshold?: number;
}

export interface ScenarioPreset {
  id: string;
  name: string;
  region: string;
  sensor: string;
  summary: string;
  expectedOutcome: 'High Evidence' | 'Medium Evidence' | 'Insufficient Evidence';
  data: InvestigationSummary;
}

export interface IInvestigationAdapter {
  listScenarios(): Promise<ScenarioPreset[]>;
  getScenarioById(id: string): Promise<ScenarioPreset | null>;
  runInvestigation(input: InvestigationInput): Promise<InvestigationSummary>;
}
