import time,sys
from subprocess import Popen, PIPE
import os
import signal
import multiprocessing
from StringIO import StringIO
import decode as d
import helper_funcs as h
import multi_logger as ml
import logging
from shutil import copyfile

def copy_file(file_i,sub_folder,delim="-"):
    
    index=file_i.rfind("/")
    base_folder=file_i[:index+1]
    file_name=file_i[index+1:]
    sub_dir=base_folder+sub_folder+"/"
    new_file_name=sub_dir+file_name

    if os.path.isfile(file_i): #check if file exists
        
        if os.path.isdir(sub_dir):
            #print "subdir exists"
            pass
        else:
            #print "subdir does not exist...creating"
            os.makedirs(sub_dir)
        
        cnt=0
        while True:
            if os.path.isfile(new_file_name+delim+str(cnt)): #check if new file exists
                #print "file already exists incrementing"
                cnt+=1
            else:
                #print "file does not exist copying"
                copyfile(file_i, new_file_name+delim+str(cnt))
                return
    else:
        #print "base file does not exist"
        return


pipe = None
num_vme_tries=20
num_vxs_bus_tries=3

def vme_write(hex_id_i,addr,val):

    return_code=0
    command=""
    if isinstance(hex_id_i, str):
        command="vme_write e0"+hex_id_i+"2"+addr+" "+val
    else:
        hex_ids=" ".join(hex_id_i)
        command="crate_write 2"+addr+" "+val+" "+hex_ids

    return_code=0
    for i in range(num_vme_tries):
        p = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        (stdout, stderr)=p.communicate()
        return_code=p.returncode
        if return_code==0:
            logging.info("VME WRITE (" + command + ") succesfull")
            logging.debug(stdout)
            logging.debug(stderr)           
            return 0
    logging.error("VME WRITE ("+command+") not succesfull after "+str(num_vme_tries)+" tries...with returncode: "+str(return_code))
    logging.debug(stdout)
    logging.debug(stderr)
    return return_code

def fast_register(hex_id_i,register_addr,register_type="2"):

    return_code=0
    command=""    
    if isinstance(hex_id_i, str):
        command="vme_write e0"+hex_id_i+"7"+register_addr+" "+register_type
    else:
        hex_ids=" ".join(hex_id_i)
        command="crate_write 7"+register_addr+" "+register_type+" "+hex_ids

    return_code=0
    for i in range(num_vme_tries):
   
        p = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        (stdout, stderr)=p.communicate()
        return_code=p.returncode
        if return_code==0:
            logging.info("FAST REGISTER (" + command + ") succesfull")
            logging.debug(stdout)
            logging.debug(stderr)
            return 0

    logging.error("FAST REGISTER ("+command+") not succesfull after "+str(num_vme_tries)+" tries...with returncode: "+str(return_code))
    logging.debug(stdout)
    logging.debug(stderr)
    return return_code

def load_gandalf(hex_id_i,bin_file_i,mem_file_i):

    return_code=0
    command=""  
    if isinstance(hex_id_i, str):
        command="gansm3 " + bin_file_i +" "+mem_file_i+" "+hex_id_i
    else:
        hex_ids=" ".join(hex_id_i)
        command="gansm3 " + bin_file_i +" "+mem_file_i+" "+hex_ids

    for i in range(num_vme_tries):

        p = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        (stdout, stderr)=p.communicate()
        return_code=p.returncode
        if return_code==0:
            logging.info("LOADING GANDALF (" + command + ") succesfull")
            logging.debug(stdout)
            logging.debug(stderr)           
            return 0

    logging.error("LOADING GANDALF ("+command+") not succesfull after "+str(num_vme_tries)+" tries...with returncode: "+str(return_code))
    logging.debug(stdout)
    logging.debug(stderr)
    return -1

