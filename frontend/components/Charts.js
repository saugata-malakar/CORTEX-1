"use client";

import { useEffect, useRef, useState } from "react";
import Chart from "chart.js/auto";

export default function Charts({ defectsList }) {
  const typeChartRef = useRef(null);
  const shapChartRef = useRef(null);
  const typeChartInstance = useRef(null);
  const shapChartInstance = useRef(null);
  const [shapMode, setShapMode] = useState("global");

  useEffect(() => {
    // 1. Defect Types Donut Chart
    if (typeChartRef.current && !typeChartInstance.current) {
      typeChartInstance.current = new Chart(typeChartRef.current, {
        type: "doughnut",
        data: {
          labels: ["Cracks", "Spalls", "Other Defects"],
          datasets: [{
            data: [0, 0, 0],
            backgroundColor: [
              "hsl(45, 92%, 50%)",   // Crack: Moderate (Yellow)
              "hsl(0, 85%, 55%)",    // Spall: Severe (Red)
              "hsl(207, 95%, 55%)"   // Other: Accent (Blue)
            ],
            borderColor: "hsla(220, 15%, 25%, 0.8)",
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "bottom",
              labels: {
                color: "hsl(215, 18%, 72%)",
                font: { family: "Inter", size: 11 },
                padding: 10
              }
            },
            title: {
            
      }
    };

    const activeData = featureData[shapMode] || featureData.global;
    shapChartInstance.current.data.labels = activeData.labels;
    shapChartInstance.current.data.datasets[0].data = activeData.values;

    if (shapMode === "crack") {
      shapChartInstance.current.data.datasets[0].backgroundColor = "hsla(45, 92%, 50%, 0.75)";
      shapChartInstance.current.data.datasets[0].borderColor = "hsl(45, 92%, 50%)";
    } else if (shapMode === "spalling") {
      shapChartInstance.current.data.datasets[0].backgroundColor = "hsla(0, 85%, 55%, 0.75)";
      shapChartInstance.current.data.datasets[0].borderColor = "hsl(0, 85%, 55%)";
    } else {
      shapChartInstance.current.data.datasets[0].backgroundColor = "hsla(207, 95%, 55%, 0.75)";
      shapChartInstance.current.data.datasets[0].borderColor = "hsl(207, 95%, 55%)";
    }

    shapChartInstance.current.update();
  }, [shapMode, defectsList]);

  return (
    <>
      <div className="chart-container">
        <canvas ref={typeChartRef} />
      </div>
      
      <div className="section-title-row" style={{ marginTop: "1.5rem", marginBottom: "6px" }}>
        <h3>SHAP Importance</h3>
        <select
          id="shap-type-filter"
          className="custom-select"
          style={{ padding: "2px 8px", fontSize: "0.65rem" }}
          value={shapMode}
          onChange={(e) => setShapMode(e.target.value)}
        >
          <option value="global">Global</option>
          <option value="crack">Cracks Only</option>
          <option value="spalling">Spalls Only</option>
        </select>
      </div>
      <div className="chart-container">
        <canvas ref={shapChartRef} />
      </div>
    </>
  );
}
