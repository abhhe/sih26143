import React from 'react';
import { SpillDetection, SatelliteObservation } from '../types/contracts';
import { Target, Compass } from 'lucide-react';

interface SpillCardProps {
  spill: SpillDetection;
  observation: SatelliteObservation;
}

export const SpillCard: React.FC<SpillCardProps> = ({ spill, observation }) => {
  const confidencePercent = (spill.confidence * 100).toFixed(1);

  return (
    <div className="card spill-card">
      <div className="card-header">
        <div className="card-title-group">
          <Target size={16} className="text-cyan" />
          <h3 className="card-title">SAR Spill Characterization</h3>
        </div>
        <span className="badge badge-cyan">{spill.detector_algorithm || 'U-Net Detector'}</span>
      </div>

      <div className="card-body">
        {/* Confidence Gauge */}
        <div className="metric-row">
          <div className="metric-label-group">
            <span className="metric-label">Detection Confidence</span>
            <span className="metric-highlight font-mono">{confidencePercent}%</span>
          </div>
          <div className="progress-bar-bg">
            <div
              className="progress-bar-fill fill-cyan"
              style={{ width: `${confidencePercent}%` }}
            ></div>
          </div>
        </div>

        {/* Primary Metrics Grid */}
        <div className="stats-grid">
          <div className="stat-box">
            <span className="stat-label">Estimated Area</span>
            <span className="stat-value font-mono">
              {spill.area} <span className="stat-unit">km²</span>
            </span>
          </div>

          <div className="stat-box">
            <span className="stat-label">Perimeter</span>
            <span className="stat-value font-mono">
              {spill.perimeter} <span className="stat-unit">km</span>
            </span>
          </div>

          <div className="stat-box">
            <span className="stat-label">Orientation</span>
            <div className="orientation-stat font-mono">
              <span>{spill.orientation.toFixed(1)}°</span>
              <Compass
                size={14}
                className="text-cyan"
                style={{ transform: `rotate(${spill.orientation}deg)` }}
              />
            </div>
          </div>

          <div className="stat-box">
            <span className="stat-label">Look-Alike Risk</span>
            <span className={`badge badge-risk-${spill.look_alike_risk || 'low'}`}>
              {(spill.look_alike_risk || 'low').toUpperCase()}
            </span>
          </div>
        </div>

        {/* Centroid & Bounding Box */}
        <div className="coord-info-block">
          <div className="coord-row">
            <span className="coord-title">Slick Centroid:</span>
            <span className="coord-val font-mono">
              {spill.centroid.latitude.toFixed(4)}°N, {spill.centroid.longitude.toFixed(4)}°E
            </span>
          </div>
          <div className="coord-row">
            <span className="coord-title">Bounding Box:</span>
            <span className="coord-val font-mono">
              [{spill.bounding_box.min_latitude.toFixed(3)}°, {spill.bounding_box.min_longitude.toFixed(3)}°] &rarr; [
              {spill.bounding_box.max_latitude.toFixed(3)}°, {spill.bounding_box.max_longitude.toFixed(3)}°]
            </span>
          </div>
          <div className="coord-row">
            <span className="coord-title">SAR Sensor:</span>
            <span className="coord-val font-mono text-cyan">
              {observation.sensor} ({observation.resolution}m/px)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
