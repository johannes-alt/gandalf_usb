import ROOT
import decode
import logging
import copy
#######################################
#fine tuning procedure helper functions
#enable with rec_meth=1,2 in fit_undef func


def rec_g(x,par):

    #par[0] plateau
    #par[1] right cutoff
    #par[2] rec steepness
    #par[3] gaus widht
    #par[4] left cutoff

    const=par[0]
    
    retval=-const
    retval*=1/(ROOT.TMath.Exp((x[0]-par[1])/par[2])+1)

    retval+=const
    retval*=ROOT.TMath.Gaus(x[0],par[1],par[3])
 
    retval+=const*1/(ROOT.TMath.Exp((x[0]-par[1])/par[2])+1)
    retval*=1/(ROOT.TMath.Exp((-x[0]+par[4])/par[2])+1)
    
    return retval


def double_rec(x,par):

    #par[0] plateau
    #par[1] right cutoff
    #par[2] rec steepness
    #par[3] right gaus widht
    #par[4] left cutoff
    #par[5] left gaus_width
    
    retval=rec_g([x[0]],[par[0],par[1],par[2],par[3],par[4]])
    retval+=rec_g([-x[0]],[par[0],-par[4],par[2],par[5],-par[1]])*1./(ROOT.TMath.Exp((x[0]-par[4])/par[2])+1)

    return retval


def do_fit(g_fit,hist,index=0):
    funci=ROOT.TF1("rec"+str(index),double_rec,g_fit.GetParameter(1)-4*g_fit.GetParameter(2),g_fit.GetParameter(1)+4*g_fit.GetParameter(2),6)
    funci.SetParameter(0,hist.GetBinContent(hist.FindBin(g_fit.GetParameter(1)))) #plateau value
    funci.SetParameter(1,g_fit.GetParameter(1)+g_fit.GetParameter(2)) #right cut off
    funci.FixParameter(2,0.0000001) #rec steepness
    funci.SetParameter(3,g_fit.GetParameter(2)) #right gaus width
    funci.SetParameter(4,g_fit.GetParameter(1)-g_fit.GetParameter(2)) #left cut off
    funci.SetParameter(5,g_fit.GetParameter(2)) #left gaus width
    ROOT.SetOwnership( funci, True )
    
    #logging.info("rec fit params before: "+str(funci.GetParameter(0))+" "+str(funci.GetParameter(1))+" "+str(funci.GetParameter(2))+" "+str(funci.GetParameter(3))+" "+str(funci.GetParameter(4))+" "+str(funci.GetParameter(5)))
    stat=hist.Fit(funci,"MNOQS","",g_fit.GetParameter(1)-4*g_fit.GetParameter(2),g_fit.GetParameter(1)+4*g_fit.GetParameter(2))
    #logging.info(" rec fit params after : "+str(funci.GetParameter(0))+" "+str(funci.GetParameter(1))+" "+str(funci.GetParameter(2))+" "+str(funci.GetParameter(3))+" "+str(funci.GetParameter(4))+" "+str(funci.GetParameter(5)))
    chi_ndf=funci.GetChisquare()/funci.GetNDF()
    logging.info("result= "+str(stat.IsValid())+" chi2/ndf: "+str(chi_ndf))

    return funci

def get_time(fit):
    mag=fit.GetParameter(0)
    perc=0.3
    times=dict()
    cross_val=mag*perc
    x1=fit.GetX(cross_val, fit.GetParameter(4)-2.*fit.GetParameter(5), fit.GetParameter(4))
    x2=fit.GetX(cross_val, fit.GetParameter(1), fit.GetParameter(1)+2.*fit.GetParameter(3))

    #logging.info("rec fit params: "+str(fit.GetParameter(0))+" "+str(fit.GetParameter(1))+" "+str(fit.GetParameter(2))+" "+str(fit.GetParameter(3))+" "+str(fit.GetParameter(4))+" "+str(fit.GetParameter(5)))
    #logging.info("name of rec fit: "+fit.GetName())
    #logging.info("time left: "+str(x1))
    #logging.info("time right: "+str(x2))
    #logging.info("time"+str((x1+x2)/2.))
    time=(x1+x2)/2.
    
    return time

