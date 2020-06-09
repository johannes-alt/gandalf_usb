#!/usr/bin/env python2
import gandalf
import sys
import time
import os
import struct
import Queue
import multiprocessing
import array

debugMode = False


def info(infotext):
    """print info messages to stderr"""
    print >> sys.stderr, infotext


# TODO: do the byteswapping after reading from the pipe
def bswap(input):
    output = array.array('I', input[:])
    output.byteswap()
    return output.tostring()


class Readout(multiprocessing.Process):
    """Class for the Readout thread.
    It reads the USB SpyFIFO and puts the data to the queue."""

    def __init__(self, work_queue, rr):
        multiprocessing.Process.__init__(self)
        self.work_queue = work_queue
        self.rr = rr

    def run(self):
        info("USB Readout Thread started")
        length = 0x800 #FIXME: not sure why, but larger chunks ('0x800') leads to lots of 'corruped' events
        start = 0
        stop = 0
        while (self.rr.value == 1):
            if (debugMode) and False:
                start = time.time()
                print >> sys.stderr, start - stop, "s wasted"

            ret = g.spyRead(length, 100)  # timeout after 100 ms

            if (debugMode) and False:
                stop = time.time()
                print >> sys.stderr, stop - start, "s for reading", length, "bytes =>",
                if stop - start > 0:
                    print >> sys.stderr, length / (1024 * (stop - start)), "kB/s"
                else:
                    print >> sys.stderr, ""

            if len(ret) > 0:
                self.work_queue.put(ret, True)
        info("USB Readout Thread finished")
        self.work_queue.put_nowait("")  # submit an empty element for date thread to finish


