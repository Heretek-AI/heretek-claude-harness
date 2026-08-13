---
name: globe-component
description: Peace-History 3D globe + MapLibre map rendering primitives (react-globe.gl, MapLibre GL, Three.js, Zustand)
user_invocable: false
---

# Globe + Map Component Patterns

How the `web/` workspace renders geographic data. Load this when working on any file under `web/src/**` that touches the globe, map, or related state.

## Stack

| Layer | Library | Purpose |
|---|---|---|
| Globe | `react-globe.gl` ^2.38 | 3D point/polyline rendering on a Cesium-backed canvas |
| Map | `maplibre-gl` ^5.6 | 2D vector basemap |
| 3D primitives | `three` ^0.184 | Custom meshes, polygon extrusion via `@turf/turf` |
| State | `zustand` ^5 | Global UI + selection state |
| Geo math | `@turf/turf` (backend) + `polylabel` | Polygon labeling, distance, bbox |

## Component conventions

- **Globe container** lives in `web/src/components/globe/`. It is a client component (`"use client"`) — WebGL requires DOM.
- **Map container** lives in `web/src/components/map/`. Same client boundary.
- **Data flow**: server fetches via Fastify WebSocket → Zustand store → component reads from store. Never prop-drill geo data through more than one level.
- **Camera state** belongs to the local component (`useRef`), not the store. Recenter triggers re-render only of the camera ref consumer.

## Rendering rules

1. **Point layers**: cap at 10k visible points. Above that, switch to `pointsMergeGeometry` or aggregate.
2. **Polygons**: use `polylabel` (backend precomputed) for label anchor, not centroid — better visual placement for irregular shapes.
3. **Polylines** (borders, routes): prefer `polygonsData` with extrusion when you need fill; `arcsData` for connections.
4. **Auto-rotate**: off by default. Toggleable, but stop on first user interaction (mousedown/touchstart).
5. **Lighting**: globe.gl default is fine. Custom `three` scenes use one ambient + one directional from the same angle the camera is heading.

## Performance budget

- Initial globe render: < 2s on mid-range laptop.
- Pan/zoom: 60fps target. If frame budget blows, the culprit is almost always: (a) point count, (b) ring/pulse animation, (c) on-hover HTML overlays. Fix in that order.

## A11y

- Globe and map are visual-only — every interaction must have a parallel keyboard-accessible list view.
- Provide a `<select>` or button group as the primary control surface; treat the 3D view as decoration with `aria-hidden="true"` once the list control is in place.
- Color-only encodings: never. Always pair color with shape or label for state.

## State names (Zustand)

The store uses these slice names — do not rename without a migration:

- `selection` — currently selected entity
- `timeRange` — `from`/`to` ISO timestamps for time-filtered layers
- `layers` — visibility map per layer id
- `camera` — `{ lat, lng, altitude }` only when user-driven; do not store animation-driven camera
