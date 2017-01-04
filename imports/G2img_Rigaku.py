# -*- coding: utf-8 -*-
########### SVN repository information ###################
# $Date: 2016-01-22 22:05:12 +0300 (Пт, 22 янв 2016) $
# $Author: toby $
# $Revision: 2133 $
# $URL: https://subversion.xray.aps.anl.gov/pyGSAS/trunk/imports/G2img_Rigaku.py $
# $Id: G2img_Rigaku.py 2133 2016-01-22 19:05:12Z toby $
########### SVN repository information ###################
'''
*Module G2img_Rigaku: .stl image file*
--------------------------------------

'''

import sys
import os
import GSASIIIO as G2IO
import GSASIIpath
GSASIIpath.SetVersionNumber("$Revision: 2133 $")
class Rigaku_ReaderClass(G2IO.ImportImage):
    '''Routine to read a Rigaku R-Axis IV image file.
    '''
    def __init__(self):
        super(self.__class__,self).__init__( # fancy way to self-reference
            extensionlist=('.stl',),
            strictExtension=True,
            formatName = 'Rigaku image',
            longFormatName = 'Read Rigaku R-Axis IV image file'
            )

    def ContentsValidator(self, filepointer):        
        '''Test by checking if the file size makes sense.
        '''
        fileSize = os.stat(filepointer.name).st_size
        Npix = (fileSize-6000)/2
        if Npix == 9000000 or Npix == 2250000 or Npix == 36000000:
            return True
        return False # not valid size
        
    def Reader(self,filename,filepointer, ParentFrame=None, **unused):
        '''Read using Bob's routine :func:`GSASIIIO.GetRigaku`
        (to be moved to this file, eventually)
        '''

        self.Comments,self.Data,self.Npix,self.Image = G2IO.GetRigaku(filename)
        if self.Npix == 0 or not self.Comments:
            return False
        self.LoadImage(ParentFrame,filename)
        return True
