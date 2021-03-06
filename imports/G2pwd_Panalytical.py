# -*- coding: utf-8 -*-
########### SVN repository information ###################
# $Date: $
# $Author: von dreele $
# $Revision: $
# $URL: $
# $Id: $
########### SVN repository information ###################
import os
import os.path as ospath
import xml.etree.ElementTree as ET
import numpy as np
import GSASIIIO as G2IO
import GSASIIpath
GSASIIpath.SetVersionNumber("$Revision: $")
class Panalytical_ReaderClass(G2IO.ImportPowderData):
    '''Routines to import powder data from a Pananalytical.xrdm (xml) file. 
    
    '''
    def __init__(self):
        super(self.__class__,self).__init__( # fancy way to self-reference
            extensionlist=('.xrdml','.xml'),
            strictExtension=True,
            formatName = 'Panalytical xrdml (xml)',
            longFormatName = 'Panalytical powder data as *.xrdml'
            )
        self.vals = None
        self.stepsize = None
        self.skip = 0
        self.root = None

    # Validate the contents -- make sure we only have valid lines and set
    # values we will need for later read.
    def ContentsValidator(self, filepointer):
        self.vals = None
        self.stepsize = None
        filepointer.seek(0)
        try:
            self.root = ET.parse(filepointer).getroot()
            tag = self.root.tag
            tag = tag.split('}')[0]+'}'
            self.root.find(tag+'comment')
           
        except:
            self.errors = 'Bad xml file'
            return False
        return True
            
    def Reader(self,filename,filepointer, ParentFrame=None, **kwarg):
        'Read a Panalytical .xrdml (.xml) file; already in self.root'
        blockNum = kwarg.get('blocknum',0)
        self.idstring = ospath.basename(filename) + ' Scan '+str(blockNum)
        x = []
        y = []
        w = []
        tag = self.root.tag
        tag = tag.split('}')[0]+'}'
        sample = self.root.find(tag+'sample')
        self.idstring = ospath.basename(filename) + ' Scan '+str(blockNum)
        dataSets = self.root.findall(tag+'xrdMeasurement')
        if blockNum-1 == len(dataSets):
            self.repeat = False
            return False
        data = dataSets[blockNum-1]
        if len(dataSets) > 1:
            self.repeat = True
        wave = data.find(tag+'usedWavelength')
        incident = data.find(tag+'incidentBeamPath')
        radius = float(incident.find(tag+'radius').text)
        tube = incident.find(tag+'xRayTube')
        scan = data.find(tag+'scan')
        header = scan.find(tag+'header')
        dataPoints = scan.find(tag+'dataPoints')
        self.comments.append('Gonio. radius=%.2f'%(radius))
        self.Sample['Gonio. radius'] = radius
        if sample.find(tag+'id').text:
            self.comments.append('Sample name='+sample.find(tag+'id').text)
        self.comments.append('Date/TimeStart='+header.find(tag+'startTimeStamp').text)
        self.comments.append('Date/TimeEnd='+header.find(tag+'endTimeStamp').text)
        self.comments.append('xray tube='+tube.attrib['name'])
        self.comments.append('Ka1=%s'%(wave.find(tag+'kAlpha1').text))
        self.comments.append('Ka2=%s'%(wave.find(tag+'kAlpha2').text))
        self.comments.append('Ka2/Ka1=%s'%(wave.find(tag+'ratioKAlpha2KAlpha1').text))
        self.comments.append('Kb=%s'%(wave.find(tag+'kBeta').text))
        self.comments.append('Voltage='+tube.find(tag+'tension').text)
        self.comments.append('Current='+tube.find(tag+'current').text)
        limits = dataPoints.find(tag+'positions')
        startPos = float(limits.find(tag+'startPosition').text)
        endPos= float(limits.find(tag+'endPosition').text)
        y = np.fromstring(dataPoints.find(tag+'intensities').text,sep=' ')
        N = y.shape[0]
        x = np.linspace(startPos,endPos,N)
        w = np.where(y>0,1./y,1.)
        self.powderdata = [
            np.array(x), # x-axis values
            np.array(y), # powder pattern intensities
            np.array(w), # 1/sig(intensity)^2 values (weights)
            np.zeros(N), # calc. intensities (zero)
            np.zeros(N), # calc. background (zero)
            np.zeros(N), # obs-calc profiles
            ]
        conditions = scan.find(tag+'nonAmbientPoints')
        if conditions:
            kind = conditions.attrib['type']
            if kind == 'Temperature':
                Temperature = float(conditions.find(tag+'nonAmbientValues').text.split()[-1])
                self.Sample['Temperature'] = Temperature
        return True
