import ROOT
import signal
import sys

class pMainFrame(ROOT.TGMainFrame):
    def __init__(self, parent, width, height, file_):
        ROOT.TGMainFrame.__init__(self, parent, width, height)

        self.tabs = ROOT.TGTab(self, width, height)
        self.canvases = {}
        self.hists = {}

        for ch in range(0, 16, 1):
            tab = self.tabs.AddTab("Channel %i" % ch)
            canvas = ROOT.TRootEmbeddedCanvas('Channel Canvas %i' % ch, tab, width, height)
            tab.AddFrame(canvas, ROOT.TGLayoutHints(ROOT.kLHintsExpandX | ROOT.kLHintsExpandY))
            self.canvases[ch] = canvas.GetCanvas()
            self.hists[ch] = ROOT.TH1F("Amplitudes %i" % ch, "Amplitudes %i" % ch, 4096, 0, 4096)

        self.AddFrame(self.tabs, ROOT.TGLayoutHints(ROOT.kLHintsExpandX | ROOT.kLHintsExpandY))
        self.ButtonsFrame = ROOT.TGHorizontalFrame(self, width, 40)
        self.ButtonsLeftFrame = ROOT.TGHorizontalFrame(self.ButtonsFrame, width // 3, 40)
        self.ButtonsRightFrame = ROOT.TGHorizontalFrame(self.ButtonsFrame, 2 * width // 3, 40)

        self.ButtonsFrame.AddFrame(self.ButtonsLeftFrame, ROOT.TGLayoutHints(ROOT.kLHintsLeft | ROOT.kLHintsExpandX))
        self.ButtonsFrame.AddFrame(self.ButtonsRightFrame,
                                   ROOT.TGLayoutHints(ROOT.kLHintsRight | ROOT.kLHintsBottom | ROOT.kLHintsExpandX))

        self.file_proc = FileProcessor()
        self.file_proc.file_ = file_
        self.file_proc.canvases = self.canvases
        self.file_proc.hists = self.hists

        self.start_stop_dispatch = ROOT.TPyDispatcher(self.start_stop)
        self.StartPauseButton = ROOT.TGTextButton(self.ButtonsLeftFrame, '&Run', 10)
        self.StartPauseButton.Connect('Clicked()', "TPyDispatcher", self.start_stop_dispatch, 'Dispatch()')
        self.ButtonsLeftFrame.AddFrame(self.StartPauseButton, ROOT.TGLayoutHints())

        self.ExitButton = ROOT.TGTextButton(self.ButtonsLeftFrame, '&Exit', 20)
        self.ExitButton.SetCommand('TPython::Exec( "raise SystemExit" )')
        self.ButtonsLeftFrame.AddFrame(self.ExitButton, ROOT.TGLayoutHints())

        self.Status = ROOT.TGLabel(self.ButtonsRightFrame, '')
        self.ButtonsRightFrame.AddFrame(self.Status, ROOT.TGLayoutHints(
            ROOT.kLHintsRight | ROOT.kLHintsBottom | ROOT.kLHintsExpandX))

        self.AddFrame(self.ButtonsFrame, ROOT.TGLayoutHints(ROOT.kLHintsExpandX))

        self.SetWindowName('Amplitudes')
        self.MapSubwindows()
        self.Resize(self.GetDefaultSize())
        self.MapWindow()

        global status
        status = self.Status

        self.start_stop()

    def start_stop(self):
        if not self.file_proc.stopped():
            self.StartPauseButton.SetTitle('&Run')
            self.file_proc.stop()

        else:
            self.StartPauseButton.SetTitle('&Pause')
            self.file_proc.start()

    def __del__(self):
        self.file_proc.stop()
        self.Cleanup()


def init_ui():
    from amc_hax import open_source

    # display GUI with amplitudes
    def signal_handler(signal, frame):
        ROOT.TPython.Exec("raise SystemExit")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    ROOT.gROOT.SetBatch(0)
    ROOT.gStyle.SetOptStat(1111111)
    ROOT.gStyle.SetPadGridX(1)
    ROOT.gStyle.SetPadGridY(1)
    ROOT.gStyle.SetOptFit(1)
    ROOT.gStyle.SetTitleOffset(0.4, 'y')
    ROOT.gStyle.SetTitleSize(0.06, 'x')
    ROOT.gStyle.SetTitleSize(0.07, 'y')
    ROOT.gStyle.SetPadBottomMargin(0.125)
    ROOT.gStyle.SetCanvasColor(22)
    ROOT.gStyle.SetFrameFillColor(42)

    window = pMainFrame(ROOT.gClient.GetRoot(), 1200, 800, open_source)
    ROOT.gApplication.Run()
