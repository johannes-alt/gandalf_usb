#!/usr/bin/env python
import gandalf
import sys

if len(sys.argv) < 3:
    print('check the arguments')
    print('expected format (arguments itself can vary): 703c 1 id0 id1 ... idn')
    exit(1)

addr = int(sys.argv[1],16)
val = None
id0 = 2
# check if 2nd arg is not of the form idx
if len(sys.argv[2])!=2:
    val = int(sys.argv[2],16)
    id0 = 3

for i in range(id0, len(sys.argv)):
    g = gandalf.Gandalf(int(sys.argv[i],16))
    if val is None:
        print(hex(g.readUSB(addr)))
    else:
        g.writeUSB(addr,val)


'''
old code (just in case ;) ):
#!/usr/bin/env python
import gandalf
import sys

if len(sys.argv) > 1:
	addr = int(sys.argv[1],16)
	if (addr>>24)!=0xe0:
		print ("addr format: e0id????")
		sys.exit()
	hexid = (addr>>16) & 0xFF
	addr = addr & 0xFFFF
	g = gandalf.Gandalf(hexid)

if len(sys.argv) == 3:
	g.writeUSB( addr , int(sys.argv[2],16) )
elif len(sys.argv) == 2:
		print ("%08x" % g.readUSB( addr ))
else:
	print("usage: " + sys.argv[0] + " <addr> [<data>]")
'''
