from typing import List, Tuple, Dict

import multi_thread_data_processing.multiThreadDataProcessing as mtl
from data_model.dataModel import FrameObject
from data_model.dataModel import FrameObjectWithBoundingBoxes
from neural_net_detector.neuralNetDetector import Detector


class DetectObjectWithModelTransform(mtl.OperationParent):
    def __init__(self, detector: Detector):
        super().__init__()
        self.__detector = detector

    def run(self, input_object: List[FrameObject]) -> FrameObject:
        frame = input_object[0]
        bboxes = self.__detector.get_bboxes(frame.get_frame())
        return FrameObjectWithBoundingBoxes(frame.get_frame(), frame.get_index(), bboxes)
