from mic_threaded import MicArray

import threading
import time
import argparse

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Raspberry Pi microphone recorder')
    parser.add_argument("--config", help='Optional json config file to use for microphones')
    parser.add_argument("--threshold", default=10, help='Detection threshold')

    args = parser.parse_args()

    m = MicArray(threshold=args.threshold)
    if args.config:
        m.load_from_file(args.config)
    else:
        m.detect_mics()

    x = threading.Thread(target=m.record, daemon=True)
    x.start()
    while True:
        print('Current recording status is: ' + str(m.recording_status))
        print('Current running status is: ' + str(m.running_status))
        time.sleep(1)