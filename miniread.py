#!/usr/bin/env python2

import time, struct, io, os, pickle
import traceback

import gandalf
import numpy as np


si_cfgs = {
    20: '20_to_440_bw10_ilm.txt',     # this is the default config hardcoded in the firmware
    # 20: '20_to_480_bw10.txt',       # config w/o ILM will result in bit errors!
    50: '50_to_500_bw10_ilm.txt',
    #100: '100_to_400_bw10_ilm.txt',  # currently not supported
}


def get_latest_event(g):
    ev, data = None, None
    while True:
        ret = g.spyRead(0x400, 100)
        if ret is None or len(ret) == 0: break
        for i in range(0, len(ret), 4):
            val = struct.unpack('>I', ret[i:i + 4])[0]
            if val == 0: data = ''
            if data is not None: data += struct.pack('I', val)
            if val == 0xCFED1200: ev = data
    return ev


def configure_device(g, dsp_bin, mem_bin):
    ret = g.configureDevice(dsp_bin,mem_bin)
    print("%08x" % ret)


def init_device(g):
    ### open Gandalf device
    if not g.is_configured():
        print("GANDALF is not configured.")
        sys.exit()

    ### clear spy fifo
    g.spyRead(0x10000,200)
    g.sendControlCommand(0x08)
    time.sleep(0.1)
    g.spyRead(0x10000,200)

    # sweep cfg
    g.writeUSB(0x2A34, 100<<16|50<<8)

    ### si conf and successive si sweep (waits for tcs_rdy)
    g.writeUSB(0x7028, 2)
    time.sleep(0.01)

    ### init tcs
    ## bor    time.sleep(15)

    g.writeUSB(0x7040, 2)
    time.sleep(0.1)
    ## bos
    g.set_spill(True)
    ## eos
    g.set_spill(False)

    ## wait for the SIs to lock
    i = 0
    while g.status()&0xfff != 0x444:
        if i > 5:
            raise Exception('SIs not locked or no signal; SI status: %02X'%(g.status()&0xfff))
        time.sleep(.1)
        i += 1

    ### now, tcs_rdy should be done and sweep data should be availale in spy_fifo
    if g.status()>>13&1: raise Exception('tcs_rdy not signaled')