def phase_adjust(hex_id_i,clks,si_settings):

    si_addresses=["A30","230","630"]
    coarse_shifts=[si_settings["coarse_shift"]["SiG"],si_settings["coarse_shift"]["SiA"],si_settings["coarse_shift"]["SiB"]]    
    fine_shifts=[si_settings["fine_shift"]["SiG"],si_settings["fine_shift"]["SiA"],si_settings["fine_shift"]["SiB"]]
    ignore_si=[si_settings["ignore_si"]["SiG"],si_settings["ignore_si"]["SiA"],si_settings["ignore_si"]["SiA"]]
    cut_frequencies=si_settings["fft_cut_of"]
    fixed_clk_positions=[si_settings["clk_position"]["SiG"],si_settings["clk_position"]["SiA"],si_settings["clk_position"]["SiB"]]
    pedantic_mode=si_settings["pedantic_mode"]

    for cnt_si, clk in clks.items(): 
        if ignore_si[cnt_si]==True: logging.info("ignoring si "+str(cnt_si)+" for phase adjust") 
        if len(clk)!=0 and ignore_si[cnt_si]==False:
            new_clk,_,_=h.do_overlap(clk,44,cut_frequencies=cut_frequencies)
            hist,fits,edge_types,sec_fits,sec_edge_types,rec_fits,rec_x=h.fit_undef(new_clk,"undef"+str(cnt_si),pedantic=pedantic_mode,si_num=cnt_si,chi_cut=si_settings["chi_cut"])
            logging.info("------phase align status for Si.No. "+str(cnt_si)+"------")
            to_conf_mem,last_rise,fine_step,clk_pos=h.stepping_logic(new_clk,fits,edge_types,rec_x,True,coarse_shift=coarse_shifts[cnt_si],fine_shift=fine_shifts[cnt_si])
            
            sweep_settings="1" #31: shift this si
            sweep_settings+="1"#30: set status to: in phase 
            
            clk_pos_set=fixed_clk_positions[cnt_si]
            if clk_pos_set!=None:
                logging.info("found fixed clk pos type in: "+str(clk_pos_set))
                sweep_settings+=str(clk_pos_set)#29: sweep interface wants 0/1
            else:
                if clk_pos<0:
                    logging.error("could not determin clk pos type: setting it to "+str(0))
                    sweep_settings+=str(0)#29: sweep interface wants 0/1
                else:
                    logging.info("clk pos type automatically set: "+str(clk_pos))
                    sweep_settings+=str(clk_pos) #29: sweep interface wants 0/1
            
            sweep_settings+="0"#28: not used
            sweep_settings="%x"%(int(sweep_settings,2))#convert to hex
            sweep_settings+="000"#not used
            vme_write(hex_id_i,si_addresses[cnt_si],sweep_settings+to_conf_mem) #write shift and settings to conf mem

    logging.info("PHASE ALIGN SET")    
    fast_register(hex_id_i,"0F4") #phase align


def check_lol_los(hex_id_i,num_tries=40,sleep_time=1,settings=None):
    
    key="check_phase_align"
    if settings==None:
        settings=dict()
        settings[key]=dict()
        settings[key]["SiG"]=True
        settings[key]["SiA"]=True
        settings[key]["SiB"]=True
    else:
        for k in settings[key]:
            if settings[key][k]==False: logging.info("!!no lol/los check for "+k+" will be done!!")

    check_si=[settings[key]["SiG"],settings[key]["SiA"],settings[key]["SiB"]]

    cnt_trys=0    
    while True:
        fast_register(hex_id_i,"058")  #update conf values
        time.sleep(sleep_time)
        command="vme_write e0"+hex_id_i+"280c"
        p = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        (stdout, stderr)=p.communicate()

        sis_ok=True
        si_status=[[True,True],[True,True],[True,True]]
        for si_num in range(3):
            to_check=stdout[7-si_num]
            to_check_bin=binary=bin(int(to_check, 16))[2:].zfill(4)
            if check_si[si_num]==True:
                if to_check_bin[-1]!="0":
                    si_status[si_num][1]=False
                if to_check_bin[-2]!="0":
                    si_status[si_num][0]=False
                if False in si_status[si_num]:
                    sis_ok=False
 
        if sis_ok==True:
            logging.info("lol and los ok on all sis: "+stdout.replace("\n",""))
            break
        else: 
            if (cnt_trys==40):
                raise Exception('lol or los problem detected: [SiG[los/lol],SiA[los/lol],SiB[los/lol]]: '+str(si_status)) 
        cnt_trys+=1

