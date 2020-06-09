import os, sys, signal, threading, traceback, argparse
import time
import struct

# gandalf time unit
TIMEUNIT = 1 / (0.03888 * 12 * 2)

# pattern to find LDC/GDC header and skip it
PATTERN_DATE = [(0xDA1E5AFE, 16, 'GDC'), (0xDA1E5AFE, 22, 'LDC')]
PATTERN_SLINK = [(0x00000000, 0, 'SLINK_HEADER')]

# some bit masks
CH_BITS = 4
BASELINE_BITS = 11
INTEGRAL_BITS = 16

MSB_BITS = 17
AMPLITUDE_BITS = 14

LSB_BITS = 21
HR_BITS = 10

FRAMESIZE_BITS = 11

EV_TYPE_BITS = 5
SRCID_BITS = 10

SIZE_BITS = 16

STATUS_BITS = 8
TCS_ERROR_BITS = 8
ERROR_WORDS_BITS = 8
FORMAT_BITS = 8

try:
    input = raw_input
except NameError:
    pass

def fetch_events(data_folder, run_no):
    file_ = os.path.join(data_folder, 'run%i.dat' % run_no)
    file_proc = FileProcessor()

    events = []
    file_proc.process_file(file_, events)
    return events


def events(data_file, pattern=None):
    file_proc = FileProcessor()
    if pattern is not None: file_proc.pattern = pattern
    for event in file_proc.process_data(data_file):
        yield event


def frame_events(data_file, pattern=None):
    for evnt in events(data_file, pattern=pattern):
        if evnt.is_frame():
            yield evnt


