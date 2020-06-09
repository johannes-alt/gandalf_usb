import sys, time, signal
from select import select

sys.path.append('.')
sys.path.append('./gandalf_usb/')
import gandalf, decode


def _fetch(g, queue, rr):
    ret = g.spyRead(0x4000, 1000)
    start = time.time()
    cnt = 0
    while ret and rr.value == 1:
        cnt += len(ret)
        queue.put(ret)
        ret = g.spyRead(0x4000, 200)
    print('Total data transferred: %.2f MB (%.2f MB/s)'%(cnt*1e-6, cnt*1e-6/(time.time()-start)))


def count_evnts(g, rr, thresh=205):
    import numpy as np
    from multiprocessing import Queue, queues

    queue = Queue() # queue with unlimited size

    ### selftrig config
    # store current config
    oldconf = [g.readUSB(0x2b00+i*4) for i in range(9)]
    time.sleep(.01)
    g.writeUSB(0x2b00, 0x10500051)
    for i in range(8): g.writeUSB(0x2b04+4*i, thresh<<16|thresh)
    g.writeUSB(0x7034, 2)
    time.sleep(.1)

    ### clear possible readout errors
    g.set_spyread(False)

    ### enable readout and start spill
    g.set_spyread(True)
    g.set_spill(True)

    # Put the reading from the device into its own process
    _t = Process(target=_fetch, args=[g, queue, rr])

    # enable self trigger for x second
    g.writeUSB(0x703c, 1)
    _t.start()

    time.sleep(.5)
    g.writeUSB(0x703c, 0)

    cnt, first, last = [0]*16, [0]*16, [0]*16
    while rr.value == 1:
        try:
            chunk = queue.get(block=True, timeout=.2)
            for ev in decode.events([chunk]):
                if first[ev.ch] == 0 or (ev.time-first[ev.ch])*4*1e-9 > 1:
                    first[ev.ch] = ev.time
                last[ev.ch] = ev.time
                cnt[ev.ch] += 1
        except queues.Empty as e:
            break

    # make sure the queue is empty
    while not queue.empty(): queue.get()
    _t.join()

    deltas = np.array(last)-np.array(first)
    for i in range(16):
        if deltas[i]>0:
            print('ch %i: %.2f s; %.3f KHz'%(i, deltas[i]*4*1e-9, cnt[i]/(deltas[i]*4*1e-6)))

    ### stop spill and disable readout
    g.set_spill(False)
    g.set_spyread(False)

    # reset old config
    for i, x in enumerate(oldconf):
        g.writeUSB(0x2b00+i*4, x)
    g.writeUSB(0x7034, 2)
    time.sleep(.1)


def thresh_test(hexid, rr):
    g = gandalf.Gandalf(hexid, True)
    #for thresh in range(195,205,1):
    for thresh in range(190,300,20):
        if rr.value == 0: break
        print('Testing threshold value %i'%thresh)
        count_evnts(g, rr, thresh)


if __name__ == '__main__':
    import argparse
    from multiprocessing import Value, Process
    from threading import Thread
    rr = Value('i', 1)

    parser = argparse.ArgumentParser()
    parser.add_argument('hexid', help='gandalf hexid')
    args = parser.parse_args()

    def doexit(signum, frame):
        global rr
        rr.value = 0

    signal.signal(signal.SIGINT, doexit)
    signal.signal(signal.SIGTERM, doexit)

    thread = Thread(
        target=thresh_test,
        args=[int(args.hexid, 16), rr])
    thread.start()

    # keyboard input loop
    while rr.value == 1 and thread.is_alive():
        rlist, _, _ = select([sys.stdin], [], [], 1)
        if rlist and sys.stdin.read(1) == "q":
            break

    rr.value = 0
    thread.join()
