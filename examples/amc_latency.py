### =============== example of finding the correct latency (remember, latency is only set on BoS)
### after gandalf is loaded (ie 'miniread 23') and suppose an AFG or PMT is connected to channel 0 together
### with a trigger connected to the gimli

import time, io
import miniread, gandalf
from amc_tools import amc_hax

import numpy as np
import matplotlib.pyplot as plt

hexid = 0x03
g = gandalf.Gandalf(hexid, True)

evnts = []
for latency in range(0,200,25):
    g.amc_config(100, latency, 1)
    time.sleep(0.1)

    ### enable spy readout
    g.set_spyread(True)

    ## start spill
    g.set_spill(True)

    ## aqcuire some events
    time.sleep(2)
    try:
        # get the most recent, complet event (can fail sometimes...)
        data = miniread.get_latest_event(g)

        # decode the event
        evnt = next(amc_hax.events(io.BytesIO(data), amc_hax.PATTERN_SLINK))
        print('event', evnt.spill, evnt.ev)
        evnts.append(evnt)

    except Exception as e:
        print e

    finally:
        ## stop spill
        g.set_spill(False)

        ### disable spy readout
        g.set_spyread(False)

idx = np.argmax([max(e.frames[0]) for e in evnts])
x = range(len(evnts[idx].frames[0]))
y = evnts[idx].frames[0]
plt.plot(x,y)
