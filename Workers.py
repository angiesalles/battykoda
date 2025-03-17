from AppropriateFile import appropriate_file
import threading
from Plotting import plotting
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=True)
class PrioItem:
    priority: int
    item: Any = field(compare=False)


def worker(request_queue, work_queue):
    mythreadstorage = {}
    while True:
        pi = request_queue.get()
        # Get the WAV path from args if it exists, otherwise use the path
        wav_path = pi.item['args'].get('wav_path', pi.item['path'])
        key = appropriate_file(wav_path, pi.item['args'])
        
        if key not in mythreadstorage:
            event = threading.Event()
            thread = threading.Thread(target=plotting,
                                      args=(wav_path, pi.item['args'], event),
                                      daemon=True)
            thread.start()
            mythreadstorage[key] = thread
            work_queue.put(PrioItem(pi.priority, {'thread': thread, 'event': event}))
        pi.item['thread'] = mythreadstorage[key]
        request_queue.task_done()


def worker2(work_queue):
    while True:
        item = work_queue.get().item
        item['event'].set()
        item['thread'].join()
        work_queue.task_done()
