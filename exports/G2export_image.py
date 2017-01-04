#!/usr/bin/env python
# -*- coding: utf-8 -*-
########### SVN repository information ###################
# $Date: 2014-03-25 02:22:41 +0400 (Вт, 25 мар 2014) $
# $Author: toby $
# $Revision: 1261 $
# $URL: https://subversion.xray.aps.anl.gov/pyGSAS/trunk/exports/G2export_image.py $
# $Id: G2export_image.py 1261 2014-03-24 22:22:41Z toby $
########### SVN repository information ###################
'''
*Module G2export_image: 2D Image data export*
------------------------------------------------------

Demonstrates how an image is retrieved and written. Uses
a SciPy routine to write a PNG format file. 
'''
import os.path
import scipy.misc
import GSASIIpath
GSASIIpath.SetVersionNumber("$Revision: 1261 $")
import GSASIIIO as G2IO
import GSASIImath as G2mth

class ExportImagePNG(G2IO.ExportBaseclass):
    '''Used to create a PNG file for a GSAS-II image

    :param wx.Frame G2frame: reference to main GSAS-II frame
    '''
    def __init__(self,G2frame):
        super(self.__class__,self).__init__( # fancy way to say <parentclass>.__init__
            G2frame=G2frame,
            formatName = 'PNG image file',
            extension='.png',
            longFormatName = 'Export image in PNG format'
            )
        self.exporttype = ['image']
        #self.multiple = True
    def Exporter(self,event=None):
        '''Export an image
        '''
        # the export process starts here
        self.InitExport(event)
        # load all of the tree into a set of dicts
        self.loadTree()
        if self.ExportSelect(): return # select one image; ask for a file name
        # process the selected image(s) (at present only one image)
        for i in sorted(self.histnam): 
            filename = os.path.join(
                self.dirname,
                os.path.splitext(self.filename)[0] + self.extension
                )
            imgFile = self.Histograms[i].get('Data',(None,None))
            Comments,Data,Npix,Image = G2IO.GetImageData(self.G2frame,imgFile)
            scipy.misc.imsave(filename,Image)
            print('Image '+str(imgFile)+' written to file '+str(filename))
            
