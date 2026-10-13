"""Bounded, timed native stdout observations for desktop/resource tests."""
from queue import Queue, Empty
from threading import Thread

class Output:
    def __init__(self, process):
        self.process = process
        self.queue = Queue(maxsize=1024)
        def read():
            for line in process.stdout:
                self.queue.put(line)
            self.queue.put(None)
        Thread(target=read, daemon=True).start()

    def line(self, seconds=20):
        try:
            line = self.queue.get(timeout=seconds)
        except Empty:
            raise AssertionError(f'Native output timed out; process status={self.process.poll()}')
        if line is None:
            raise AssertionError(f'Unexpected native EOF; process status={self.process.poll()}')
        return line.decode().strip()