def check_phase_adjusted(hex_id_i,num_tries=40,sleep_time=1,settings=None):

    key="check_phase_align"
    if settings==None:
        settings=dict()
        settings[key]=dict()
        settings[key]["SiG"]=True
        settings[key]["SiA"]=True
        settings[key]["SiB"]=True
    else:
        for k in settings[key]:
            if settings[key][k]==False: logging.info("!!no phase check for "+k+" will be done!!")
            
    check_si=[settings[key]["SiG"],settings[key]["SiA"],settings[key]["SiB"]]

    cnt_trys=0    
    while True:
        fast_register(hex_id_i,"058")  #update conf values
        time.sleep(sleep_time)
        command="vme_write e0"+hex_id_i+"280c"
        p = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        (stdout, stderr)=p.communicate()

        sis_ok=[True,True,True]
        for si_num in range(3):
            to_check=stdout[7-si_num]
            to_check_bin=binary=bin(int(to_check, 16))[2:].zfill(4)
            if to_check_bin[-3]!="0" and check_si[si_num]==True:
                sis_ok[si_num]=False
 
        if False not in sis_ok:
            logging.info("PHASE IS ALIGNED: "+stdout.replace("\n",""))
            break
        else: 
            if (cnt_trys==40):
                raise Exception('no ok for phase adjust: ["SiG","SiA","SiB"]: '+str(sis_ok)+" ("+stdout.replace("\n","")+")") 
        cnt_trys+=1

def sigterm_handler(_signo, _stack_frame):
    logging.info("sigterm handler called")    
    terminate()
    sys.exit(0)

def time_out_handler(signum, frame):
    logging.info("timeout is reached!")
    terminate()
    time.sleep(5)
    raise Exception("end of time")

def terminate():
    global pipe
    global path
    if pipe is not None:
        logging.info('killing spyread')
        os.killpg(pipe.pid, signal.SIGTERM)
    path,pipe = None,None

def check_vxs_bus(hex_id,settings,force_fail=False):

    if force_fail==True:
        return False

    logging.info("setting fast register for vxs bus calibration")
    if fast_register(hex_id,"0ac")!=0:
        logging.warning("calibrate vxs fast register failed")
        return False

    time.sleep(1)    

    command="ssh -q -o ConnectTimeout=10 -o UserKnownHostsFile=/dev/null "
    command+="-o StrictHostKeyChecking=no -t %s \"source /etc/profile;source ~/.bashrc;"%settings["tiger_hostname"]
    command+="cd /opt/tiger_trigger_tools/;"
    command+="PYTHONPATH=. python monitor/crate_status.py -c %s\""%hex_id
    p = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    (stdout, stderr)=p.communicate()
    return_code=p.returncode
    if return_code==0:
        logging.info("calibrated vxs bus succesfully")
        return True
    logging.warning("vxs bus calibration failed")
    return False

def care_about_vxs_bus(hex_id,bin_file,mem_file,settings,force=False):
    for i in range(num_vxs_bus_tries):       
        if check_vxs_bus(hex_id,settings,force)==False:
            if load_gandalf(hex_id,bin_file,mem_file)!=0:
                logging.error("loading failed...trying again")
                continue
            stat_coarse_val=hex(settings["sweep_statistics"]).split('x')[1].zfill(4)
            stat_coarse_val+=hex(settings["sweep_coarse_steps"]).split('x')[1].zfill(2)
            if settings["wait_for_TCS_data"]==False:
		stat_coarse_val+="01"
            else:
		stat_coarse_val+="00"
                
	    if vme_write(hex_id,"A34",stat_coarse_val)!=0:
                logging.error("vme command failed...trying again")
                continue
            
            if fast_register(hex_id,"028")!=0:
                logging.error("fast register failed...trying again")
                continue  
            time.sleep(5)
            if check_vxs_bus(hex_id,settings)==True: return True
        else:
            return True
    return False

