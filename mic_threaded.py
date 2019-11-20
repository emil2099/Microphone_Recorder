import pyaudio
import wave
import math
import struct
import os
import time
from collections import deque
import json
import uuid

class MicArray:
    def __init__(self, prepend_length=2, timeout_length=2, threshold=10, chunk_size=1024, output_folder='records'):
        print('Initialised')
        self.p = pyaudio.PyAudio() #TODO Delete duplication of pyaudio instances - can be top level.
        self.mics = []
        self.prime_mic = None
        self.prepend_length = prepend_length
        self.timeout_length = timeout_length
        self.threshold = threshold
        self.chunk_size = chunk_size
        self.output_folder=output_folder
        self.recording_status = False
        self.running_status = True

    def detect_mics(self):
        self.mics = []
        for i in range(self.p.get_device_count()):
            d = self.p.get_device_info_by_index(i)
            if d['maxInputChannels'] > 0:
                mic = {
                    'name': d['name'],
                    'input_device_index': i,
                    'channels': d['maxInputChannels'],
                    'rate': d['defaultSampleRate']
                }
                self.add_mic_from_dict(mic)
        self._print_mics()

    def add_mic_from_dict(self, d):
        mic = Microphone(name=d['name'],
                         input_device_index=d['input_device_index'],
                         format=pyaudio.paInt16,
                         channels=d['channels'],
                         rate=int(d['rate']),
                         frames_per_buffer=self.chunk_size,
                         prepend_length=self.prepend_length
                         )
        self.mics.append(mic)

    def add_mic(self, input_device_index, channels, rate, frames_per_buffer, prepend_length, name = None):
        mic = Microphone(name=name,
                         input_device_index=input_device_index,
                         format=pyaudio.paInt16,
                         channels=channels,
                         rate=rate,
                         frames_per_buffer=frames_per_buffer,
                         prepend_length=prepend_length
                         )
        self.mics.append(mic)

    def delete_mic(self, input_device_index):
        self.mics = [mic for mic in self.mics if mic._input_device_index != input_device_index]

    def save_to_file(self, filename):
        l = [self._mic_to_dict(mic) for mic in self.mics]
        with open(filename, 'w') as f:
            json.dump(l, f)

    def load_from_file(self, filename):
        in_mics = []
        with open(filename) as f:
            in_mics = json.load(f)
        for mic in in_mics:
            self.add_mic_from_dict(mic)

    def detect_prime(self):
        self.prime_mic = max(self.mics, key=lambda x: x.average_rms())

    def record(self):
        if not os.path.exists(self.output_folder):
                os.makedirs(self.output_folder)

        if self.prime_mic is None:
            mic1 = self.mics[0]
        else:
            mic1 = self.prime_mic

        print('Starting listening')
        self.running_status = True
        while True:
            try:
                now = time.time()
                if not mic1.recording_status:
                    avg_rms = mic1.average_rms()
                    if avg_rms > self.threshold:
                    # if mic1.rms - self.threshold > avg_rms:
                        print(f'Triggered by RMS: {mic1.rms}. Average RMS: {avg_rms}')
                        self.recording_status = True
                        for mic in self.mics:
                            mic.start_recording()
                        end = now + self.timeout_length

                if mic1.recording_status:
                    avg_rms = mic1.average_rms()
                    if avg_rms > self.threshold: end = now + self.timeout_length

                    if now > end:
                        time_str = time.strftime("%Y%m%d_%H%M%S")
                        self.recording_status = False
                        for mic in self.mics:
                            print('Mic array stopped recording')
                            mic.stop_recording()

                        for i, mic in enumerate(self.mics):
                            filepath = os.path.join(self.output_folder, '{}_{}.wav'.format(time_str, i))
                            mic.save(filepath)

            except KeyboardInterrupt:
                print('Cancelled')
                for mic in self.mics:
                    mic.stream.stop_stream()
                    mic.stream.close()
                self.p.terminate()
                self.running_status = False

            # except:
            #     self.running_status = False

    def _print_mics(self):
        print('The following microphones have been detected and added:')
        if len(self.mics) > 0:
            for mic in self.mics:
                print(mic)
        else:
            print(None)

    @staticmethod
    def _mic_to_dict(mic):
        d = {
            'name': mic.__name__,
            'input_device_index': mic._input_device_index,
            'channels': mic._channels,
            'rate': mic._rate
        }
        return d


class Microphone:
    def __init__(self, input_device_index, format, channels, rate, name=str(uuid.uuid1()),
                 frames_per_buffer=1024, prepend_length=0, rms_points=100):

        self.p = pyaudio.PyAudio()

        self.__name__ = name

        self._channels = channels
        self._format = format
        self._rate = rate
        self._input_device_index = input_device_index

        self.stream = self.p.open(input_device_index=input_device_index,
                                  format=format,
                                  channels=channels,
                                  rate=rate,
                                  input=True,
                                  # output=True,
                                  frames_per_buffer=frames_per_buffer,
                                  stream_callback=self.get_callback())

        self.prev_data = deque(maxlen=prepend_length * rate // frames_per_buffer)
        self.data = []
        self.recording_status = False
        self.rms = 0
        self.rms_history = deque(maxlen=rms_points)
        self.out = b''

        self.stream.start_stream()

    def __str__(self):
        return(f'Name: {self.__name__}, input_device_index: {self._input_device_index}, '
               f'channels: {self._channels}, rate: {self._rate}')

    def get_callback(self):
        def callback(in_data, frame_count, time_info, status):
            self.rms = self.update_rms(in_data)
            self.rms_history.append(self.rms)
            self.prev_data.append(in_data)

            if self.recording_status:
                self.data.append(in_data)
            return in_data, pyaudio.paContinue
        return callback

    def start_recording(self):
        self.recording_status = True
        self.out = b''.join(self.prev_data)

    def stop_recording(self):
        self.recording_status = False

    def save(self, filepath):
        self.out = self.out + b''.join(self.data)

        self.data = []

        wf = wave.open(filepath, 'wb')
        wf.setnchannels(self._channels)
        wf.setsampwidth(self.p.get_sample_size(self._format))
        wf.setframerate(self._rate)
        wf.writeframes(self.out)
        wf.close()
        print('Written to file: {}'.format(filepath))

    @staticmethod
    def update_rms(frame):
        SHORT_NORMALIZE = (1.0 / 32768.0)
        SWIDTH = 2

        count = len(frame) / SWIDTH
        format = "%dh" % (count)
        shorts = struct.unpack(format, frame)

        sum_squares = 0.0
        for sample in shorts:
            n = sample * SHORT_NORMALIZE
            sum_squares += n * n
        return min([math.pow(sum_squares / count, 0.5) * 1000, 100])

    def average_rms(self):
        try:
            avg = sum(self.rms_history) / len(self.rms_history)
        except ZeroDivisionError:
            avg = 0
        return avg


if __name__ == '__main__':
    m = MicArray(threshold=15)
    m.detect_mics()
    m.record()