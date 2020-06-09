#!/usr/bin/env python2
# Diese Datei in gandalf_usb/ kopieren.

import sys, argparse
import matplotlib.pyplot as plt
sys.path.append('.')
sys.path.append("./gandalf_usb")
import reader, decode
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('-f', dest='file', help='filename')
args = parser.parse_args()


plot_bin(args.file)

def plot_bin(file):
    for k,ev in enumerate(decode.events(reader.file_source(file), debug=True)):
        print 'event number (from enumerate function)', k
        print 'event number (from binfile)', ev.no
        print 'channel', ev.ch
        print 'time', ev.time
        print 'time_lsb', ev.time_lsb
        print 'time_msb', ev.time_msb
        print 'end_time', ev.endtime
        plt.figure()
        plt.plot(ev.samples)
        plt.legend()
        plt.xlabel('time [1.042ns]')
        plt.ylabel('voltage [mV]')
        plt.show()
