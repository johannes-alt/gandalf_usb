#!/usr/bin/python2
import sys
from subprocess import Popen, PIPE
from optparse import OptionParser
begin_tags=["procedure", "while", "if", "function", "program"]
usage="""Usage: %prog
          reads from stdin"""
# Options
parser = OptionParser(usage=usage)
parser.add_option("-f", "--filename", dest="fn", default="amc_delay",
    help="Basename of output Files")
(opts, args) = parser.parse_args()
tex_head="""\\documentclass{article}
\\usepackage{tikz-timing}[2009/12/09]
\\usetikztiminglibrary[new={char=Q,reset char=R}]{counters}
\\usepackage[active,tightpage]{preview}

%
% Defining foreground (fg) and background (bg) colors
\\definecolor{bgblue}{rgb}{0.41961,0.80784,0.80784}%
\\definecolor{bgred}{rgb}{1,0.61569,0.61569}%
\\definecolor{fgblue}{rgb}{0,0,0.6}%
\\definecolor{fgred}{rgb}{0.6,0,0}%
%
\\PreviewEnvironment{tikzpicture}
\\setlength{\\PreviewBorder}{5mm}
\\pagestyle{empty}
\\begin{document}
"""
tex_tikz_head="""
\\begin{tikztimingtable}[
    timing/slope=0,         % no slope
    timing/coldist=2pt,     % column distance
    timing/rowdist=0.3cm,     % column distance
    xscale=1,yscale=0.7, % scale diagrams
    semithick               % set line width
  ]
"""
tex_tikz_foot="""\\extracode
 \\makeatletter
 \\begin{pgfonlayer}{background}
  \\begin{scope}[gray,semitransparent,semithick]
    \\vertlines{1,...,%i}
  \\end{scope}
 \\end{pgfonlayer}
\\end{tikztimingtable}"""
tex_foot="""
\\end{document}"""
texline_head="  \\scriptsize step  &"

del_mat_head="""constant GEN_IDEL_INT   : idel_int_array(0 to 15):= (
(A-00_B-00,A-00_B-01,A-00_B-02,A-00_B-03,A-00_B-04,A-00_B-05,A-00_B-06,A-00_B-07,A-00_B-08,A-00_B-09,A-00_B-10,A-00_B-11), (A-01_B-00,A-01_B-01,A-01_B-02,A-01_B-03,A-01_B-04,A-01_B-05,A-01_B-06,A-01_B-07,A-01_B-08,A-01_B-09,A-01_B-10,A-01_B-11),
(A-02_B-00,A-02_B-01,A-02_B-02,A-02_B-03,A-02_B-04,A-02_B-05,A-02_B-06,A-02_B-07,A-02_B-08,A-02_B-09,A-02_B-10,A-02_B-11), (A-03_B-00,A-03_B-01,A-03_B-02,A-03_B-03,A-03_B-04,A-03_B-05,A-03_B-06,A-03_B-07,A-03_B-08,A-03_B-09,A-03_B-10,A-03_B-11),
(A-04_B-00,A-04_B-01,A-04_B-02,A-04_B-03,A-04_B-04,A-04_B-05,A-04_B-06,A-04_B-07,A-04_B-08,A-04_B-09,A-04_B-10,A-04_B-11), (A-05_B-00,A-05_B-01,A-05_B-02,A-05_B-03,A-05_B-04,A-05_B-05,A-05_B-06,A-05_B-07,A-05_B-08,A-05_B-09,A-05_B-10,A-05_B-11),
(A-06_B-00,A-06_B-01,A-06_B-02,A-06_B-03,A-06_B-04,A-06_B-05,A-06_B-06,A-06_B-07,A-06_B-08,A-06_B-09,A-06_B-10,A-06_B-11), (A-07_B-00,A-07_B-01,A-07_B-02,A-07_B-03,A-07_B-04,A-07_B-05,A-07_B-06,A-07_B-07,A-07_B-08,A-07_B-09,A-07_B-10,A-07_B-11),
(A-08_B-00,A-08_B-01,A-08_B-02,A-08_B-03,A-08_B-04,A-08_B-05,A-08_B-06,A-08_B-07,A-08_B-08,A-08_B-09,A-08_B-10,A-08_B-11), (A-09_B-00,A-09_B-01,A-09_B-02,A-09_B-03,A-09_B-04,A-09_B-05,A-09_B-06,A-09_B-07,A-09_B-08,A-09_B-09,A-09_B-10,A-09_B-11),
(A-10_B-00,A-10_B-01,A-10_B-02,A-10_B-03,A-10_B-04,A-10_B-05,A-10_B-06,A-10_B-07,A-10_B-08,A-10_B-09,A-10_B-10,A-10_B-11), (A-11_B-00,A-11_B-01,A-11_B-02,A-11_B-03,A-11_B-04,A-11_B-05,A-11_B-06,A-11_B-07,A-11_B-08,A-11_B-09,A-11_B-10,A-11_B-11),
(A-12_B-00,A-12_B-01,A-12_B-02,A-12_B-03,A-12_B-04,A-12_B-05,A-12_B-06,A-12_B-07,A-12_B-08,A-12_B-09,A-12_B-10,A-12_B-11), (A-13_B-00,A-13_B-01,A-13_B-02,A-13_B-03,A-13_B-04,A-13_B-05,A-13_B-06,A-13_B-07,A-13_B-08,A-13_B-09,A-13_B-10,A-13_B-11),
(A-14_B-00,A-14_B-01,A-14_B-02,A-14_B-03,A-14_B-04,A-14_B-05,A-14_B-06,A-14_B-07,A-14_B-08,A-14_B-09,A-14_B-10,A-14_B-11), (A-15_B-00,A-15_B-01,A-15_B-02,A-15_B-03,A-15_B-04,A-15_B-05,A-15_B-06,A-15_B-07,A-15_B-08,A-15_B-09,A-15_B-10,A-15_B-11));
"""


