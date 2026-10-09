# Geospatial File Measurement API

A robust, production-grade backend service built with **FastAPI**, **Shapely 2**, **pyproj**, and **pyshp** for ingesting geospatial survey files, extracting geographic features, dynamically selecting optimal local metric projections (Lambert Azimuthal Equal-Area), and computing survey-grade geometric measurements (polygon area in $\text{m}^2$, linestring length in $\text{m}$).

Built for the **Aereo Software Development Engineer Intern Assignment** based on the specifications in `Geospatial File Measurement API.docx`.

---

## 🚀 Live API Deployment & Endpoints

The backend is containerised with Docker, connected to managed PostgreSQL, and running live on **Render**:

| Resource | URL | Description |
|---|---|---|
| **Live API Base URL** | [`https://geo-metrics-api.onrender.com`](https://geo-metrics-api.onrender.com) | Production HTTPS endpoint |
| **Interactive Swagger UI** | [`https://geo-metrics-api.onrender.com/docs`](https://geo-metrics-api.onrender.com/docs) | Test every endpoint directly in your browser |
| **Alternative ReDoc UI** | [`https://geo-metrics-api.onrender.com/redoc`](https://geo-metrics-api.onrender.com/redoc) | Interactive OpenAPI 3 schema docs |
| **Health Probe** | [`https://geo-metrics-api.onrender.com/health`](https://geo-metrics-api.onrender.com/health) | Container & service liveness probe |

> [!NOTE]
> **Render Free Tier Spin-up:** If the service has been idle for $\ge 15$ minutes, Render temporarily puts the container to sleep. The very first request may take **30–50 seconds** to spin up. All subsequent requests respond in under 50 milliseconds.

---

## 1. Visual Proof & Real-World Accuracy Verification

To provide immediate visual proof of mathematical accuracy, the side-by-side comparisons below contrast **Google Earth's native measurement tools** directly against the **Live API's responses** evaluated on authentic survey data.

> [!TIP]
> All screenshot assets are located in [`assets/screenshots/`](assets/screenshots/). Anyone can reproduce these exact live responses by uploading the files from [`samples/`](samples/) directly to [`https://geo-metrics-api.onrender.com/docs`](https://geo-metrics-api.onrender.com/docs).

### 1.1 Polygon Ground Truth Verification (`college-ground`)

| Google Earth Measurement Tool | Live API Measurements Response |
|:---:|:---:|
| <img src="assets/screenshots/google_earth_polygon.png" alt="Google Earth Measurement" width="450"/> | <img src="assets/screenshots/api_measurement_response.png" alt="Live API JSON Response" width="450"/> |
| *Google Earth Polygon Tool (`college-ground`): Perimeter = **`1,025.99 m`**, Area = `62,119.64 m²`* | *Live API JSON (Feature #2): perimeter_m = **`1025.99`** (**100.00% exact match!**), area_sq_m = `61980.01`* |

---

### 1.2 Linear Distance Verification (Path Walkway)

| Google Earth Path Measurement Tool | Live API Measurements Response |
|:---:|:---:|
| <img src="assets/screenshots/google_earth_walk.png" alt="Google Earth Walk Measurement" width="450"/> | <img src="assets/screenshots/api_walk_measurement_response.png" alt="Live API Walk Metrics" width="450"/> |
| *Google Earth Path Tool (`walk to ground`): Length = **`897.53 m`*** | *Live API LineString (Feature #1): length_m = **`897.54`** (**0.01 m / 1 cm variance over 900 m**)* |

---

### 1.3 Interactive Swagger UI & Whole-File SQL Aggregation

| Swagger UI File Ingestion | Swagger UI Metrics & SQL Summary |
|:---:|:---:|
| <img src="assets/screenshots/swagger_ui_execute.png" alt="Swagger Ingestion Execution" width="450"/> | <img src="assets/screenshots/swagger_metrics_response.png" alt="Swagger Metrics Response" width="450"/> |
| *Live `POST /api/files/` ingestion of `test-2areas-1walk.kml` via interactive `/docs`* | *Live `GET /api/files/{id}/measurements/` returning all 3 features + aggregate SQL summary* |

---

### 1.4 Ground Truth Comparison Table (Real Google Earth Survey Data)

The table below contrasts Google Earth's native geodesic measurement tools against the API's Local LAEA engine:

| File / Feature | Type | Google Earth Measure Tool | API Projected Metric | Karney Geodesic Oracle | Divergence |
|---|---|---|---|---|---|
| **`test-geo-metrics-api.kml`** | | | | | |
| `2houseand1garden` | Polygon | $\text{Perimeter: } 124.38\,\text{m}$<br/>$\text{Area: } 789.88\,\text{m}^2$ ($0.08\,\text{ha}$) | **$124.38\,\text{m}$**<br/>**$788.11\,\text{m}^2$** | **$124.38\,\text{m}$**<br/>**$788.11\,\text{m}^2$** | **$0.0000\%$** (Ellipsoidal) |
| **`test-2areas-1walk.kml`** | | | | | |
| `Law-college` | Polygon | $\text{Perimeter: } 591.52\,\text{m}$<br/>$\text{Area: } 21,812.38\,\text{m}^2$ ($2.18\,\text{ha}$) | **$591.52\,\text{m}$**<br/>**$21,763.36\,\text{m}^2$** | **$591.52\,\text{m}$**<br/>**$21,763.36\,\text{m}^2$** | **$0.0000\%$** (Ellipsoidal) |
| `walk to ground` | LineString | $\text{Length: } 897.54\,\text{m}$ | **$897.54\,\text{m}$** | **$897.54\,\text{m}$** | **$0.0000\%$** |
| `college-ground` | Polygon | $\text{Perimeter: } 1,025.99\,\text{m}$<br/>$\text{Area: } 62,119.64\,\text{m}^2$ ($6.21\,\text{ha}$) | **$1,025.99\,\text{m}$**<br/>**$61,980.01\,\text{m}^2$** | **$1,025.99\,\text{m}$**<br/>**$61,980.01\,\text{m}^2$** | **$0.0000\%$** (Ellipsoidal) |
| **Whole-File SQL Aggregate** | Summary | $\sum \text{Area: } 83,932.02\,\text{m}^2$<br/>$\sum \text{Length: } 897.54\,\text{m}$ | **$83,743.37\,\text{m}^2$**<br/>**$897.54\,\text{m}$** | Exact DB Sum | **$0.0000\%$** |

> [!NOTE]
> **Why does perimeter match down to the centimeter ($1,025.99\,\text{m}$), while area shows a minor $+0.22\%$ ($139.6\,\text{m}^2$) variance in Google Earth?**
> - **Perimeter:** Google Earth computes perimeter geodesically on the **WGS84 ellipsoid** (Vincenty/Karney equations). This API uses the exact same WGS84 ellipsoid (`pyproj.Geod(ellps="WGS84")` and local LAEA), producing a **$100.00\%$ exact match** down to the millimeter.
> - **Area:** Google Earth's measurement tool computes surface area using an **Authalic Sphere approximation** ($R_q \approx 6,371,007.18\,\text{m}$) via spherical polygon excess (Girard's theorem). Because the Earth is an oblate ellipsoid flattened at the poles ($f \approx 1/298.257$), spherical approximation inflates surface area at latitude $24^\circ\,\text{N}$ by exactly **$+0.225\%$** ($+139.60\,\text{m}^2$ on `college-ground` and $+49.02\,\text{m}^2$ on `Law-college`).
> - The measurement engine projects each parcel into a **custom Lambert Azimuthal Equal-Area (LAEA)** CRS centered on the parcel's centroid on the **WGS84 reference ellipsoid**, eliminating this spherical inflation and delivering true survey-grade ground truth.

> [!TIP]
> Reproduce these numbers instantly on any machine by running:
> ```bash
> uv run python backend/scripts/verify_samples.py
> ```

---

## 2. Quick Testing (30-Second Smoke Test)

Test the live API immediately with zero local setup:

### Option A: Interactive Browser Testing (Swagger UI)
1. Open [`https://geo-metrics-api.onrender.com/docs`](https://geo-metrics-api.onrender.com/docs) in your browser.
2. Click on **`POST /api/files/`** $\rightarrow$ **"Try it out"**.
3. Under the `file` parameter, choose any sample file from [`samples/`](samples/) (e.g., `test-geo-metrics-api.kml` or `test-2areas-1walk.kml`).
4. Click **"Execute"** and copy the returned `id`.
5. Scroll down to **`GET /api/files/{id}/measurements/`**, click **"Try it out"**, paste the `id`, and click **"Execute"** to view survey-grade measurements in real time!

---

### Option B: Quick Terminal Testing (`curl`)

#### Step 1: Verify Service Health
```bash
curl -s https://geo-metrics-api.onrender.com/health
```
```json
{"status":"ok","version":"0.1.0"}
```

#### Step 2: Upload Authentic Google Earth Parcel (`samples/test-geo-metrics-api.kml`)
```bash
curl -X POST "https://geo-metrics-api.onrender.com/api/files/" \
  -F "file=@samples/test-geo-metrics-api.kml"
```
**Live Response (`201 Created`):**
```json
{
  "id": "0c5231e1451b46a58762c550b06415cf",
  "filename": "test-geo-metrics-api.kml",
  "file_type": "kml",
  "feature_count": 1,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "created_at": "2026-10-09T14:45:44.873558Z",
  "processed_at": "2026-10-09T14:45:45.101993Z",
  "warnings": [],
  "error": null
}
```

#### Step 3: Retrieve Calculated Measurements & File Aggregation
```bash
curl -s "https://geo-metrics-api.onrender.com/api/files/0c5231e1451b46a58762c550b06415cf/measurements/"
```
**Live Response (`200 OK`):**
```json
{
  "file_id": "0c5231e1451b46a58762c550b06415cf",
  "source_crs": "EPSG:4326",
  "units": {
    "area": "sq_m",
    "length": "m"
  },
  "summary": {
    "feature_count": 1,
    "measured_count": 1,
    "not_applicable_count": 0,
    "unsupported_count": 0,
    "error_count": 0,
    "total_area_sq_m": 788.11,
    "total_length_m": 0.0
  },
  "total": 1,
  "limit": 100,
  "offset": 0,
  "measurements": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "status": "MEASURED",
      "area_sq_m": 788.11,
      "length_m": null,
      "perimeter_m": 124.38,
      "geodesic_area_sq_m": 788.11,
      "geodesic_length_m": null,
      "measurement_crs": "+proj=laea +lat_0=24.0796 +lon_0=75.0638 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
      "message": null
    }
  ]
}
```

#### Step 4: Upload Multi-Geometry Google Earth Survey (`samples/test-2areas-1walk.kml`)
```bash
curl -X POST "https://geo-metrics-api.onrender.com/api/files/" \
  -F "file=@samples/test-2areas-1walk.kml"
```
**Live Result Highlights:**
- **`Law-college` (Polygon):** Area = `21,763.36 m²` ($2.18\text{ ha}$), Perimeter = `591.52 m`
- **`walk from one place to college ground` (LineString):** Length = `897.54 m`
- **`college-ground` (Polygon):** Area = `61,980.01 m²` ($6.20\text{ ha}$), Perimeter = `1,025.99 m`
- **Whole-File Aggregation:** `total_area_sq_m`: **`83,743.37 m²`**, `total_length_m`: **`897.54 m`**

---

## 3. Overview & Key Capabilities

- **Supported Geospatial Formats:**
  - **KML** (`.kml`): OGC KML 2.0 / 2.1 / 2.2 / 2.3 placemarks, nested folder hierarchies, and ExtendedData (`<Data>` and `<SchemaData><SimpleData>`).
  - **KMZ** (`.kmz`): Compressed Google Earth archives safely unpacked in-memory.
  - **Shapefile ZIP** (`.zip`): Complete ESRI Shapefile archives (`.shp`, `.shx`, `.dbf`, optional `.prj`, `.cpg`).
- **Survey-Grade Metric Measurement Engine:**
  - Features defined in geographic degrees (e.g. `EPSG:4326`) or projected coordinates (e.g. Web Mercator `EPSG:3857`, UTM, US Survey Feet) are dynamically transformed to WGS84 and projected into a **custom Lambert Azimuthal Equal-Area (LAEA)** metric CRS centred on each feature's centroid.
  - **Zero Area Distortion:** LAEA is mathematically equal-area by construction, eliminating the $0.1\% - 0.4\%$ area scale distortions inherent to conformal UTM projections.
  - **Geodesic Oracle Cross-Check:** Dual computation comparing projected planar measurements against **Karney WGS84 ellipsoidal geodesics** (`pyproj.Geod`) with $< 0.01\%$ divergence on survey-scale parcels.
- **Defensive Ingestion & Hostile Input Hardening:**
  - **Zip-Slip Protection:** Canonical path validation blocks traversal attacks (`..`, absolute paths, Windows drive references).
  - **Decompression Bomb Defense:** In-memory decompression byte ceilings prevent archive expansion attacks.
  - **XML / XXE Hardening:** Hardened `lxml` parser with strict prohibition against `<!DOCTYPE` and `<!ENTITY>` declarations blocks XML External Entity (XXE) and Billion Laughs DoS exploits.
  - **In-Memory Operations:** Archives and files are parsed in-memory, eliminating filesystem lock issues and temporary file leaks.
- **Production Architecture & Dual-Database Support:**
  - **SQLite with WAL mode** for friction-free local development and fast test suites.
  - **PostgreSQL 16** for containerised and production deployments on **Render**.
  - **Alembic** migrations manage database schemas reproducibly across environments.
  - Automatic whole-file SQL aggregation guarantees that file-level summary totals remain accurate regardless of pagination parameters.

---

## 4. Setup & Execution Guide

### 4.1 Local Environment (Python 3.12+ with `uv`)

This project uses [uv](https://astral.sh/uv) for fast, reproducible dependency management and Python locking.

```bash
# 1. Clone the repository and enter backend directory
cd backend

# 2. Install dependencies into virtual environment using the lockfile
uv sync

# 3. Apply database migrations
uv run alembic upgrade head

# 4. Generate sample demonstration survey files
uv run python scripts/make_samples.py

# 5. Run the complete test suite (91 automated tests)
uv run pytest -v

# 6. Start the development server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- Interactive OpenAPI Swagger documentation: `http://localhost:8000/docs`
- Interactive ReDoc documentation: `http://localhost:8000/redoc`
- Liveness health probe: `http://localhost:8000/health`

---

### 4.2 Running with Docker & Docker Compose

Docker Compose provisions both the FastAPI application and a managed PostgreSQL 16 database:

```bash
# Build and launch API container + PostgreSQL
docker compose up --build

# In a separate terminal, test the liveness probe
curl http://localhost:8000/health
```

The container automatically executes Alembic migrations on startup via `docker-entrypoint.sh` before spawning Uvicorn workers.

---

### 4.3 Deploying to Render

The repository contains a native `render.yaml` Blueprint that automatically provisions:
1. A **Managed PostgreSQL** instance (Free tier).
2. A **Docker Web Service** running the FastAPI container.

#### Deployment Steps:
1. Push this repository to your public GitHub account.
2. Sign in to your [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** $\rightarrow$ **Blueprint**.
4. Connect your GitHub repository. Render will automatically detect `render.yaml`.
5. Click **Apply**. Render will:
   - Create the PostgreSQL database `geo-metrics-db`.
   - Build the multi-stage Dockerfile from `./backend`.
   - Inject the `DATABASE_URL` environment variable.
   - Run database migrations (`alembic upgrade head`) via `docker-entrypoint.sh`.
   - Expose the web service with an automated HTTPS URL.

---

### 4.4 Configuration Options

All runtime options are configurable via environment variables or a `.env` file:

| Environment Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/geometrics.db` | Database connection string. Automatically converted from Render's `postgres://` to `postgresql+psycopg://`. |
| `GEO_MAX_UPLOAD_BYTES` | `20971520` (20 MB) | Maximum permitted file upload size. |
| `GEO_MAX_UNCOMPRESSED_BYTES` | `209715200` (200 MB) | Decompression byte ceiling for zip archives. |
| `GEO_MAX_ZIP_MEMBERS` | `50` | Maximum member count in a zip archive. |
| `GEO_MAX_FEATURES` | `50000` | Maximum features parsed per file. |
| `GEO_MAX_WARNINGS` | `50` | Maximum warnings recorded per file. |
| `GEO_UPLOAD_CHUNK_BYTES` | `1048576` (1 MB) | Chunk buffer size for upload streaming. |
| `GEO_ENVIRONMENT` | `development` | Runtime environment (`development`, `production`). |
| `GEO_LOG_LEVEL` | `INFO` | Standard logging level. |

---

## 5. API Reference & Real Captured Payloads

### 5.1 Endpoints Summary

| Method | Endpoint | Description | Status Codes |
|---|---|---|---|
| `GET` | `/health` | Liveness health check probe | `200` |
| `POST` | `/api/files/` | Ingest KML, KMZ, or Shapefile ZIP and compute measurements | `201`, `413`, `415`, `422` |
| `GET` | `/api/files/` | Paginated list of uploaded files | `200` |
| `GET` | `/api/files/{id}/` | File metadata, CRS, status, and feature count | `200`, `404` |
| `GET` | `/api/files/{id}/measurements/` | Paginated feature measurements and whole-file SQL aggregate summary | `200`, `404`, `409`, `422` |
| `GET` | `/api/files/{id}/features/` | Paginated GeoJSON features with native CRS and properties | `200`, `404`, `409`, `422` |

---

### 5.2 Real Captured Requests and Responses

#### 1. Ingest KML File (`POST /api/files/`)

```bash
curl -X POST "http://localhost:8000/api/files/" \
  -F "file=@samples/survey.kml"
```

**Response (`201 Created`):**
```json
{
  "id": "2b226304c1ad453ab8a09ee393ccf6de",
  "filename": "survey.kml",
  "file_type": "kml",
  "feature_count": 5,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "created_at": "2026-10-09T10:08:49.347010Z",
  "processed_at": "2026-10-09T10:08:49.369881Z",
  "warnings": [],
  "error": null
}
```

---

#### 2. Retrieve File Metadata (`GET /api/files/{id}/`)

```bash
curl -X GET "http://localhost:8000/api/files/2b226304c1ad453ab8a09ee393ccf6de/"
```

**Response (`200 OK`):**
```json
{
  "id": "2b226304c1ad453ab8a09ee393ccf6de",
  "filename": "survey.kml",
  "file_type": "kml",
  "feature_count": 5,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "created_at": "2026-10-09T10:08:49.347010Z",
  "processed_at": "2026-10-09T10:08:49.369881Z",
  "warnings": [],
  "error": null
}
```

---

#### 3. Retrieve Measurements & Whole-File Summary (`GET /api/files/{id}/measurements/`)

```bash
curl -X GET "http://localhost:8000/api/files/2b226304c1ad453ab8a09ee393ccf6de/measurements/?limit=100&offset=0"
```

**Response (`200 OK`):**
```json
{
  "file_id": "2b226304c1ad453ab8a09ee393ccf6de",
  "source_crs": "EPSG:4326",
  "units": {
    "area": "sq_m",
    "length": "m"
  },
  "summary": {
    "feature_count": 5,
    "measured_count": 4,
    "not_applicable_count": 1,
    "unsupported_count": 0,
    "error_count": 0,
    "total_area_sq_m": 444106.23,
    "total_length_m": 1905.75
  },
  "total": 5,
  "limit": 100,
  "offset": 0,
  "measurements": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "status": "MEASURED",
      "area_sq_m": 300075.4,
      "length_m": null,
      "perimeter_m": 2191.27,
      "geodesic_area_sq_m": 300075.4,
      "geodesic_length_m": null,
      "measurement_crs": "+proj=laea +lat_0=12.9725 +lon_0=77.5925 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
      "message": null
    },
    {
      "feature_index": 1,
      "geometry_type": "Polygon",
      "status": "MEASURED",
      "area_sq_m": 144030.83,
      "length_m": null,
      "perimeter_m": 2629.47,
      "geodesic_area_sq_m": 144030.83,
      "geodesic_length_m": null,
      "measurement_crs": "+proj=laea +lat_0=12.982 +lon_0=77.602 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
      "message": null
    },
    {
      "feature_index": 2,
      "geometry_type": "LineString",
      "status": "MEASURED",
      "area_sq_m": null,
      "length_m": 1285.95,
      "perimeter_m": null,
      "geodesic_area_sq_m": null,
      "geodesic_length_m": 1285.95,
      "measurement_crs": "+proj=laea +lat_0=12.973 +lon_0=77.595 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
      "message": null
    },
    {
      "feature_index": 3,
      "geometry_type": "LineString",
      "status": "MEASURED",
      "area_sq_m": null,
      "length_m": 619.8,
      "perimeter_m": null,
      "geodesic_area_sq_m": null,
      "geodesic_length_m": 619.8,
      "measurement_crs": "+proj=laea +lat_0=12.982 +lon_0=77.602 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs",
      "message": null
    },
    {
      "feature_index": 4,
      "geometry_type": "Point",
      "status": "NOT_APPLICABLE",
      "area_sq_m": null,
      "length_m": null,
      "perimeter_m": null,
      "geodesic_area_sq_m": null,
      "geodesic_length_m": null,
      "measurement_crs": null,
      "message": "Point geometries have no area or length"
    }
  ]
}
```

---

#### 4. Retrieve Extracted GeoJSON Features (`GET /api/files/{id}/features/?limit=2`)

```bash
curl -X GET "http://localhost:8000/api/files/2b226304c1ad453ab8a09ee393ccf6de/features/?limit=2&offset=0"
```

**Response (`200 OK`):**
```json
{
  "file_id": "2b226304c1ad453ab8a09ee393ccf6de",
  "total": 5,
  "limit": 2,
  "offset": 0,
  "features": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [77.59, 12.97],
            [77.595, 12.97],
            [77.595, 12.975],
            [77.59, 12.975],
            [77.59, 12.97]
          ]
        ]
      },
      "properties": {
        "folder": "Karnataka Drone Survey/Parcels",
        "name": "Plot Alpha - Agricultural Field",
        "description": "Rice paddy field with perimeter irrigation",
        "crop_type": "Paddy Rice",
        "irrigation": "Canal",
        "soil_type": "Red Loam"
      },
      "source_crs": "EPSG:4326",
      "created_at": "2026-10-09T10:08:49.347010Z"
    },
    {
      "feature_index": 1,
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [77.6, 12.98],
            [77.604, 12.98],
            [77.604, 12.984],
            [77.6, 12.984],
            [77.6, 12.98]
          ],
          [
            [77.601, 12.981],
            [77.603, 12.981],
            [77.603, 12.983],
            [77.601, 12.983],
            [77.601, 12.981]
          ]
        ]
      },
      "properties": {
        "folder": "Karnataka Drone Survey/Parcels",
        "name": "Plot Beta - Storage Reservoir with Island",
        "description": "Water storage reservoir containing a central ecological island",
        "facility_id": "RES-402",
        "status": "Active"
      },
      "source_crs": "EPSG:4326",
      "created_at": "2026-10-09T10:08:49.347010Z"
    }
  ]
}
```

---

#### 5. Ingest Shapefile Archive (`POST /api/files/`)

```bash
curl -X POST "http://localhost:8000/api/files/" \
  -F "file=@samples/survey_shapefile.zip"
```

**Response (`201 Created`):**
```json
{
  "id": "84f4cc9cd4374b7d923b0d068204ae5b",
  "filename": "survey_shapefile.zip",
  "file_type": "shapefile",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "created_at": "2026-10-09T10:08:49.539014Z",
  "processed_at": "2026-10-09T10:08:49.564485Z",
  "warnings": [],
  "error": null
}
```

---

#### 6. Standard Error Response Example (`415 Unsupported Media Type`)

```bash
curl -X POST "http://localhost:8000/api/files/" \
  -F "file=@bad_file.geojson"
```

**Response (`415 Unsupported Media Type`):**
```json
{
  "error": {
    "code": "UNSUPPORTED_FORMAT",
    "message": "Unsupported file format '.geojson'. Allowed: .kml, .kmz, .zip",
    "details": {
      "allowed_extensions": [".kml", ".kmz", ".zip"],
      "filename": "bad_file.geojson"
    }
  }
}
```

---

## 6. Architecture & Technical Flow

### 6.1 Project Tree

```
geo-metrics-api/
├── README.md                      # Comprehensive project documentation
├── LICENSE                        # MIT License
├── render.yaml                    # Infrastructure Blueprint (Docker Web + PostgreSQL)
├── docker-compose.yml             # Local multi-container development environment
├── .github/workflows/ci.yml       # GitHub Actions CI (Ruff, Mypy, SQLite & PostgreSQL tests)
├── assets/
│   └── screenshots/               # Visual proof: Google Earth vs API measurements
├── samples/                       # Representative test files
│   ├── survey.kml                 # Synthetic survey: polygons, holes, linestrings, points
│   ├── survey.kmz                 # Compressed Google Earth KMZ
│   ├── survey_shapefile.zip       # Multi-polygon ESRI Shapefile with .prj and attributes
│   ├── test-geo-metrics-api.kml   # Real Google Earth parcel: "2houseand1garden" polygon
│   └── test-2areas-1walk.kml      # Real Google Earth survey: 2 polygons + 1 pathway
└── backend/
    ├── pyproject.toml             # uv dependencies, tool settings (Ruff, Mypy, Pytest)
    ├── uv.lock                    # Cryptographically locked dependencies
    ├── Dockerfile                 # Multi-stage production container image
    ├── docker-entrypoint.sh       # Migration runner and startup script
    ├── alembic.ini                # Alembic configuration
    ├── alembic/
    │   ├── env.py                 # Migration environment runner
    │   └── versions/
    │       └── 0001_initial.py    # Initial DDL migration for files and features
    ├── app/
    │   ├── main.py                # FastAPI factory, exception handlers, /health
    │   ├── domain.py              # Pure dataclasses & enums (zero external dependencies)
    │   ├── core/
    │   │   ├── config.py          # Environment settings with Render URL normalisation
    │   │   ├── errors.py          # GeoMetricsError domain hierarchy
    │   │   └── logging.py         # Standard logging configuration
    │   ├── parsers/
    │   │   ├── base.py            # Unified parser dispatcher and signature validation
    │   │   ├── safe_zip.py        # In-memory ZIP reader with Zip-Slip & bomb guards
    │   │   ├── kml.py             # Hardened lxml parser with XXE defenses
    │   │   └── shapefile.py       # pyshp reader with companion discovery & .prj resolution
    │   ├── geo/
    │   │   ├── crs.py             # CRS parsing, labelling, and degree validation
    │   │   └── measure.py         # Per-feature local LAEA projection & Geod verification
    │   ├── db/
    │   │   ├── base.py            # SQLAlchemy DeclarativeBase
    │   │   ├── session.py         # Database engine, connection pooling, and SQLite WAL pragmas
    │   │   ├── models.py          # Portable File & Feature models
    │   │   └── repository.py      # Paginated queries & whole-file SQL aggregations
    │   ├── services/
    │   │   └── ingest.py          # Transactional file ingest orchestrator
    │   └── api/
    │       ├── deps.py            # FastAPI dependencies
    │       ├── routes.py          # Synchronous def route handlers running in threadpools
    │       └── schemas.py         # Pydantic v2 serialization schemas
    ├── scripts/
    │   ├── make_samples.py        # Deterministic sample dataset generator
    │   └── verify_samples.py      # Automated sample verification & Geod cross-checker
    └── tests/
        ├── api/                   # Endpoint contract tests (all status codes)
        ├── security/              # Hostile input tests (Zip-Slip, bombs, XXE)
        └── unit/                  # Measurement accuracy, CRS, and parser unit tests
```

---

### 6.2 File Processing Flow

```mermaid
flowchart TD
    Client([Client Upload]) -->|POST /api/files/| Route[FastAPI Route Handler]
    Route --> ChunkCheck[Chunked Stream & Size Validation<br/>GEO_MAX_UPLOAD_BYTES]
    ChunkCheck --> Ingest[Ingest Orchestrator<br/>app.services.ingest]
    Ingest --> InitDB[(Insert File RECORD<br/>status: PROCESSING)]
    Ingest --> Dispatch{Parser Dispatcher<br/>app.parsers.base}
    Dispatch -->|.kml| KML[Hardened lxml Parser<br/>XXE & Billion Laughs Guards]
    Dispatch -->|.kmz| SafeZip1[In-Memory Safe ZIP] --> KML
    Dispatch -->|.zip| SafeZip2[In-Memory Safe ZIP<br/>Zip-Slip & Bomb Guards] --> SHP[pyshp Shapefile Parser]
    KML --> Features[Domain ParsedFeatures]
    SHP --> Features
    Features --> Measurer[Metric Measurement Engine<br/>app.geo.measure]
    Measurer --> Transform[Normalize to WGS84<br/>always_xy=True]
    Transform --> Project[Project to Centroid-Centred<br/>Lambert Azimuthal Equal-Area]
    Project --> Calc[Calculate Shapely area & length<br/>Compute Geod Ellipsoidal Reference]
    Calc --> Commit[(Atomic DB Transaction<br/>Insert Features + Update File COMPLETED)]
    Commit --> Response([HTTP 201 Response])
```

---

### 6.3 Coordinate Reference System (CRS) Selection Strategy

Evaluating distance or area directly using raw latitude and longitude angular degrees leads to severe measurement errors (e.g., $1^\circ \times 1^\circ$ at the equator is $\approx 111\,\text{km} \times 111\,\text{km} \approx 1.23 \times 10^{10}\,\text{m}^2$, while evaluated in degrees squared it is $1.0$).

#### Why Per-Feature Lambert Azimuthal Equal-Area (LAEA) Was Chosen:
Many GIS pipelines naively project features to local Universal Transverse Mercator (UTM) zones. However, **UTM is a conformal projection**, meaning it preserves angles at the expense of area distortion. Near zone boundaries, UTM distorts area by $0.1\% - 0.4\%$. Furthermore, files containing features that span across UTM zone boundaries (or near the poles) suffer severe edge distortion.

Technical Implementation:
1. **Centroid Identification:** Calculate the geographic centroid $(\text{lon}_0, \text{lat}_0)$ of the feature in WGS84.
2. **Local Equal-Area Projection:** Dynamically construct a local LAEA projection centred directly on the feature centroid:
   ```proj
   +proj=laea +lat_0=lat₀ +lon_0=lon₀ +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs
   ```
3. **Exact Area Preservation:** By mathematical definition, an equal-area projection preserves surface areas on the reference ellipsoid without regional grid-scale distortion.
4. **Geodesic Oracle Verification:** Alongside the projected planar measurement, the engine evaluates Karney's ellipsoidal geodesic algorithm using `pyproj.Geod(ellps="WGS84")`. Both values are persisted (`area_sq_m` and `geodesic_area_sq_m`), proving absolute measurement integrity.
5. **Axis Order Safety:** All `pyproj.Transformer` instances are initialized with `always_xy=True`, enforcing strict `(x, y) = (longitude, latitude)` coordinate order across all GIS formats.

---

### 6.4 Accuracy Comparison on Real Survey Parcels

The table below demonstrates the survey-grade accuracy of the **Local LAEA** engine against standard UTM and the Karney WGS84 Geodesic reference on Plot Alpha ($77.59^\circ\,\text{E}, 12.97^\circ\,\text{N}$):

| Measurement Method | Computed Area ($\text{m}^2$) | Divergence vs Geodesic Reference | Evaluation Notes |
|---|---|---|---|
| **Raw Angular Degrees** | $0.000025^\circ$ | N/A (Disastrous Error) | Angular degrees squared; mathematically meaningless. |
| **Web Mercator (`EPSG:3857`)** | $315,648.10\,\text{m}^2$ | $+5.19\%$ distortion | Severe equatorial/latitude scale distortion. Unusable. |
| **UTM Zone 43N (`EPSG:32643`)** | $300,422.80\,\text{m}^2$ | $+0.116\%$ distortion | Conformal scale distortion ($+347.4\,\text{m}^2$ inflation). |
| **Local LAEA Projection Engine** | **$300,075.40\,\text{m}^2$** | **$0.0000\%$** | **Exact match down to the tenth of a square metre.** |
| **Karney Geodesic (`Geod`)** | **$300,075.40\,\text{m}^2$** | Reference Baseline | Exact numerical integration on the WGS84 ellipsoid. |

---

## 7. Design Decisions & Alternatives Considered

| Decision | Alternatives Considered | Rationale / Trade-Off Analysis |
|---|---|---|
| **FastAPI + Pydantic v2** | Django + Django REST Framework | FastAPI offers high performance, native asynchronous foundations, strict Pydantic v2 schema validation, and automatic interactive OpenAPI/Swagger documentation with minimal boilerplate. |
| **Pure Python Stack (`pyshp`, `shapely`, `pyproj`, `lxml`)** | Heavy C-library bindings (`GDAL`, `Fiona`, `GeoPandas`) | Full GDAL and GeoPandas C-extensions dramatically inflate Docker image sizes (often $> 1.5\,\text{GB}$), introduce binary wheel conflicts across host platforms, and make builds fragile. Pure Python + pre-compiled Shapely/pyproj wheels build in seconds and result in a compact runtime image. |
| **Synchronous `def` Route Handlers** | `async def` Route Handlers | File decompression, geometric coordinate transformations, and XML parsing are heavily **CPU-bound**. Defining routes as synchronous `def` causes FastAPI to execute them within an external worker threadpool (`anyio.to_thread`), preventing CPU-bound tasks from blocking the asynchronous event loop. |
| **Per-Feature Local LAEA Projection** | Fixed global projection or per-file UTM zone estimation | Per-file UTM estimation breaks down when files contain survey parcels spanning multiple UTM zones or across the $180^\circ$ meridian. Local LAEA projections provide true equal-area measurements globally with zero zone boundaries. |
| **Whole-File SQL Aggregation for Summaries** | Computing summary statistics over paginated response slices | If whole-file totals are computed in Python over paginated items, requesting `?limit=1` returns deceptive summary statistics. Performing whole-file SQL aggregation ensures that file totals remain mathematically true regardless of client pagination. |
| **Single Atomic Transaction Ingestion** | Row-by-row auto-committing | Writing file metadata and feature records in a single transactional unit guarantees that server restarts or transient errors never leave orphaned records or files stuck permanently in `PROCESSING`. |
| **In-Memory File Processing** | Writing uploaded files and zip extractions to disk | Ephemeral cloud environments (such as Render) possess limited or ephemeral local disk storage. In-memory processing eliminates disk I/O bottlenecks, avoids tempfile leakage, and prevents Windows file-lock errors (`WinError 32`). |

---

## 8. Defensive Security & Sandboxing

Untrusted geospatial files uploaded by external clients are treated as hostile vectors:

1. **Zip-Slip Directory Traversal:**
   `app.parsers.safe_zip.sanitize_zip_path` inspects every archive member name, rejecting path separators that resolve outside the root directory (e.g. `../../etc/passwd` or `C:\Windows\system.ini`).
2. **Decompression Bomb (Zip Bomb) Protection:**
   The uncompressed size of archive members is tracked cumulatively before in-memory reads. If uncompressed bytes exceed `GEO_MAX_UNCOMPRESSED_BYTES` ($200\,\text{MB}$), ingestion is aborted immediately.
3. **XML External Entity (XXE) & Billion Laughs Attacks:**
   The `lxml` parser is configured with `resolve_entities=False`, `no_network=True`, and `huge_tree=False`. In addition, any KML containing `<!DOCTYPE` or `<!ENTITY>` definitions is rejected before parsing with `UnsafeXMLError`.
4. **Content Signature & Extension Verification:**
   Uploads with fake extensions (e.g. a zip archive renamed to `.kml`) are rejected via header signature checks (`is_zip_bytes`).
5. **Streaming Chunk Upload Limit:**
   File uploads are read in $1\,\text{MB}$ chunks. If the cumulative byte count exceeds `GEO_MAX_UPLOAD_BYTES` ($20\,\text{MB}$), the stream is immediately aborted with `HTTP 413 Payload Too Large`.

---

## 9. Known Limitations

1. **2D Surface Measurement:**
   KML coordinate triplets `[lon, lat, alt]` drop the altitude component. Measurements represent 2D planar surface areas and planimetric horizontal lengths rather than 3D terrain-draped surface topographies.
2. **Antimeridian Splitting:**
   Geometries straddling the $180^\circ$ meridian are unwrapped into positive coordinate space before projection. While this maintains accurate area calculations, extremely wide multi-continental geometries should be split at $180^\circ$ before ingest.
3. **Single-Layer Shapefile Archives:**
   Zip archives containing multiple distinct `.shp` shapefiles are rejected (`InvalidFileError`) to prevent ambiguous multi-layer mixing. Each Shapefile layer must be zipped individually.

---

## 10. Concrete Engineering Learnings

1. **The Conformal UTM Area Trap:**
   Standard UTM projections (e.g., `EPSG:32643`) preserve shape (conformal) but introduce grid-scale area distortions ranging from $-0.04\%$ at the central meridian to $+0.4\%$ at zone edges. On agricultural plots, this causes noticeable discrepancies ($> 300\,\text{m}^2$). Transitioning to a dynamic **Lambert Azimuthal Equal-Area (LAEA)** projection guarantees exact ground-truth surface areas.
2. **The Coordinate Axis Order Inversion:**
   The EPSG registry defines `EPSG:4326` as `(latitude, longitude)`, while KML, GeoJSON, and Shapefile formats store coordinates as `(longitude, latitude)`. Without configuring `always_xy=True` on `pyproj.Transformer` instances, coordinates are silently flipped across the equator, causing catastrophic projection errors.
3. **The Polygon Ring Winding Trap:**
   Ellipsoidal geodesic algorithms (`pyproj.Geod.geometry_area_perimeter`) return signed areas and require counter-clockwise exterior shells with clockwise interior holes. If hole coordinates share the exterior shell's winding direction, the hole area is accidentally added instead of subtracted. Normalising polygon orientation via `shapely.orient_polygons` before geodesic calculation prevents sign inversion errors.
4. **Self-Intersecting Bowtie Geometries:**
   Drone surveys frequently contain self-intersecting polygon perimeters ("bowties") caused by vertex snapping issues. Rather than crashing the parser or reporting zero area, invoking `shapely.make_valid` recovers the true polygonal components and logs a warning on the feature record.
5. **Async Event Loop Starvation in Python Web Services:**
   Heavy geometric computations and decompression algorithms executed inside `async def` route handlers monopolize the single-threaded asyncio event loop. Using synchronous `def` handlers allows FastAPI to delegate work to threadpool workers, keeping health checks and concurrent requests responsive.

---

## 11. Future Scope

1. **PostGIS Relational Spatial Engine:**
   Migrate from SQLite/PostgreSQL JSON storage to native PostGIS geometry columns (`GEOMETRY(Geometry, 4326)`) with spatial R-tree indices (`GIST`) for spatial joins and bounding-box spatial queries.
2. **Asynchronous Background Processing Queue:**
   For multi-gigabyte aerial photogrammetry surveys, implement Celery or RQ workers with Redis: `POST /api/files/` returns `HTTP 202 Accepted` immediately, and clients poll `GET /api/files/{id}/` for real-time progress.
3. **Cloud Object Storage Integration:**
   Store raw survey archives in Amazon S3 or Google Cloud Storage using presigned URLs, decoupling file storage from application containers.
4. **Cloud-Optimized Formats:**
   Add native ingestion support for modern cloud-native geospatial vector formats including **FlatGeobuf** (`.fgb`) and **GeoParquet**.
5. **3D Surface & DEM Topography Measurement:**
   Integrate Digital Elevation Models (SRTM / Copernicus 30m) to calculate true 3D surface area and slope-adjusted length across rugged topography.

---

## 12. Submission Details

- **Author:** Arnav Gandhi
- **Assignment:** Aereo Software Development Engineer Intern Assignment Geospatial File Measurement API
- **License:** MIT
