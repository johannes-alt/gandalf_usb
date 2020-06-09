import sys
import socket
import gzip
import zlib
import time

try:
    sys.path.append("/users/gotzl/workspace/gandalf_usb")
    import gandalf
except:
    pass


def activate_zlib():
    wbits = -zlib.MAX_WBITS
    compress = zlib.compressobj(5, zlib.DEFLATED, wbits)
    compressor = lambda x: compress.compress(x) + \
                           compress.flush(zlib.Z_SYNC_FLUSH)

    decompress = zlib.decompressobj(wbits)
    decompressor = lambda x: decompress.decompress(x) + \
                             decompress.flush()
    return (compressor, decompressor)


def device_source(hexid, cond=lambda: True):
    if isinstance(hexid,gandalf.Gandalf): g = hexid
    else: g = gandalf.Gandalf(hexid, True)

    ### init gp
    g.writeUSB(0x70b0, 2)
    time.sleep(0.01)

    ### copy eeprom to configmem
    g.writeUSB(0x7020, 2)
    time.sleep(0.1)

    ### set dacs
    g.writeUSB(0x702c, 2)
    time.sleep(0.01)

    # clear spy fifo
    g.spyRead(0x20000, 200)
    g.sendControlCommand(0x08)  # UsbPktEnd command -> scount.vhd
    time.sleep(0.1)
    g.spyRead(0x20000, 200)

    ### disable readout and reset errors
    g.set_spyread(False)

    ### reset biterr flag
    g.writeUSB(0x707c, 2)
    time.sleep(0.01)

    ### enable spy readout
    g.set_spyread(True)

    ### start spill
    g.set_spill(True)

    # FIXME:
    #   * must be >=0x200;
    #   * also, not sure why, larger chunks ('0x800') leads to 'corruped' events; (is this still true ???)
    #   * USB3 doesn't work with <0x400
    length = 0x800
    length = 0x1000
    length = 0x4000 # to maximize throughput with USB2, why not keep it there ??

    try:
        while cond():
            ret = g.spyRead(length, 100)
            if len(ret) > 0: yield ret

    except GeneratorExit:
        g.set_spill(False)
        g.set_spyread(False)
        del g


def netcat_source(hostname, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((hostname, port))
    #     s.sendall(content)
    s.shutdown(socket.SHUT_WR)

    _, dec = activate_zlib()  # zlib.decompressobj(32 + zlib.MAX_WBITS)  # offset 32 to skip the header

    rv = bytes()
    while True:
        data = s.recv(4096)
        if data == "":
            break

        rv += dec(data)
        n_words = int(len(rv) / 4)
        if n_words == 0:
            continue

        # align rv to 32bits
        rv_ = rv[:4 * n_words]
        rv = rv[4 * n_words:]

        yield rv_

    print("Connection closed.")
    s.close()


def file_source(filename):
    if '.gz' in filename:
        open_with = gzip.open
    else:
        open_with = open

    with open_with(filename, 'rb') as f:
        while True:
            data = f.read(4096)
            if len(data)==0: break
            yield data


def netcat_sink(source=device_source, args=None):
    if args is None: args = [0x03]

    HOST = ''  # Symbolic name meaning all available interfaces
    PORT = 12345  # Arbitrary non-privileged port

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('Socket created')

    try:
        s.bind((HOST, PORT))
    except socket.error as msg:
        print('Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
        sys.exit()

    print('Socket bind complete')

    s.listen(10)
    print('Socket now listening')

    while True:
        # wait to accept a connection - blocking call
        conn, addr = s.accept()

        # display client information
        print('Connected with ' + addr[0] + ':' + str(addr[1]))
        enc, _ = activate_zlib()  # zlib.compressobj(5)
        for data in source(*args):
            rv = enc(data)
            if len(rv) == 0:
                continue

            try:
                conn.sendall(rv)
            except:
                break

        #         conn.sendall(enc.flush())
        print('Closing connection.')
        conn.close()
    s.close()


def abstract_sink(sink, source, args, verbose=False):
    """
    Read data from the source and put them into a sink
    :param sink: function that accepts the data
    :param source: source to read data from, defaults to 'device_source'
    :param args: arguments for the function used as 'source'
    :param verbose: print status information every second (if data is present...)
    """
    start = time.time()
    round_start = start
    size, total = 0, 0
    for data in source(*args):
        sink(data)

        if not verbose: continue

        n = len(data)

        size += n
        total += n

        stop = time.time()
        if stop - round_start > 1:
            print('abstract_sink: %.2f kB/s'%(size / (1024 * (stop - round_start))))
            round_start = time.time()
            size = 0

    if verbose:
        print('abstract_sink: Total: %.2f kB / %.2f kB/s'%(total/1024, total / (1024 * (time.time() - start))))


def file_sink(filename='/dev/null', source=device_source, args=None, verbose=False):
    """
    Read data from the source and put them into a file.
    :param filename: filename to put the data in, compress on-the-fly if ends with .gz
    :param source: source to read data from, defaults to 'device_source'
    :param args: arguments for the function used as 'source'
    :param verbose: print status information every second (if data is present...)
    """
    if args is None: args = []

    if '.gz' in filename:
        open_with = gzip.open
    else:
        open_with = open

    with open_with(filename, 'wb') as out:
        abstract_sink(out.write, source, args, verbose)


def queue_sink(queue, source=device_source, args=None, verbose=False):
    """
    Read data from the source and put them into a file.
    :param queue: queue object to dump data in
    :param source: source to read data from, defaults to 'device_source'
    :param args: arguments for the function used as 'source'
    :param verbose: print status information every second (if data is present...)
    """
    if args is None: args = []
    abstract_sink(queue.put, source, args, verbose)


if __name__ == '__main__':
    import argparse, signal

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', dest='file', help='filename to write to (use .gz suffix to compress it)')
    parser.add_argument('hexid', nargs=1, help='gandalf hexid')
    args = parser.parse_args()

    hexid = int(args.hexid[0],16)
    if args.file:

        rr = 1
        def doexit(signum, frame):
            global rr
            rr = 0

        signal.signal(signal.SIGINT, doexit)
        signal.signal(signal.SIGTERM, doexit)
        file_sink(args=[hexid, lambda: rr == 1], filename=args.file, verbose=True)

    else:
        netcat_sink(args=[hexid])