def fit_all(fits,hist,edge_types=None):
    cnt=0
    ret_funcs=[]
    ret_x=[]
    for g_fit in fits:
	if edge_types==None:
            logging.info("fitting peak no "+str(cnt))     
	    f=do_fit(g_fit,hist,cnt)
            ret_funcs.append(f)
            ret_x.append(get_time(f))
	else:
	    if edge_types[cnt]==True: #cnt==len(edge_types)-2 and
                logging.info("fitting peak no "+str(cnt))                     
                f=do_fit(g_fit,hist,cnt)
                ret_funcs.append(f)
                ret_x.append(get_time(f))
	    #elif edge_types[cnt]==True:	    # cnt==len(edge_types)-1 and
            #    logging.info("fitting peak no "+str(cnt))     
            #    f=do_fit(g_fit,hist,cnt)
            #    ret_funcs.append(f)
            #    ret_x.append(get_time(f))
	    else:
	        ret_funcs.append(0)
		ret_x.append(0)

        cnt+=1
    #logging.info("rec method found: "+str(ret_x))
    return ret_funcs,ret_x

################################


def benchmark(new_order,fine_step,verbose=False):
    bench=0
    for i in range(1,len(new_order)):
        benchi=0
        for l in range(fine_step,len(new_order[i])):
	    if l>=len(new_order[i-1]):
	        break
            benchi+=(new_order[i-1][l].zero-new_order[i][l-fine_step].zero)**2
            benchi+=(new_order[i-1][l].one-new_order[i][l-fine_step].one)**2
            benchi+=(new_order[i-1][l].undef-new_order[i][l-fine_step].undef)**2
        if (len(new_order[i])-fine_step)==0:
            if verbose:
                print "warning zero denominator at coarse step: "+str(i)+" and fine_step: "+str(l)
                print "length fine steps:",len(new_order[i])
                print "actual fine step:",fine_step
            benchi=0.
        else:
            benchi/=(len(new_order[i])-fine_step)
        bench+=benchi
        
    return bench