class DataOut(multiprocessing.Process):
    """Class for data output.
    It receives data through the queue and writes it to stdout (raw)"""

    def __init__(self, work_queue, rr, file_name, run_number, date_format=0):
        multiprocessing.Process.__init__(self)
        self.work_queue = work_queue
        self.rr = rr
        self.file_name = file_name
        self.run_number = run_number
        self.date_format = date_format
        self.date_headerlength = {0:0, 1:0, 3:92, 5:96}[date_format]

    def run(self):
        info("DataOut Thread started")

        if self.date_format != 0:
            info("opening file " + self.file_name + " for writing")
            datefile = open(self.file_name, "wb")

        cfed1200 = "cfed1200".decode("hex")
        event_buffer = None
        first_slink_word = None
        startmarker = False
        read_pos = 0
        read_bytes = 0
        slink_len = 0
        total_len = 0
        lastTime = time.time()

        while (self.rr.value == 1):
            if read_bytes - read_pos == 0:
                """try:
                  read_buffer = self.work_queue.get(True,1)
                except Queue.Empty:
                  read_buffer = ""
                  continue
                """
                read_buffer = self.work_queue.get(True)
                read_bytes = len(read_buffer)
                if (debugMode):
                    info("read %d bytes, buffer id %d" % (read_bytes, id(read_buffer)))
                read_pos = 0
                assert (read_bytes % 4 == 0)

            if (read_bytes == 0):
                break  # this was the last element on the queue

            # format 0: print raw data to stdout
            if self.date_format == 0:
                if binary_format:
                    print(read_buffer)
                    read_pos = read_bytes
                else:
                    while read_bytes - read_pos != 0:
                        print('%08X'%struct.unpack('>I',read_buffer[read_pos:read_pos + 4])[0])
                        read_pos += 4
                continue

            # date format: looking for start marker "00000000"
            while startmarker == False and read_bytes - read_pos != 0:
                if read_buffer[read_pos:read_pos + 4] == 0:
                    if (debugMode): info("start marker found at %d" % (read_pos))
                    startmarker = True
                    event_buffer = None
                    first_slink_word = None
                read_pos += 4

            if read_bytes - read_pos == 0:
                continue

            # a new event has just started: create event buffer with header
            if first_slink_word is None:
                first_slink_word = bswap(read_buffer[read_pos:read_pos + 4])
                slink_len = (ord(read_buffer[read_pos + 2]) << 8) + ord(read_buffer[read_pos + 3])
                if (debugMode):
                    info(("Slink length: %i words\nDate Header Length: %i") % (slink_len, self.date_headerlength))
                total_len = 4 * slink_len + self.date_headerlength
                slink_len -= 1  # first slink word is counted in the header bytes
                read_pos += 4

                if read_bytes - read_pos == 0:
                    continue

            if event_buffer is None:
                event_word = (ord(read_buffer[read_pos]) << 24) + (ord(read_buffer[read_pos + 1]) << 16) + \
                             (ord(read_buffer[read_pos + 2]) << 8) + ord(read_buffer[read_pos + 3])
                SpillNo = ((event_word >> 20) & ((1 << 11) - 1))
                EventNo = ((event_word >> 0) & ((1 << 20) - 1))
                event_buffer = self.DateHeader(total_len + 68,
                                               self.run_number,
                                               SpillNo,
                                               EventNo,
                                               first_slink_word,
                                               self.date_format)
                # print status only once per second
                now = time.time()
                if (now - lastTime > 1):
                    info("Spill: %d, Event: %d (%d+%d words)" % (SpillNo, EventNo, slink_len + 1, self.date_headerlength / 4))
                    lastTime = now
                # info("Spill: %d, Event: %d (%d+%d words)" % (SpillNo, EventNo, slink_len + 1, self.date_headerlength / 4))

            # copy data to event buffer
            # print(read_pos , 4 * slink_len, read_pos + 4 * slink_len,read_bytes)
            if read_pos + 4 * slink_len >= read_bytes:
                event_buffer.extend(bswap(read_buffer[read_pos:]))
                if debugMode:
                    info("extending buffer length %i"%(len(event_buffer)/4))
                    info("Slink length: %i" % slink_len)
                    info("read_pos: %i" % read_pos)
                slink_len -= (read_bytes - read_pos) / 4
                read_pos = read_bytes
            else:
                event_buffer.extend(bswap(read_buffer[read_pos:read_pos + 4 * slink_len]))
                read_pos += 4 * slink_len
                slink_len = 0
                if debugMode:
                    info("buffer length %i"%(len(event_buffer)/4))
                    info("Slink length: %i" % slink_len)
                    info("read_pos: %i" % read_pos)

                startmarker = False
                # end marker should be here
                # info("end marker should be at %d: " % read_pos )
                if read_buffer[read_pos:read_pos + 4] == cfed1200:
                    if total_len != len(event_buffer) - self.date_headerlength + 28:
                        info("wrong event length: is %d, should be %d" % (len(event_buffer), total_len))
                    else:
                        if (debugMode): info("event complete")
                        datefile.write(event_buffer)
                else:
                    # for i in range(0, read_pos, 4):print(read_buffer[i:i + 4].encode("hex"))
                    info(("event corrupted: %s") % (read_buffer[read_pos:read_pos + 4].encode("hex")))
                    # TODO: try to recover
                if debugMode: info('\n')

        if self.date_format != 0:
            datefile.close()
        info("Date Thread finished")

    def DateHeader(self, length, run, spill, event, firstword, date_format):
        if date_format == 3:
            return self.DateHeaderV3(length, run, spill, event, firstword)
        elif date_format == 5:
            return self.DateHeaderV5(length, run, spill, event, firstword)

    def DateHeaderV3(self, length, run, spill, event, firstword):
        now = time.time()
        a = bytearray()
        a.extend(struct.pack("<I", length))
        a.extend(struct.pack("<I", 0xDA1E5AFE))
        a.extend(struct.pack("<I", 7))  # event type: (7) physical
        a.extend(struct.pack("<I", 80))  # header size
        a.extend(struct.pack("<I", run))  # run nb
        a.extend(struct.pack("<I", spill))  # spill nb
        a.extend(struct.pack("<I", spill * 0x100000 + event))  # nb in run
        a.extend(struct.pack("<I", event))  # nb in spill
        a.extend(struct.pack("<I", event))  # trigger nb
        a.extend(struct.pack("<I", 1))  # file seq nb
        a.extend(struct.pack("<I", 0))  # det ID
        a.extend(struct.pack("<I", 0))  # det ID
        a.extend(struct.pack("<I", 0))  # det ID
        a.extend(struct.pack("<I", int(now)))  # time
        a.extend(struct.pack("<I", int((now % 1) * 1000000)))  # utime
        a.extend(struct.pack("<I", 0))  # error code
        a.extend(struct.pack("<I", 0))  # dead time s
        a.extend(struct.pack("<I", 1))  # dead time us
        a.extend(struct.pack("<I", 0))  # attr
        a.extend(struct.pack("<I", 0))  # attr
        a.extend(struct.pack("<I", 0x00400000))  #
        a.extend(struct.pack("<I", 0x00400000))  # slink 0
        a.extend(struct.pack("<I", length - self.date_headerlength))  # slink size in bytes
        a.extend(firstword)
        return a

    def DateHeaderV5(self, length, run, spill, event, firstword):
        now = time.time()
        a = bytearray()
        a.extend(struct.pack("<I", length))
        # GDC Header
        a.extend(struct.pack("<I", 0xDA1E5AFE))
        a.extend(struct.pack("<I", 68))  # header size
        a.extend(struct.pack("<I", 0x00030006))  # event version
        a.extend(struct.pack("<I", 7))  # event type: (7) physical
        a.extend(struct.pack("<I", run))  # run nb
        a.extend(struct.pack("<I", spill * 0x100000 + event))  # nb in run
        a.extend(struct.pack("<I", spill * 0x100000 + event))  # nb in run
        a.extend(struct.pack("<I", 0))  # trigger pattern
        a.extend(struct.pack("<I", 0))  # trigger pattern
        a.extend(struct.pack("<I", 3))  # det pattern
        a.extend(struct.pack("<I", 0))  # attr
        a.extend(struct.pack("<I", 0))  # attr
        a.extend(struct.pack("<I", 0x10))  # attr
        a.extend(struct.pack("<I", 0xffffffff))  # LDC
        a.extend(struct.pack("<I", 0))  # GDC
        a.extend(struct.pack("<I", int(now)))  # time
        a.extend(struct.pack("<I", length - 68))  # slink size in bytes
        # LDC Header
        a.extend(struct.pack("<I", 0xDA1E5AFE))
        a.extend(struct.pack("<I", 68))  # header size
        a.extend(struct.pack("<I", 0x00030006))  # event version
        a.extend(struct.pack("<I", 7))  # event type: (7) physical
        a.extend(struct.pack("<I", run))  # run nb
        a.extend(struct.pack("<I", spill * 0x100000 + event))  # nb in run
        a.extend(struct.pack("<I", spill * 0x100000 + event))  # nb in run
        a.extend(struct.pack("<I", 0))  # trigger pattern
        a.extend(struct.pack("<I", 0))  # trigger pattern
        a.extend(struct.pack("<I", 3))  # det pattern
        a.extend(struct.pack("<I", 0))  # attr
        a.extend(struct.pack("<I", 0))  # attr
        a.extend(struct.pack("<I", 0))  # attr
        a.extend(struct.pack("<I", 0))  # LDC
        a.extend(struct.pack("<I", 0))  # GDC
        a.extend(struct.pack("<I", int(now)))  # time
        a.extend(struct.pack("<I", length - 2 * 68))  # slink size in bytes
        # ?
        a.extend(struct.pack("<I", 0x40))  #
        a.extend(struct.pack("<I", 0x40))  #
        a.extend(struct.pack("<I", 0))  #
        a.extend(struct.pack("<I", 0))  #
        a.extend(struct.pack("<I", 0))  #
        a.extend(struct.pack("<I", 0))  #
        a.extend(firstword)
        return a


