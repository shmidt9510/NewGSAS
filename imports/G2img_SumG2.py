# -*- coding: utf-8 -*-
########### SVN repository information ###################
# $Date: 2016-06-05 20:58:58 +0300 (Вс, 05 июн 2016) $
# $Author: vondreele $
# $Revision: 2309 $
# $URL: https://subversion.xray.aps.anl.gov/pyGSAS/trunk/imports/G2img_SumG2.py $
# $Id: G2img_SumG2.py 2309 2016-06-05 17:58:58Z vondreele $
########### SVN repository information ###################
'''
*Module G2img_SumG2: Python pickled image*
------------------------------------------

'''

import sys
import os
import cPickle
import GSASIIIO as G2IO
import GSASIIpath
GSASIIpath.SetVersionNumber("$Revision: 2309 $")
class G2_ReaderClass(G2IO.ImportImage):
    '''Routine to read an image that has been pickled in Python. Images
    in this format are created by the "Sum image data" command. At least for
    now, only one image is permitted per file.
    '''
    def __init__(self):
        super(self.__class__,self).__init__( # fancy way to self-reference
            extensionlist=('.G2img',),
            strictExtension=True,
            formatName = 'GSAS-II image',
            longFormatName = 'cPickled image from GSAS-II'
            )

    def ContentsValidator(self, filepointer):
        '''test by trying to unpickle (should be quick)
        '''
        try:
            cPickle.load(filepointer)
        except:
            return False
        return True
        
    def Reader(self,filename,filepointer, ParentFrame=None, **unused):
        '''Read using cPickle
        '''
        import scipy.misc
        Fp = open(filename,'rb')
        self.Comments,self.Data,self.Npix,self.Image = cPickle.load(Fp)
        Fp.close()
        self.LoadImage(ParentFrame,filename)
        return True
