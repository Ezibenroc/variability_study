#! /usr/bin/env python3

import psutil
import time
import sys
import csv
from collections import namedtuple

def get_cpu_freq():
    return [freq.current for freq in psutil.cpu_freq(percpu=True)]

def get_cpu_percent():
    return psutil.cpu_percent(percpu=True)

def get_cpu_temp(): # long and not very precise...
    return [temp.current for temp in psutil.sensors_temperatures()['coretemp'][1:]]

base_time = time.time()

def get_time():
    return time.time() - base_time

def get_next_entry():
    return namedtuple('Entry', ['time', 'frequency', 'load'])(get_time(), get_cpu_freq(), get_cpu_percent())

if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.stderr.write('Syntax: %s <csv_file> <frequency (Hz)>\n')
        sys.exit(1)
    filename = sys.argv[1]
    freq = float(sys.argv[2])
    assert freq > 0
    period = 1/freq
    with open(filename, 'w') as f:
        writer = csv.writer(f)
        entry = get_next_entry()
        header = ['time', 'metric', 'metric_type', 'metric_id']
        writer.writerow((header))
        while True:
            try:
                for i, freq in enumerate(entry.frequency):
                    writer.writerow([entry.time, freq, 'frequency', i])
                for i, load in enumerate(entry.load):
                    writer.writerow([entry.time, load, 'load', i])
                time.sleep(period)
                entry = get_next_entry()
            except KeyboardInterrupt:
                break
