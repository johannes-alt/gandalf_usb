#!/bin/bash
INCREASE=false
HEXID=""
NSTEPS="10"
SLEEPTIME=.5
#usage
USAGE="""Usage: `basename $0` [options]
        options:
                        -b              board Hex ID
                        -n              number of steps [$NSTEPS]
                        -t              time to sleep between steps [$SLEEPTIME]
"""

#parse command line options.
while getopts hn:b:t: OPT; do
    case "$OPT" in
        h)
            echo "$USAGE"
            exit 0
            ;;
        n)
            NSTEPS=$OPTARG
            ;;
        b)
            HEXID=$OPTARG
            ;;
        t)
            SLEEPTIME=$OPTARG
            ;;
        \?)
            echo "$USAGE" >&2
            exit 1
            ;;
    esac
done

#remove the switches we parsed above.
shift `expr $OPTIND - 1`

if [ "$HEXID" == "" ]; then
    echo "Hex ID needed. -h for help." >&2
    exit 1
fi

echo "Preparing cfmem for scan ..."
for nBit in {0..13}; do
  ADDR=$(echo $(printf "%03x" $(echo "768 + (4 * $nBit)" | bc)))
  cmd_set_all_inc="vme_write e0$(echo $HEXID)2$(echo $ADDR) FFFFFFFF"
  $cmd_set_all_inc>>/dev/zero
  if [ $? -ne 0 ]; then
	echo 'prep cfmem failed'
	exit 1
  fi
done;

cmd_exec_shift="vme_write e0$(echo $HEXID)70cc 2"
TEX_STEPS="  \scriptsize step  &"
TEX_DATA=""
for n in $(seq $NSTEPS); do
  sleep $SLEEPTIME
  echo "STEP:$n:$NSTEPS"
  cmd_write_cfmem="vme_write e0$(echo $HEXID)70d0 2"
  $cmd_write_cfmem >>/dev/zero
  if [ $? -ne 0 ]; then
	echo 'cfmem write acc failed'
	exit 1
  fi
  COLOR="[fgblue]"
  # read cfmem
  for i in {0..15}; do
    ADDR=$(echo "ibase=10;obase=16;4 * $i + 2448"|bc);
    cmd_read_cfmem="vme_write e0$(echo $HEXID)2$(echo $ADDR)"
    LINE="  \tiny          & [fgblue]"
    RESULT=$($cmd_read_cfmem | tr '[:lower:]' '[:upper:]')
    BIN_RES=$(echo "ibase=16; obase=2; $RESULT"|bc)

    BIN_RES_REV=""
    for (( j=0; j<${#BIN_RES}; j++ )); do
      BIN_RES_REV=${BIN_RES:$j:1}$BIN_RES_REV
    done
    echo "ADC_$i:$BIN_RES_REV"
  done
  TEX_STEPS=$TEX_STEPS"1D{$n}"
  # execute cDown
  $cmd_exec_shift>>/dev/zero
  if [ $? -ne 0 ]; then
	echo 'executing shift failed'
	exit 1
  fi
done;