##################################3
## main
if __name__ == '__main__':
    # check command line parameters
    binary_format = False
    date_format = 0
    hexid = None
    for argmt in sys.argv[1:]:
        if argmt[0] != "-":
            if hexid == None:
                try:
                    hexid = int(argmt, 16)
                except ValueError:
                    info("invalid hexID")
        elif argmt == "-v0":
            binary_format = True
        elif argmt == "-v3":
            date_format = 3
        elif argmt == "-v5":
            date_format = 5

    if len(sys.argv) < 2 or hexid == None:
        info("usage: " + sys.argv[0] + " <hexID> [options]")
        info("options are:")
        info("\t-v0\tpipe raw data words to stdout in binary")
        info("\t-v1\tpipe raw data words to stdout in hex  (default)")
        info("\t-v3\tdate v3 format")
        info("\t-v5\tdate v5 format")
        sys.exit()

    # run number
    file_name,run_number = None, None
    if date_format != 0:
        if os.path.isdir("output"):
            if os.path.isfile("output/runnumber.txt"):
                rnfile = open("output/runnumber.txt", "r")
                run_number = int(rnfile.readline()) + 1
                rnfile.close()
            else:
                run_number = 10000
            rnfile = open("output/runnumber.txt", "w")
            rnfile.write(str(run_number))
            rnfile.close()
            file_name = "output/run" + str(run_number) + ".dat"
        else:
            info("you have to create a directory (or symlink) 'output' in your working directory (" + os.getcwd() + ")")
            sys.exit()

    # open Gandalf device
    g = gandalf.Gandalf(hexid, True)
    if not g.is_configured():
        info("GANDALF is not configured.")
        sys.exit()

    # info messages
    info("stop readout with 'q'+<enter>")
    info("force trigger with 't'+<enter>")
    info("now press enter to start")
    sys.stdin.read(1)
    info("starting DAQ")

    # clear spy fifo
    g.spyRead(0x10000, 200)
    g.sendControlCommand(0x08)
    time.sleep(0.1)
    g.spyRead(0x10000, 200)

    ### disable readout and reset errors
    g.set_spyread(False)

    ### reset biterr flag
    g.writeUSB(0x707c, 2)
    time.sleep(0.01)

    ### enable spy readout
    g.set_spyread(True)

    ### start spill
    g.set_spill(True)

    # multiprocessing state
    rr1 = multiprocessing.Value('i', 1)
    rr2 = multiprocessing.Value('i', 1)
    # create pipe
    work_queue = multiprocessing.Queue()

    # start threads
    thread1 = Readout(work_queue, rr1)
    thread1.start()
    thread2 = DataOut(work_queue, rr2, file_name, run_number, date_format)
    thread2.start()

    # keyboard input loop
    while rr1.value == 1:
        x = sys.stdin.read(1)

        if x == "q":
            info("stopping DAQ!")
            ### stop spill
            g.set_spill(False)
            time.sleep(0.1)
            rr1.value = 0
            g.set_spyread(False)
        elif x == "t":
            ### trigger
            g.trigger()

    # wait for threads to finish
    thread1.join()
    rr2.value = 0
    thread2.join()
