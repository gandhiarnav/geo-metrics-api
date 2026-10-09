# Screenshot Assets Guide

This directory stores visual verification assets referenced in the root `README.md`.

## Recommended Screenshots to Add

| File Name | Recommended Content | Why It Stands Out |
|---|---|---|
| `google_earth_polygon.png` | Google Earth Desktop or Web Polygon Measure tool showing perimeter (m) and area (m² or ha) for `2houseand1garden` or `Law-college`. | Proves the ground truth reference baseline. |
| `api_measurement_response.png` | Live API JSON response from `GET /api/files/{id}/measurements/` showing `area_sq_m: 788.11` and `perimeter_m: 124.38`. | Demonstrates exact mathematical match down to the centimeter. |
| `google_earth_walk.png` | Google Earth Ruler tool measuring the distance along `walk from one place to college ground` (~898 m). | Confirms linear feature distance accuracy. |
| `swagger_ui_execute.png` | Interactive OpenAPI Swagger UI (`/docs`) showing `POST /api/files/` file upload execution with `201 Created`. | Highlights API ease-of-use and interactive documentation. |
| `swagger_metrics_response.png` | Swagger UI showing `GET /api/files/{id}/measurements/` with whole-file SQL aggregate summary. | Demonstrates database persistence and SQL aggregation. |

## Screenshot Capture Best Practices
- **Format:** PNG or WebP for crisp text.
- **Framing:** Crop cleanly to the relevant window / dialog modal without unnecessary desktop clutter.
- **Resolution:** 1080p or retina scale so numbers are easily legible.
- **Theme:** Consistent dark or light theme between Google Earth and browser devtools / Swagger UI.
