"use client";
import { useEffect, useRef } from "react";

export default function StructureViewer({ defects = [], mosaicUrl, onDefectClick }) {
  const mountRef = useRef(null);

  useEffect(() => {
    let renderer, animId;

    async function init() {
      const THREE = await import("three");

      const w = mountRef.current.clientWidth;
      const h = mountRef.current.clientHeight;

      // Scene
      const scene    = new THREE.Scene();
      scene.background = new THREE.Color(0x0A0B0F);

      // Camera
      const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
      camera.position.set(0, 0, 5);

      // Renderer
      renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(w, h);
      mountRef.current.appendChild(renderer.domElement);

      // Building box — front face is the facade
      const geometry = new THREE.BoxGeometry(3, 4, 1);
      const loader   = new THREE.TextureLoader();

      const facadeTex = mosaicUrl
        ? loader.load(mosaicUrl)
        : null;

      const materials = [
        new THREE.MeshStandardMaterial({ color: 0x888888 }), // right
        new THREE.MeshStandardMaterial({ color: 0x888888 }), // left
        new THREE.MeshStandardMaterial({ color: 0x888888 }), // top
        new THREE.MeshStandardMaterial({ color: 0x888888 }), // bottom
        new THREE.MeshStandardMaterial({                      // front = facade
          map: facadeTex || null,
          color: facadeTex ? 0xffffff : 0xAAAAAA
        }),
        new THREE.MeshStandardMaterial({ color: 0x888888 }), // back
      ];

      const building = new THREE.Mesh(geometry, materials);
      scene.add(building);

      // Lighting
      scene.add(new THREE.AmbientLight(0xffffff, 0.6));
      const dir = new THREE.DirectionalLight(0xffffff, 0.8);
      dir.position.set(5, 5, 5);
      scene.add(dir);

      // Defect markers on front face
      const SEVERITY_COLOR = {
        critical: 0xFF0000,
        severe:   0xFF6B35,
        moderate: 0xF59E0B,
        minor:    0x4F7EFF,
        hairline: 0x22C55E,
      };

      const markerGroup = new THREE.Group();
      defects.forEach(d => {
        // Map centroid to face coordinates (-1.5 to 1.5, -2 to 2)
        const fx = ((d.centroid_x_norm || 0.5) - 0.5) * 3;
        const fy = ((0.5 - (d.centroid_y_norm || 0.5))) * 4;

        const color  = SEVERITY_COLOR[d.severity_class] || 0xffffff;
        const sphere = new THREE.Mesh(
          new THREE.SphereGeometry(0.04, 8, 8),
          new THREE.MeshStandardMaterial({
            color,
            emissive: color,
            emissiveIntensity: 0.6
          })
        );
        sphere.position.set(fx, fy, 0.51);
        sphere.userData = { defectId: d.defect_id };
        markerGroup.add(sphere);
      });
      scene.add(markerGroup);

      // Rebar wireframe overlay (orange cylinders)
      // Shown inside the box at cover depth
      const rebarMat = new THREE.MeshStandardMaterial({
        color: 0xFF8C00, wireframe: false, transparent: true, opacity: 0.5
      });
      for (let i = -1; i <= 1; i += 0.4) {
        const cyl = new THREE.Mesh(
          new THREE.CylinderGeometry(0.012, 0.012, 4, 6),
          rebarMat
        );
        cyl.position.set(i, 0, 0.3);
        scene.add(cyl);
      }

      // Mouse orbit (manual, no OrbitControls dependency)
      let isDragging = false, prevX = 0, prevY = 0;
      renderer.domElement.addEventListener("mousedown", e => {
        isDragging = true; prevX = e.clientX; prevY = e.clientY;
      });
      window.addEventListener("mouseup",   () => { isDragging = false; });
      window.addEventListener("mousemove", e => {
        if (!isDragging) return;
        building.rotation.y += (e.clientX - prevX) * 0.01;
        building.rotation.x += (e.clientY - prevY) * 0.01;
        markerGroup.rotation.y = building.rotation.y;
        markerGroup.rotation.x = building.rotation.x;
        prevX = e.clientX; prevY = e.clientY;
      });

      // Click raycasting for defect selection
      renderer.domElement.addEventListener("click", e => {
        const rect   = renderer.domElement.getBoundingClientRect();
        const mouse  = new THREE.Vector2(
          ((e.clientX - rect.left)  / rect.width)  *  2 - 1,
          -((e.clientY - rect.top) / rect.height) *  2 + 1
        );
        const raycaster = new THREE.Raycaster();
        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObjects(markerGroup.children);
        if (hits.length > 0) {
          const id = hits[0].object.userData.defectId;
          onDefectClick?.(id);
        }
      });

      // Animate
      const animate = () => {
        animId = requestAnimationFrame(animate);
        renderer.render(scene, camera);
      };
      animate();
    }

    init();

    return () => {
      cancelAnimationFrame(animId);
      if (mountRef.current && renderer) {
        mountRef.current.removeChild(renderer.domElement);
        renderer.dispose();
      }
    };
  }, [defects, mosaicUrl]);

  return (
    <div
      ref={mountRef}
      style={{ width: "100%", height: "420px", borderRadius: "12px", overflow: "hidden" }}
      aria-label="3D structural view"
    />
  );
}
