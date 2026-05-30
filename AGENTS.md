# AGENTS.md

## Project Overview

Multi-camera person detection system with a Flask REST control plane. Uses YOLOv5 for detection and a custom threading pipeline framework. Python-only project, no build system.

## Commands

### Run application
```bash
python3 src/main.py
```
Flask starts on `0.0.0.0:2137` (not 5000 — the Dockerfile `EXPOSE 5000` is a mismatch).

### Run tests
```bash
# From project root — PYTHONPATH must include project root
python -m unittest discover -s test
```
Tests import `src.multi_thread_data_processing.multiThreadDataProcessing`, so run from repo root or set `PYTHONPATH=.`.

### Docker
```bash
docker build -t detectorproject -f Dockerfile .
docker run -p 2137:2137 detectorproject
```

## Critical Gotchas

- **Hardcoded config path:** `data_model/dataModel.py:22` loads config from `/tmp/build/src/resources/config.yml` — this only works inside the Docker container. For local dev, change it to `src/resources/config.yml`.
- **YOLOv5 auto-downloads on first run** via `torch.hub.load('ultralytics/yolov5', 'yolov5s')`. Requires internet access. Local weights exist at `src/yolov5s.pt` and `src/yolov5n.pt` but are not used by default.
- **GPU disabled:** CUDA code is commented out in `cameraIO.py` and `neuralNetDetector.py`. Model runs on CPU unless you re-enable those lines.
- **Mailtrap credentials are hardcoded** in `notification_channel/notificationSender.py` (test sandbox only, not production).

## Architecture

### Data pipeline (custom framework in `src/multi_thread_data_processing/`)
```
PeriodicDataGetter  →  Queue  →  DataWorker (OperationChain)  →  Queue  →  DataSink
   (camera poll)                  (YOLOv5 transform)                      (draw boxes, email alert)
```
- Extend `GetParent.get_data()` to produce data
- Extend `OperationParent.run(input)` for transforms, chain with `OperationChain.add_operation()`
- Extend `SinkParent.sink_data(list)` for output/side effects
- Documentation: `documentation/multi_thread_lib_doc.adoc`

### Config singleton
`data_model/dataModel.py` — `Config` is a singleton loaded from YAML. Controls: AprilTag family, tracked objects (by tag ID), max camera search index (10), detection field size (900×900).

### Detection
- Filtered to **class 0 (person) only**, max 5 per frame, confidence 0.25
- Training experiment artifacts in `exp4/` — best custom weights at `exp4/weights/best.pt` (not used by default)

### Notification
Email sent via Mailtrap SMTP when detected person count **changes** on a camera (and is non-zero). Includes a PNG frame attachment.

## Branches
- `main` — YOLOv5 neural net detection (current)
- `engineeringThesis` — archived original version using AprilTag markers

## Dependencies
`requirements.txt` only lists `flask` and `torch`. In practice also requires `opencv-python`, `numpy`, `Pillow`, `PyYAML`, and YOLOv5 transitive deps. No lockfile exists.

## No CI / No linter / No formatter configured.
