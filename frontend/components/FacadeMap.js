"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";

export default function FacadeMap({
  rawDefects,
  defectsList,
  selectedDefectId,
  zoneHighlight,
  onSelectDefect
}) {
  const mapContainerRef = useRef(null);
  const mapInstance = useRef(null);
  const activeVectorsGroup = useRef(null);
  const zoneOverlaysGroup = useRef(null);
  const cachedImageDimensions = useRef({ w: 1000, h: 1000 });
  const vectorLayersRef = useRef({});

  // Helper to convert pixel offsets to Leaflet L.LatLng coordinates
  const pixelToLatLng = (pxX, pxY) => {
    const h = cachedImageDimensions.current.h;
    return L.latLng(h - pxY, pxX);
  };

  // Helper to draw grid bounds
  const getZoneBounds = (zoneId) => {
    const w = cachedImageDimensions.current.w;
    const h = cachedImageDimensions.current.h;
    const colChar = zoneId.charAt(0);
    const rowNum = parseInt(zoneId.slice(1));
    const colIndex = colChar.charCodeAt(0) - 65; // A=0, B=1, C=2, D=3
    const rowIndex = rowNum - 1;
    
    const x1 = (colIndex * w) / 4;
    const x2 = ((colIndex + 1) * w) / 4;
    const y1 = ((4 - rowNum) * h) / 4;
    const y2 = (((4 - rowNum) + 1) * h) / 4;
    return [[y1, x1], [y2, x2]];
  };

  useEffect(() => {
    if (!mapContainerRef.current || mapInstance.current) return;

    // 1. Initialize map
    const map = L.map(mapContainerRef.current, {
      crs: L.CRS
      const bounds = getZoneBounds(zoneId);
      const rect = L.rectangle(bounds, {
        color: "var(--accent)",
        weight: 2,
        dashArray: "5, 5",
        fillColor: "var(--accent)",
        fillOpacity: 0.12,
        interactive: false
      });
      zoneOverlaysGroup.current.addLayer(rect);
    });
  }, [zoneHighlight, rawDefects]);

  // Handle vectors list updates
  useEffect(() => {
    drawDefectVectors();
  }, [defectsList]);

  // Center view and highlight active defect
  useEffect(() => {
    if (!mapInstance.current || !selectedDefectId) return;
    const defect = defectsList.find((d) => d.defect_id === selectedDefectId);
    if (!defect) return;

    const cx = defect.centroid_px?.x || defect.centroid_x;
    const cy = defect.centroid_px?.y || defect.centroid_y;
    const latlng = pixelToLatLng(cx, cy);

    mapInstance.current.setView(latlng, 1.5, {
      animate: true,
      duration: 0.75
    });

    // Style highlighting overlays
    Object.keys(vectorLayersRef.current).forEach((id) => {
      const item = vectorLayersRef.current[id];
      if (id === selectedDefectId) {
        item.layer.setStyle({
          color: "var(--accent)",
          weight: item.weight + 4,
          opacity: 1.0,
          fillOpacity: 0.6
        });
      } else {
        item.layer.setStyle({
          color: item.color,
          weight: item.weight,
          opacity: 0.85,
          fillOpacity: item.type === "spalling" ? 0.35 : 0.3
        });
      }
    });
  }, [selectedDefectId, defectsList]);

  return <div ref={mapContainerRef} id="facade-map" style={{ width: "100%", height: "100%" }} />;
}
