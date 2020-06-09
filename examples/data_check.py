import sys, struct
import numpy as np
sys.path.append('.')
sys.path.append('./gandalf_usb/')
import reader, decode


def _decode_selftrig():
    last = None
    #    for ev in decode.events(reader.file_source('/scratch/gotzl/data_35'), debug=True):
    for ev in decode.events(reader.device_source(0x03), debug=True):
        if isinstance(ev, Exception):
            if last is not None: print (last.time, last.no, last.ch, last.full, len(last.samples), last.endtime-last.time&((1<<30)-1))
            print(ev)
            break
        else: last = ev


def _decode_rnd_dat():
    for word in decode.lfsr(reader.file_source('./test_35.bin'), debug=True):
        if isinstance(word, Exception):
            print(word)
            input()

if __name__ == '__main__':
    _decode_rnd_dat()
    #import cProfile
    #cProfile.run('_decode()')
