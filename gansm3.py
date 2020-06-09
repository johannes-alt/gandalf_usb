#!/usr/bin/env python2
import gandalf
import sys,os

if len(sys.argv) >= 4 and os.path.isfile(sys.argv[1]) and os.path.isfile(sys.argv[2]):
    hex_ids = list(map(lambda x:int(x,16), sys.argv[3:]))
    for hex in hex_ids:
        g = gandalf.Gandalf(hex, True )
        ret = g.configureDevice(sys.argv[1],sys.argv[2])
        print ("%08x" % ret)
else:
    print("usage: " + sys.argv[0] + " <FPGAfile1.bin> <FPGAfile2.bin> <hexID> (<hexID> ...)")