def sweep(hex_id_i,file_i=None,ASCII=False,proc_si=True,max_tries=10,bin_files_i=[],settings={}):
    
    multiprocessing.current_process().name=hex_id_i
    global pipe
    for sweep_no in range(max_tries):
        logging.info("retrying sweep for the: "+str(sweep_no)+" time")

        if settings["calibrate_vxs_bus"]==True:
            if sweep_no!=0:
                if care_about_vxs_bus(hex_id_i,bin_files_i[0],bin_files_i[1],settings,force=True)==False:
                    if sweep_no!=max_tries-1:
                        logging.warning("vxs_bus_calibration failed...trying again in next sweep turn")
		    else:
                        logging.error("vxs_bus_calibration failed !!!!! A SECOND RELOAD WILL HELP !!!!")
                    continue 
            elif care_about_vxs_bus(hex_id_i,bin_files_i[0],bin_files_i[1],settings)==False:
                logging.warning("vxs_bus_calibration failed...trying again in next sweep turn")
                continue 
        else: 
           if sweep_no!=0:
		#load the module if sweep failed
                if load_gandalf(hex_id_i,bin_files_i[0],bin_files_i[1])!=0:
                    logging.error("loading failed...trying again")
                    continue
                stat_coarse_val=hex(settings["sweep_statistics"]).split('x')[1].zfill(4)
                stat_coarse_val+=hex(settings["sweep_coarse_steps"]).split('x')[1].zfill(2)
                if settings["wait_for_TCS_data"]==False:
                    stat_coarse_val+="01"
	    	else:
	    	    stat_coarse_val+="00"
      	    	if vme_write(hex_id_i,"A34",stat_coarse_val)!=0:
                    logging.error("vme command failed...trying again")
                    continue
                if proc_si==True:
                    #load Si and sweep 
                    if fast_register(hex_id_i,"028")!=0:
                        logging.error("fast register failed...trying again")
                        continue
                else: 
                    #just sweep
                    fast_register(hex_id_i,"0F0")

	#start only to do something if lol and los are ok
        try:
            check_lol_los(hex_id_i,settings=settings)
	except Exception,e:
            if (sweep_no!=max_tries-1):
                logging.warning(str(e))
	    else:
            	logging.error(str(e))     
            continue        

        if ASCII:
            command = "spyread2 "
        else:
            command = "spyread2fast "
        command += hex_id_i
        
        if file_i is not None:
            command += "| tee "+file_i
            
        #open the pipe to the spy fifo
        pipe = Popen(command, stdout=PIPE, shell=True, preexec_fn=os.setsid) 

        decode_thread = d.Decode(pipe.stdout, ASCII) 
        decode_thread.daemon = True
        decode_thread.start()
        
        # wait ten seconds for data to come 
        time.sleep(10)
        if len(decode_thread.clk)==0:
            terminate()
            if (sweep_no!=max_tries-1):
                logging.warning("received no data")
	        logging.warning("a possible reason is that TCS itself sends no data...in this case set <wait_for_TCS_data> to False in xxx.cfg or check TCS system!")
            else:
                logging.error("received no data")
	        logging.error("a possible reason is that TCS itself sends no data...in this case set <wait_for_TCS_data> to False in xxx.cfg or check TCS system!")
            continue
        
        logging.info("received data")   

        # just to check, join is enough
        while decode_thread.is_alive():
            logging.info(str(map(len,decode_thread.clk.values())))
            time.sleep(1)
        logging.debug("received all data")

        decode_thread.join()
        logging.debug("decode thread joined")
        terminate()        
        logging.debug("terminate function done")

        try:    
            phase_adjust(hex_id_i,decode_thread.clk,settings)
            logging.debug("phase_adjust() done")
            if proc_si==True:
                check_phase_adjusted(hex_id_i,settings=settings)        
                logging.debug("check_phase_adjust() done")
	    if file_i is not None: 
	        copy_file(file_i,"succ_sweeps")
                logging.debug("succ sweep file copied")
        except Exception,e:
	    if file_i is not None:            
                copyfile(file_i, file_i+"_failed")
		copy_file(file_i,"failed_sweeps")
                logging.debug("failed sweep file copied")
            if (sweep_no!=max_tries-1):
                logging.warning(str(e))
            else:
	        logging.error(str(e))     
            continue
        
        #if settings["calibrate_vxs_bus"]==True:
        #    if check_vxs_bus(hex_id_i,settings)==False:
        #        logging.error("vxs_bus_calibration failed...trying again in next sweep turn")
        #        continue

        return True
    
    return False

