import React, { useState, useEffect } from 'react';
import { Upload, Sliders, Play, Crosshair, Wind, Compass, RefreshCw } from 'lucide-react';
import { InvestigationInput } from '../services/adapterInterface';

interface InputPanelProps {
  initialLatitude: number;
  initialLongitude: number;
  initialTimestamp: string;
  initialWindU: number;
  initialWindV: number;
  initialCurrentU: number;
  initialCurrentV: number;
  onRunAnalysis: (input: InvestigationInput) => Promise<void>;
  isLoading: boolean;
}

export const InputPanel: React.FC<InputPanelProps> = ({
  initialLatitude,
  initialLongitude,
  initialTimestamp,
  initialWindU,
  initialWindV,
  initialCurrentU,
  initialCurrentV,
  onRunAnalysis,
  isLoading,
}) => {
  const [latitude, setLatitude] = useState(initialLatitude);
  const [longitude, setLongitude] = useState(initialLongitude);
  const [obsDate, setObsDate] = useState('2026-08-14');
  const [obsTime, setObsTime] = useState('06:15');
  const [fileName, setFileName] = useState<string | null>('S1A_NORTH_SEA_20260814.tiff');

  // Metocean demo overrides
  const [showOverrides, setShowOverrides] = useState(false);
  const [windSpeed, setWindSpeed] = useState(
    Number(Math.sqrt(initialWindU ** 2 + initialWindV ** 2).toFixed(1))
  );
  const [windDir, setWindDir] = useState(245);
  const [currentSpeed, setCurrentSpeed] = useState(
    Number(Math.sqrt(initialCurrentU ** 2 + initialCurrentV ** 2).toFixed(2))
  );
  const [currentDir, setCurrentDir] = useState(90);

  // Sync with prop updates when scenario changes
  useEffect(() => {
    setLatitude(initialLatitude);
    setLongitude(initialLongitude);
    try {
      const dt = new Date(initialTimestamp);
      if (!isNaN(dt.getTime())) {
        setObsDate(dt.toISOString().split('T')[0]);
        setObsTime(dt.toISOString().split('T')[1].substring(0, 5));
      }
    } catch {
      // fallback
    }
    setWindSpeed(Number(Math.sqrt(initialWindU ** 2 + initialWindV ** 2).toFixed(1)));
    setCurrentSpeed(Number(Math.sqrt(initialCurrentU ** 2 + initialCurrentV ** 2).toFixed(2)));
  }, [initialLatitude, initialLongitude, initialTimestamp, initialWindU, initialWindV, initialCurrentU, initialCurrentV]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFileName(e.target.files[0].name);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRunAnalysis({
      latitude,
      longitude,
      observationDate: obsDate,
      observationTime: obsTime,
      windSpeedMs: showOverrides ? windSpeed : undefined,
      windDirectionDeg: showOverrides ? windDir : undefined,
      currentSpeedMs: showOverrides ? currentSpeed : undefined,
      currentDirectionDeg: showOverrides ? currentDir : undefined,
    });
  };

  return (
    <div className="panel input-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <Crosshair size={16} className="text-cyan" />
          <span>Investigation Target Parameters</span>
        </h2>
        <span className="panel-subtitle">Observation Ingestion</span>
      </div>

      <form onSubmit={handleSubmit} className="input-form">
        {/* File Upload Zone */}
        <div className="form-group">
          <label className="form-label">Sentinel-1 / SAR Image Acquisition</label>
          <div className="upload-dropzone">
            <input
              type="file"
              id="sar-upload"
              accept=".tiff,.tif,.png,.jpg,.h5,.nc"
              onChange={handleFileUpload}
              className="file-input-hidden"
            />
            <label htmlFor="sar-upload" className="dropzone-label">
              <Upload size={20} className="dropzone-icon" />
              <div className="dropzone-text">
                <span className="dropzone-primary">{fileName ? fileName : 'Upload SAR Granule (.tiff, .png)'}</span>
                <span className="dropzone-secondary">Copernicus CDSE / CSIRO SAR Benchmark</span>
              </div>
            </label>
          </div>
        </div>

        {/* Lat / Lon */}
        <div className="form-row-2">
          <div className="form-group">
            <label className="form-label">Scene Latitude (°N)</label>
            <input
              type="number"
              step="0.0001"
              value={latitude}
              onChange={(e) => setLatitude(parseFloat(e.target.value))}
              className="form-input font-mono"
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Scene Longitude (°E)</label>
            <input
              type="number"
              step="0.0001"
              value={longitude}
              onChange={(e) => setLongitude(parseFloat(e.target.value))}
              className="form-input font-mono"
              required
            />
          </div>
        </div>

        {/* Date / Time */}
        <div className="form-row-2">
          <div className="form-group">
            <label className="form-label">Observation Date (UTC)</label>
            <input
              type="date"
              value={obsDate}
              onChange={(e) => setObsDate(e.target.value)}
              className="form-input font-mono"
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Observation Time (UTC)</label>
            <input
              type="time"
              value={obsTime}
              onChange={(e) => setObsTime(e.target.value)}
              className="form-input font-mono"
              required
            />
          </div>
        </div>

        {/* Collapsible Environmental Overrides */}
        <div className="overrides-section">
          <button
            type="button"
            className="overrides-toggle-btn"
            onClick={() => setShowOverrides(!showOverrides)}
          >
            <Sliders size={14} />
            <span>Meteo-Oceanographic Forcing Overrides</span>
            <span className="toggle-indicator">{showOverrides ? '▲' : '▼'}</span>
          </button>

          {showOverrides && (
            <div className="overrides-content">
              <div className="form-row-2">
                <div className="form-group">
                  <label className="form-label text-muted">
                    <Wind size={12} className="inline-icon" /> 10m Wind Speed (m/s)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="30"
                    value={windSpeed}
                    onChange={(e) => setWindSpeed(parseFloat(e.target.value))}
                    className="form-input font-mono"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label text-muted">
                    <Compass size={12} className="inline-icon" /> Wind From (° True)
                  </label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    max="360"
                    value={windDir}
                    onChange={(e) => setWindDir(parseInt(e.target.value))}
                    className="form-input font-mono"
                  />
                </div>
              </div>

              <div className="form-row-2">
                <div className="form-group">
                  <label className="form-label text-muted">
                    <Wind size={12} className="inline-icon" /> Current Speed (m/s)
                  </label>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="5"
                    value={currentSpeed}
                    onChange={(e) => setCurrentSpeed(parseFloat(e.target.value))}
                    className="form-input font-mono"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label text-muted">
                    <Compass size={12} className="inline-icon" /> Current To (° True)
                  </label>
                  <input
                    type="number"
                    step="1"
                    min="0"
                    max="360"
                    value={currentDir}
                    onChange={(e) => setCurrentDir(parseInt(e.target.value))}
                    className="form-input font-mono"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Analyze Action Button */}
        <button
          type="submit"
          disabled={isLoading}
          className={`btn-analyze ${isLoading ? 'btn-loading' : ''}`}
        >
          {isLoading ? (
            <>
              <RefreshCw size={16} className="spin-icon" />
              <span>Computing Hindcast & AIS Correlation...</span>
            </>
          ) : (
            <>
              <Play size={16} fill="currentColor" />
              <span>Execute Attribution Pipeline</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};