texlines=dict()
line = sys.stdin.readline()
adc=0
step=0
nbits=12
nadcs=0
nsteps=0
color="[fgblue]"
key_str="A-%.2i_B-%.2i"
while line:
  if "ADC" in line:
    if "[fgblue]" in color: color = "[fgred]"
    else: color = "[fgblue]"
    adc=int(line.split(':')[0].split('_')[1])
    if nadcs < adc: nadcs = adc
#    data=line.split(':')[1].zfill(12)
    data=line.split(':')[1].ljust(12, '0')
#    print data 
    for nbit in range(nbits):
      key=key_str%(adc, nbit)
      if not key in texlines: texlines[key] = "  \\tiny %s  & %s"%(key.replace("_", "\\_"), color)
#      print data[nbit],"1" in data[nbit]
      if "1" in data[nbit]:
        texlines[key] += "U"
      else: texlines[key] += "D"
  if "STEP" in line:
    step = int(line.split(':')[1])
    nsteps = int(line.split(':')[2])
    texline_head+="D{%.02i}"%step
    statstr="reading. Step %i ["%step
    for i in range(step): statstr+="#"
    for i in range(nsteps-step): statstr+="."
    statstr+="]"
    print statstr,"  \r",
    sys.stdout.flush()
  line = sys.stdin.readline()
texline_head += "\\\\"
tex_tikz_foot=tex_tikz_foot%nsteps
for aKey in texlines:
  texlines[aKey] += """\\\\
"""


better_texlines={}
# Get Calibration Matrix
for key in texlines:
    step_cnt=0
    old_char='D'
    transitions=[]
    was_down=False
    trans_cnt=0
    data = texlines[key].strip().split(']')[1].strip('\\')
    start = texlines[key].strip().split(']')[0]
    for step_sign in data:
        step_cnt+=1
        if old_char != step_sign and was_down==True and trans_cnt>3 and (len(transitions) > 0 or step_sign == 'U'):
                transitions.append(step_cnt-1)
                trans_cnt=0
        trans_cnt+=1
        if step_sign == 'D' and step_cnt > 2: was_down=True
        old_char = step_sign
    if len(transitions) > 2:
        data_eye=transitions[2] - transitions[1]
        delay = transitions[1] + (( transitions[2] - transitions[1] ) / 2)
        del_mat_head = del_mat_head.replace("%s"%key, "%.2i"%delay)
        new_data=[]
        for sign in data: new_data.append(sign)
        new_data[delay] = 'M'
        better_texlines[key] = start + ']' + "".join(new_data) + """\\\\
"""
    else:
        better_texlines[key] = texlines[key]
    #~ print key, transitions, data_eye, delay, "".join(new_data)

fn="%s.tex"%opts.fn
fp=open(fn, 'w')
fp.write(tex_head)
fp.write(tex_tikz_head)
fp.write(texline_head)
for adc in range(0, nadcs/2+1):
  for bit in range(0, nbits):
    key=key_str%(adc, bit)
    fp.write(better_texlines[key])
fp.write(tex_tikz_foot)
fp.write(tex_tikz_head)
fp.write(texline_head)
for adc in range(nadcs/2+1, nadcs+1):
  for bit in range(0, nbits):
    key=key_str%(adc, bit)
    fp.write(better_texlines[key])
fp.write(tex_tikz_foot)
fp.write(tex_foot)
fp.close()
print "wrote latex output to %s                                                     "%fn
#~ #~
fn="%s_matrix.dat"%opts.fn
fp=open(fn, 'w')
fp.write(del_mat_head)
fp.close()
print "wrote matrix output to %s                                                     "%fn















