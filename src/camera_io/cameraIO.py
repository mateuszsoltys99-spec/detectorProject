from copy import deepcopy
from queue import Queue
from typing import Optional, List, Dict, Tuple
import threading

import cv2
import torch
import numpy as np

from camera_io.settings import Settings
from image_transforms.imageTransforms import DetectObjectWithModelTransform
import multi_thread_data_processing.multiThreadDataProcessing as mtl
from data_model.dataModel import Config
from data_model.dataModel import FrameObject
from data_model.dataModel import FrameObjectWithDetectedObjects
from data_model.dataModel import FrameObjectWithBoundingBoxes
from neural_net_detector.neuralNetDetector import BaseYoloDetector
from notification_channel.notificationSender import send_notification


class CameraReader(mtl.GetParent):
    def __init__(self, camera_number: int):
        super(CameraReader, self).__init__()
        self.cap = cv2.VideoCapture(camera_number)
        if not self.cap.isOpened():
            raise Exception("Couldn't open camera {}".format(camera_number))
        self.index: int = camera_number

    def get_data(self) -> Optional[FrameObject]:
        ret, frame = self.cap.read()
        if not ret:
            return None
        return FrameObject(deepcopy(frame), self.index)

    def get_resolution(self) -> Tuple[int, int]:
        return int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


class CameraDisplayPersonDetections(mtl.SinkParent):
    def __init__(self):
        super(CameraDisplayPersonDetections, self).__init__()
        self.__camera_detections: Dict[int, int] = {}
        self.__lock = threading.Lock()

    def sink_data(self, input_object: List[FrameObjectWithBoundingBoxes]):
        for frame_object in input_object:
            frame_to_draw = deepcopy(frame_object.get_frame())
            camera_index = frame_object.get_index()
            bboxes = frame_object.get_bounding_boxes()
            # frame.shape is (height, width, channels); iterate over bboxes in (x, y, w, h) == (col, row, w, h)
            frame_h, frame_w = frame_to_draw.shape[:2]
            for x_s, y_s, w, h in bboxes:
                x_end = min(frame_w - 1, x_s + w)
                y_end = min(frame_h - 1, y_s + h)
                # top and bottom horizontal edges
                frame_to_draw[y_s, x_s:x_end, :] = [255, 0, 0]
                frame_to_draw[y_end, x_s:x_end, :] = [255, 0, 0]
                # left and right vertical edges
                frame_to_draw[y_s:y_end, x_s, :] = [255, 0, 0]
                frame_to_draw[y_s:y_end, x_end, :] = [255, 0, 0]

            with self.__lock:
                prev_count = self.__camera_detections.get(camera_index)
                if len(bboxes) != prev_count and len(bboxes) != 0:
                    threading.Thread(
                        target=send_notification,
                        args=(camera_index, frame_to_draw),
                        daemon=True,
                    ).start()
                self.__camera_detections[camera_index] = len(bboxes)


class Camera:
    def __init__(
        self,
        index: int,
        fps: float,
        x: int,
        y: int,
        angle: float,
        data_output: List[Queue],
        model,
    ):
        self.index = index
        self.fps = fps
        self.x = x
        self.y = y
        self.angle = angle
        self.status = "INACTIVE"
        self.settings: Settings = Settings()
        camera_reader = CameraReader(self.index)
        self.resolution = camera_reader.get_resolution()
        data_from_input: List[Queue] = [Queue()]
        self.data_getter = mtl.PeriodicDataGetter(data_from_input, camera_reader, self.fps)
        self.data_worker_detect = mtl.DataWorker(
            data_from_input,
            data_output,
            mtl.OperationChain().add_operation(DetectObjectWithModelTransform(BaseYoloDetector(model))),
        )

    def cals_display_points(self):
        p1 = [int(self.x), int(self.y)]
        res_x, res_y = self.resolution
        sin = np.sin(self.angle)
        cos = np.cos(self.angle)
        p2 = [int(self.x + (res_x * cos)), int(self.y + res_x * sin)]
        p3 = [int(self.x + (res_x * cos) - (res_y * sin)), int(self.y + (res_x * sin) + (res_y * cos))]
        p4 = [int(self.x - (res_y * sin)), int(self.y + res_y * cos)]
        pts = np.array([p1, p2, p3, p4], np.int32)
        return pts.reshape((-1, 1, 2))

    def start(self):
        self.data_getter.start()
        self.data_worker_detect.start()
        self.status = "ACTIVE"

    def stop(self):
        self.data_getter.stop()
        self.data_worker_detect.stop()
        self.status = "INACTIVE"

    def set_settings(self, settings: Settings):
        self.settings = settings

    def to_dict(self):
        return {
            "fps": self.fps,
            "status": self.status,
            "handle point": (self.x, self.y),
            "camera angle": self.angle,
        }

    def __str__(self) -> str:
        return "Camera {}: FPS={}".format(self.index, self.fps)


class AllCameras:
    def __init__(self):
        self.all_cameras: Dict[int, Camera] = {}
        self.indexes: List[int] = []
        self.data_output: List[Queue] = []
        self.camera_data: Dict[int, tuple] = {}
        self._lock = threading.Lock()
        print("CUDA available: {}".format(torch.cuda.is_available()))
        self.__yolo_model = torch.hub.load('ultralytics/yolov5', 'yolov5s')

    def add_camera(self, index: int, fps: float, x: int, y: int, angle: float):
        output_queue: Queue = Queue()
        with self._lock:
            self.data_output.append(output_queue)
            self.all_cameras[index] = Camera(index, fps, x, y, angle, [output_queue], self.__yolo_model)
            self.indexes.append(index)
            camera = self.all_cameras[index]
            self.camera_data[index] = (x, y, angle, camera.resolution, camera.cals_display_points())

    def start_camera(self, index: int):
        self.all_cameras[index].start()

    def stop_camera(self, index: int):
        self.all_cameras[index].stop()

    def start_all_cameras(self):
        for index in self.indexes:
            self.start_camera(index)

    def stop_all_cameras(self):
        for index in self.indexes:
            self.stop_camera(index)

    def remove_camera(self, index: int):
        with self._lock:
            self.stop_camera(index)
            camera = self.all_cameras.pop(index)
            self.indexes.remove(index)
            self.camera_data.pop(index, None)
            # Remove the queue that belonged to this camera from data_output
            output_queues = camera.data_worker_detect.output_object
            for q in output_queues:
                if q in self.data_output:
                    self.data_output.remove(q)

    def cameras_to_dict(self) -> Dict:
        with self._lock:
            return {index: self.all_cameras[index].to_dict() for index in self.indexes}
