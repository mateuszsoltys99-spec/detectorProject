# DuckyTown Robot Fleet Tracker

Engineering thesis project. A multi-camera computer vision system that tracks the real-time position and orientation of a fleet of [DuckieTown](https://www.duckietown.org/) autonomous robots, each marked with an AprilTag fiducial marker. A REST API allows cameras to be configured and managed at runtime.

---

## Overview

Each DuckyTown robot carries a unique AprilTag (family `tag36h11`). One or more USB cameras are mounted above the arena. The system:

1. Captures video frames from each camera in parallel.
2. Detects AprilTags in every frame and extracts the pixel-space center and orientation of each robot.
3. Transforms per-camera pixel coordinates into a shared world coordinate system using each camera's registered position and rotation angle.
4. Fuses detections from multiple cameras (averaging position and orientation) to produce a single best-estimate location for each robot.
5. Renders an annotated composite overhead view of the entire field alongside individual camera windows.

Up to 5 robots (AprilTag IDs 0–4) are tracked simultaneously. The tracked set and tag family are configured in `src/resources/config.yml`.

---

## Architecture

### Multi-Thread Pipeline Library (MTL)

All data processing runs through a custom pipeline library (`src/multi_thread_data_processing/multiThreadDataProcessing.py`) built around three thread-safe abstractions:

```
PeriodicDataGetter  →  [Queue]  →  DataWorker (OperationChain)  →  [Queue]  →  DataSink
```

- **`PeriodicDataGetter`** — reads a frame from a camera at a fixed FPS, pushes it to a queue.
- **`DataWorker`** — consumes frames, runs an `OperationChain` of `OperationParent` steps (AprilTag detection), pushes results.
- **`DataSink`** — consumes detection results from all cameras, fuses them, and renders the display.

Each camera has its own `PeriodicDataGetter` + `DataWorker` pair running in separate threads. All camera output queues feed into a single `DataSink`.

### Coordinate System

Each camera is registered with an origin point `(x, y)` and a rotation angle relative to the world frame. Camera-local pixel coordinates are transformed into world coordinates via a 2D rotation matrix:

```
x_world = x_cam + x_local * cos(angle) - y_local * sin(angle)
y_world = y_cam + x_local * sin(angle) + y_local * cos(angle)
```

When the same robot is visible to multiple cameras, positions and orientations are averaged.

### Key Source Files

| Path | Role |
|------|------|
| `src/main.py` | Entrypoint — Flask app, `AllCameras` init, `DataSink` display loop |
| `src/multi_thread_data_processing/multiThreadDataProcessing.py` | MTL pipeline library: `DataWorker`, `PeriodicDataGetter`, `DataSink`, `OperationChain` |
| `src/camera_io/cameraIO.py` | `Camera`, `AllCameras`, `CameraDisplay`, `CameraReader` |
| `src/image_transforms/imageTransforms.py` | `DetectObjectsTransform` — AprilTag detection via `apriltag.Detector` |
| `src/data_model/dataModel.py` | `Config` singleton, `FrameObject`, `FrameObjectWithDetectedObjects` |
| `src/resources/config.yml` | Tag family, tracked object IDs, camera search limit, display window size |
| `documentation/multi_thread_lib_doc.adoc` | MTL library design documentation with UML diagrams |

---

## Setup

No package manifest is provided. Install dependencies manually:

```bash
pip install flask opencv-python numpy pyyaml apriltag
```

> `apriltag` (or `pupil-apriltags`) must be installed explicitly — it is not available as a transitive dependency of any of the above.

---

## Running

Must be run from the **repository root** — the config file is opened with the hardcoded path `src/resources/config.yml`:

```bash
python src/main.py
```

This starts Flask on `localhost:5000` and opens an OpenCV window named **"Video"** showing the composite overhead field view. A separate window is opened for each active camera.

---

## REST API

Cameras are not started automatically — they must be registered and activated via the API.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/cameras/get` | List all registered cameras and their status |
| `POST` | `/cameras/create?index=<n>&fps=<f>&x=<x>&y=<y>&angle=<a>` | Register a camera at device index `n`, placed at world position `(x, y)` with rotation `angle` (radians) |
| `PUT` | `/cameras/activate?index=<n>&active=<true\|false>` | Start or stop a camera |
| `PUT` | `/cameras/update?index=<n>&fps=<f>&x=<x>&y=<y>&angle=<a>` | Update an existing camera's parameters |
| `GET` | `/cameras/free` | List device indexes that are available but not yet registered |
| `GET` | `/cameras/resolutions` | List the resolution reported by each available device |

**Example — add and start camera 0 at the world-frame origin, 30 fps, no rotation:**

```bash
curl -X POST "localhost:5000/cameras/create?index=0&fps=30&x=0&y=0&angle=0"
curl -X PUT  "localhost:5000/cameras/activate?index=0&active=true"
```

---

## Configuration

`src/resources/config.yml`:

```yaml
tag_family: "tag36h11"      # AprilTag family — must match the physical tags on the robots

objects:                    # Maps object ID (0–4) to AprilTag ID
  0:
    tag_id: 0
  1:
    tag_id: 1
  # ...

max_search_index: 10        # Scan /dev/video0 through /dev/video9

field_of_detection:
  x: 900                    # Composite overhead window width in pixels
  y: 900                    # Composite overhead window height in pixels
```

---

## Running Tests

Tests cover the MTL pipeline library only and require no camera hardware or `apriltag` installation:

```bash
python -m pytest test/
```

---

## Documentation

AsciiDoc source and a compiled PDF describing the MTL library design are in `documentation/`. Architecture and UML diagrams are in `documentation/images/`.
