#!/usr/bin/python2
import os,sys,re,ROOT,re
import decode as d
import helper_funcs as h
import copy
import os.path

use_asci=False
cut_frequencise=None

if len(sys.argv)==2: 
	file_name=sys.argv[1]
	if os.path.isfile(file_name):
		print "reading file: ", file_name
	else:
		print "!!given spy out file does not exist!!"
		sys.exit(1)
elif len(sys.argv)==3: 
	if "-f" in sys.argv:
		print "FFT cut enabled"
		cut_frequencise=[[0.4,0.5]]
		for arg in sys.argv[1:]:
			if arg!="-f":
				file_name=arg
				if os.path.isfile(file_name):
					print "reading file: ", file_name
				else:
					print "!!given spy out file does not exist!!"
					sys.exit(1)
	else:
		print "!!invalid optional argument type -f for FFT or leave blank!!"
		sys.exit(1)
else:
	print "please provide a spy out file name as argument"
	print "optionally you can provide -f to use FFT cutoff"

clks=None
with open(file_name,"r") as f:
	clks=d.decode(f,use_asci)

cans=dict()
for key in clks:

        draw_objects=[[],[],[],[],[]]
	try:
		new_clk,min_index,graph=h.do_overlap(clks[key],44,True,cut_frequencies=cut_frequencise)
		parab_fit=ROOT.TF1("pol","pol4",0,45)
		graph.Fit(parab_fit,"MNOQ","")
		draw_objects[0].append(graph)
		draw_objects[0].append(parab_fit)
	except Exception,e:
		draw_objects[0]=[]
		print str(e)

	try:
		hist,fits,edge_types,fits_sec,edge_types_sec,rec_fits,ret_x=h.fit_undef(new_clk,"undef",pedantic=True,rec_meth=1)
		draw_objects[1].append(hist)
		draw_objects[1].extend(fits)
		draw_objects[1].extend(rec_fits)
		h.stepping_logic(new_clk,fits,edge_types,ret_x)
	except Exception,e:
		try:
			hist,fits,edge_types,fits_sec,edge_types_sec,rec_fits,ret_x=h.fit_undef(new_clk,"undef",pedantic=False,rec_meth=1)
			draw_objects[1].append(hist)
			draw_objects[1].extend(fits)
			draw_objects[1].extend(rec_fits)
		except:
			draw_objects[1]=[]
		print str(e)

	try:
		rec_fits_zero,hist_zero=h.proc_rec(new_clk,fits,"zeros")
		draw_objects[2].append(hist_zero)
		draw_objects[2].extend(rec_fits_zero)
	except Exception,e:
		draw_objects[2]=[]
		print str(e)

	try:
		rec_fits_one,hist_one=h.proc_rec(new_clk,fits,"ones")
		draw_objects[3].append(hist_one)
		draw_objects[3].extend(rec_fits_one)
	except Exception,e:
		draw_objects[3]=[]
		print str(e)
	try:
		hb,h_fft=h.do_fft(hist_one,"",[])
		draw_objects[4].append(h_fft)
	except Exception,e:
		draw_objects[4]=[]
		print str(e)

	cans[key]=ROOT.TCanvas()
	cans[key].SetTitle("Si"+str(key))
        cans[key].Divide(2,3)
        cnt=1
        for objs in draw_objects:
		if cnt==5: cans[key].cd(cnt).SetLogy(1)
		else: cans[key].cd(cnt).SetLogy(0)
		for obj in objs:
                        if obj==0: continue
			obj.SetName(obj.GetName()+"_"+str(key))
						
			if type(obj)==ROOT.TH1F:
				obj.GetYaxis().SetRangeUser(0,obj.GetBinContent(obj.GetMaximumBin())*1.2)
				obj.Draw("hist")

                        elif type(obj)==ROOT.TGraph: 
				obj.Draw("ap")
			else:
				obj.Draw("same")

		cnt+=1
	cans[key].Draw()
	raw_input()

#for key in cans:
#	cans[key].Draw()
#	raw_input()




