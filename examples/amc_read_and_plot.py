### =============== coding with direct interface to gandalf
### after gandalf is loaded (ie 'miniread 23')

import time, io
import miniread, gandalf
from amc_tools import amc_hax

import matplotlib.pyplot as plt


hexid = 0x03
g = gandalf.Gandalf(hexid, True)

### enable spy readout
g.set_spyread(True)

## start spill
g.set_spill(True)

# generate trigger (2 triggers to make sure there is enough data in the spyfifo)
for _ in range(2):
    g.trigger()

try:
    # get the most recent, complet event (can fail sometimes...)
    data = miniread.get_latest_event(g)

    # decode the event
    evnt = next(amc_hax.events(io.BytesIO(data), amc_hax.PATTERN_SLINK))
    print('event', evnt.spill, evnt.ev)

except Exception as e:
    print e
finally:
    ## stop spill
    g.set_spill(False)

    ### disable spy readout
    g.set_spyread(False)

# create a plot of the frame
ch = 2
x = range(len(evnt.frames[ch]))
y = evnt.frames[ch]
plt.plot(x,y)
plt.show()
