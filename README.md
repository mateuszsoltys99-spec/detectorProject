# detectorProject

A multi-camera person detection system with a REST API control plane. Cameras are managed at runtime via HTTP; each camera runs an independent detection pipeline using YOLOv5 and sends email alerts when the number of detected persons changes.

## How it works

Each registered camera runs a three-stage background pipeline:

```
CameraReader (OpenCV)
  → PeriodicDataGetter   polls camera at configured FPS
  → Queue
  → DataWorker           runs YOLOv5s inference (CPU by default)
  → Queue
  → DataSink             draws bounding boxes; emails alert on count change
```

The pipeline is built on a custom threading framework in `src/multi_thread_data_processing/`. Cameras are registered, started, and stopped through a Flask REST API.

## Requirements

- Python 3.8+
- A connected webcam (or V4L2 camera device)
- Internet access on first run (YOLOv5 model weights are downloaded via `torch.hub`)

Install dependencies:

```bash
pip install flask torch opencv-python numpy Pillow PyYAML
```

> `requirements.txt` only lists `flask` and `torch`; the remaining packages are implicit transitive dependencies.

## Running locally

Before starting, change the hardcoded config path in `src/data_model/dataModel.py` line 22 from:

```python
with open("/tmp/build/src/resources/config.yml", "r") as ymlfile:
```

to:

```python
with open("src/resources/config.yml", "r") as ymlfile:
```

Then run from the project root:

```bash
python3 src/main.py
```

The Flask server starts on `http://0.0.0.0:2137`.

## Running with Docker

```bash
docker build -t detectorproject -f Dockerfile .
docker run -p 2137:2137 detectorproject
```

> The `Dockerfile` exposes port 5000, but the app listens on **2137**. Map accordingly.

## REST API

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| `GET` | `/cameras/get` | — | List all registered cameras and their state |
| `POST` | `/cameras/create` | `index`, `fps`, `x`, `y`, `angle` | Register and start a new camera |
| `PUT` | `/cameras/activate` | `index`, `active=true\|false` | Start or stop a camera |
| `PUT` | `/cameras/update` | `index`, `fps`, `x`, `y`, `angle` | Update camera parameters at runtime |
| `GET` | `/cameras/free` | — | List available (unregistered) camera device indexes |
| `GET` | `/cameras/resolutions` | — | List available device indexes with their native resolutions |

### Example: register camera 0 at 10 fps

```bash
curl -X POST "http://localhost:2137/cameras/create?index=0&fps=10&x=0&y=0&angle=0"
```

## Configuration

`src/resources/config.yml` controls:

| Key | Default | Description |
|-----|---------|-------------|
| `max_search_index` | `10` | Upper bound when scanning for available camera devices |
| `field_of_detection.x/y` | `900` | Detection field size in pixels |
| `tag_family` | `tag36h11` | AprilTag family (legacy, unused in current detection mode) |

## Detection

- Model: YOLOv5s loaded via `torch.hub.load('ultralytics/yolov5', 'yolov5s')`
- Filtered to **class 0 (person)** only
- Max 5 detections per frame, confidence threshold 0.25
- Runs on **CPU by default** — GPU lines are commented out in `camera_io/cameraIO.py` and `neural_net_detector/neuralNetDetector.py`
- Pre-trained weights also available locally at `src/yolov5s.pt` and `src/yolov5n.pt`
- A custom-trained checkpoint (10 epochs, COCO128) is at `exp4/weights/best.pt`

## Alerts

An email is sent via Mailtrap SMTP whenever the detected person count on a camera **changes** (and is non-zero). The email includes a PNG frame attachment. Credentials in `notification_channel/notificationSender.py` are a test sandbox and must be replaced for production use.

## Tests

```bash
# Run from project root
python -m unittest discover -s test
```

Tests cover the custom threading/pipeline framework. There is no CI configuration.

## Project layout

```
src/
  main.py                          Flask app + pipeline wiring
  resources/config.yml             Runtime configuration
  camera_io/                       Camera capture, pipeline setup, detection sink
  data_model/                      Config singleton, frame data transfer objects
  image_transforms/                Pipeline transform operations (YOLOv5 inference step)
  multi_thread_data_processing/    Custom threading/pipeline framework
  neural_net_detector/             YOLOv5 wrapper (Detector ABC + BaseYoloDetector)
  notification_channel/            Email alert sender
test/
  multi_thread_lib/                Unit tests for the pipeline framework
exp4/                              YOLOv5 training artifacts and custom weights
documentation/                     AsciiDoc + PDF docs for the pipeline framework
```

## Branches

- `main` — current version, YOLOv5 neural net detection
- `engineeringThesis` — archived original version using AprilTag markers