def do_overlap(clk,best_index=-1,verbose=False,cut_frequencies=[[0.4,0.5]]):

    graph=ROOT.TGraph()
    ROOT.SetOwnership( graph, True )

    coarse=clk[0].coarse_step
    same_coarse=[]
    new_order=[]

    for info in clk:

        if info.coarse_step!=coarse:
            coarse=info.coarse_step
            new_order.append(same_coarse)
            same_coarse=[]
            same_coarse.append(info)
        else:
            same_coarse.append(info)

    new_order.append(same_coarse)

    benchs=[]
    bench_sets=[]
    cnt=0
    for fine_step in range(len(new_order[1])):
        benchs.append(benchmark(new_order,fine_step,verbose))
        cnt+=1

    min_index=benchs.index(min(benchs))

    cnt=0
    for b in benchs:
        graph.SetPoint(cnt,cnt,b)
        cnt+=1

    if verbose:
        print "best index=",min_index
    
    used_index=min_index
    if best_index!=-1:
        if verbose:
            print "replaced min index with",best_index
        used_index=best_index
    
    new_clk=[]
    last_inf=copy.deepcopy(new_order[0][0])
    last_inf.fine_step+=1
    for infs in new_order:
        for inf in infs[:(used_index)]:
            if inf.fine_step!=last_inf.fine_step-1 and inf.coarse_step==last_inf.coarse_step:
                logging.warning("inf: "+str(inf))
                logging.warning("last inf: "+str(last_inf))
                raise Exception('fine steps ordering inconsistent!!')
            last_inf=inf
            new_clk.append(inf)       
    

    #clean the new_clk infos with fft back and forth
    if cut_frequencies!=None:
        hists=[]
        back_hists=[]
        hists.append(ROOT.TH1F("undef","undef",len(new_clk)+1,0,len(new_clk)))
        hists.append(ROOT.TH1F("zero","zero",len(new_clk)+1,0,len(new_clk)))
        hists.append(ROOT.TH1F("one","one",len(new_clk)+1,0,len(new_clk)))
        cnt=1
        for inf in new_clk:
            hists[0].SetBinContent(cnt,inf.undef)
            hists[0].SetBinError(cnt,ROOT.TMath.Sqrt(inf.undef))
            hists[1].SetBinContent(cnt,inf.zero)
            hists[1].SetBinError(cnt,ROOT.TMath.Sqrt(inf.zero))
            hists[2].SetBinContent(cnt,inf.one)
            hists[2].SetBinError(cnt,ROOT.TMath.Sqrt(inf.one))
            cnt+=1
    
        for hist in hists:
            hb,h_fft=do_fft(hist,"back"+hist.GetName(),cut_frequencies)#[[0.42,0.48],[0.54,0.58]]
            back_hists.append(hb)
    
        cnt=1
        trans_clk=[]
        for inf in new_clk:
            trans_clk.append(decode.sweep_info(inf.si_nr,inf.coarse_step,inf.fine_step))
            trans_clk[-1].undef=back_hists[0].GetBinContent(cnt)
            trans_clk[-1].zero=back_hists[1].GetBinContent(cnt)
            trans_clk[-1].one=back_hists[2].GetBinContent(cnt)
            cnt+=1
    
        for h in hists:
            ROOT.SetOwnership( h, True )
        
        #output the fft cutted clk
        new_clk=trans_clk
    
    return new_clk,min_index,graph