def print_amplitudes(data_file):
    def signal_handler(signal, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    for ch in range(0,16,2):
        print('chan %i:'%ch)
        for evnt in events(data_file):
            if not ch in evnt.hits: continue
            for hit_ in evnt.hits[ch]:
                print(hit_.amplitude,)


def plot_frames(evnt, ax):
    for ch, samples in evnt.frames.items():
        ax[ch // 2 // 4][ch // 2 % 4].clear()
        ax[ch // 2 // 4][ch // 2 % 4].plot(samples)


def plot_frame_evnts(data_file):
    import matplotlib.pyplot as plt

    print('Hit \'Enter\' for the next frame event. Hit \'Ctrl+C\' and \'Enter\' to stop')

    def signal_handler(signal, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    plt.ion()
    fig, ax = plt.subplots(nrows=2, ncols=4)

    for evnt in frame_events(data_file):
        plot_frames(evnt, ax)
        fig.canvas.draw()
        print(evnt.srcId, evnt.spill, evnt.ev)
        input()


def read_word(file_, accept_end=False):
    w=unpack_word(file_.read(4), accept_end)
    # print(file_.tell(), '%08x'%w)
    #input()
    return w


def unpack_word(bytes_, accept_end=False):
    if bytes_ is None or bytes_ == "":
        return None

    word = struct.unpack('>I', bytes_)[0]

    if word == 0xcfed1200 and not accept_end:
        traceback.print_exc(file=sys.stdout)
        raise Exception('Found unexpected event END marker!')
    #     print '%08x'%(word)
    #     val = ''
    #     for i in range(31,-1,-1):
    #         val += '%i'%(int( ((word>>i)&0x1) ))
    #     print val
    return word


def read_bits(word, bits):
    val = ((1 << bits) - 1) & (word)
    word = word >> bits
    return word, val


class hit(object):
    def __init__(self, file_):
        word = read_word(file_)
        word, self.integral = read_bits(word, INTEGRAL_BITS)
        word, self.baseline = read_bits(word, BASELINE_BITS)
        word, self.ch = read_bits(word, CH_BITS)

        word = read_word(file_)
        word, self.amplitude = read_bits(word, AMPLITUDE_BITS)
        word, self.msb = read_bits(word, MSB_BITS)

        word = read_word(file_)
        word, self.hr = read_bits(word, HR_BITS)
        word, self.lsb = read_bits(word, LSB_BITS)

        self.time = TIMEUNIT * ((self.msb<<LSB_BITS|self.lsb) + self.hr / 1024.)


class event(object):
    def __init__(self):
        self.hits = {}
        self.frames = {}
        self.format = -1

    def is_frame(self):
        return self.format & 0x1f == 26 or self.format & 0x1f == 28 or self.format == 128

    def handle_frame_data(self, file_):
        word = read_word(file_)

        ch = (((1 << CH_BITS) - 1)) & (word >> 20)
        framesize = (((1 << FRAMESIZE_BITS) - 1)) & (word >> 4)
        # framesize is actually the word count
        framesize *= 2

        # print ('frame of size %i'%framesize)

        n = framesize // 2
        self.frames[ch] = []
        for i in range(n):
            word = read_word(file_)
            if not (word >> 31):
                raise Exception("something rotten here... Expected non header word, got %08x"%word)

            self.frames[ch].append(0xfff & (word >> 16))
            self.frames[ch].append(0xfff & word)
        return n + 1

    def read_channel_data(self, file_):

        # skip frame data
        size = 0

        if self.format & 0x1f == 24 or self.format & 0x1f == 20:
            has_data = lambda x: (x >> 31) & 0x1 and x != 0xcfed1200
            while has_data(read_word(file_, accept_end=True)):
                file_.seek(-1 * 4, 1)
                hit_ = hit(file_)
                size += 3
                if hit_.ch not in self.hits:
                    self.hits[hit_.ch] = []
                self.hits[hit_.ch].append(hit_)

        elif self.format & 0x1f == 26 or self.format & 0x1f == 28 or self.format == 128:
            # print('parsing debug')

            # each channel has its own frame/hits block
            for ch in range(16 if (self.format & 0x1f == 26) else 8):
                size += self.handle_frame_data(file_)

                # check for trailer
                word = unpack_word(file_.read(4), accept_end=True)
                if not (word >> 31) & 0x1:
                    size += 1
                    continue

                # print(ch, '%08x'%word)
                # rewind one word if previous was no trailer
                file_.seek(-1 * 4, 1)

                # we are now at the hit list                 
                while True:
                    hit_ = hit(file_)
                    size += 3

                    if hit_.integral != 65518:
                        if hit_.ch not in self.hits:
                            self.hits[hit_.ch] = []
                        self.hits[hit_.ch].append(hit_)

                    # skip cfd info
                    file_.seek(1 * 4, 1)
                    size += 1

                    # check for trailer
                    word = unpack_word(file_.read(4), accept_end=True)
                    if not (word >> 31) & 0x1:
                        size += 1
                        break

                    # rewind one word if previous was no trailer
                    file_.seek(-1 * 4, 1)
        return size


class FileProcessor(threading.Thread):
    def __init__(self):
        super(FileProcessor, self).__init__()
        self._stop = threading.Event()
        # default to DATE data pattern
        try: self.pattern = PATTERN
        except: self.pattern = PATTERN_DATE

    def start(self):
        self._stop.clear()
        self.process_file()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

    def update_histos(self):
        if not hasattr(self, 'canvases'):
            return
        if not hasattr(self, 'hists'):
            return

        for ch in range(0, 16, 1):
            self.canvases[ch].cd()
            self.hists[ch].Draw()
            self.canvases[ch].Update()

    def process_file(self, source=None):
        if source is None:
            source = self.file_

        with source() as file_:
            for _ in self.process_data(file_): pass

    def process_data(self, file_):
        pattern_pos = 0
        last_, mux_event, cur_event = None, None, None

        file_.seek(0, 2)
        file_size = float(file_.tell())
        file_.seek(0)

        while file_.tell() < file_size and not self.stopped():

            if last_ is None or (time.time() - last_) > 1:
                status = ((file_.tell() / file_size) * 100)
                #print 'Processing ... (%i%%)'%status
                self.update_histos()
                last_ = time.time()

            word = read_word(file_, accept_end=True)
            #print 'first word %08x'%word
            if word is None:
                break

            if pattern_pos < len(self.pattern):
                if word == self.pattern[pattern_pos][0]:
                    # print('found %s marker, skipping %i words'%(self.pattern[pattern_pos][2], self.pattern[pattern_pos][1]))
                    #for _ in range(self.pattern[pattern_pos][1]): read_word(file_, accept_end=True)
                    #print()
                    file_.seek(self.pattern[pattern_pos][1] * 4, 1)
                    pattern_pos += 1
                    cur_event = None
                elif pattern_pos>0:
                    sys.stderr.write('something rotten here.. Excpected marker %s\n'%(str(self.pattern[pattern_pos])))
                    pattern_pos = 0
                    cur_event = None
                continue

            # parse ADC data
            if pattern_pos >= len(self.pattern):

                if cur_event is None:
                    cur_event = event()

                    word, cur_event.size = read_bits(word, SIZE_BITS)
                    word, cur_event.srcId = read_bits(word, SRCID_BITS)
                    word, cur_event.ev_type = read_bits(word, EV_TYPE_BITS)

                    # spill/ev no
                    word = read_word(file_)
                    word, cur_event.ev = read_bits(word, 20)
                    word, cur_event.spill = read_bits(word, 11)

                    size = 2

                    smux = False
                    if cur_event.srcId > 900:
                        smux = True
                        mux_event = cur_event
                        mux_event.sub_events = {}

                    try:
                        length = mux_event.size if smux else cur_event.size
                        while (size < length):
                            if smux:
                                cur_event = event()

                                word = read_word(file_)
                                word, cur_event.size = read_bits(word, SIZE_BITS)
                                word, cur_event.srcId = read_bits(word, SRCID_BITS)
                                word, cur_event.ev_type = read_bits(word, EV_TYPE_BITS)

                                while cur_event.srcId in mux_event.sub_events:
                                    cur_event.srcId += 0.1

                                mux_event.sub_events[cur_event.srcId] = cur_event

                                # spill/ev no
                                word = read_word(file_)
                                word, cur_event.ev = read_bits(word, 20)
                                word, cur_event.spill = read_bits(word, 11)
                                size += 2

                            word = read_word(file_)
                            word, cur_event.status = read_bits(word, STATUS_BITS)
                            word, cur_event.tcs_error = read_bits(word, TCS_ERROR_BITS)
                            word, cur_event.error_words = read_bits(word, ERROR_WORDS_BITS)
                            word, cur_event.format = read_bits(word, FORMAT_BITS)

                            size += 1
                            # print(length, cur_event.size, cur_event.format, cur_event.ev, cur_event.spill, cur_event.ev_type)

                            # some events have only slink headers (ie BoS/EoS), so check if there
                            # is actually more data to expect in the slink package
                            if size < cur_event.size:
                                if cur_event.format & 0x1f in [20, 24, 26, 28, 128]:
                                    # now, read channel data
                                    size += cur_event.read_channel_data(file_)

                                # skip tiger words
                                elif cur_event.format & 0x7f == 0:
                                    file_.seek((cur_event.size - 3) * 4, 1)
                                    size += cur_event.size - 3
                                else:
                                    print('Wrong format',cur_event.format)
                                    print(size, length)
                                    if smux:
                                        cur_event = mux_event
                                    raise
                            #                                 cur_event.words = []
                            #                                 while size<cur_event.size-3:
                            #                                     cur_event.words.append(read_word(file_))
                            #                                     size+=1

                        if hasattr(self, 'hists'):
                            for ch in cur_event.hits:
                                for hit_ in cur_event.hits[ch]:
                                    self.hists[hit_.ch].Fill(hit_.amplitude)

                        if smux:
                            cur_event = mux_event

                        yield cur_event
                        #raw_input()

                    except Exception as e:
                        # print ('Corrupted event:',size, cur_event.__dict__)
                        sys.stderr.write(str(e)+"\n")
                        raise e
                        # pass

                    pattern_pos = 0
                    continue
        # done reading, update histos one last time
        self.update_histos()


class open_source():
    def __init__(self):
        self.f = None

    def __enter__(self):
        if args.infile is None:
            print('reading from stdin')
            return sys.stdin
        else:
            if not os.path.isfile(args.infile):
                print('could not find', args.infile)
                exit(1)
            self.f = open(args.infile, 'rb')
            return self.f

    def __exit__(self, type, value, traceback):
        if self.f is not None: self.f.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Decode AMC data.')
    parser.add_argument('-f','--frames', dest='frames', action='store_true',
                        help='Plot frame events, event-by-event')
    parser.add_argument('-r','--raw', dest='raw', action='store_true',
                        help='Read data without GDC/LDC header (i.e. data directly from spyfifo)')
    parser.add_argument('infile', nargs='?', default=None)
    args = parser.parse_args()

    # use PATTERN_DATE if the data file is in valid DATE format with GDC/LDC blocks
    # use PATTERN_SLINK if the data is the raw SLINK block
    if args.raw: PATTERN = PATTERN_SLINK
    else: PATTERN = PATTERN_DATE

    # display frames using matplotlib and exit
    if args.frames:
        with open_source() as source:
            plot_frame_evnts(source)
        exit(0)

    try:
        import amc_ui
        amc_ui.init_ui()

    except Exception as e:
        print("Cannot run UI!")
        print(e)
        exit(1)
