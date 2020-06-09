import struct,time
import threading
import logging

class sweep_info( object ):
    def __init__(self,si_nr,coarse_step,fine_step):
        self.si_nr = si_nr
        self.coarse_step = coarse_step
        self.fine_step = fine_step
        self.zero = None # measured amount of '00'
        self.one = None # measured amount of '11'
        self.undef = None # measured amount of '01','10' or in general everything which is not covered by '00'/'11'
    def get_value(self):
        values = [self.zero,self.one,self.undef]
        return self.undef
#         return (-self.zero+self.one) #* (1 if self.undef==0 else self.undef)
    def is_valid(self):
        if None in [self.undef,self.zero,self.one]: #or sum([self.undef,self.zero,self.one])!=10001:
            return False
        return True
    def __float__(self):
        return float(self.get_value())    
    def __repr__(self):
        return str(self.__dict__)
    
def read_sweep_info(source,ASCII=False):
    data = ''
    while True:
        # always require 4 words in the data buffer
        if ASCII:
            # pack lines in order to have one decoding for binary/ascii mode
            while len(data)/4 < 4:
                line = source.readline()
                # reached end of file
                if len(line)==0:
                    data = ''
                    break
                data += struct.pack('I',int(line,16))
            if len(data)==0:
                break
        else:
            data += source.read(4*4 - len(data)) 

        # In case of piped data, we always have 4*4 word, since read() blocks
        # until it has the correct amount of words
        # This is to stop in case of EOF.
        if len(data)<4*4:
            break
        
        header = struct.unpack('I',data[0:4])[0]
        # word is no header word
        if header>>31!=1:
            #print 'not a header', header
            logging.debug("not a header "+str(header))
            # forget the shitty word
            data = data[4:]
            continue
            
        info = sweep_info((header>>29)&0x3,(header>>8)&0xff,header&0xff)

        info.undef = struct.unpack('I',data[4:8])[0]
        info.zero = struct.unpack('I',data[8:12])[0]
        info.one = struct.unpack('I',data[12:16])[0]
        data = ''
        
        yield info
    
def decode(source,ASCII=False):
    dec = Decode(source,ASCII)
    dec.start()
    dec.join()
    return dec.clk

class Decode(threading.Thread):
    def __init__(self, source, ASCII=False, verbose=False, pedantic=False):
        threading.Thread.__init__(self)
        self.pedantic = pedantic
        self.verbose = verbose
        self.source = source
        self.ASCII = ASCII
        self.clk = {}
        
    def run(self):
        for info in read_sweep_info(self.source,self.ASCII):
            #if len(self.clk[0])==0 and info.si_nr!=0:
            #    msg= 'invalid si_nr, expected si_nr 0: %s'%info
            #    if self.pedantic: raise Exception(msg)
            #    else:
 		    #print msg
		    #logging.debug(msg)
            #    continue
            if info.si_nr not in range(3):
                msg=  'not a vald si nr: %s'%info
                if self.pedantic: raise Exception(msg)
                else:
		    #print msg
		    logging.debug(msg)
                continue
            if not info.is_valid():
                msg=  'invalid info: %s'%info
                if self.pedantic: raise Exception(msg)
                else: 
		    #print msg
		    logging.debug(msg)
                continue

            if info.si_nr not in self.clk: self.clk[info.si_nr] = []
            
            if len(self.clk[info.si_nr])>0 and info.si_nr==self.clk[info.si_nr][-1].si_nr:
                if info.coarse_step == self.clk[info.si_nr][-1].coarse_step:
                    if info.fine_step != self.clk[info.si_nr][-1].fine_step-1:
                        msg= 'invalid info: %s %s'%(info,self.clk[info.si_nr][-1])
                        if self.pedantic: raise Exception(msg)
                        else:
                            #print msg
			    logging.debug(msg)                        
                        continue
                                
            self.clk[info.si_nr].append(info)
                                 
            if self.verbose:
                if info.coarse_step%10==0 and info.fine_step==0:
                    #print info
		    logging.debug(info)
                            
            # stop when 'all' data was read            
            if self.ASCII and (info.si_nr, info.coarse_step, info.fine_step) == (2, 10, 0):
                break
            if (info.si_nr, info.coarse_step, info.fine_step) == (2, 0, 1):
                break
                    
        
    
