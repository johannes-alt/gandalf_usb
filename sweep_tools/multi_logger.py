import multiprocessing, threading, logging, sys, traceback

class Whitelist(logging.Filter):
    def __init__(self, *whitelist):
        self.whitelist = [name for name in whitelist]

    def filter(self, record):
        if len(set(self.whitelist).intersection(vars(record).values()))!=0:
            return True
        return False

class Blacklist(logging.Filter):
    def __init__(self, *blacklist):
        self.blacklist = [name for name in blacklist]

    def filter(self, record):
        if len(set(self.blacklist).intersection(vars(record).values()))!=0:
            return False
        return True

#def customEmit(self, record):

#    try:
#        self.last_len+=1
#    except:
#        self.last_len=1
#        self.flush()
#    try:
#        msg = self.format(record)
#        if "ERROR" not in msg and "LOADING WAS SUCCESFULL" not in msg and "LOADING PROCEDURE STARTED" not in msg:
#            msg = "*"
#        elif self.last_len==1:
#            msg=msg+"\n"
#        else:
#	    msg="\n"+msg+"\n"

#        try:
#            if getattr(self.stream, 'encoding', None) is not None:
#                self.stream.write(msg.encode(self.stream.encoding))
#            else:
#                self.stream.write(msg)
#        except UnicodeError:
#            self.stream.write(msg.encode("UTF-8"))
#        self.flush()
#    except (KeyboardInterrupt, SystemExit):
#        raise
#    except:
#        self.handleError(record)

class cust_stream_handler(logging.StreamHandler):
    
    def emit(self, record):

        try:
            self.last_len+=1
        except:
            self.last_len=1
            self.flush()
        try:
            msg = self.format(record)
            if "ERROR" not in msg and "LOADING WAS SUCCESFULL" not in msg and "LOADING PROCEDURE STARTED" not in msg:
                msg = "*"
            elif self.last_len==1:
                msg=msg+"\n"
            else:
	        msg="\n"+msg+"\n"

            try:
                if getattr(self.stream, 'encoding', None) is not None:
                    self.stream.write(msg.encode(self.stream.encoding))
                else:
                    self.stream.write(msg)
            except UnicodeError:
                self.stream.write(msg.encode("UTF-8"))
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class MultiProcessingLog(logging.Handler):
    def __init__(self, log_file_base_name, mode="w",file_loger_types=[]):
        logging.Handler.__init__(self)

        self._handler=None
        if log_file_base_name!=None:
            log_file_name=get_log_file(log_file_base_name,"main")
            self._handler = logging.FileHandler(log_file_name, mode)
            self._handler.addFilter(Whitelist("MainProcess"))

        self._file_handlers=[]
        if log_file_base_name!=None:
            for lt in file_loger_types:
                log_file_name=get_log_file(log_file_base_name,lt)
                self._file_handlers.append(logging.FileHandler(log_file_name, mode))
                self._file_handlers[-1].addFilter(Whitelist(lt))
	
	#setattr(logging.StreamHandler, logging.StreamHandler.emit.__name__, customEmit)
        #self._stream_handler = logging.StreamHandler(sys.stdout)        
	self._stream_handler =cust_stream_handler(sys.stdout)        
	self._stream_handler.addFilter(Blacklist("DEBUG"))
        
        self.queue = multiprocessing.Queue(-1)

	self.stop_thread=False

        t = threading.Thread(target=self.receive)
        t.daemon = True
        t.start()

    def setFormatter(self, fmt):
        logging.Handler.setFormatter(self, fmt)
        if self._handler!=None: self._handler.setFormatter(fmt)
        for fh in self._file_handlers:
            fh.setFormatter(fmt)
        self._stream_handler.setFormatter(fmt)
    
    def receive(self):
        while True:
            try:
                record = self.queue.get()
                
                if self._handler!=None: self._handler.handle(record)
                for fh in self._file_handlers:
                    fh.handle(record)
                
                self._stream_handler.handle(record)
            	
		if self.stop_thread==True:
		    break
	    
	    except (KeyboardInterrupt, SystemExit):
                raise
            except EOFError:
                break
            except:
                traceback.print_exc(file=sys.stderr)
	
	self.stop_thread=False
    
    def send(self, s):
        self.queue.put_nowait(s)

    def _format_record(self, record):
        # ensure that exc_info and args
        # have been stringified.  Removes any chance of
        # unpickleable things inside and possibly reduces
        # message size sent over the pipe
        if record.args:
            record.msg = record.msg % record.args
            record.args = None
        if record.exc_info:
            dummy = self.format(record)
            record.exc_info = None

        return record

    def emit(self, record):
        try:
            s = self._format_record(record)
            self.send(s)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def close(self):
        if self._handler!=None: self._handler.close()
        self._stream_handler.close()        
        for fh in self._file_handlers:    
            fh.close()   
        logging.Handler.close(self)


import os,time,datetime

def get_log_file(file_name,ident=""):

    path=os.path.dirname(file_name)+"/"
    log_file_name=ident+"_"+os.path.basename(file_name)

    files = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        files.extend(filenames)
        break

    files_dates=[]
    for f in files:
        t = os.path.getmtime(path+f)
        files_dates.append([path+f,datetime.datetime.fromtimestamp(t)])

    files_dates.sort(key=lambda x: x[1])

    log_files=[]
    for el in files_dates:
        if log_file_name in el[0].split("/")[-1]:
            log_files.append(el[0])
            
    log_file=""
    log_file=path+log_file_name+"_"+str(len(log_files))

    return log_file
    