class AppFilter(logging.Filter):
    def filter(self, record):
        record.module_name = multiprocessing.current_process().name
        return True


class gandalf_load_manager:
    
    def __init__(self):
  
        self.hex_ids=[]

        self.load_file_name=None    
        self.out_file_name=None

        self.bin_file=None
        self.mem_file=None
        
        self.sweep_settings=dict()
        self.sweep_settings["sweep_statistics"]=65535 #until 65535
        self.sweep_settings["sweep_coarse_steps"]=60 #until 127
        self.sweep_settings["coarse_shift"]={"SiG":18,"SiA":18,"SiB":18}#18
        self.sweep_settings["fine_shift"]={"SiG":0,"SiA":0,"SiB":0}
        self.sweep_settings["fft_cut_of"]=[[0.4,0.5]]
        self.sweep_settings["check_phase_align"]={"SiG":True,"SiA":True,"SiB":True}
        self.sweep_settings["ignore_si"]={"SiG":False,"SiA":False,"SiB":False}
        self.sweep_settings["clk_position"]={"SiG":None,"SiA":None,"SiB":None}
	self.sweep_settings["pedantic_mode"]=True
        self.sweep_settings["wait_for_TCS_data"]=True
        self.sweep_settings["calibrate_vxs_bus"]=False
        self.sweep_settings["chi_cut"]=None

    def load_and_start_sweep(self):
        load_gandalf(self.hex_ids,self.bin_file,self.mem_file) #loads all given hex_ids
        stat_coarse_val=hex(self.sweep_settings["sweep_statistics"]).split('x')[1].zfill(4)
        stat_coarse_val+=hex(self.sweep_settings["sweep_coarse_steps"]).split('x')[1].zfill(2)
        if self.sweep_settings["wait_for_TCS_data"]==False:
            stat_coarse_val+="01"
        else:
	    stat_coarse_val+="00"
        vme_write(self.hex_ids,"A34",stat_coarse_val) #set num samples and coarse steps here
        fast_register(self.hex_ids,"028") #loads all sis and starts sweep on all sis of given hex_ids
        time.sleep(4) #waiting for filled spy fifos and configuration of si
        #if self.sweep_settings["calibrate_vxs_bus"]==True:
        #    for hexi in self.hex_ids:
        #        care_about_vxs_bus(hexi,self.bin_file,self.mem_file,self.sweep_settings)

    def load_and_sweep_linear(self,check_ident=""):
        self.load_and_start_sweep()
        succesfull_loads=[]
        for hex_id in self.hex_ids:
            print "----------------SWEEPING GANDALF with HEXID", hex_id,"------------------------------------------"
            check_file=None        
            if check_ident!="" and self.load_file_name!=None:
                check_file=self.load_file_name+"_"+hex_id+"_"+check_ident
            succeded=sweep(hex_id,file_i=check_file,ASCII=False,proc_si=True,max_tries=10,bin_files_i=[self.bin_file,self.mem_file],settings=self.sweep_settings) #read & analyse spy fifo data + set and check phase align
            succesfull_loads.append(succeded)
        return succesfull_loads

    def load_and_sweep_paralell(self,check_ident=""):
        self.load_and_start_sweep()

        pool = multiprocessing.Pool(4)
        jobs=dict()
        for hex_id in self.hex_ids:
            check_file=None        
            if check_ident!="" and self.load_file_name!=None:
                check_file=self.load_file_name+"_"+hex_id+"_"+check_ident
            jobs[hex_id]= pool.apply_async(sweep, (hex_id,check_file,False,True,5,[self.bin_file,self.mem_file],self.sweep_settings,))

        results=dict()
        while True:        
            time.sleep(1)            
            for hex_id, job in jobs.iteritems():
                if job.ready()==True:            
                    if hex_id not in results:
                        result=job.get()
                        if result==True:
                            logging.info(hex_id+" has finished loading and sweeping with status: "+str(result))
                        else:
                            logging.critical(hex_id+" has finished loading and sweeping with status: "+str(result))
                        results[hex_id]=result
  
            if len(results)==len(jobs):
                break        

        pool.close()
        logging.debug("pool closed")
        signal.alarm(10)      
        try:        
            pool.terminate()
            logging.debug("pool terminated")
        except:
            logging.debug("can not terminate pool")
        signal.alarm(0)
       
        return results

    def check_sweep_paralell(self,check_ident=""):
        
        fast_register(self.hex_ids,"0F0") #start sweep
        time.sleep(1) #waiting for filled spy fifos since sweep takes quiet some time

        pool = multiprocessing.Pool(4)
        jobs=dict()
        for hex_id in self.hex_ids:
            check_file=None        
            if check_ident!="" and self.load_file_name!=None:
                check_file=self.out_file_name+"_"+hex_id+"_"+check_ident
            jobs[hex_id]= pool.apply_async(sweep, (hex_id,check_file,False,False,1,[self.bin_file,self.mem_file],self.sweep_settings,))

        results=dict()
        while True:        
            time.sleep(1)            
            for hex_id, job in jobs.iteritems():
                if job.ready()==True:            
                    if hex_id not in results:
                        result=job.get()
                        if result==True:
                            logging.info(hex_id+" has finished loading and sweeping with status: "+str(result))
                        else:
                            logging.critical(hex_id+" has finished loading and sweeping with status: "+str(result))
                        results[hex_id]=result
  
            if len(results)==len(jobs):
                break        

        pool.close()
        logging.debug("pool closed")
        signal.alarm(10)      
        try:        
            pool.terminate()
            logging.debug("pool terminated")
        except:
            logging.debug("can not terminate pool")
        signal.alarm(0)
       
        return results

    def check_sweep_status(self,check_ident=""):
        #for testing purposes        
        print "checking the sweep"
        succesfull_sweeps=[]
        for hex_id in self.hex_ids:
            check_file=None        
            if check_ident!="":
                check_file=self.out_file_name+"_"+hex_id+"_"+check_ident
            succeded=sweep(hex_id,file_i=check_file,ASCII=False,proc_si=False,max_tries=1) #sweep + read & analyse spy fifo data + check phase align
            succesfull_sweeps.append(succeded)
        return succesfull_sweeps

    def test_sweep_over_time(self,start_index=0,mes_ident="0",paralell=False):
        #for testing purposes
        n_sweep=start_index        
        while True:
            print "PROCESSING sweep no."+str(n_sweep)
            load_statuses=self.load_and_sweep_linear(check_ident=mes_ident+"_"+str(n_sweep))
            if False in load_statuses:
                print "retrying, error in load_statuses"
                continue
            check_statuses=self.check_sweep_status(check_ident=mes_ident+"_"+str(n_sweep))
            if False in check_statuses:
                print "retrying, error in check_statuses"
                continue
            n_sweep+=1

if __name__ != "__main__":
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)
    signal.signal(signal.SIGALRM, time_out_handler)


