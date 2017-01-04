# -*- coding: utf-8 -*-
########### SVN repository information ###################
# $Date: 2016-11-21 20:13:37 +0300 (Пн, 21 ноя 2016) $
# $Author: vondreele $
# $Revision: 2539 $
# $URL: https://subversion.xray.aps.anl.gov/pyGSAS/trunk/imports/G2img_ADSC.py $
# $Id: G2img_ADSC.py 2539 2016-11-21 17:13:37Z vondreele $
########### SVN repository information ###################
'''
*Module G2img_ADSC: .img image file*
--------------------------------------

'''

import GSASIIIO as G2IO
import GSASIIpath
GSASIIpath.SetVersionNumber("$Revision: 2539 $")
class ADSC_ReaderClass(G2IO.ImportImage):
    '''Reads an ADSC .img file
    '''
    def __init__(self):
        super(self.__class__,self).__init__( # fancy way to self-reference
            extensionlist=('.img',),
            strictExtension=True,
            formatName = 'ADSC image',
            longFormatName = 'ADSC image file'
            )

    def ContentsValidator(self, filepointer):
        '''no test at this time
        '''
        return True
        
    def Reader(self,filename,filepointer, ParentFrame=None, **unused):
        '''Read using Bob's routine :func:`GSASIIIO.GetImgData`
        (to be moved to this file, eventually)
        '''
        self.Comments,self.Data,self.Npix,self.Image = G2IO.GetImgData(filename)
        if self.Npix == 0 or not self.Comments:
            return False
        self.LoadImage(ParentFrame,filename)
        return True
