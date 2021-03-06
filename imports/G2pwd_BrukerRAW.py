# -*- coding: utf-8 -*-
########### SVN repository information ###################
# $Date: 2014-12-27 11:14:59 -0600 (Sat, 27 Dec 2014) $
# $Author: vondreele $
# $Revision: 1620 $
# $URL: https://subversion.xray.aps.anl.gov/pyGSAS/trunk/imports/G2pwd_xye.py $
# $Id: G2pwd_xye.py 1620 2014-12-27 17:14:59Z vondreele $
########### SVN repository information ###################
'''
*Module G2pwd_BrukerRAW: Bruker v.1-v.3 .raw data*
---------------------------------------------------

Routine to read in powder data from a Bruker versions 1-3 .raw file

'''

import sys
import os.path as ospath
import struct as st
import numpy as np
import GSASIIIO as G2IO
import GSASIIpath
GSASIIpath.SetVersionNumber("$Revision: 1620 $")
class raw_ReaderClass(G2IO.ImportPowderData):
    'Routines to import powder data from a binary Bruker .RAW file'
    def __init__(self):
        super(self.__class__,self).__init__( # fancy way to self-reference
            extensionlist=('.RAW',),
            strictExtension=False,
            formatName = 'Bruker RAW',
            longFormatName = 'Bruker .RAW powder data file'
            )

    # Validate the contents -- make sure we only have valid lines
    def ContentsValidator(self, filepointer):
        'Look through the file for expected types of lines in a valid Bruker RAW file'
        head = filepointer.read(7)
        if head[:4] == 'RAW ':
            self.formatName = 'Bruker RAW ver. 1'
        elif head[:4] == 'RAW2':
            self.formatName = 'Bruker RAW ver. 2'
        elif head == 'RAW1.01':
            self.formatName = 'Bruker RAW ver. 3'
        elif head == 'RAW4.00':
            self.formatName = 'Bruker RAW ver. 4'
            self.errors += "Sorry, this is a Version 4 Bruker file. "
            self.errors += "We need documentation for it so that it can be implemented in GSAS-II. "
            self.errors += "Use PowDLL (http://users.uoi.gr/nkourkou/powdll/) to convert it to ASCII xy."
            print(self.errors)
            return False
        else:
            self.errors = 'Unexpected information in header: '
            if all([ord(c) < 128 and ord(c) != 0 for c in str(head)]): # show only if ASCII
                self.errors += '  '+str(head)
            else: 
                self.errors += '  (binary)'
            return False
        return True
            
    def Reader(self,filename,filepointer, ParentFrame=None, **kwarg):
        'Read a Bruker RAW file'
        self.comments = []
        self.repeat = True
        self.powderentry[0] = filename
        File = open(filename,'rb')
        if 'ver. 1' in self.formatName:
            raise Exception    #for now
        elif 'ver. 2' in self.formatName:
            try:
                File.seek(4)
                nBlock = int(st.unpack('<i',File.read(4))[0])
                File.seek(168)
                self.comments.append('Date/Time='+File.read(20))
                self.comments.append('Anode='+File.read(2))
                self.comments.append('Ka1=%.5f'%(st.unpack('<f',File.read(4))[0]))
                self.comments.append('Ka2=%.5f'%(st.unpack('<f',File.read(4))[0]))
                self.comments.append('Ka2/Ka1=%.5f'%(st.unpack('<f',File.read(4))[0]))
                File.seek(206)
                self.comments.append('Kb=%.5f'%(st.unpack('<f',File.read(4))[0]))
                pos = 256
                File.seek(pos)
                blockNum = kwarg.get('blocknum',0)
                self.idstring = ospath.basename(filename) + ' Scan '+str(blockNum)
                if blockNum <= nBlock:
                    for iBlock in range(blockNum):
                        headLen = int(st.unpack('<H',File.read(2))[0])
                        nSteps = int(st.unpack('<H',File.read(2))[0])
                        if iBlock+1 == blockNum:
                            File.seek(pos+12)
                            step = st.unpack('<f',File.read(4))[0]
                            start2Th = st.unpack('<f',File.read(4))[0]
                            pos += headLen      #position at start of data block
                            File.seek(pos)                                    
                            x = np.array([start2Th+i*step for i in range(nSteps)])
                            y = np.array([max(1.,st.unpack('<f',File.read(4))[0]) for i in range(nSteps)])
                            y = np.where(y<0.,y,1.)
                            w = 1./y
                            self.powderdata = [x,y,w,np.zeros(nSteps),np.zeros(nSteps),np.zeros(nSteps)]
                            break
                        pos += headLen+4*nSteps
                        File.seek(pos)
                    if blockNum == nBlock:
                        self.repeat = False                                   
                File.close()
            except Exception as detail:
                self.errors += '\n  '+str(detail)
                print self.formatName+' read error:'+str(detail) # for testing
                import traceback
                traceback.print_exc(file=sys.stdout)
                return False
        elif 'ver. 3' in self.formatName:
            try:
                File.seek(12)
                nBlock = int(st.unpack('<i',File.read(4))[0])
                self.comments.append('Date='+File.read(10))
                self.comments.append('Time='+File.read(10))
                File.seek(326)
                self.comments.append('Sample='+File.read(60))
                File.seek(564)
                radius = st.unpack('<f',File.read(4))[0]
                self.comments.append('Gonio. radius=%.2f'%(radius))
                self.Sample['Gonio. radius'] = radius
                File.seek(608)
                self.comments.append('Anode='+File.read(4))
                File.seek(616)
                self.comments.append('Ka mean=%.5f'%(st.unpack('<d',File.read(8))[0]))
                self.comments.append('Ka1=%.5f'%(st.unpack('<d',File.read(8))[0]))
                self.comments.append('Ka2=%.5f'%(st.unpack('<d',File.read(8))[0]))
                self.comments.append('Kb=%.5f'%(st.unpack('<d',File.read(8))[0]))
                self.comments.append('Ka2/Ka1=%.5f'%(st.unpack('<d',File.read(8))[0]))
                pos = 712
                File.seek(pos)      #position at 1st block header
                blockNum = kwarg.get('blocknum',0)
                self.idstring = ospath.basename(filename) + ' Scan '+str(blockNum)
                if blockNum <= nBlock:
                    for iBlock in range(blockNum):
                        headLen = int(st.unpack('<i',File.read(4))[0])+40
                        nSteps = int(st.unpack('<i',File.read(4))[0])
                        if iBlock+1 == blockNum:
                            st.unpack('<d',File.read(8))[0]
                            start2Th = st.unpack('<d',File.read(8))[0]
                            File.seek(pos+176)
                            step = st.unpack('<d',File.read(8))[0]
                            pos += headLen      #position at start of data block
                            File.seek(pos)                                    
                            x = np.array([start2Th+i*step for i in range(nSteps)])
                            y = np.array([max(1.,st.unpack('<f',File.read(4))[0]) for i in range(nSteps)])
                            w = 1./y
                            self.powderdata = [x,y,w,np.zeros(nSteps),np.zeros(nSteps),np.zeros(nSteps)]
                            break
                        pos += headLen+4*nSteps
                        File.seek(pos)
                    if blockNum == nBlock:
                        self.repeat = False                                   
                File.close()
            except Exception as detail:
                self.errors += '\n  '+str(detail)
                print self.formatName+' read error:'+str(detail) # for testing
                import traceback
                traceback.print_exc(file=sys.stdout)
                return False
            
        elif 'ver. 4' in self.formatName:   #does not work - format still elusive
            try:
                File.seek(12)   #ok
                self.comments.append('Date='+File.read(10))
                self.comments.append('Time='+File.read(10))
                File.seek(144)
                self.comments.append('Sample='+File.read(60))
                File.seek(564)  # where is it?
                radius = st.unpack('<f',File.read(4))[0]
                self.comments.append('Gonio. radius=%.2f'%(radius))
                self.Sample['Gonio. radius'] = radius
                File.seek(516)  #ok
                self.comments.append('Anode='+File.read(4))
                File.seek(472)  #ok
                self.comments.append('Ka mean=%.5f'%(st.unpack('<d',File.read(8))[0]))
                self.comments.append('Ka1=%.5f'%(st.unpack('<d',File.read(8))[0]))
                self.comments.append('Ka2=%.5f'%(st.unpack('<d',File.read(8))[0]))
                self.comments.append('Kb=%.5f'%(st.unpack('<d',File.read(8))[0]))
                self.comments.append('Ka2/Ka1=%.5f'%(st.unpack('<d',File.read(8))[0]))
                File.seek(pos)  #deliberate fail here - pos not known from file contents
                self.idstring = ospath.basename(filename) + ' Scan '+str(1)
                nSteps = int(st.unpack('<i',File.read(4))[0])
                st.unpack('<d',File.read(8))[0]
                start2Th = st.unpack('<d',File.read(8))[0]
                File.seek(pos+176)
                step = st.unpack('<d',File.read(8))[0]
                pos += headLen      #position at start of data block
                File.seek(pos)                                    
                x = np.array([start2Th+i*step for i in range(nSteps)])
                y = np.array([max(1.,st.unpack('<f',File.read(4))[0]) for i in range(nSteps)])
                w = 1./y
                self.powderdata = [x,y,w,np.zeros(nSteps),np.zeros(nSteps),np.zeros(nSteps)]
                File.close()
            except Exception as detail:
                self.errors += '\n  '+str(detail)
                print self.formatName+' read error:'+str(detail) # for testing
                import traceback
                traceback.print_exc(file=sys.stdout)
                return False
            
        return True