def fit_undef(new_clk,hist_name="undef",sigma=20,threshold=0.2,rough_period=1055,period_margin=3,pedantic=True,si_num=0,rec_meth=1,chi_cut=None):
    
    if pedantic==False:
	threshold=0.05
	period_margin=500

    hist=ROOT.TH1F(hist_name,hist_name,len(new_clk)+1,0,len(new_clk))
    ROOT.SetOwnership( hist, True )
    cnt=1
    for inf in new_clk:
        hist.SetBinContent(cnt,inf.undef)
        hist.SetBinError(cnt,ROOT.TMath.Sqrt(inf.undef))
        cnt+=1
    
    cut_off=sigma*12
    dist=sigma*6
    
    ######
    #first method
    s = ROOT.TSpectrum()
    ROOT.SetOwnership( s, True )
    nfound = s.Search(hist,sigma,"goff",threshold);     
    peaks_pos=[]
    for i in range(nfound):
        peaks_pos.append(s.GetPositionX()[i])
    peaks_pos.sort()
    
    fits=[]
    for i in range(0,len(peaks_pos)):
        #dist=(peaks_pos[i]-peaks_pos[i-1])/4.
        fit=ROOT.TF1("fit"+str(i)+"_"+hist_name,"gaus",peaks_pos[i]-dist,peaks_pos[i]+dist)
        ROOT.SetOwnership( fit, True )
        fit.SetParameter(1,peaks_pos[i])
        hist.Fit(fit,"MNOQ","",peaks_pos[i]-dist,peaks_pos[i]+dist)
        sec_fit=ROOT.TF1("sec_fit"+str(i)+"_"+hist_name,"gaus",fit.GetParameter(1)-dist,fit.GetParameter(1)+dist)
        ROOT.SetOwnership( sec_fit, True )
        sec_fit.SetParameter(1,fit.GetParameter(1))
        hist.Fit(sec_fit,"MNOQ","",fit.GetParameter(1)-dist,fit.GetParameter(1)+dist)
        if sec_fit.GetParameter(1)>cut_off and sec_fit.GetParameter(1)<(len(new_clk)-cut_off):
            fits.append(sec_fit)
    edge_types=get_edge_types(fits,new_clk,dist)

    ######
    #sec method
    peaks_pos_sec_alg,edge_types_sec=find_peaks(new_clk,sigma)
    edge_types_sec_new=[]

    fits_sec=[]
    for i in range(0,len(peaks_pos_sec_alg)):
        fit=ROOT.TF1("fit_sec_alg"+str(i)+"_"+hist_name,"gaus",peaks_pos_sec_alg[i]-dist,peaks_pos_sec_alg[i]+dist)
        ROOT.SetOwnership( fit, True )
        fit.SetParameter(1,peaks_pos_sec_alg[i])
        hist.Fit(fit,"MNOQ","",peaks_pos_sec_alg[i]-dist,peaks_pos_sec_alg[i]+dist)
        sec_fit=ROOT.TF1("fit_sec_alg_sec"+str(i)+"_"+hist_name,"gaus",fit.GetParameter(1)-dist,fit.GetParameter(1)+dist)
        ROOT.SetOwnership( sec_fit, True )
        sec_fit.SetParameter(1,fit.GetParameter(1))
        hist.Fit(sec_fit,"MNOQ","",fit.GetParameter(1)-dist,fit.GetParameter(1)+dist)
        if sec_fit.GetParameter(1)>cut_off and sec_fit.GetParameter(1)<(len(new_clk)-cut_off):
            fits_sec.append(sec_fit)
            edge_types_sec_new.append(edge_types_sec[i])

    rec_fits=None
    ret_x=None
    if rec_meth==1:
    	rec_fits,ret_x=fit_all(fits,hist,edge_types)
    elif rec_meth==2:
	rec_fits,ret_x=fit_all(fits,hist)
    
    check_consistency(fits,edge_types,fits_sec,edge_types_sec_new,rec_fits,ret_x,rough_period,period_margin,pedantic=pedantic,si_num=si_num,chi_cut=chi_cut)

    return hist,fits,edge_types,fits_sec,edge_types_sec_new,rec_fits,ret_x

def find_peaks(new_clk,dist):
    
    n_stat=new_clk[0].zero+new_clk[0].one+new_clk[0].undef
    edge_state=0
    peaks_pos=[]
    peaks_type=[]
    for i in range(dist,len(new_clk)-dist):
        mean_before=0
        for l in range(i-dist,i): 
            mean_before+=new_clk[l].one
        mean_before/=dist
        
        mean_after=0
        for l in range(i+1,i+dist): 
            mean_after+=new_clk[l].one
        mean_after/=dist
        
        if new_clk[i].one>n_stat/2 and mean_before<n_stat/2 and mean_after>n_stat/2 and (edge_state==0 or edge_state==-1):
            edge_state=1
            peaks_pos.append(i)
            peaks_type.append(True)
        
        if new_clk[i].one<n_stat/2 and mean_before>n_stat/2 and mean_after<n_stat/2 and (edge_state==0 or edge_state==1):
            edge_state=-1
            peaks_pos.append(i)
            peaks_type.append(False)

    improved_peaks_pos=[]
    for peak in peaks_pos:
        maxi=0
        for l in range(peak-dist,peak+dist):
            if new_clk[l].undef>maxi:
                maxi=l
        improved_peaks_pos.append(maxi)
    return improved_peaks_pos,peaks_type

def get_edge_types(fits,new_clk,dist):
    
    n_stat=new_clk[0].zero+new_clk[0].one+new_clk[0].undef
    edge_types=[]
    for fit in fits:
        val=fit.GetParameter(1)
        val_one=new_clk[int(val+dist)].one
        val_zero=new_clk[int(val-dist)].zero

        is_rising=False
        if (val_one>0.9*n_stat and val_zero>0.9*n_stat):
            edge_types.append(True)
        elif (val_one<0.1*n_stat and val_zero<0.1*n_stat):
            edge_types.append(False)
    return edge_types

