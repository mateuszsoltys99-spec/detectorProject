from unittest import TestCase
from queue import Queue
import time

import src.multi_thread_data_processing.multiThreadDataProcessing as mtl


class Test(TestCase):
    def test_data_worker(self):
        input_queue = Queue()
        input_queue.put("1")
        input_queue.put("2")
        input_queue.put("3")
        output_queue = Queue()
        data_worker = mtl.DataWorker([input_queue], [output_queue], mtl.OperationChain())
        data_worker.start()
        # Wait long enough for all 3 items to be processed (each poll is 50 ms max)
        time.sleep(0.5)
        data_worker.stop()
        output_list = []
        while not output_queue.empty():
            output_list.append(output_queue.get())
        self.assertIn(["1"], output_list)
        self.assertIn(["2"], output_list)
        self.assertIn(["3"], output_list)

    def test_data_getter(self):
        class TestGetObject(mtl.GetParent):
            def __init__(self):
                super().__init__(None)
                self.test_data = ["1", "2", "3"]

            def get_data(self):
                if self.test_data:
                    return self.test_data.pop()
                return None

        output_queue = Queue()
        data_getter = mtl.DataGetter([output_queue], TestGetObject())
        data_getter.start()
        time.sleep(0.2)
        data_getter.stop()
        output_list = []
        while not output_queue.empty():
            output_list.append(output_queue.get())
        self.assertIn("1", output_list)
        self.assertIn("2", output_list)
        self.assertIn("3", output_list)

    def test_data_sink(self):
        input_queue = Queue()
        input_queue.put("1")
        input_queue.put("2")
        input_queue.put("3")

        processed = []

        class CollectingSink(mtl.SinkParent):
            def sink_data(self, input_object: list):
                processed.extend(input_object)

        data_sink = mtl.DataSink([input_queue], CollectingSink())
        data_sink.start()
        time.sleep(0.5)
        data_sink.stop()
        self.assertIn("1", processed)
        self.assertIn("2", processed)
        self.assertIn("3", processed)
