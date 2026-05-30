import queue
import threading
import time
from typing import List, Optional, Any
from queue import Queue

_POLL_TIMEOUT = 0.05  # seconds; used by blocking queue reads to stay responsive to stop signals


class OperationParent:
    def __init__(self, side_input: Optional[Any] = None):
        """
        A parent class for a single operation. Operation objects should implement it.
        @param side_input: optional additional input used when the run() method is executed
        """
        self.side_input = side_input

    def run(self, input_object: Any) -> Any:
        """
        Run method, executed on the input_object by DataWorker. Should return a type accepted
        by the run() method of the next OperationParent in OperationChain.
        @param input_object: any object that will be processed by the OperationParent
        @return: processed input_object
        """
        return input_object

    def set_side_input(self, side_input: Any):
        """
        Updates additional input of the OperationParent.
        @param side_input: any object that can serve as a side input
        """
        self.side_input = side_input

    def get_side_input(self) -> Optional[Any]:
        """Returns current side input of the OperationParent."""
        return self.side_input


class OperationChain:
    """
    Fluent builder for chaining OperationParent steps:
        chain = OperationChain().add_operation(op1).add_operation(op2)
    """

    def __init__(self):
        self.operations: List[OperationParent] = []

    def add_operation(self, operation_object: OperationParent) -> "OperationChain":
        self.operations.append(operation_object)
        return self

    def run_operations(self, input_object: List[Any]) -> Any:
        """Execute the operation chain sequentially. Used internally by DataWorker."""
        output_object = input_object
        for operation in self.operations:
            output_object = operation.run(output_object)
        return output_object


class DataWorker:
    """
    Drains items from input queues, runs the OperationChain on each batch, and
    pushes the result to all output queues.
    """

    def __init__(self, input_object: List[Queue], output_object: List[Queue], operation_chain: OperationChain):
        self.input_object = input_object
        self.output_object = output_object
        self.operation_chain = operation_chain
        self._stop_event = threading.Event()

    def start(self):
        self._stop_event.clear()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self._stop_event.is_set():
            current_obj = []
            for input_queue in self.input_object:
                try:
                    current_obj.append(input_queue.get(timeout=_POLL_TIMEOUT))
                except queue.Empty:
                    pass
            if current_obj:
                result = self.operation_chain.run_operations(current_obj)
                for output_queue in self.output_object:
                    output_queue.put(result)

    def stop(self):
        """Signal the worker to stop and wait for the current operation to finish."""
        self._stop_event.set()


class GetParent:
    """Parent class for a data producer. Subclass and override get_data()."""

    def __init__(self, side_input: Optional[Any] = None):
        self.side_input = side_input

    def get_data(self) -> Any:
        return None

    def stop(self):
        pass


class DataGetter:
    """
    Calls get_parent.get_data() in a tight loop and pushes non-None results to
    all output queues.
    """

    def __init__(self, output_object: List[Queue], get_parent: GetParent):
        self.output_object = output_object
        self.get_parent = get_parent
        self._stop_event = threading.Event()

    def start(self):
        self._stop_event.clear()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self._stop_event.is_set():
            current_obj = self.get_parent.get_data()
            if current_obj is not None:
                for output_queue in self.output_object:
                    output_queue.put(current_obj)
        self.get_parent.stop()

    def stop(self):
        self._stop_event.set()


class PeriodicDataGetter:
    """
    Calls get_parent.get_data() at a fixed frequency and pushes non-None results
    to all output queues. Runs in a single background thread — no unbounded
    thread spawning.
    """

    def __init__(self, output_object: List[Queue], get_parent: GetParent, frequency: float):
        self.output_object = output_object
        self.get_parent = get_parent
        self.period = 1.0 / frequency
        self._stop_event = threading.Event()

    def start(self):
        self._stop_event.clear()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self._stop_event.is_set():
            start = time.monotonic()
            current_obj = self.get_parent.get_data()
            if current_obj is not None:
                for output_queue in self.output_object:
                    output_queue.put(current_obj)
            elapsed = time.monotonic() - start
            remaining = self.period - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self.get_parent.stop()

    def stop(self):
        self._stop_event.set()


class SinkParent:
    """Parent class for a data consumer. Subclass and override sink_data()."""

    def __init__(self, side_input: Optional[Any] = None):
        self.side_input = side_input

    def sink_data(self, input_object: list):
        pass

    def stop(self):
        pass


class DataSink:
    """
    Drains items from input queues and calls sink_parent.sink_data() with each
    batch. Blocks on each queue with a timeout so it stays responsive to stop().
    """

    def __init__(self, input_object: List[Queue], sink_parent: SinkParent):
        self.input_object = input_object
        self.sink_parent = sink_parent
        self._stop_event = threading.Event()

    def start(self):
        self._stop_event.clear()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self._stop_event.is_set():
            current_obj = []
            for input_queue in self.input_object:
                try:
                    current_obj.append(input_queue.get(timeout=_POLL_TIMEOUT))
                except queue.Empty:
                    pass
            if current_obj:
                self.sink_parent.sink_data(current_obj)
        self.sink_parent.stop()

    def stop(self):
        self._stop_event.set()


class PeriodicDataSink:
    """
    Polls input queues at a fixed frequency and calls sink_parent.sink_data()
    with whatever items are available. Runs in a single background thread.
    """

    def __init__(self, input_object: List[Queue], sink_parent: SinkParent, frequency: float):
        self.input_object = input_object
        self.sink_parent = sink_parent
        self.period = 1.0 / frequency
        self._stop_event = threading.Event()

    def start(self):
        self._stop_event.clear()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self._stop_event.is_set():
            start = time.monotonic()
            current_obj = []
            for input_queue in self.input_object:
                try:
                    current_obj.append(input_queue.get_nowait())
                except queue.Empty:
                    pass
            if current_obj:
                self.sink_parent.sink_data(current_obj)
            elapsed = time.monotonic() - start
            remaining = self.period - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self.sink_parent.stop()

    def stop(self):
        self._stop_event.set()
