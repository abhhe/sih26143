import React, { useEffect, useState, useMemo, useRef } from 'react';
import {
  MapContainer,
  TileLayer,
  Polygon,
  Polyline,
  CircleMarker,
  Popup,
  Tooltip,
  useMap,
} from 'react-leaflet';
import {
  SpillDetection,
  DriftResult,
  VesselEvidence,
  AISTrajectory,
  AISPoint,
} from '../types/contracts';
import {
  Layers,
  Play,
  Pause,
  RotateCcw,
  SkipBack,
  SkipForward,
  Clock,
  Navigation,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface MapViewProps {
  spill: SpillDetection;
  drift: DriftResult;
  candidateVessels: VesselEvidence[];
  selectedVesselMmsi?: string | null;
  onSelectVessel: (mmsi: string) => void;
}

function MapRecenter({
  centerLat,
  centerLon,
  zoom = 10,
}: {
  centerLat: number;
  centerLon: number;
  zoom?: number;
}) {
  const map = useMap();
  useEffect(() => {
    map.setView([centerLat, centerLon], zoom, { animate: true });
  }, [centerLat, centerLon, zoom, map]);
  return null;
}

// Linear interpolation between two coordinates
function interpolateCoord(
  p1: [number, number],
  p2: [number, number],
  ratio: number
): [number, number] {
  return [
    p1[0] + (p2[0] - p1[0]) * ratio,
    p1[1] + (p2[1] - p1[1]) * ratio,
  ];
}

export const MapView: React.FC<MapViewProps> = ({
  spill,
  drift,
  candidateVessels,
  selectedVesselMmsi,
  onSelectVessel,
}) => {
  // Layer visibility toggles
  const [showSpill, setShowSpill] = useState(true);
  const [showBackwardDrift, setShowBackwardDrift] = useState(true);
  const [showForwardDrift, setShowForwardDrift] = useState(true);
  const [showSourceRegions, setShowSourceRegions] = useState(true);
  const [showVesselTracks, setShowVesselTracks] = useState(true);
  const [showCpaVector, setShowCpaVector] = useState(true);
  const [showLegend, setShowLegend] = useState(true);

  // Center coordinate
  const centerLat = spill.centroid.latitude;
  const centerLon = spill.centroid.longitude;

  // Timeline State Setup
  // Range: From release earliest (-18h) to forward forecast (+12h)
  const obsTimeMs = useMemo(
    () => new Date((spill as any).timestamp || drift.release_time_window.latest || drift.release_time_window.most_probable).getTime(),
    [spill, drift]
  );

  const releasePeakMs = useMemo(
    () => new Date(drift.release_time_window.most_probable).getTime(),
    [drift]
  );

  const timelineStartMs = useMemo(() => {
    const earliest = new Date(drift.release_time_window.earliest).getTime();
    return Math.min(earliest - 2 * 3600 * 1000, releasePeakMs - 4 * 3600 * 1000);
  }, [drift, releasePeakMs]);

  const timelineEndMs = useMemo(() => {
    return obsTimeMs + (drift.forward_trajectories?.length ? 12 : 4) * 3600 * 1000;
  }, [obsTimeMs, drift]);

  const [currentTimelineMs, setCurrentTimelineMs] = useState<number>(obsTimeMs);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const playTimerRef = useRef<number | null>(null);

  // Auto playback loop
  useEffect(() => {
    if (isPlaying) {
      playTimerRef.current = window.setInterval(() => {
        setCurrentTimelineMs((prev) => {
          const step = 30 * 60 * 1000; // 30 min step
          if (prev + step > timelineEndMs) {
            return timelineStartMs;
          }
          return prev + step;
        });
      }, 700);
    } else if (playTimerRef.current) {
      clearInterval(playTimerRef.current);
    }
    return () => {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    };
  }, [isPlaying, timelineStartMs, timelineEndMs]);

  // Convert GeoJSON coordinates [lon, lat] to Leaflet [lat, lon]
  const spillPolygonCoords = useMemo(() => {
    if (!spill.spill_mask || !spill.spill_mask.coordinates) return [];
    const ring = spill.spill_mask.coordinates[0] as [number, number][];
    return ring.map(([lon, lat]) => [lat, lon] as [number, number]);
  }, [spill]);

  const sourcePolygon95Coords = useMemo(() => {
    if (!drift.source_region || !drift.source_region.coordinates) return [];
    const ring = drift.source_region.coordinates[0] as [number, number][];
    return ring.map(([lon, lat]) => [lat, lon] as [number, number]);
  }, [drift]);

  const sourcePolygon50Coords = useMemo(() => {
    const geom = drift.source_region_50;
    if (!geom || !geom.coordinates) return [];
    const ring = geom.coordinates[0] as [number, number][];
    return ring.map(([lon, lat]) => [lat, lon] as [number, number]);
  }, [drift]);

  const sourcePolygon90Coords = useMemo(() => {
    const geom = drift.source_region_90;
    if (!geom || !geom.coordinates) return [];
    const ring = geom.coordinates[0] as [number, number][];
    return ring.map(([lon, lat]) => [lat, lon] as [number, number]);
  }, [drift]);

  // Calculate estimated oil slick position at timeline time t
  const estimatedOilAtT = useMemo(() => {
    // If t >= obsTimeMs, interpolate along forward forecast or stay at spill centroid
    const t = currentTimelineMs;
    const sLat = drift.source_centroid.latitude;
    const sLon = drift.source_centroid.longitude;
    const oLat = spill.centroid.latitude;
    const oLon = spill.centroid.longitude;

    if (t <= releasePeakMs) {
      return { lat: sLat, lon: sLon, stage: 'Source Release' };
    } else if (t < obsTimeMs) {
      const progress = (t - releasePeakMs) / (obsTimeMs - releasePeakMs);
      const lat = sLat + (oLat - sLat) * progress;
      const lon = sLon + (oLon - sLon) * progress;
      return { lat, lon, stage: 'Advecting Slick' };
    } else {
      // Forward drift
      const fwdProgress = Math.min(1.0, (t - obsTimeMs) / (12 * 3600 * 1000));
      const lat = oLat + 0.10 * fwdProgress;
      const lon = oLon + 0.15 * fwdProgress;
      return { lat, lon, stage: 'Forecasted Transport' };
    }
  }, [currentTimelineMs, releasePeakMs, obsTimeMs, drift, spill]);

  // Interpolate vessel positions and track segments at timeline time t
  const renderedVessels = useMemo(() => {
    return candidateVessels.map((vessel) => {
      const isSelected = vessel.mmsi === selectedVesselMmsi;

      // Determine vessel color based on attribution evidence score
      let color = '#94a3b8'; // default slate
      if (vessel.overall_evidence_score >= 80) color = '#00f59b'; // Strong Candidate (emerald)
      else if (vessel.overall_evidence_score >= 60) color = '#38bdf8'; // Moderate Candidate (sky)
      else if (vessel.overall_evidence_score >= 40) color = '#ffb703'; // Weak Candidate (amber)
      else color = '#64748b'; // Low Consistency (slate)

      const pts = vessel.trajectory?.points || [];
      const hasFullTrajectory = pts.length > 1;

      // Extract coordinates for entire track
      let allCoords: [number, number][] = [];
      let currentPos: [number, number] = [
        vessel.closest_approach.vessel_latitude,
        vessel.closest_approach.vessel_longitude,
      ];
      let currentSpeed = 0;
      let currentCourse = 0;

      if (hasFullTrajectory) {
        allCoords = pts.map((p) => [p.latitude, p.longitude] as [number, number]);

        // Find interpolated position at currentTimelineMs
        const t = currentTimelineMs;
        const firstT = new Date(pts[0].timestamp).getTime();
        const lastT = new Date(pts[pts.length - 1].timestamp).getTime();

        if (t <= firstT) {
          currentPos = [pts[0].latitude, pts[0].longitude];
          currentSpeed = pts[0].speed;
          currentCourse = pts[0].course;
        } else if (t >= lastT) {
          currentPos = [pts[pts.length - 1].latitude, pts[pts.length - 1].longitude];
          currentSpeed = pts[pts.length - 1].speed;
          currentCourse = pts[pts.length - 1].course;
        } else {
          // Find bounding pings
          for (let i = 0; i < pts.length - 1; i++) {
            const t1 = new Date(pts[i].timestamp).getTime();
            const t2 = new Date(pts[i + 1].timestamp).getTime();
            if (t >= t1 && t <= t2) {
              const ratio = (t - t1) / Math.max(1, t2 - t1);
              currentPos = interpolateCoord(
                [pts[i].latitude, pts[i].longitude],
                [pts[i + 1].latitude, pts[i + 1].longitude],
                ratio
              );
              currentSpeed = pts[i].speed + (pts[i + 1].speed - pts[i].speed) * ratio;
              currentCourse = pts[i].course;
              break;
            }
          }
        }
      } else {
        // Fallback simple 3-point track centered around CPA
        const cpa = vessel.closest_approach;
        const offset = 0.08;
        const angle = vessel.mmsi === '244123456' ? 45 : 85;
        const rad = (angle * Math.PI) / 180;
        allCoords = [
          [cpa.vessel_latitude - offset * Math.cos(rad), cpa.vessel_longitude - offset * Math.sin(rad)],
          [cpa.vessel_latitude, cpa.vessel_longitude],
          [cpa.vessel_latitude + offset * Math.cos(rad), cpa.vessel_longitude + offset * Math.sin(rad)],
        ];
      }

      const cpaCoord: [number, number] = [
        vessel.closest_approach.vessel_latitude,
        vessel.closest_approach.vessel_longitude,
      ];

      return {
        vessel,
        mmsi: vessel.mmsi,
        name: vessel.vessel_name || `Vessel ${vessel.mmsi}`,
        type: vessel.vessel_type || 'Commercial',
        color,
        isSelected,
        allCoords,
        currentPos,
        currentSpeed: Number(currentSpeed.toFixed(1)),
        currentCourse: Number(currentCourse.toFixed(0)),
        cpaCoord,
      };
    });
  }, [candidateVessels, selectedVesselMmsi, currentTimelineMs]);

  // Selected vessel object
  const selectedVesselObj = useMemo(() => {
    return renderedVessels.find((v) => v.isSelected) || null;
  }, [renderedVessels]);

  // Format current timeline timestamp for display
  const timelineDateStr = useMemo(() => {
    const d = new Date(currentTimelineMs);
    return d.toUTCString().replace('GMT', 'UTC');
  }, [currentTimelineMs]);

  const timelineRelHours = useMemo(() => {
    const diffHours = (currentTimelineMs - obsTimeMs) / (3600 * 1000);
    if (Math.abs(diffHours) < 0.1) return 'T = 0.0h (SAR Observation)';
    if (diffHours < 0) return `T ${diffHours.toFixed(1)}h (Hindcast)`;
    return `T +${diffHours.toFixed(1)}h (Forecast)`;
  }, [currentTimelineMs, obsTimeMs]);

  return (
    <div className="map-wrapper forensic-map-wrapper">
      {/* Top Map Controls Header */}
      <div className="map-overlay-controls">
        <div className="map-legend-group">
          <div className="legend-title">
            <Layers size={14} className="text-cyan" />
            <span>Forensic Layers</span>
          </div>

          <div className="layer-toggles">
            <button
              type="button"
              className={`layer-btn ${showSpill ? 'active' : ''}`}
              onClick={() => setShowSpill(!showSpill)}
              title="Toggle detected SAR slick polygon"
            >
              <span className="legend-swatch swatch-spill"></span>
              <span>Spill Mask</span>
            </button>

            <button
              type="button"
              className={`layer-btn ${showBackwardDrift ? 'active' : ''}`}
              onClick={() => setShowBackwardDrift(!showBackwardDrift)}
              title="Toggle backward Lagrangian particles"
            >
              <span className="legend-swatch swatch-drift"></span>
              <span>Hindcast Particles</span>
            </button>

            <button
              type="button"
              className={`layer-btn ${showSourceRegions ? 'active' : ''}`}
              onClick={() => setShowSourceRegions(!showSourceRegions)}
              title="Toggle 50% and 90% source credible regions"
            >
              <span className="legend-swatch swatch-source"></span>
              <span>Source 50% / 90% KDE</span>
            </button>

            <button
              type="button"
              className={`layer-btn ${showForwardDrift ? 'active' : ''}`}
              onClick={() => setShowForwardDrift(!showForwardDrift)}
              title="Toggle forward drift transport forecast"
            >
              <span className="legend-swatch" style={{ background: '#d946ef' }}></span>
              <span>Forward Forecast (+12h)</span>
            </button>

            <button
              type="button"
              className={`layer-btn ${showVesselTracks ? 'active' : ''}`}
              onClick={() => setShowVesselTracks(!showVesselTracks)}
              title="Toggle AIS trajectories"
            >
              <span className="legend-swatch swatch-vessel"></span>
              <span>AIS Tracks ({candidateVessels.length})</span>
            </button>

            {selectedVesselObj && (
              <button
                type="button"
                className={`layer-btn ${showCpaVector ? 'active' : ''}`}
                onClick={() => setShowCpaVector(!showCpaVector)}
                title="Toggle closest point of approach vector"
              >
                <span className="legend-swatch" style={{ background: '#00e5ff', border: '1px dashed #ffffff' }}></span>
                <span>CPA Vector</span>
              </button>
            )}
          </div>
        </div>

        <div className="map-status-pill">
          <span className="status-dot"></span>
          <span>EPSG:4326 &bull; RK2 LAGRANGIAN</span>
        </div>
      </div>

      {/* Main Leaflet Map Canvas */}
      <MapContainer
        center={[centerLat, centerLon]}
        zoom={10}
        scrollWheelZoom={true}
        className="leaflet-map-canvas"
      >
        <MapRecenter centerLat={centerLat} centerLon={centerLon} zoom={10} />

        {/* Base Layer: CartoDB Dark Matter */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          maxZoom={19}
        />

        {/* 1. Detected Spill Polygon & Centroid */}
        {showSpill && spillPolygonCoords.length > 0 && (
          <>
            <Polygon
              positions={spillPolygonCoords}
              pathOptions={{
                color: '#00e5ff',
                weight: 2.5,
                fillColor: '#00b4d8',
                fillOpacity: 0.45,
              }}
            >
              <Popup>
                <div className="map-popup">
                  <div className="popup-title">Detected SAR Oil Slick</div>
                  <div className="popup-row">
                    <span>Confidence:</span> <strong>{(spill.confidence * 100).toFixed(1)}%</strong>
                  </div>
                  <div className="popup-row">
                    <span>Area:</span> <strong>{spill.area} km²</strong>
                  </div>
                  <div className="popup-row">
                    <span>Orientation:</span> <strong>{spill.orientation.toFixed(1)}°</strong>
                  </div>
                  <div className="popup-row">
                    <span>Observed:</span> <strong>{new Date((spill as any).timestamp || obsTimeMs).toUTCString()}</strong>
                  </div>
                </div>
              </Popup>
            </Polygon>

            <CircleMarker
              center={[spill.centroid.latitude, spill.centroid.longitude]}
              radius={6}
              pathOptions={{
                color: '#ffffff',
                fillColor: '#00e5ff',
                fillOpacity: 1.0,
                weight: 2,
              }}
            >
              <Tooltip direction="top" offset={[0, -6]} opacity={0.9}>
                Slick Centroid (Observed)
              </Tooltip>
            </CircleMarker>
          </>
        )}

        {/* 2. Backward Lagrangian Particles */}
        {showBackwardDrift &&
          drift.particle_trajectories.map((pt) => {
            const polylinePoints = pt.steps.map(
              (s) => [s.latitude, s.longitude] as [number, number]
            );
            const oldestStep = pt.steps[pt.steps.length - 1];

            return (
              <React.Fragment key={`bwd-${pt.particle_id}`}>
                <Polyline
                  positions={polylinePoints}
                  pathOptions={{
                    color: '#ffb703',
                    weight: 1.2,
                    opacity: 0.30,
                    dashArray: '3, 4',
                  }}
                />
                {oldestStep && (
                  <CircleMarker
                    center={[oldestStep.latitude, oldestStep.longitude]}
                    radius={2}
                    pathOptions={{
                      color: '#fb8500',
                      fillColor: '#fb8500',
                      fillOpacity: 0.6,
                      weight: 1,
                    }}
                  />
                )}
              </React.Fragment>
            );
          })}

        {/* 3. Forward Drift Transport Forecast (+12 hours) */}
        {showForwardDrift &&
          drift.forward_trajectories?.map((pt) => {
            const fwdPoints = pt.steps.map(
              (s) => [s.latitude, s.longitude] as [number, number]
            );
            return (
              <Polyline
                key={`fwd-${pt.particle_id}`}
                positions={fwdPoints}
                pathOptions={{
                  color: '#d946ef',
                  weight: 1.4,
                  opacity: 0.40,
                  dashArray: '4, 4',
                }}
              />
            );
          })}

        {/* 4. Probable Source Regions (50% Core and 90% Extended Uncertainty Envelopes) */}
        {showSourceRegions && (
          <>
            {/* 90% / 95% Extended Envelope */}
            {(sourcePolygon90Coords.length > 0 ? sourcePolygon90Coords : sourcePolygon95Coords).length > 0 && (
              <Polygon
                positions={sourcePolygon90Coords.length > 0 ? sourcePolygon90Coords : sourcePolygon95Coords}
                pathOptions={{
                  color: '#ffb703',
                  weight: 2.0,
                  fillColor: '#fb8500',
                  fillOpacity: 0.18,
                  dashArray: '6, 6',
                }}
              >
                <Popup>
                  <div className="map-popup">
                    <div className="popup-title">Probable Source Envelope (90% KDE)</div>
                    <div className="popup-row">
                      <span>Uncertainty Radius:</span> <strong>{drift.uncertainty.spatial_radius_km} km</strong>
                    </div>
                    <div className="popup-row">
                      <span>Confidence:</span> <strong>90% Credible Region</strong>
                    </div>
                  </div>
                </Popup>
              </Polygon>
            )}

            {/* 50% Core Credible Zone */}
            {sourcePolygon50Coords.length > 0 && (
              <Polygon
                positions={sourcePolygon50Coords}
                pathOptions={{
                  color: '#f97316',
                  weight: 2.2,
                  fillColor: '#ea580c',
                  fillOpacity: 0.35,
                }}
              >
                <Popup>
                  <div className="map-popup">
                    <div className="popup-title">Core Source Region (50% KDE)</div>
                    <div className="popup-row">
                      <span>Status:</span> <strong>Highest Particle Density</strong>
                    </div>
                  </div>
                </Popup>
              </Polygon>
            )}

            {/* Source Centroid Marker */}
            <CircleMarker
              center={[drift.source_centroid.latitude, drift.source_centroid.longitude]}
              radius={7}
              pathOptions={{
                color: '#ffffff',
                fillColor: '#f97316',
                fillOpacity: 1.0,
                weight: 2,
              }}
            >
              <Popup>
                <div className="map-popup">
                  <div className="popup-title">Reconstructed Source Centroid</div>
                  <div>Lat: {drift.source_centroid.latitude.toFixed(4)}°N</div>
                  <div>Lon: {drift.source_centroid.longitude.toFixed(4)}°E</div>
                  <div>Peak Release: {new Date(drift.release_time_window.most_probable).toUTCString()}</div>
                </div>
              </Popup>
              <Tooltip direction="bottom" offset={[0, 8]} opacity={0.9}>
                Reconstructed Source Centroid
              </Tooltip>
            </CircleMarker>
          </>
        )}

        {/* 5. Dynamic Estimated Oil Position at Timeline Time t */}
        <CircleMarker
          center={[estimatedOilAtT.lat, estimatedOilAtT.lon]}
          radius={9}
          pathOptions={{
            color: '#00e5ff',
            fillColor: '#00b4d8',
            fillOpacity: 0.85,
            weight: 2,
          }}
        >
          <Tooltip permanent direction="top" offset={[0, -10]} opacity={0.9}>
            Oil ({estimatedOilAtT.stage})
          </Tooltip>
        </CircleMarker>

        {/* 6. Candidate Vessel Tracks and Moving Positions */}
        {showVesselTracks &&
          renderedVessels.map((v) => (
            <React.Fragment key={v.mmsi}>
              {/* Full Trajectory Track */}
              <Polyline
                positions={v.allCoords}
                pathOptions={{
                  color: v.color,
                  weight: v.isSelected ? 4.5 : 2.2,
                  opacity: v.isSelected ? 1.0 : 0.65,
                }}
                eventHandlers={{
                  click: () => onSelectVessel(v.mmsi),
                }}
              />

              {/* Closest Point of Approach (CPA) Marker */}
              <CircleMarker
                center={v.cpaCoord}
                radius={v.isSelected ? 7 : 4}
                pathOptions={{
                  color: '#ffffff',
                  fillColor: v.color,
                  fillOpacity: 0.9,
                  weight: v.isSelected ? 2.5 : 1.5,
                }}
                eventHandlers={{
                  click: () => onSelectVessel(v.mmsi),
                }}
              >
                <Tooltip direction="right" offset={[6, 0]} opacity={0.9}>
                  {v.name} (CPA: {v.vessel.closest_approach.distance_km} km)
                </Tooltip>
              </CircleMarker>

              {/* Dynamic Vessel Position at Timeline Time t */}
              <CircleMarker
                center={v.currentPos}
                radius={v.isSelected ? 10 : 7}
                pathOptions={{
                  color: v.isSelected ? '#ffffff' : '#0f172a',
                  fillColor: v.color,
                  fillOpacity: 1.0,
                  weight: 2,
                }}
                eventHandlers={{
                  click: () => onSelectVessel(v.mmsi),
                }}
              >
                <Popup>
                  <div className="map-popup">
                    <div className="popup-title">{v.name}</div>
                    <div className="popup-row">
                      <span>MMSI:</span> <strong>{v.mmsi}</strong>
                    </div>
                    <div className="popup-row">
                      <span>Type:</span> <strong>{v.type}</strong>
                    </div>
                    <div className="popup-row">
                      <span>Speed at t:</span> <strong>{v.currentSpeed} kn</strong>
                    </div>
                    <div className="popup-row">
                      <span>Evidence Score:</span>{' '}
                      <strong style={{ color: v.color }}>
                        {v.vessel.overall_evidence_score.toFixed(1)} / 100
                      </strong>
                    </div>
                    <div className="popup-row">
                      <span>Classification:</span> <strong>{v.vessel.classification}</strong>
                    </div>
                    <div className="popup-row">
                      <span>CPA Distance:</span> <strong>{v.vessel.closest_approach.distance_km} km</strong>
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            </React.Fragment>
          ))}

        {/* 7. Selected Vessel CPA Vector (Dashed connector line to Source Centroid) */}
        {showCpaVector && selectedVesselObj && (
          <Polyline
            positions={[
              selectedVesselObj.cpaCoord,
              [drift.source_centroid.latitude, drift.source_centroid.longitude],
            ]}
            pathOptions={{
              color: '#00e5ff',
              weight: 2,
              dashArray: '5, 5',
              opacity: 0.9,
            }}
          >
            <Tooltip permanent direction="center" opacity={0.95}>
              CPA: {selectedVesselObj.vessel.closest_approach.distance_km.toFixed(2)} km
            </Tooltip>
          </Polyline>
        )}
      </MapContainer>

      {/* Floating Scientific Reasoning Legend */}
      <div className="forensic-legend-panel">
        <div className="legend-header" onClick={() => setShowLegend(!showLegend)}>
          <div className="legend-title-wrap">
            <Info size={14} className="text-cyan" />
            <span>Forensic Symbology & Legend</span>
          </div>
          <button type="button" className="legend-toggle-btn">
            {showLegend ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>

        {showLegend && (
          <div className="legend-body">
            <div className="legend-item">
              <span className="legend-symbol symbol-polygon" style={{ borderColor: '#00e5ff', background: '#00b4d866' }}></span>
              <div className="symbol-label">
                <strong>Observed SAR Spill</strong>
                <span>Sentinel-1 adaptive segmentation</span>
              </div>
            </div>

            <div className="legend-item">
              <span className="legend-symbol symbol-polygon" style={{ borderColor: '#f97316', background: '#ea580c55' }}></span>
              <div className="symbol-label">
                <strong>50% Core Source</strong>
                <span>Highest particle density credible zone</span>
              </div>
            </div>

            <div className="legend-item">
              <span className="legend-symbol symbol-polygon" style={{ borderColor: '#ffb703', background: '#fb85002a', borderStyle: 'dashed' }}></span>
              <div className="symbol-label">
                <strong>90% Source Envelope</strong>
                <span>Lagrangian dispersion boundary</span>
              </div>
            </div>

            <div className="legend-item">
              <span className="legend-symbol symbol-line" style={{ background: '#ffb703' }}></span>
              <div className="symbol-label">
                <strong>Backward Hindcast</strong>
                <span>RK2 advection + leeway + diffusion</span>
              </div>
            </div>

            <div className="legend-item">
              <span className="legend-symbol symbol-line" style={{ background: '#d946ef', borderStyle: 'dashed' }}></span>
              <div className="symbol-label">
                <strong>Forward Forecast</strong>
                <span>Projected slick movement (+12h)</span>
              </div>
            </div>

            <div className="legend-item">
              <span className="legend-symbol symbol-line" style={{ background: '#00f59b' }}></span>
              <div className="symbol-label">
                <strong>Strong Candidate (80–100)</strong>
                <span>High spatial & temporal convergence</span>
              </div>
            </div>

            <div className="legend-item">
              <span className="legend-symbol symbol-line" style={{ background: '#ffb703' }}></span>
              <div className="symbol-label">
                <strong>Weak / Low Candidate (&lt;60)</strong>
                <span>Corridor transit or timing offset</span>
              </div>
            </div>

            <div className="legend-item">
              <span className="legend-symbol symbol-line" style={{ background: '#00e5ff', borderStyle: 'dashed' }}></span>
              <div className="symbol-label">
                <strong>CPA Geodesic Vector</strong>
                <span>Distance to source centroid at CPA</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Primary Forensic Timeline Scrubber */}
      <div className="forensic-timeline-controller">
        <div className="timeline-meta-row">
          <div className="timeline-title-wrap">
            <Clock size={14} className="text-cyan" />
            <span className="timeline-title">Forensic Reconstruction Timeline</span>
            <span className="timeline-rel-badge font-mono">{timelineRelHours}</span>
          </div>
          <div className="timeline-time-display font-mono">
            {timelineDateStr}
          </div>
        </div>

        <div className="timeline-scrubber-row">
          {/* Play / Pause / Step Controls */}
          <div className="timeline-buttons">
            <button
              type="button"
              className="timeline-btn"
              onClick={() => {
                setIsPlaying(false);
                setCurrentTimelineMs(timelineStartMs);
              }}
              title="Jump to Start of Release Window"
            >
              <SkipBack size={14} />
            </button>

            <button
              type="button"
              className="timeline-btn"
              onClick={() => {
                setIsPlaying(false);
                setCurrentTimelineMs(releasePeakMs);
              }}
              title="Jump to Peak Release Time"
            >
              <Navigation size={13} />
              <span>T_peak</span>
            </button>

            <button
              type="button"
              className={`timeline-btn timeline-play-btn ${isPlaying ? 'active' : ''}`}
              onClick={() => setIsPlaying(!isPlaying)}
              title={isPlaying ? 'Pause Playback' : 'Play Timeline'}
            >
              {isPlaying ? <Pause size={15} /> : <Play size={15} />}
            </button>

            <button
              type="button"
              className="timeline-btn"
              onClick={() => {
                setIsPlaying(false);
                setCurrentTimelineMs(obsTimeMs);
              }}
              title="Reset to Satellite Observation Time"
            >
              <RotateCcw size={14} />
              <span>T_obs</span>
            </button>

            <button
              type="button"
              className="timeline-btn"
              onClick={() => {
                setIsPlaying(false);
                setCurrentTimelineMs(timelineEndMs);
              }}
              title="Jump to End of Forecast Horizon"
            >
              <SkipForward size={14} />
            </button>
          </div>

          {/* Interactive Range Slider */}
          <div className="timeline-slider-container">
            <input
              type="range"
              min={timelineStartMs}
              max={timelineEndMs}
              step={15 * 60 * 1000} // 15 min steps
              value={currentTimelineMs}
              onChange={(e) => {
                setIsPlaying(false);
                setCurrentTimelineMs(Number(e.target.value));
              }}
              className="timeline-slider"
              title="Scrub timeline to update vessel and slick positions"
            />
            <div className="timeline-ticks">
              <span className="tick-label">Release Window</span>
              <span className="tick-label active">Observation</span>
              <span className="tick-label">Forecast</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