def stepping_logic(new_clk,fits,edge_types,ret_x,verbose=False,coarse_shift=18,fine_shift=0,):
    
    last_rise=0
    if edge_types[-1]==False:
	if ret_x==None:
            last_rise=fits[-2].GetParameter(1)
	else:
            last_rise=ret_x[-2]	    
	    logging.info("using the REC METHOD: "+str(ret_x))
    else:
        if ret_x==None:
    	    last_rise=fits[-1].GetParameter(1)
        else:
	    last_rise=ret_x[-1]	
	    logging.info("using the REC METHOD: "+str(ret_x))


    last_rise_inf=new_clk[int(round(last_rise))]
    #TODO this is not completely understood!!!
    fine_step=last_rise_inf.fine_step
    #if (fine_step+fine_shift)>43 or (fine_step+fine_shift)<1:
    #    raise Exception('total fine step = '+str(fine_step+fine_shift)+" is <1 or >43;")
    fine_step_hex="0x%0.2X" % (fine_step+fine_shift)
    coarse_step=last_rise_inf.coarse_step
    coarse_step_hex="0x%0.2X" % (coarse_step+coarse_shift)
    
    step_to_conf_mem=coarse_step_hex[2:]+fine_step_hex[2:]
    
    if verbose:
        peak_pos=[]
        for fit in fits:
            peak_pos.append(fit.GetParameter(1))
        logging.info("found peaks: "+str(peak_pos))
        logging.info("found edge types: "+str(edge_types))
        logging.info("last rising edge: "+str(last_rise))
        logging.debug("corresponding info: "+str(last_rise_inf))
        logging.debug("last rise fine_step:" +str(fine_step)+" (0x"+str(fine_step_hex)+" incl. shift "+str(fine_shift)+")")
        logging.debug("last rise coarse_step:" +str(coarse_step)+" (0x"+str(coarse_step_hex)+" incl. shift "+str(coarse_shift)+")")
        logging.debug("steps to conf mem:"+str(step_to_conf_mem))

    clk_pos=-1
    coarse_fine_units=44
    tolerated_perc_dev=0.1
    if (coarse_fine_units*coarse_shift+fine_shift)<1.1*(fits[-1].GetParameter(1)-fits[-3].GetParameter(1)):
    
        new_pos=int(last_rise)-coarse_fine_units*coarse_shift-fine_shift
        new_one_val=new_clk[new_pos].one
        left_check_val=new_clk[new_pos-coarse_fine_units].one
        right_check_val=new_clk[new_pos+coarse_fine_units].one
        stat=new_clk[new_pos].one+new_clk[new_pos].zero+new_clk[new_pos].undef
        
        right_perc_dev=ROOT.TMath.Abs(new_one_val-right_check_val)/stat
        left_perc_dev=ROOT.TMath.Abs(new_one_val-left_check_val)/stat
        
        if new_one_val>0.5*stat:
            clk_pos=1
        else:
            clk_pos=0
        
        if right_perc_dev<tolerated_perc_dev and left_perc_dev<tolerated_perc_dev:
            logging.info("stable position is set with edge type "+str(clk_pos))

        else:
            clk_pos=-1
            logging.warning("you are shifting into a region which has undef. behaviour! edge_type: "+str(clk_pos))
    else:
        logging.warning("you are definitely shifting more than one period...reconsider your shift settings! edge_type: "+str(clk_pos))
    
    return step_to_conf_mem,last_rise,fine_step,clk_pos

