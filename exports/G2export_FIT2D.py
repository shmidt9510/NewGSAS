#!/usr/bin/env python
# -*- coding: utf-8 -*-
########### SVN repository information ###################
# $Date: 2016-07-13 23:01:31 +0300 (Ср, 13 июл 2016) $
# $Author: vondreele $
# $Revision: 2376 $
# $URL: https://subversion.xray.aps.anl.gov/pyGSAS/trunk/exports/G2export_FIT2D.py $
# $Id: G2export_FIT2D.py 2376 2016-07-13 20:01:31Z vondreele $
########### SVN repository information ###################
'''
*Module G2export_FIT2D: Fit2D "Chi" export*
-------------------------------------------

Code to create .chi (Fit2D like) files for GSAS-II powder data export 

'''
import os.path
import numpy as np
import GSASIIpath
GSASIIpath.SetVersionNumber("$Revision: 2376 $")
import GSASIIIO as G2IO
import GSASIIpy3 as G2py3
import GSASIIobj as G2obj
import GSASIImath as G2mth
import GSASIIpwd as G2pwd

class ExportPowderCHI(G2IO.ExportBaseclass):
    '''Used to create a CHI file for a powder data set

    :param wx.Frame G2frame: reference to main GSAS-II frame
    '''
    def __init__(self,G2frame):
        super(self.__class__,self).__init__( # fancy way to say <parentclass>.__init__
            G2frame=G2frame,
            formatName = 'Fit2D chi file',
            extension='.chi',
            longFormatName = 'Export powder data as Fit2D .chi file'
            )
        self.exporttype = ['powder']
        self.multiple = True

    def Writer(self,TreeName,filename=None):
        self.OpenFile(filename)
        histblk = self.Histograms[TreeName]
        self.Write(str(TreeName)[5:]) # drop 'PWDR '
        self.Write("2-Theta Angle (Degrees)")
        self.Write("Intensity")
        self.Write("       "+str(len(histblk['Data'][0])))
        for X,Y in zip(histblk['Data'][0],histblk['Data'][1]):
            line = " %5.7e" % X
            line += "   %5.7e" % Y
            self.Write(line)
        self.CloseFile()
        
    def Exporter(self,event=None):
        '''Export a set of powder data as a Fit2D .chi file
        '''
        # the export process starts here
        self.InitExport(event)
        # load all of the tree into a set of dicts
        self.loadTree()
        if self.ExportSelect( # set export parameters
            AskFile='single' # get a file name/directory to save in
            ): return
        filenamelist = []
        for hist in self.histnam:
            # multiple files: create a unique name from the histogram
            fileroot = G2obj.MakeUniqueLabel(self.MakePWDRfilename(hist),filenamelist)
            # create an instrument parameter file
            self.filename = os.path.join(self.dirname,fileroot + self.extension)
            self.Writer(hist)
            print('Histogram '+str(hist)+' written to file '+str(self.fullpath))

class ExportPowderQCHI(G2IO.ExportBaseclass):
    '''Used to create a q-binned CHI file for a powder data set

    :param wx.Frame G2frame: reference to main GSAS-II frame
    '''
    def __init__(self,G2frame):
        super(self.__class__,self).__init__( # fancy way to say <parentclass>.__init__
            G2frame=G2frame,
            formatName = 'Fit2D q-bin chi file',
            extension='.chi',
            longFormatName = 'Export powder data as q-bin Fit2D .chi file'
            )
        self.exporttype = ['powder']
        self.multiple = True

    def Writer(self,TreeName,filename=None):
        import GSASIIlattice as G2lat
        self.OpenFile(filename)
        histblk = self.Histograms[TreeName]
        inst = histblk['Instrument Parameters'][0]
        self.Write(str(TreeName)[5:]) # drop 'PWDR '
        self.Write("Q")
        self.Write("Intensity")
        self.Write("       "+str(len(histblk['Data'][0])))
        for X,Y in zip(histblk['Data'][0],histblk['Data'][1]):
            line = " %5.7e" % (2.*np.pi/G2lat.Pos2dsp(inst,X))
            line += "   %5.7e" % Y
            self.Write(line)
        self.CloseFile()
        
    def Exporter(self,event=None):
        '''Export a set of powder data as a q-bin Fit2D .chi file
        '''
        # the export process starts here
        self.InitExport(event)
        # load all of the tree into a set of dicts
        self.loadTree()
        if self.ExportSelect( # set export parameters
            AskFile='single' # get a file name/directory to save in
            ): return
        filenamelist = []
        for hist in self.histnam:
            # multiple files: create a unique name from the histogram
            fileroot = G2obj.MakeUniqueLabel(self.MakePWDRfilename(hist),filenamelist)
            # create an instrument parameter file
            self.filename = os.path.join(self.dirname,fileroot + self.extension)
            self.Writer(hist)
            print('Histogram '+str(hist)+' written to file '+str(self.fullpath))
