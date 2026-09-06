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
  appMode?: 'demo' | 'real';
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
  appMode = 'demo',
}) => {
  const [latitude, setLatitude] = useState(initialLatitude);
  const [longitude, setLongitude] = useState(initialLongitude);
  const [obsDate, setObsDate] = useState('2026-08-14');
  const [obsTime, setObsTime] = useState('06:15');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState<string | null>(
    appMode === 'real' ? null : 'S1A_NORTH_SEA_20260814.tiff'
  );
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.50);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // AIS Trajectory Configuration (Phase 5)
  const [selectedAisFile, setSelectedAisFile] = useState<File | null>(null);
  const [aisFileName, setAisFileName] = useState<string | null>(null);
  const [aisDatasetPath, setAisDatasetPath] = useState<string>(
    'data/sample_ais/marine_cadastre_ais_fixture.csv'
  );
  const [spatialRadiusKm, setSpatialRadiusKm] = useState<number>(25.0);

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
    if (appMode === 'demo') {
      setSelectedFile(null);
      setFileName('S1A_NORTH_SEA_20260814.tiff');
    }
    setUploadError(null);
  }, [initialLatitude, initialLongitude, initialTimestamp, initialWindU, initialWindV, initialCurrentU, initialCurrentV, appMode]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setFileName(file.name);
      setUploadError(null);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (appMode === 'real' && !selectedFile) {
      setUploadError('Please select a valid SAR image (.tiff, .png, .jpg) to analyze in Real Data Mode.');
      return;
    }
    setUploadError(null);
    onRunAnalysis({
      imageFile: selectedFile,
      latitude,
      longitude,
      observationDate: obsDate,
      observationTime: obsTime,
      confidenceThreshold,
      windSpeedMs: showOverrides ? windSpeed : undefined,
      windDirectionDeg: showOverrides ? windDir : undefined,
      currentSpeedMs: showOverrides ? currentSpeed : undefined,
      currentDirectionDeg: showOverrides ? currentDir : undefined,
      aisFile: selectedAisFile,
      aisDatasetPath: aisDatasetPath ? aisDatasetPath.trim() : undefined,
      spatialRadiusKm,
    });
  };

  return (
    <div className="panel input-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <Crosshair size={16} className="text-cyan" />
          <span>Investigation Target Parameters</span>
        </h2>
        <span className="panel-subtitle">
          {appMode === 'real' ? 'Live SAR Ingestion (FastAPI)' : 'Observation Ingestion (Demo Mode)'}
        </span>
      </div>

      <form onSubmit={handleSubmit} className="input-form">
        {/* File Upload Zone */}
        <div className="form-group">
          <label className="form-label">
            Sentinel-1 / SAR Image Acquisition
            {appMode === 'real' && (
              <span className="badge badge-cyan font-mono" style={{ marginLeft: '0.5rem', fontSize: '0.65rem' }}>
                REAL MODE
              </span>
            )}
          </label>
          <div className="upload-dropzone">
            <input
              type="file"
              id="sar-upload"
              accept=".tiff,.tif,.png,.jpg,.jpeg"
              onChange={handleFileUpload}
              className="file-input-hidden"
            />
            <label htmlFor="sar-upload" className="dropzone-label">
              <Upload size={20} className="dropzone-icon" />
              <div className="dropzone-text">
                <span className="dropzone-primary">
                  {fileName
                    ? fileName
                    : appMode === 'real'
                    ? 'Click to select SAR Scene (.tiff, .png, .jpg)'
                    : 'Upload SAR Granule (.tiff, .png)'}
                </span>
                <span className="dropzone-secondary">
                  Supported SAR formats: .tiff, .tif, .png, .jpg, .jpeg
                </span>
              </div>
            </label>
          </div>
          {uploadError && (
            <div className="text-danger" style={{ fontSize: '0.8rem', marginTop: '0.4rem', color: '#ef4444' }}>
              {uploadError}
            </div>
          )}
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

        {/* AIS Trajectory Ingestion Section */}
        {appMode === 'real' && (
          <div className="form-group" style={{ marginTop: '0.8rem', marginBottom: '1.2rem' }}>
            <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Historical AIS Dataset (CSV)</span>
              <span className="badge badge-cyan font-mono" style={{ fontSize: '0.65rem' }}>
                PHASE 5
              </span>
            </label>
            <div className="form-row-2">
              <input
                type="text"
                value={aisDatasetPath}
                onChange={(e) => setAisDatasetPath(e.target.value)}
                placeholder="data/sample_ais/marine_cadastre_ais_fixture.csv"
                className="form-input font-mono"
                style={{ fontSize: '0.78rem' }}
                title="Historical AIS trajectory CSV file path on server"
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span className="text-muted font-mono" style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>Corridor:</span>
                <input
                  type="number"
                  min="5"
                  max="150"
                  step="5"
                  value={spatialRadiusKm}
                  onChange={(e) => setSpatialRadiusKm(parseFloat(e.target.value) || 25)}
                  className="form-input font-mono"
                  style={{ width: '80px', fontSize: '0.8rem' }}
                  title="Search corridor radius in km"
                />
                <span className="text-muted font-mono" style={{ fontSize: '0.75rem' }}>km</span>
              </div>
            </div>
          </div>
        )}

        {/* Analyze Action Button */}
        <button
          type="submit"
          disabled={isLoading}
          className={`btn-analyze ${isLoading ? 'btn-loading' : ''}`}
        >
          {isLoading ? (
            <>
              <RefreshCw size={16} className="spin-icon" />
              <span>{appMode === 'real' ? 'Analyzing SAR image...' : 'Computing Hindcast & AIS Correlation...'}</span>
            </>
          ) : (
            <>
              <Play size={16} fill="currentColor" />
              <span>{appMode === 'real' ? 'Analyze Uploaded SAR Image' : 'Execute Attribution Pipeline'}</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};