def print_info(fits,edge_types,add_string=""):

    peaks_int=[]
    peaks=[]
    peaks_width=[]
    for fit in fits:
        peaks_int.append(fit.GetParameter(0))
        peaks.append(fit.GetParameter(1))
        peaks_width.append(fit.GetParameter(2))
        
    logging.warning(add_string+" peak Integrals: "+str(peaks_int))
    logging.warning(add_string+" peaks pos: "+str(peaks))
    logging.warning(add_string+" peaks width: "+str(peaks_width))
    logging.warning(add_string+" peaks type is rising: "+str(edge_types))

def consistency_msg(message,pedantic):
    if pedantic==True:
    	raise Exception(message)
    else:
	logging.warning(message)

def check_consistency(fits,edge_types,fits_sec,edge_types_sec,fits_rec,x_vals_rec,rough_period=1055,period_margin=3,pedantic=True,si_num=0,chi_cut=None):
   
    si_names=["SiG","SiA","SiB"]    

    if len(fits)>2: 
        period=fits[-1].GetParameter(1)-fits[-3].GetParameter(1)
        if ROOT.TMath.Abs(period-rough_period)>period_margin:
            print_info(fits,edge_types)
	    print_info(fits_sec,edge_types_sec,"sec alg")
            consistency_msg('wrong period ('+str(period)+') '+'on '+si_names[si_num]+"found: "+str(period)+",expected: "+str(rough_period)+",margin: "+str(period_margin),pedantic)  
	else:
	    logging.info("period check succesfull with deviation of "+str(ROOT.TMath.Abs(period-rough_period))+"inside tolerance of "+str(period_margin))	
    else:
        print_info(fits,edge_types)
	print_info(fits_sec,edge_types_sec,"sec alg")
    	consistency_msg("cannot do period consistency check: not enough edges found"+'on '+si_names[si_num],pedantic)
    
    if x_vals_rec!=None:
        found_vals=[]
    	for x in x_vals_rec:
            if x!=0:
                found_vals.append(x)
        if len(found_vals)<2:
            consistency_msg("cannot do period consistency rec check: not enough edges found"+'on '+si_names[si_num],pedantic)
        else:
            period=found_vals[-1]-found_vals[-2]
            if ROOT.TMath.Abs(period-rough_period)>period_margin:
                print_info(fits,edge_types)
	        print_info(fits_sec,edge_types_sec,"sec alg")
                consistency_msg('wrong rec period ('+str(period)+') '+'on '+si_names[si_num]+"found: "+str(period)+",expected: "+str(rough_period)+",margin: "+str(period_margin),pedantic) 
	    else:
	        logging.info("rec period check succesfull with deviation of "+str(ROOT.TMath.Abs(period-rough_period))+"inside tolerance of "+str(period_margin))

    if len(fits)!=len(edge_types):
        print_info(fits,edge_types)
	print_info(fits_sec,edge_types_sec,"sec alg")
        consistency_msg('length of fits and edge types is not the same'+'on '+si_names[si_num],pedantic)
    
    last_type=-1
    for et in edge_types:
        if last_type==et:
            print_info(fits,edge_types)
	    print_info(fits_sec,edge_types_sec,"sec alg")
            consistency_msg('edge type is not alternating'+' on '+si_names[si_num],pedantic)
        last_type=et
        
    if len(fits)!=len(fits_sec):
        print_info(fits,edge_types)
        print_info(fits_sec,edge_types_sec,"sec alg")
        consistency_msg('both methods do not agree in number of found undef peaks'+'on '+si_names[si_num],pedantic) 
    
    cnt=0
    for f,fs in zip(fits,fits_sec):
        if ROOT.TMath.Abs(f.GetParameter(1)-fs.GetParameter(1))>3.:
            print_info(fits,edge_types)
            print_info(fits_sec,edge_types_sec,"sec alg")
            consistency_msg('both methods do not agree in mean for fit '+str(cnt)+'on '+si_names[si_num],pedantic)
        cnt+=1
    
    cnt=0
    for t,ts in zip(edge_types,edge_types_sec):
        if t!=ts:
            print_info(fits,edge_types)
            print_info(fits_sec,edge_types_sec,"sec alg")
            consistency_msg('both methods do not agree in edge type for edge '+str(cnt)+'on '+si_names[si_num],pedantic)
        cnt+=1

    if fits_rec!=None:
	for r_f in fits_rec:
	    if r_f!=0 and chi_cut!=None:
                if r_f.GetChisquare()/r_f.GetNDF()>chi_cut:
                    consistency_msg('abnormal chi2/ndf ('+str(r_f.GetChisquare()/r_f.GetNDF())+') for edge fit '+'on '+si_names[si_num]+"(cut val: "+str(chi_cut)+")",pedantic)
		else:
		    logging.info("chi cut of "+str(chi_cut)+" passed succesfull with val: "+str(r_f.GetChisquare()/r_f.GetNDF()))
            elif chi_cut==None:
		logging.warning("chi_cut disabled this is generally unsave")

