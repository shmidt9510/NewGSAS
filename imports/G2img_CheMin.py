# -*- coding: utf-8 -*-
########### SVN repository information ###################
# $Date: 2016-01-22 22:05:12 +0300 (Пт, 22 янв 2016) $
# $Author: toby $
# $Revision: 2133 $
# $URL: https://subversion.xray.aps.anl.gov/pyGSAS/trunk/imports/G2img_CheMin.py $
# $Id: G2img_CheMin.py 2133 2016-01-22 19:05:12Z toby $
########### SVN repository information ###################
'''
*Module G2img_png: png image file*
---------------------------------------

Routine to read an image in .png (Portable Network Graphics) format.
For now, the only known use of this is with converted Mars Rover (CheMin)
tif files, so default parameters are for that.

'''

import sys
import os
import GSASIIIO as G2IO
import GSASIIpath
GSASIIpath.SetVersionNumber("$Revision: 2133 $")
class png_ReaderClass(G2IO.ImportImage):
    '''Reads standard PNG images; parameters are set to those of the
    Mars Rover (CheMin) diffractometer.
    '''
    def __init__(self):
        super(self.__class__,self).__init__( # fancy way to self-reference
            extensionlist=('.png',),
            strictExtension=True,
            formatName = 'PNG image',
            longFormatName = 'PNG image from CheMin'
            )

    def ContentsValidator(self, filepointer):
        '''no test at this time
        '''
        return True
        
    def Reader(self,filename,filepointer, ParentFrame=None, **unused):
        '''Reads using standard scipy PNG reader
        '''
        import scipy.misc
        self.Image = scipy.misc.imread(filename,flatten=True)
        self.Npix = self.Image.size
        if self.Npix == 0:
            return False
        if ParentFrame:
            self.Comments = ['no metadata']
            pixy = list(self.Image.shape)
            sizexy = [40,40]
            self.Data = {'wavelength': 1.78892, 'pixelSize': sizexy, 'distance': 18.0,'size':pixy}
            self.Data['center'] = [pixy[0]*sizexy[0]/1000,pixy[1]*sizexy[1]/2000]
            G2IO.EditImageParms(ParentFrame,self.Data,self.Comments,self.Image,filename)
        self.LoadImage(ParentFrame,filename)
        return True
