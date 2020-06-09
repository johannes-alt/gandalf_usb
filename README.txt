=============== dependencies and setup
-- needs libusb1 python wrapper:
pip install libusb1>=1.7 --user

-- Setup:
python2 setup.py build_ext --inplace
python3 setup.py build_ext --inplace


=============== general info
-- Tools:
miniread.py: load, initiate, sweep and take baseline
gandalf_status.py: show device status
spyread.py: readout the acquired data

gansm3.py: configure the FPGAs of the GANDALF module
vme_write.py: read and write data words from/to config memory


-- Tools should be in '$PATH' and available via the 'usual' commands, e.g.
> ls -l /opt/bin/
spyread -> /opt/gandalf_usb/spyread.py
gansm3 -> /opt/gandalf_usb/gansm3.py
gandalf_status -> /opt/gandalf_usb/gandalf_status.py
vme_write -> /opt/gandalf_usb/vme_write.py
miniread -> /opt/gandalf_usb/miniread.py

-- GANDALF_BINFILE_FOLDER has to be set

-- USB connection permission:
create a example_name.rules file in directory /etc/udev/rules.d/ with content:

SUBSYSTEM=="usb", ATTRS{idVendor}=="04b4", ATTRS{idProduct}=="1002", GROUP="users", MODE="0666"

This line is for the gandalf with the hex id 23
If another gandalf is used  ATTRS{idVendor} and ATTRS{idProduct} can vary.
With "sudo lsusb -vs xxx:yyy" ATTRS{idVendor} and ATTRS{idProduct} can be found out.
Use "lsusb" to find out what to insert for "xxx" and "yyy".

=============== usage in freiburg
export GANDALF_BINFILE_FOLDER=/sc/gandalf/binfiles/

### gandalf hex id in this example is 23

## load gandalf module (includes sweep)
miniread 23
# or, in case of reloading a configured gandalf 
miniread -r 23

## take baseline
# disconnect trigger lemo cable
miniread -b 23

## to modify amc config (framesize/latency/prescaler), see help of miniread
miniread -h

# Take data; script will ask for directory called 'output' in current location
# It will create a file with the current runnumber and write the data in the dir
cd /some/meaningful/place/
spyread -v5 23



=============== controlling AFG (https://www.tek.com/signal-generator/afg3000-manual/afg3000-series-2)
pip2 install python-usbtmc --user

#!/usr/bin/python2
import usbtmc

instr =  usbtmc.Instrument("USB::0x0699::0x0345::INSTR")
print(instr.ask("*IDN?"))
print(instr.write("output1 off"))
print(instr.write("output2 off"))

print(instr.write("source2:frequency 50e6")) # set freq to 50MHz