def rec(x,par):
    retval=par[0]
    retval*=1/(ROOT.TMath.Exp((x[0]-(par[1]+par[2]))/par[3])+1)
    retval*=1/(ROOT.TMath.Exp((-x[0]+(par[1]-par[2]))/par[3])+1)
    return retval

def intersect_rects(x,par):
    
    par0=[par[0],par[1],par[2],par[3]]
    par1=[par[4],par[5],par[6],par[7]]
    
    return ROOT.TMath.Abs(rec(x,par0)-rec(x,par1))

def get_rec_pos_vals(fits,rec_fits_one,rec_fits_zero,name,sigma=120):

    cnt=0
    pos=[]
    for f in fits:
        for ro,rz in zip(rec_fits_one,rec_fits_zero):
            inter=ROOT.TF1("rec_inter",intersect_rects,f.GetParameter(1)-sigma,f.GetParameter(1)+sigma,8)
            ROOT.SetOwnership( inter, True )
            for i in range(4):
                inter.SetParameter(i,rec_fits_zero[0].GetParameter(i))
                inter.SetParameter(i+4,rec_fits_one[0].GetParameter(i))
            pos.append(inter.GetMinimumX(f.GetParameter(1)-sigma,f.GetParameter(1)+sigma))
            cnt+=1
    
    new_pos=[]
    new_pos.append(pos[0])
    for p in pos:
        if ROOT.TMath.Abs(p-new_pos[-1])>sigma:
            new_pos.append(p)
    
    return new_pos

def proc_rec(new_clk,fits,hist_name,do_fit=True):
    
    hist=ROOT.TH1F(hist_name,hist_name,len(new_clk),0,len(new_clk))
    ROOT.SetOwnership( hist, True )
    cnt=1
    for inf in new_clk:
        if "zero" in hist_name:
            hist.SetBinContent(cnt,inf.zero)
            hist.SetBinError(cnt,ROOT.TMath.Sqrt(inf.zero))
        if "one" in hist_name:
            hist.SetBinContent(cnt,inf.one)
            hist.SetBinError(cnt,ROOT.TMath.Sqrt(inf.one))
        cnt+=1
    
    rec_fits=[]
    
    if do_fit:
    
        pos=[]
        width=fits[-1].GetParameter(1)-fits[-2].GetParameter(1)
        for i in range(0,len(fits)):
            pos.append(fits[i].GetParameter(1)-width/2.)
        for i in range(0,len(fits)):
            add_pos=fits[i].GetParameter(1)+width/2.
            is_in=False
            for p in pos:
                if (ROOT.TMath.Abs(add_pos-p)<width/2.):
                    is_in=True
            if is_in==False:    
                pos.append(add_pos)
    
        new_pos=[]
        for p in pos:
            if hist.GetBinContent(hist.FindBin(p))>hist.GetMaximum()/2.:
                new_pos.append(p)
    
        for p in new_pos:
            rec_fits.append(ROOT.TF1("rec",rec,p-width,p+width,4))
            ROOT.SetOwnership( rec_fits[-1], True )
            rec_fits[-1].SetParameter(0,hist.GetMaximum())
            rec_fits[-1].SetParameter(1,p)
            rec_fits[-1].SetParameter(2,width/2.)
            rec_fits[-1].SetParameter(3,10)
            hist.Fit(rec_fits[-1],"MNOQ","",p-width,p+width)
    
        #for i in range(1,len(rec_fits)):
        #    print "period:",rec_fits[i].GetParameter(1)-rec_fits[i-1].GetParameter(1),"+-",str(ROOT.TMath.Sqrt(rec_fits[i].GetParError(1)**2+rec_fits[i-1].GetParError(1)**2))
        #    print 1000000./((178.61225423/44.)*(rec_fits[i].GetParameter(1)-rec_fits[i-1].GetParameter(1)))
        
    return rec_fits,hist

