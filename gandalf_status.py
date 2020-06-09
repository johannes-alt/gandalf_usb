#!/usr/bin/env python
import gandalf
import sys, time

print ("  SN  HEX  GA  INIT SRCID  TCS_SL  SI_G  SI_A  SI_B  RESET  MCSup  MCSd   Gtemp  VCCAUX VCCINT SYSMON")
print ("----------------------------------------------------------  ------------  ------ ------ ------ ------")

devices = gandalf.listDevices()

for device_data in devices:
  sn = device_data & 0x3FF;
  hex = (device_data>>20) & 0xFF;
  ga = (device_data>>12) & 0x1F;
  init = (device_data>>28) & 0xF;

  g = gandalf.Gandalf(hex)
  # read src id
  val = g.readUSB( 0x2804 )
  srcid = val & 0x3FF
  # update temp
  g.writeUSB( 0x7010, 2)
  time.sleep(.1) # w8 100 ms to let cfmem settle

  # update/read status
  val = g.status()
  si_a = (val>>8) & 0x7
  si_b = (val>>4) & 0x7
  si_g = val & 0x7
  tcs = (val>>12) & 0x7
  reset = (val>>16) & 0x7
  sysmon = (val>>20) & 0x7
  head = (val>>24)

  # MCS up
  val = g.readUSB( 0x2000 )
  mcsup_sn = val & 0xFFF
  mcsup_type = (val>>12) & 0x7

  # MCS up
  val = g.readUSB( 0x2400 )
  mcsdn_sn = val & 0xFFF
  mcsdn_type = (val>>12) & 0x7

  # Gtemp
  val = g.readUSB( 0x2840 )
  temp = (( (val & 0x3FF)*503.975)/1024.0)-273.15
  # VCCaux
  val = g.readUSB( 0x2860 )
  vccaux = (( (val & 0x3FF)/1024.0) * 3.0)
  # VCCint
  val = g.readUSB( 0x2880 )
  vcc = (( (val & 0x3FF)/1024.0)* 3.0)

  print ("%4d  %02Xh  %2d  %x     %.3i     %i       %i     %i     %i    %i      %i/%i   %i/%i    %i     %i      %i      %i" % (sn, hex, ga, init, srcid, tcs, si_g, si_a, si_b, reset, mcsup_sn, mcsup_type, mcsdn_sn, mcsdn_type, temp, vccaux, vcc, sysmon))


