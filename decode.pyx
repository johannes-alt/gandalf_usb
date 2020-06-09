# cython: nonecheck=True
#        ^^^ Turns on nonecheck globally

class event(object):
    #cdef public unsigned int time_lsb = None
    #cdef public unsigned int time_msb = None
    #cdef readonly unsigned int time
    #cdef readonly unsigned int endtime
    #cdef readonly unsigned short full
    #cdef readonly unsigned short ch
    #cdef readonly unsigned short no
    #cdef readonly unsigned short srcid
    def __init__(self):
        self.samples = []
        self.time_lsb = None
        self.time_msb = None
        self.time = None
        self.ch = -1
        self.srcid = None
        self.full = 0
        self.endtime = None
        self.no = -1
        self.biterr = False

    def __str__(self):
        return "ch: %i; no: %i"%(self.ch, self.no)

def events(source, debug=False, out=None):
    import numpy as np
    if debug and out is None:
        import sys
        out = sys.stdout
    cdef unsigned int val

    ev = None
    words = []
    bytes = 0
    first = True
    for chunk in source:
        for val in np.ndarray((len(chunk)/4,), '>I', chunk):
#            print('%08X'%val)
            if debug:
                words.append(val)
                bytes += 4

            if val>>30==0b10:
                if not first and (ev is not None or len(words)>1):
                    msg = "unexpected header or unassigned words (%s, new ev: %i)"%(str(len(words)) if ev is None else ev, val>>8&0xffff)
                    for v in words: out.write('%08X\n'%v)
                    if debug: yield Exception(msg+", %f kB"%(bytes/1024))
                    else: print(msg)
                    words = words[-1:] # keep the new header word

                ev = event()
                ev.srcid = val&0xff
                ev.biterr = (val>>23&0x1)==1
                ev.no = val>>8&0xffff
                #if debug and ev.full==1: print('lff !!')
                first = False
                continue

            if ev is None: continue

            if val>>30==0b11:
                ev.endtime = val&((1<<30)-1)
                length = ev.endtime-ev.time&((1<<30)-1)
                if length<0: length += 1<<30
                if len(ev.samples)!=(length-2)*2 and \
                               len(ev.samples)!=(length-2)*2-2 and \
                               len(ev.samples)!=(length-1)*4-2 and \
                               len(ev.samples)!=length*2+1:
                    msg = "missing samples, skipping event (%i vs %i; lff: %i; ch: %i)"%(len(ev.samples),length,ev.full,ev.ch)
                    if debug:
                        for v in words: out.write('%08X\n'%v)
                        yield Exception(msg+", %f kB"%(bytes/1024))
                        yield ev
                    else: print(msg)
                else:
                    yield ev
                ev = None
                words = []

            elif val>>30==0b01:
                if ev.time_msb is None:
                    ev.time_msb = val&((1<<30)-1)
                elif ev.time_lsb is None:
                    ev.time_lsb = val&((1<<30)-1)
                    ev.time = (ev.time_msb<<30)|ev.time_lsb
                else:
                    msg = "unexpected time info, skipping event (%s)"%(ev)
                    for v in words: out.write('%08X\n'%v)
                    if debug: yield Exception(msg+", %f kB"%(bytes/1024))
                    else: print(msg)
                    ev = None
                    words = []

            else:
                ch = val>>24&0xf
                full = val>>29&0x1
                #if debug and full==1: print('lff !!')
                if ev.ch == -1: ev.ch = ch
                elif ev.ch != ch:
                    msg = "channel number not matching, skipping event (%i vs %i; lff: %i)"%(ev.ch, ch, full)
                    for v in words: out.write('%08X\n'%v)
                    if debug: yield Exception(msg+", %f kB"%(bytes/1024))
                    else: print(msg)
                    ev = None
                    words = []
                else:
                    ev.samples.extend([val&0xfff,val>>12&0xfff])


cdef unsigned int expand(unsigned int pattern):
    cdef unsigned int res = 0
    cdef unsigned int i = 0
    for i in range(0, 32, 4):
        res |= pattern<<i
    return res


#cdef unsigned int lfsr_next(unsigned int pattern):
#    cdef unsigned int a = (pattern>>3)&1
#    cdef unsigned int b = (pattern>>2)&1
#    return (pattern&0x7)<<1 | (not ( a^b ))

cdef unsigned int lfsr_next(unsigned int pattern):
    cdef unsigned int a = (pattern>>31)&1
    cdef unsigned int b = (pattern>>21)&1
    cdef unsigned int c = (pattern>>1)&1
    cdef unsigned int d = (pattern>>0)&1
    return pattern<<1 | (not ( a^b^c^d ))

def lfsr(source, debug=False):
    import numpy as np
    cdef long armed = 0
    cdef unsigned int pattern = 0x0
    cdef unsigned int n = 0
    cdef unsigned int word
    cdef unsigned int i
    for chunk in source:
        for word in np.ndarray((len(chunk)/4,), '>I', chunk):
            if word == 0x0 or pattern == 0x0:
                if armed <= 0:
                    #if debug: yield Exception('%i: skipped %i words to next begin marker'%(n, -1*armed))
                    pattern = word
                elif word != pattern:
                    if debug: yield Exception('%i: unexpected begin marker'%(n))
                    pattern = 0x0
                armed = 1

            #if debug: print('%08X %08X'%(word, expand(pattern)))
            n += 1

            if armed <= 0:
                armed -= 1
                continue

            if word != pattern:
                if debug: yield Exception('%i: pattern doesnt match %08X %08X'%(n, word, pattern))
                armed = 0
                pattern = 0x0
                continue

            yield word
            pattern = lfsr_next(pattern)