def plot_rec(new_clk,rec_fits,hist,c1,file_name):

    c1.cd()
    hist.Draw("hist")
    for fit in rec_fits:
        fit.Draw("same")
    
    c1.SaveAs("/tmp/"+file_name)
    return c1,hist

import array
def do_fft(in_hist,name="",cut_offs=[]):
    
    ROOT.TVirtualFFT.SetTransform(0)
    hm=in_hist.FFT(0, "MAG")
    ROOT.SetOwnership( hm, True )
    hm.SetName("fft_"+name)
    hm.GetXaxis().Set(hm.GetNbinsX(),0,hm.GetBinCenter(hm.GetNbinsX())/ROOT.TMath.Abs(in_hist.GetXaxis().GetXmax()-in_hist.GetXaxis().GetXmin()))
    
    fft = ROOT.TVirtualFFT.GetCurrentTransform()
    ROOT.SetOwnership( fft, True )
    re_full = array.array('d', (0,)*hm.GetNbinsX())
    im_full = array.array('d', (0,)*hm.GetNbinsX())
    fft.GetPointsComplex(re_full,im_full)
    for i in range(hm.GetNbinsX()):
        val = ROOT.TMath.Sqrt(re_full[i]**2 + im_full[i]**2)
        x_ = i*hm.GetXaxis().GetBinWidth(0)
        
        is_ok=True
        for cut_off in cut_offs:
            if x_> cut_off[0] and x_ < cut_off[1]:
                is_ok=False

        if is_ok==False:
            re_full[i] = 0
            im_full[i] = 0
    
    fft_back = ROOT.TVirtualFFT.FFT(1, array.array('i', [hm.GetNbinsX()]), "C2R M K")
    ROOT.SetOwnership( fft_back, True )
    fft_back.SetPointsComplex(re_full,im_full)
    fft_back.Transform()
    hb = ROOT.TH1.TransformHisto(fft_back,0,"Re")
    ROOT.SetOwnership( hb, True )
    hb.SetName("fft_back_"+name)
    #hb.Draw()
    hb.GetXaxis().Set(hb.GetNbinsX(),in_hist.GetXaxis().GetXmin(),in_hist.GetXaxis().GetXmax())
    hb.Scale(1./(in_hist.GetNbinsX()))
    return hb,hm

def fit_pol(hist,gaus_fits,sigma):
    
    new_pos=[]
    new_fits=[]
    cnt=0
    for gf in gaus_fits:
    
        pol_fit=ROOT.TF1("pol14"+str(cnt),"pol14",gf.GetParameter(1)-sigma,gf.GetParameter(1)+sigma)
        ROOT.SetOwnership( pol_fit, True )
        hist.Fit(pol_fit,"MNOQ","",gf.GetParameter(1)-sigma,gf.GetParameter(1)+sigma)
        new_fits.append(pol_fit)
        new_pos.append(pol_fit.GetMaximumX(gf.GetParameter(1)-sigma,gf.GetParameter(1)+sigma))
    
    return new_pos,new_fits

