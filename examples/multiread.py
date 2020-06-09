#!/usr/bin/python
import signal
import time
import sys
sys.path.append(".")
sys.path.append("./gandalf_usb/")
import reader
import gandalf

def _filereader(hexid, rr, file_base):
    """
    Read data from the device and put them into a file.
    :param hexid: hexid of gandalf to read from
    :param rr: a multiprocessing.Value to indicate the end of datataking
    """
    import gzip
    #reader.file_sink(args=[hexid, lambda: rr == 1], filename='/scratch/gotzl/data_%i'%hexid, verbose=True)

    from multiprocessing import Queue, queues
    from threading import Thread

    queue = Queue(0x100)

    # Put the reading from the device into its own thread.
    # Could've used a Process, but gain is not so much and makes problems when finishing up...
    _t = Thread(target=_enqueue, args=[hexid, queue, rr])
    _t.start()

    start = time.time()
    round_start = start
    size, total = 0, 0
    with open('%s_%i.bin'%(file_base,hexid), 'wb') as out:
        while rr.value == 1:
            try:
                data = queue.get(block=True, timeout=1)
                out.write(data)
                n = len(data)

                size += n
                total += n

            except queues.Empty:
                pass

            stop = time.time()
            if stop - round_start > 1:
                print(hexid, 'Total: %.2f kB / %.2f kB/s'%(total/1024, size / (1024 * (stop - round_start))))
                round_start = time.time()
                size = 0

    while not queue.empty(): queue.get()
    _t.join()
    print(hexid, 'Total: %.2f kB / %.2f kB/s'%(total/1024, total / (1024 * (time.time() - start))))


def _enqueue(hexid, queue, rr):
    """
    Read data from the device and put them into the queue.
    :param hexid: hexid of gandalf to read from, or gandalf.Gandalf object
    :param queue: the queue to put the data in
    :param rr: a multiprocessing.Value to indicate the end of datataking
    """
    reader.queue_sink(queue, args=[hexid, lambda: rr.value == 1], verbose=False)


def _dequeue(hexid, rr):
    """
    Generator that yields data received from the device.
    Creates a Thread to read data, communicates via multiprocessing.Queue.
    :param hexid: hexid of gandalf to read from
    :param rr: a multiprocessing.Value to indicate the end of datataking
    :return: a generator that yields data received from the device
    """
    from multiprocessing import Queue, queues
    from threading import Thread

    queue = Queue(0x100)

    # Put the reading from the device into its own thread.
    # Could've used a Process, but gain is not so much and makes problems when finishing up...
    _t = Thread(target=_enqueue, args=[hexid, queue, rr])
    _t.start()

    while rr.value == 1:
        try: ret = queue.get(block=True, timeout=1)
        except queues.Empty: continue
        yield ret

    while not queue.empty(): queue.get()
    _t.join()


def _decoder(hexid, rr):
    """
    read events and decode them, count decoding errors
    source for the events is the _dequeue function
    :param hexid: hexid of gandalf to read from
    :param rr: a multiprocessing.Value to indicate the end of datataking
    """
    import decode
    cnt, errs = 0,0
    start = time.time()
    with open('/scratch/gotzl/log_%i'%hexid,'w') as f_:
        #for ev in decode.lfsr(_dequeue(hexid, rr), debug=True):
        for ev in decode.events(_dequeue(hexid, rr), debug=True, out=f_):
            if isinstance(ev, Exception):
                f_.write('%.2f: %s\n'%(time.time() - start,ev))
                errs += 1
            elif ev.full: f_.write('%.2f: full (%i/%i)\n'%(time.time() - start, ev.ch, ev.no))
            else: pass #f_.write(str(ev)+"\n")
            cnt += 1
    print(hexid, 'Decoded %i events, %i with errors, data taking took %.2f s '%(cnt, errs, time.time() - start))


if __name__ == '__main__':
    import argparse
    from multiprocessing import Value, Process
    rr = Value('i', 1)

    def doexit(signum, frame):
        global rr
        rr.value = 0

    signal.signal(signal.SIGINT, doexit)
    signal.signal(signal.SIGTERM, doexit)

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', dest='file', help='filename base to write to, will be appended with _${srcid}.gz')
    parser.add_argument('hexid', nargs='+', help='gandalf hexid')
    args = parser.parse_args()

    target = _decoder
    target_args = [rr]
    if args.file is not None:
        target = _filereader
        target_args += [args.file]

    threads = list(map(lambda x: Process(
        target=target,
        args=[int(x, 16)]+target_args), args.hexid))
    list(map(lambda x:x.start(), threads))

    # keyboard input loop
    print("Press 'q' to end data taking.")
    while sys.stdin:
        if sys.stdin.read(1) == "q" or rr.value == 0:
            break

    rr.value = 0
    list(map(lambda x:x.join(), threads))