def set_si_registers(g, filename, verbose=True):
    addresses, values = [], []
    with open(filename, 'r') as f_:
        for line in f_:
            actLine = line.strip()
            if actLine[0] == "#": continue
            addresses.append(actLine.split(',')[0])
            values.append(actLine.split(',')[1].strip('h').strip())

    addresses = list(map(int, addresses))
    values = list(map(lambda x:int(x, 16), values))

    register_out_A, register_out_B= "|", "|"
    for i in range(len(addresses)):
        register_out_A += "%.2x|"%int(addresses[i])
        register_out_B += "%.2x|"%values[i]

    if verbose:
        print ("\n[+] Register Map:")
        print ("----------------------------------------------------------------------------------------------------------------------------------------")
        print (register_out_A)
        print (register_out_B)
        print ("----------------------------------------------------------------------------------------------------------------------------------------")

    si_addresses = [0x2A00, 0x2200, 0x2600]
    for _ in range(512//8 - len(values)):
        values.append(0)

    if verbose:
        print ("\n[+] G_PARAMS:")
        print ("----------------------------------------------------------------------------------------------------------------------------------------")
        print ("".join(map(lambda x:'%.2x'%x, values[::-1])))
        print ("----------------------------------------------------------------------------------------------------------------------------------------")

    for i in range(0, len(values), 4):
        val = struct.unpack('I', bytearray(values[i:i+4]))[0]
        if verbose: print('%08X: %08X'%(si_addresses[0]+i, val))
        if g is not None:
            for si_address in si_addresses:
                g.writeUSB(si_address+i, val)


def set_si_phase_(clk, cnt_si):
    from sweep_tools import helper_funcs

    chi_cut = 100
    cut_frequencies = [0.4, 0.5]
    si_addresses = [0x2A30, 0x2230, 0x2630]
    new_clk = clk
    # new_clk,_,_ = helper_funcs.do_overlap(clk[cnt_si],
    #                                       44,
    #                                       cut_frequencies=cut_frequencies)
    hist,fits,edge_types,sec_fits,sec_edge_types,rec_fits,rec_x = helper_funcs.fit_undef(
            new_clk,
            "undef%i"%cnt_si,
            pedantic=False,
            si_num=cnt_si,
            chi_cut=chi_cut)
    to_conf_mem,last_rise,fine_step,clk_pos = helper_funcs.stepping_logic(
            new_clk,
            fits,
            edge_types,
            rec_x,
            True,
            coarse_shift=17,
#            coarse_shift=8,
            fine_shift=0)

    print(last_rise,fine_step,clk_pos)
    print(clk[int(last_rise)])
    print(clk[-1])

    sweep_settings="1" #31: shift this si
    sweep_settings+="1"#30: set status to: in phase
    sweep_settings+=str(clk_pos) #29: sweep interface wants 0/1
    sweep_settings+="0"#28: not used
    sweep_settings="%x"%(int(sweep_settings,2))#convert to hex
    sweep_settings+="000"#not used
    return int(sweep_settings+to_conf_mem,16)

def set_si_phase(clk, si_no):
    first = None
    periods = []
    fsteps = 0

    ### get stable periods, ie periods, where undef is 0 for enough steps and get number of fsteps
    for idx,i in enumerate(clk):
        if fsteps < i.fine_step: fsteps = i.fine_step

        if first is None:
            if i.undef==0:
                first=idx
        else:
            if i.undef>0:
                # only use periods with at least 200 fine steps
                if idx-first>200:
                    periods.append([first, idx])
                first = None

    if first is not None:
        periods.append([first, None])
    print(periods)

    undef_period,cycle,crossings,widths = [],[],[],[]
    ### get bit crossing, which is given by the end of the current stable
    ### preiod and the start of the next stable area
    for i,j in zip(periods[:-1],periods[1:]): crossings.append(i[1]+(j[0]-i[1])/2.)
    for i,j in zip(periods[:-1],periods[1:]): widths.append(j[0]-i[1])
    ### get fine steps between two bit crossings
    for i,j in zip(crossings[:-1],crossings[1:]): undef_period.append(j-i)
    ### get the length of a full cycle
    for i,j in zip(undef_period[:-1],undef_period[1:]): cycle.append(j+i)
    period = np.array(cycle).mean()

    print(undef_period, cycle, crossings, widths, period)

    ### we choose the last detected clock edge as reference point
    ref = int(crossings[-1])

    #     ---      --
    #    /   \    /
    # ---     ---
    #            ^
    #            |
    #           ref
    # if we are at a rising edge, choose the previous edge
    if clk[int(ref-period/4.)].zero > 0:
        ref = int(crossings[-2])

    #     ---     --
    #    / ^ \   /
    # ---  |  ---
    #     /  ^
    # target |
    #       ref
    # we want to position the phase into the stable 1 zone
    # since coarsesteps are counted backwards, add <coarse_shift> steps to the ref to go back into the stable zone
    coarse_shift = 7
    coarse = clk[ref].coarse_step + coarse_shift
    fine   = clk[ref].fine_step

    print('Setting phase to coarse/fine %i/%i, ref/shift index %i/%i'%(coarse, fine, ref, ref-(coarse_shift*fsteps)))

    cfg = int('1110',2)<<28 # shift si, set state 'in phase', monitor expected value '1'
    val = cfg|(coarse<<8)|(fine)
    return val

def sweep_check(g):
    try: sweep(g, '/sc/userdata/gotzl/tmp/sweep_%i.pkl'%g.hexid)
    except: pass

    # sweep cfg and fetch new sweep data
    g.writeUSB(0x2A34, 100<<16|25<<8)
    g.writeUSB(0x70f0, 2)

    clk = sweep_fetch(g)
    pickle.dump(clk, open('/sc/userdata/gotzl/tmp/check_%i.pkl'%g.hexid,'wb'))

def sweep(g, pkl=None):
    clk = sweep_fetch(g)
    if args.pkl_path is not None:
        pickle.dump(clk, open('%slast_sweep_%i.pkl'%(args.pkl_path,g.hexid),'wb'))

    val1 = set_si_phase(clk[1], 1)
    val2 = set_si_phase(clk[2], 2)

    si_addresses = [0x2A30, 0x2230, 0x2630]
    g.writeUSB(si_addresses[1], val1) #write shift and settings to conf mem
    g.writeUSB(si_addresses[2], val2)
    time.sleep(0.01)

    ### apply phase setting
    g.writeUSB(0x70f4, 2)

    ## wait for the SIs to be in phase
    time.sleep(1)
    i = 0
    while g.status()&0xfff != 0x4:
        if i > 10:
            raise Exception('SIs not in phase; SI status: %02X'%(g.status()&0xfff))
        time.sleep(1)
        i += 1

def sweep_fetch(g):
    from sweep_tools.decode import sweep_info

    data = bytearray()
    # wait for sweep data to appear
    ret = g.spyRead(0x400, 15000)
    while ret:
        data += ret
        ret = g.spyRead(0x400, 2000)
    print(len(data))

    clk = {}
    while len(data)>=16:
        header = struct.unpack('>I', data[0:4])[0]
        # word is no header word
        if header>>31!=1:
            print ('not a header', header)
            # forget the shitty word
            data = data[4:]
            continue

        info = sweep_info((header>>29)&0x3,
                                 (header>>8)&0xff,
                                 header&0xff)

        info.undef = struct.unpack('>I',data[4:8])[0]
        info.zero = struct.unpack('>I',data[8:12])[0]
        info.one = struct.unpack('>I',data[12:16])[0]
        if info.si_nr not in clk: clk[info.si_nr] = []
        clk[info.si_nr].append(info)

        data = data[16:]
    print(clk.keys(), list(map(len,clk.values())))
    return clk

def init_readout(g):
    ### disable readout  (just in case)
    g.set_spyread(False)

    ### clear spy fifo
    g.spyRead(0x10000,200)
    g.sendControlCommand(0x08)
    time.sleep(0.1)
    g.spyRead(0x10000,200)

    ### reset biterr flag
    g.writeUSB(0x707c, 2)
    time.sleep(0.01)

    ### init gp
    g.writeUSB(0x70b0, 2)
    time.sleep(0.01)

    ### copy eeprom to configmem
    g.writeUSB(0x7020, 2)
    time.sleep(0.1)

    ### set dacs
    g.writeUSB(0x702c, 2)
    time.sleep(0.01)


def set_baseline(g, type_):
    import baseline

    ### enable readout
    g.set_spyread(True)

    ### start spill
    g.set_spill(True)

    try:
        # for chan in range(0,16,2):
        #     print('Processing channel %i'%chan)
        #     minim = baseline.Minimizer(g, chan)
        #     minim.minimize()
        #     print(minim.last)
        res_ = baseline.Minimizer(g).fit(type_)
        print('Final frame-samples mean values:')
        print(res_)
    except Exception as e:
        print('Baseline algo failed: %s'%e)
    finally:
        ### stop spill
        g.set_spill(False)

        ### disable readout
        g.set_spyread(False)

        ### copy configmem to eeprom
        g.writeUSB(0x7024, 2)
        time.sleep(0.1)

def load(hexid, rr):
    try:
        ### open Gandalf device
        g = gandalf.Gandalf(hexid, True)

        is_conf = g.is_configured()
        if not is_conf or args.reload:
            if args.dsp is None:
                dsp_bin = os.environ['GANDALF_BINFILE_FOLDER']+'/gotzl/028/usb/g_dsp.bin'
            else: dsp_bin = args.dsp

            if args.mem is None:
                mem_bin = os.environ['GANDALF_BINFILE_FOLDER']+'/gandalf_mem_2009'
            else: mem_bin = args.mem


            i=0
            while i<3:
                try:
                    print('Configuring')
                    configure_device(g, dsp_bin, mem_bin)
                    if not g.is_configured():
                        raise Exception('Configuring failed')

                    # enable external clk source if requested
                    if args.external:
                        g.writeUSB(0x7014, 1)

                        # 20MHz is the default config hardcoded in the firmware, no need to use another config
                        if args.external != 20:
                            set_si_registers(g, '/sc/gandalf/GandalfTools/%s'%si_cfgs[args.external])

                    # program the SI chips
                    init_device(g)

                    print('Setting SrcID to %02X'%hexid)
                    g.writeUSB(0x2804, hexid)

                    if args.sweepcheck:
                        print('Doing sweep check, ignoring possible sweep errors')
                        sweep_check(g)
                    else:
                        print('Processing sweep, this will take a minute')
                        sweep(g)

                    print('Initiating readout')
                    init_readout(g)
                    break

                except Exception as e:
                    traceback.print_exc()
                    i+=1
                    time.sleep(1)
                    break

        else:
            print('Device already configured - use \'-r\' to reconfigure')

        type_ =  g.readUSB(0x2808)>>20&0xf
        if args.baseline:
            print('Setting baseline, this will take a minute')
            if type_ == 0x04: g.amc_config(200, 1000, 1)
            set_baseline(g, type_)

        # firmware type:
        # 0x04: compass
        # 0x05: self-trigger (xenon)
        if type_ == 0x04:
            print('Applying AMC config')
            g.amc_config(args.window, args.latency, args.prescaler)

        elif type_ == 0x05:
            print('Applying self-trig config')

            n_before, n_over, n_after, thresh = map(int,args.triggercfg.split(':'))
            cfg = n_before<<24 | n_over<<20 | n_after<<4 | args.alternate
            print(cfg)
            #cfg = 0x10500050

            # set self-trigger config
            g.writeUSB(0x2b00, cfg)

            # set thresholds
            for i in range(8): g.writeUSB(0x2b04+4*i, thresh<<16 | thresh)
            # load config
            g.writeUSB(0x7034, 2)

    except Exception as e:
        traceback.print_exc()


if __name__ == '__main__':
    import sys, argparse
    from multiprocessing import Value, Process

    parser = argparse.ArgumentParser()
    parser.add_argument('-b', dest='baseline', action='store_true', help='determine baseline')
    parser.add_argument('-r', dest='reload', action='store_true', help='reconfigure FPGAs')
    parser.add_argument('-d', dest='dsp', default='g_dsp.bin', help='firmware for the DSP')
    parser.add_argument('-s', dest='sweepcheck', action='store_true', help='only do a check of the sweep implementation')
    parser.add_argument('hexid', nargs='+', help='gandalf hexid')
    parser.add_argument('-m', dest='mem', default='gandalf_mem_2009.bin', help='firmware for the mem')
    parser.add_argument('-pk', dest='pkl_path', help='pkl file')

    # COMPASS firmware options
    parser.add_argument('-w', dest='window', default=100, type=int, help='half the size of a frame, ie ~2ns')
    parser.add_argument('-l', dest='latency', default=40, type=int, help='latency in ~4ns')
    parser.add_argument('-p', dest='prescaler', default=250, type=int, help='create debug event every n\'th event')

    # self trigger firmware options
    parser.add_argument('-a', dest='alternate', action='store_true', help='use an alternate self-trigger mode')
    parser.add_argument('-e', dest='external', type=int, help='use external clock source (available options: 20, 50, 100)')
    parser.add_argument('-t', dest='triggercfg', default='10:5:5:210', type=str, help='configuration for the self trigger (format: n_before:n_after:n_over)')

    args = parser.parse_args()

    rr = Value('i', 1)
    threads = list(map(lambda x: Process(
        target=load,
        args=[int(x, 16), rr]), args.hexid))

    # start configuration in parallel, but with some offset to avoid concurrent USB access conflicts
    for _t in threads:
        _t.start()
        time.sleep(1)

    # wait for loading to finish
    list(map(Process.join, threads))

