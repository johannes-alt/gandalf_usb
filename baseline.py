#!/usr/bin/python
import sys, io, time

import numpy as np
from scipy.optimize import minimize

def request_data(g):
    for _ in range(2):
        g.writeUSB(0x704c, 2)
        time.sleep(0.01)

class Minimizer():
    def __init__(self, g, channel=None, target_value=200):
        self.target_value = target_value
        self.channel = channel
        self.g = g
        self.last = None

    @staticmethod
    def set_dac_(x, g, channel=list(range(0, 16, 2))):
        ## set dac
        if not isinstance(channel, list): channel = [channel]
        if not isinstance(x[0], list) and not isinstance(x[0], tuple):
            x = [x]*len(channel)

        for i, chan in enumerate(channel):
            addr = int('2%xc%x' % ((chan // 8) * 4,
                                   (chan % 8) * 2), 16)
            dac = x[i][1] << 16 | (x[i][0]&0xffff)
            g.writeUSB(addr, dac)

        ## apply dac
        g.writeUSB(0x702c, 2)
        # let dacs settle
        time.sleep(0.1)

    @staticmethod
    def eval_(x, g, channel=list(range(0, 16, 2))):
        import miniread
        from amc_tools import amc_hax
        Minimizer.set_dac_(x, g, channel)

        ## get frame samples with the current DAC setting
        cnt=0
        while True:
            request_data(g)
            data = miniread.get_latest_event(g)
            ### this call might fail, so try until it succeeds
            try: evnt = next(amc_hax.frame_events(io.BytesIO(data), amc_hax.PATTERN_SLINK))
            except:
                cnt+=1
                if cnt>5: raise Exception('Could not acquire frame event!')
                continue
            #print('event', evnt.spill, evnt.ev, hex(dac))
            break

        frames = [(np.array(evnt.frames[chan][0::2]),
                   np.array(evnt.frames[chan][1::2]))
                  for chan in channel]
        if len(channel)==1: return frames[0]
        return frames

    @staticmethod
    def eval_xenon_(x, g, channel=list(range(0, 16, 2))):
        import decode

        Minimizer.set_dac_(x, g, channel)
        request_data(g)

        data = bytes()
        ret = g.spyRead(0x800, 1000)
        while ret:
            data += ret
            ret = g.spyRead(0x800, 200)

        frames = {}
        for ev in decode.events([data]):
            frames[ev.ch] = ev.samples

        if len(frames) == 8:
            return [(np.array(frames[i][0::2]),
                     np.array(frames[i][1::2]))
                    for i in range(0, 16, 2)]
        else:
            return [(np.array(frames[i]),
                     np.array(frames[i+1]))
                    for i in range(0, 16, 2)]

    def eval(self,x):
        x = list(map(round, x))
        x = list(map(int, x))

        adc0,adc1 = Minimizer.eval_(x, self.g, self.channel)

        ## maybe implement proper histogramming to
        ## be less susceptible to pulses in the frame
        y = [adc0.mean(),adc1.mean()]
        ye = [adc0.std(),adc1.std()]

        ## the score function to minimize
        a = ((y[0] - self.target_value) ** 2) #/ ye[0] ** 2
        b = ((y[1] - self.target_value) ** 2) #/ ye[1] ** 2
        score = a+b
        self.last = x,y,ye
        return score

    def minimize(self):
        return minimize(self.eval,
                       np.array([0x53d8, 0x53d8]),
                       method='Nelder-Mead',
                       options={'maxfev':40,
                                'disp': True,
                                # 'xtol':1,
                                # 'ftol':1
                                })

    def fit(self, type_, debug=False):
        # switch readout types base on design type, 0x04 is compass, 0x05 is selftrig/xenon
        if type_ == 0x04:
            eval_ = Minimizer.eval_
        elif type_ == 0x05:
            sys.path.append('./gandalf_usb/')
            eval_ = Minimizer.eval_xenon_
            # disable self trigger
            self.g.writeUSB(0x703c, 0)
        else:
            raise Exception("Firmware type {} not detected.", type_)

        coarse_points = 40
        fine_points = 10

        # coarse scan dac values
        print('Performing DAC coarse scan ...')
        x = np.linspace(1000, 1<<15, coarse_points)
        y = []
        for xi in x:
            frames = eval_([int(xi), int(xi)], self.g)
            y.append([(i[0].mean(),i[1].mean()) for i in frames])
        y = np.array(y)

        if debug:
            import matplotlib as mpl
            mpl.use('Agg')
            import matplotlib.pyplot as plt

            fig = plt.figure()
            ax = fig.add_subplot(111)
            for chan in range(8):
                for adc in range(2):
                    ax.plot(x, y[:, chan, adc])
            fig.savefig('temp.png')

        # get fine range
        print('Resulting DAC fine ranges:')
        ranges = []
        for chan in range(8):
            ranges.append([])
            for adc in range(2):
                idx = next(k[0] for k in enumerate(y[:,chan,adc]) if k[1] < self.target_value)
                #print(y[:,chan,adc])##
                l_, h_ = max(idx-2,0), min(idx+1, coarse_points-1)
                #print('idx: ',idx)##
                #print(l_,' | ', h_)##
                ranges[chan].append(list(map(int, np.linspace(x[l_], x[h_], fine_points))))
                print('%i %i: %.1f %.1f / %i %i'%(chan, adc, y[:,chan,adc][l_], y[:,chan,adc][idx+1], x[l_], x[h_]))
        ranges = np.array(ranges)

        # fine scan dac values
        y = []
        for k in range(fine_points):
            frames = eval_(ranges[:,:,k].tolist(), self.g)
            y.append([(i[0].mean(),i[1].mean()) for i in frames])
        y = np.array(y)


        # linear fit to obtain dac for target baseline
        dacs, chans = [], []
        for chan in range(8):
            if y[:, chan, 0].max()> self.target_value > y[:, chan, 0].min() and \
                    y[:, chan, 1].max() > self.target_value > y[:, chan, 1].min():

                z = [np.polyfit(y[:,chan,adc], ranges[chan,adc], 1) for adc in range(2)]
                dacs.append((int(round(z[0][0]*self.target_value + z[0][1])),
                             int(round(z[1][0]*self.target_value + z[1][1]))))
                chans.append(chan*2)
            else: print('skipping weird channel %i'%(chan*2))

        # apply and check the baseline
        frames = eval_(dacs, self.g, chans)
        return [(i[0].mean(),i[1].mean()) for i in frames]


if __name__ == '__main__':
    import gandalf, traceback
    sys.path.append('./gandalf_usb/')
    #import matplotlib.pyplot as plt

    hexid = int(sys.argv[1],16)

    ### open Gandalf device
    g = gandalf.Gandalf(hexid, True)
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
        print(Minimizer(g).fit(0x05, debug=True))

        # request_data(g)
        # request_data(g)
        # request_data(g)
        # request_data(g)

        # data = bytearray()
        # ret = g.spyRead(0x400, 1000)
        # while ret:
        #     data += ret
        #     ret = g.spyRead(0x400, 100)
        #
        # frames = {}
        # for ev in decode.events([data]):
        #     if ev.ch not in frames.keys(): frames[ev.ch] = []
        #     frames[ev.ch].extend(ev.samples)
        # for i in range(16):
        #     print(np.mean(frames[i]), np.std(frames[i]))

    except Exception as e:
        print('Baseline algo failed: %s'%e)
        traceback.print_exc()
    finally:
        ### stop spill
        g.set_spill(False)

        ### disable readout
        g.set_spyread(False)

        ### copy configmem to eeprom
        #g.writeUSB(0x7024, 2)
        #time.sleep(0.1)