"use client";

import { useRef, useState, useEffect } from "react";
import Charts from "./Charts";

const ROW_HEIGHT = 42;

export default function Sidebar({
  meta,
  rawDefects,
  defectsList,
  selectedDefectId,
  zoneHighlight,
  onToggleZoneHighlight,
  onSelectDefect,
  onRunInspection
}) {
  // IS 13311 Grid Rendering
  const cols = ["A", "B", "C", "D"];
  const rows = [1, 2, 3, 4];

  // Temporal Progression Filtered List
  const propagatedDefects = rawDefects.filter(
    (d) => d.temporal_status === "propagated" || (d.growth_rate_mm_per_month && d.growth_rate_mm_per_month > 0)
  );

  // Determine Class styling for VI
  const viVal = meta.vi_score || 0.0;
  const viClass = (meta.vi_class || "minor").toLowerCase();
  let badgeClass = "badge sev-hairline";
  if (viClass === "moderate" || viClass === "ii" || viClass === "iii") {
    badgeClass = "badge sev-moderate";
  } else if (viClass === "severe" || viClass === "critical" || viClass === "significant") {
    badgeClass = "badge sev-severe";
  }

  return (
    <aside className="sidebar glass-card">
      <header className="sidebar-header">
        <div className="logo">
          <span className="logo-accent">CORTEX</span>
          <span className="logo-text">STRUCTURAL</span>
        </div>
        <div className="subtitle">Façade Intelligence & Quantification</div>
        <button id="btn-run-inspection" className="btn-run-i
                  }

                  // Visual indicator for acceleration (Δ growth rate)
                  const accel = defect.growth_acceleration || 0.0;
                  let accelBadge = null;
                  if (accel > 0) {
                    accelBadge = (
                      <span className="growth-accel-up" title="Growth speed increasing" style={{ fontSize: "0.6rem", display: "inline-block", marginTop: "2px" }}>
                        Accel +{accel.toFixed(2)}
                      </span>
                    );
                  } else if (accel < 0) {
                    accelBadge = (
                      <span className="growth-accel-down" title="Growth speed stabilizing" style={{ fontSize: "0.6rem", display: "inline-block", marginTop: "2px" }}>
                        Decel {accel.toFixed(2)}
                      </span>
                    );
                  }

                  return (
                    <div
                      key={defect.defect_id}
                      className="delta-row"
                      onClick={() => onSelectDefect(defect.defect_id, true)}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                        <strong>{defect.defect_id}</strong>
                        {accelBadge}
                      </div>
                      <div className="growth-val">{trendBadge}</div>
                      <strong style={{ textAlign: "right" }}>+{ (defect.delta_width_mm || 0).toFixed(1) } mm</strong>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </section>
      </div>
    </aside>
  );
}
