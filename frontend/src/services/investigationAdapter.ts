import { IInvestigationAdapter, InvestigationInput, ScenarioPreset } from './adapterInterface';
import { PRESET_SCENARIOS } from './mockInvestigationData';
import { InvestigationSummary } from '../types/contracts';

export class MockInvestigationAdapter implements IInvestigationAdapter {
  private scenarios: ScenarioPreset[] = PRESET_SCENARIOS;

  async listScenarios(): Promise<ScenarioPreset[]> {
    return this.scenarios;
  }

  async getScenarioById(id: string): Promise<ScenarioPreset | null> {
    const found = this.scenarios.find((s) => s.id === id);
    return found || null;
  }

  async runInvestigation(input: InvestigationInput): Promise<InvestigationSummary> {
    // Simulate pipeline calculation latency (e.g. 600ms) for realistic UX
    await new Promise((resolve) => setTimeout(resolve, 600));

    // If a scenario ID was selected, return its calibrated summary with any overrides applied
    let baseScenario = this.scenarios[0];
    if (input.scenarioId) {
      const matched = this.scenarios.find((s) => s.id === input.scenarioId);
      if (matched) baseScenario = matched;
    }

    const summary: InvestigationSummary = JSON.parse(JSON.stringify(baseScenario.data));

    // Apply manual lat/lon if explicitly changed from base
    if (input.latitude && input.longitude) {
      summary.satellite_observation.latitude = input.latitude;
      summary.satellite_observation.longitude = input.longitude;
    }

    // Apply optional metocean overrides if provided
    if (input.windSpeedMs !== undefined) {
      const angleRad = ((input.windDirectionDeg || 240) * Math.PI) / 180;
      summary.environmental_snapshot.wind_u = Number((input.windSpeedMs * Math.sin(angleRad)).toFixed(2));
      summary.environmental_snapshot.wind_v = Number((input.windSpeedMs * Math.cos(angleRad)).toFixed(2));
    }

    if (input.currentSpeedMs !== undefined) {
      const angleRad = ((input.currentDirectionDeg || 90) * Math.PI) / 180;
      summary.environmental_snapshot.current_u = Number((input.currentSpeedMs * Math.sin(angleRad)).toFixed(2));
      summary.environmental_snapshot.current_v = Number((input.currentSpeedMs * Math.cos(angleRad)).toFixed(2));
    }

    return summary;
  }
}

// Export singleton instance. Can later be switched to BackendInvestigationAdapter
export const investigationService: IInvestigationAdapter = new MockInvestigationAdapter();
