import sys
import time
import usb1
import libusb1
import struct
from multiprocessing import Lock

debugMode = False


def listDevices():
    statusWords = []
    # find all devices
    ctxt = usb1.USBContext()
    devs = ctxt.getDeviceList()
    for dev in devs:
        if dev.getVendorID() != 0x4B4 or dev.getProductID() != 0x1002:
            continue
        devh = dev.open()
        ret = devh.controlRead(libusb1.LIBUSB_RECIPIENT_DEVICE | libusb1.LIBUSB_TYPE_VENDOR, 0x40, 0xfc, 0,
                               4)  # read ID
        devh.close()
        assert len(ret) is 4  # check tranfer length
        statusWords.append(struct.unpack('>I', ret)[0])
    return statusWords


def debug(dbgtext):
    if debugMode == True:
        print >> sys.stderr, dbgtext


class Gandalf:
    def __init__(self, hexid, claimEPs=False):
        self.hexid = hexid
        self.ctxt = None
        self.devh = None
        self.dev = None
        self.lock = Lock()
        self.openDevice(hexid, claimEPs)

    def sendControlCommand(self, val):
        if val == 0:
            rcpt = libusb1.LIBUSB_RECIPIENT_ENDPOINT
        else:
            rcpt = libusb1.LIBUSB_RECIPIENT_DEVICE
        self.lock.acquire()
        self.devh.controlWrite(rcpt |  # request target
                               libusb1.LIBUSB_TYPE_VENDOR,  # vendor request
                               0x40,  # destination: cpld config block
                               val, 0, bytes([0])  # value, index, length
                               )
        self.lock.release()

    def writeUSB(self, val, data):
        data = struct.pack('>I', data)
        assert len(data) is 4
        self.lock.acquire()
        ret = self.devh.controlWrite(
            libusb1.LIBUSB_RECIPIENT_DEVICE |  # request target
            libusb1.LIBUSB_TYPE_VENDOR,  # vendor request
            0xC0,  # destination: cpld config block
            val, 0, data  # value, index, data array
        )
        self.lock.release()
        assert ret is 4  # check tranfer length

    def readUSB(self, val):
        if val < 0x1000:
            dest = 0x40
        else:
            dest = 0xC0
        self.lock.acquire()
        ret = self.devh.controlRead(
            libusb1.LIBUSB_RECIPIENT_DEVICE |  # request target
            libusb1.LIBUSB_TYPE_VENDOR,  # vendor request
            dest,  # destination: config or protocol block
            val, 0, 4  # value, index, length
        )
        self.lock.release()
        assert len(ret) is 4  # check tranfer length
        return struct.unpack('>I', ret)[0]

    def sendConfigurationFile(self, fname):
        with open(fname, "rb") as f:
            self.lock.acquire()
            while 1:
                chunk = f.read(0x4000)
                if len(chunk) == 0:
                    break
                self.devh.bulkWrite(0x02, chunk)  # write to EP2
            self.devh.bulkWrite(0x02, bytes([0] * 0x4000))  # some more byte for finishing fpga startup
            self.lock.release()

    def openDevice(self, hexid, claimEPs):
        # find our device
        self.ctxt = usb1.USBContext()
        devs = self.ctxt.getDeviceList()
        for dev in devs:
            if dev.getVendorID() != 0x4B4 or dev.getProductID() != 0x1002:
                continue
            self.dev = dev
            self.devh = self.dev.open()
            # self.devh.resetDevice()
            devStatus = self.readUSB(0xFC)
            if ((devStatus >> 20) & 0xFF) == hexid:
                break
            self.devh.close()
            self.devh = None
            self.dev = None

        # was it found?
        if self.dev is None:
            print >> sys.stderr, "GANDALF with hexID %02x not found" % hexid
            sys.exit()

        if claimEPs == False:
            return

        self.maxTransferSize = 0x800000  # 1MB

        if self.devh.kernelDriverActive(0):
            self.devh.detachKernelDriver(0)
            print >> sys.stderr, "detachKernelDriver(0)"

        if self.devh.kernelDriverActive(1):
            self.devh.detachKernelDriver(1)
            print >> sys.stderr, "detachKernelDriver(1)"

        # self.devh.setConfiguration(0)  # this is not working !
        # also self.devh.releaseInterface(0) is not working...
        self.devh.claimInterface(0)

    def configureDevice(self, file1, file2):
        self.sendControlCommand(0x0010)  # reset/prog command -> scount.vhd
        self.sendControlCommand(0x0000)  # prepare for config data in EP2 -> scount.vhd
        self.sendConfigurationFile(file1)  # sys.argv[1]
        self.sendControlCommand(0x0014)  # switch to 2nd FPGA -> scount.vhd
        self.sendControlCommand(0x0000)  # prepare for config data in EP2 -> scount.vhd
        self.sendConfigurationFile(file2)
        return self.readUSB(0xFC)

    def is_configured(self):
        return (self.readUSB(0xFC)>>28) == 0xF

    def spyRead(self, length=0x4000, timeout=2000):
        """Try to read maximum <length> bytes from the SpyFIFO. Returns after <timeout> ms."""
        self.lock.acquire()
        try:
            ret = self.devh.bulkRead(0x86, min(length, self.maxTransferSize), timeout)
        except usb1.USBErrorTimeout as e:
            ret = e.received
        self.lock.release()
        debug("USBlen = %d" % len(ret))
        return ret

    def amc_config(self, window, latency, prescaler):
        v = self.readUSB(0x20d0)
        old_p = v>>12

        v = self.readUSB(0x2b00)
        old_w = v>>16
        old_l = v&0xffff

        ### set prescaler:baseline
        self.writeUSB(0x20d0, prescaler << 12 | 0x0c2)

        ### set win:lat
        self.writeUSB(0x2b00, window << 16 | latency)

        ### load config
        time.sleep(0.01)
        self.writeUSB(0x7034, 2)
        time.sleep(0.01)
        print('Setting window, latency, prescaler (old vals): %i, %i, %i (%i,%i,%i)'%
              (window,latency,prescaler,old_w,old_l,old_p))



    def set_spyread(self, onoff):
        self.writeUSB(0x7118, 0)
        self.writeUSB(0x711c, 0)
        self.writeUSB(0x7120, int(onoff))
        time.sleep(0.01)

    def set_spill(self, onoff):
        if onoff:
            self.writeUSB(0x7044, 2)
        else:
            self.writeUSB(0x7048, 2)
        time.sleep(0.1)

    def trigger(self):
        self.writeUSB(0x704c, 2)
        time.sleep(0.01)

    def status(self):
        self.writeUSB( 0x7058, 2)
        time.sleep(.01)
        return self.readUSB(0x280c)
