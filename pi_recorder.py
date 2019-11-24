from mic_threaded import MicArray

import threading
import time
import argparse
import pijuice

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Raspberry Pi microphone recorder')
    parser.add_argument("--config", help='Optional json config file to use for microphones')
    parser.add_argument("--threshold", default=20, help='Detection threshold')

    args = parser.parse_args()

    m = MicArray(threshold=int(args.threshold))
    try:
        if args.config:
            m.load_from_file(args.config)
        else:
            m.detect_mics()
    except OSError: # Fix for RPI ALSA issue
        pass
    
    pj = pijuice.PiJuice(1, 0x14)
    
    time.sleep(0.5)
    x = threading.Thread(target=m.record, daemon=True)
    x.start()
    while True:
        print('Current recording status is: ' + str(m.recording_status))
        print('Current running status is: ' + str(m.running_status))
        if pj.status.GetButtonEvents()['data']['SW2'] == 'SINGLE_PRESS':
            pj.status.AcceptButtonEvent('SW2')
            pj.status.SetLedState('D2', [255, 128, 0])
            m.running_status = False
            time.sleep(2)
            m.detect_prime()
            m.running_status = True
        elif pj.status.GetButtonEvents()['data']['SW3'] == 'SINGLE_PRESS':
            pj.status.AcceptButtonEvent('SW3')
            m.running_status = not m.running_status
        elif m.recording_status:
            pj.status.SetLedState('D2', [0, 255, 0])
        elif m.running_status:
            pj.status.SetLedState('D2', [0, 0, 255])
        else:
            pj.status.SetLedState('D2', [255, 0, 0])
        time.sleep(0.5)