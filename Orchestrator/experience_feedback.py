"""Best-effort, ordered Quest display updates, independent of command execution."""
import queue
import threading


class ExperienceFeedback:
    def __init__(self, transport):
        self.transport = transport
        self.queue = queue.Queue(maxsize=1)
        self.lock = threading.Lock()
        self.latest = {}
        self.thread = None
        self.closed = False

    def publish(self, serial, notice):
        key = (serial, notice['session'])
        with self.lock:
            if self.closed or notice['sequence'] <= self.latest.get(key, 0): return
            self.latest[key] = notice['sequence']
            try: self.queue.get_nowait()
            except queue.Empty: pass
            self.queue.put_nowait((serial, notice))
            if self.thread is None:
                self.thread = threading.Thread(target=self._work, daemon=True, name='oryn-feedback')
                self.thread.start()

    def _work(self):
        while True:
            item = self.queue.get()
            if item is None: return
            serial, notice = item
            try: self.transport.notice(serial, notice)
            except Exception: pass  # Display failure cannot authorize, cancel or repeat an action.

    def close(self):
        with self.lock:
            self.closed = True
            try: self.queue.get_nowait()
            except queue.Empty: pass
            self.queue.put_nowait(None)
