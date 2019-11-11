from mic_threaded import MicArray

import threading
import time

if __name__ == '__main__':
    m = MicArray(threshold=50)
    m.detect_mics()

    x = threading.Thread(target=m.record, daemon=True)
    x.start()
    while True:
        print('Current recording status is: ' + str(m.recording_status))
        print('Current running status is: ' + str(m.running_status))
        time.sleep(1)