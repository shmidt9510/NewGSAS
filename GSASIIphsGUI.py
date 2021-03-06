# -*- coding: utf-8 -*-
#GSASII - phase data display routines
########### SVN repository information ###################
# $Date: 2016-12-23 22:37:14 +0300 (Пт, 23 дек 2016) $
# $Author: vondreele $
# $Revision: 2601 $
# $URL: https://subversion.xray.aps.anl.gov/pyGSAS/trunk/GSASIIphsGUI.py $
# $Id: GSASIIphsGUI.py 2601 2016-12-23 19:37:14Z vondreele $
########### SVN repository information ###################
'''
*GSASIIphsGUI: Phase GUI*
-------------------------

Module to create the GUI for display of phase information
in the data display window when a phase is selected.
Phase information is stored in one or more
:ref:`Phase Tree Item <Phase_table>` objects.
Note that there are functions
that respond to some tabs in the phase GUI in other modules
(such as GSASIIddata).

'''
import os.path
import wx
import wx.grid as wg
import wx.lib.scrolledpanel as wxscroll
import matplotlib as mpl
import math
import copy
import time
import sys
import random as ran
import GSASIIpath
GSASIIpath.SetVersionNumber("$Revision: 2601 $")
import GSASIIlattice as G2lat
import GSASIIspc as G2spc
import GSASIIElem as G2elem
import GSASIIElemGUI as G2elemGUI
import GSASIIddataGUI as G2ddG
import GSASIIplot as G2plt
import GSASIIgrid as G2gd
import GSASIIIO as G2IO
import GSASIIstrMain as G2stMn
import GSASIIstrIO as G2strIO
import GSASIImath as G2mth
import GSASIIpwd as G2pwd
import GSASIIpy3 as G2py3
import GSASIIobj as G2obj
import GSASIIctrls as G2G
import GSASIIconstrGUI as G2cnstG
import numpy as np
import numpy.linalg as nl

VERY_LIGHT_GREY = wx.Colour(235,235,235)
WHITE = wx.Colour(255,255,255)
BLACK = wx.Colour(0,0,0)
WACV = wx.ALIGN_CENTER_VERTICAL
mapDefault = {'MapType':'','RefList':'','Resolution':0.5,'Show bonds':True,
                'rho':[],'rhoMax':0.,'mapSize':10.0,'cutOff':50.,'Flip':False}
TabSelectionIdDict = {}
# trig functions in degrees
sind = lambda x: np.sin(x*np.pi/180.)
tand = lambda x: np.tan(x*np.pi/180.)
cosd = lambda x: np.cos(x*np.pi/180.)
asind = lambda x: 180.*np.arcsin(x)/np.pi
acosd = lambda x: 180.*np.arccos(x)/np.pi
atan2d = lambda x,y: 180.*np.arctan2(y,x)/np.pi
    
def SetPhaseWindow(mainFrame,phasePage,mainSizer,Scroll=0):
    phasePage.SetSizer(mainSizer)
    Size = mainSizer.GetMinSize()
    Size[0] += 40
    Size[1] = min(Size[1]+ 150,500) 
    phasePage.SetScrollbars(10,10,Size[0]/10-4,Size[1]/10-1)
    phasePage.SetSize(Size)
    phasePage.Scroll(0,Scroll)
    Size[1] = min(500,Size[1])
    mainFrame.setSizePosLeft(Size)
    
def FindBondsDraw(data):    
    '''uses numpy & masks - very fast even for proteins!
    '''
    import numpy.ma as ma
    cx,ct,cs,ci = data['Drawing']['atomPtrs']
    hydro = data['Drawing']['showHydrogen']
    atomData = data['Drawing']['Atoms']
    generalData = data['General']
    Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])
    radii = generalData['BondRadii']
    if generalData.get('DisAglCtls',{}):
        radii = generalData['DisAglCtls']['BondRadii']
    atomTypes = generalData['AtomTypes']
    try:
        indH = atomTypes.index('H')
        radii[indH] = 0.5
    except:
        pass            
    for atom in atomData:
        atom[-2] = []               #clear out old bonds/polyhedra
        atom[-1] = []
    Indx = range(len(atomData))
    Atoms = []
    Styles = []
    Radii = []
    for atom in atomData:
        Atoms.append(np.array(atom[cx:cx+3]))
        Styles.append(atom[cs])
        try:
            if not hydro and atom[ct] == 'H':
                Radii.append(0.0)
            else:
                Radii.append(radii[atomTypes.index(atom[ct])])
        except ValueError:          #changed atom type!
            Radii.append(0.20)
    Atoms = np.array(Atoms)
    Radii = np.array(Radii)
    IASR = zip(Indx,Atoms,Styles,Radii)
    for atomA in IASR:
        if atomA[2] in ['lines','sticks','ellipsoids','balls & sticks','polyhedra']:
            Dx = Atoms-atomA[1]
            dist = ma.masked_less(np.sqrt(np.sum(np.inner(Amat,Dx)**2,axis=0)),0.5) #gets rid of G2frame & disorder "bonds" < 0.5A
            sumR = atomA[3]+Radii
            IndB = ma.nonzero(ma.masked_greater(dist-data['Drawing']['radiusFactor']*sumR,0.))                 #get indices of bonded atoms
            i = atomA[0]
            for j in IndB[0]:
                if Styles[i] == 'polyhedra':
                    atomData[i][-2].append(np.inner(Amat,Dx[j]))
                elif Styles[j] != 'polyhedra' and j > i:
                    atomData[i][-2].append(Dx[j]*Radii[i]/sumR[j])
                    atomData[j][-2].append(-Dx[j]*Radii[j]/sumR[j])
            if Styles[i] == 'polyhedra':
                Bonds = atomData[i][-2]
                Faces = []
                if len(Bonds) > 2:
                    FaceGen = G2lat.uniqueCombinations(Bonds,3)     #N.B. this is a generator
                    for face in FaceGen:
                        vol = nl.det(face)
                        if abs(vol) > 1. or len(Bonds) == 3:
                            if vol < 0.:
                                face = [face[0],face[2],face[1]]
                            face = np.array(face)
                            if not np.array([np.array(nl.det(face-bond))+0.0001 < 0 for bond in Bonds]).any():
                                norm = np.cross(face[1]-face[0],face[2]-face[0])
                                norm /= np.sqrt(np.sum(norm**2))
                                Faces.append([face,norm])
                    atomData[i][-1] = Faces
                        
def UpdatePhaseData(G2frame,Item,data,oldPage):
    '''Create the data display window contents when a phase is clicked on
    in the main (data tree) window.
    Called only from :meth:`GSASIIgrid.MovePatternTreeToGrid`,
    which in turn is called from :meth:`GSASII.GSASII.OnPatternTreeSelChanged`
    when a tree item is selected.

    :param wx.frame G2frame: the main GSAS-II frame object
    :param wx.TreeItemId Item: the tree item that was selected
    :param dict data: all the information on the phase in a dictionary
    :param int oldPage: This sets a tab to select when moving
      from one phase to another, in which case the same tab is selected
      to display first. This is set only when the previous data tree
      selection is a phase, if not the value is None. The default action
      is to bring up the General tab.

    '''
    
    def GetReflData(G2frame,phaseName,reflNames):
        ReflData = {'RefList':[],'Type':''}
        if '' in reflNames:
            return None
        for reflName in reflNames:
            if 'PWDR' in reflName:
                PatternId = G2gd.GetPatternTreeItemId(G2frame,G2frame.root, reflName)
                reflSets = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,PatternId,'Reflection Lists'))
                reflData = reflSets[phaseName]
            elif 'HKLF' in reflName:
                PatternId = G2gd.GetPatternTreeItemId(G2frame,G2frame.root, reflName)
                reflData = G2frame.PatternTree.GetItemPyData(PatternId)[1]
                if 'Type' not in reflData:
                    reflData['Type'] = 'SXC'
            if ReflData['Type'] and reflData['Type'] != ReflData['Type']:
                G2frame.ErrorDialog('Data type conflict',
                    reflName+' conflicts with previous '+ReflData['Type'])
                return None
            ReflData['RefList'] += list(reflData['RefList'])
            ReflData['Type'] = reflData['Type']
        return ReflData

    # UpdatePhaseData execution continues below
    
    def SetupGeneral():
        generalData = data['General']
        atomData = data['Atoms']
        generalData['AtomTypes'] = []
        generalData['Isotopes'] = {}
# various patches
        if 'Isotope' not in generalData:
            generalData['Isotope'] = {}
        if 'Data plot type' not in generalData:
            generalData['Data plot type'] = 'Mustrain'
        if 'POhkl' not in generalData:
            generalData['POhkl'] = [0,0,1]
        if 'Map' not in generalData:
            generalData['Map'] = mapDefault.copy()
        if 'Flip' not in generalData:
            generalData['Flip'] = {'RefList':'','Resolution':0.5,'Norm element':'None',
                'k-factor':0.1,'k-Max':20.,}
        if 'testHKL' not in generalData['Flip']:
            generalData['Flip']['testHKL'] = [[0,0,2],[2,0,0],[1,1,1],[0,2,0],[1,2,3]]
        if 'doPawley' not in generalData:
            generalData['doPawley'] = False
        if 'Pawley dmin' not in generalData:
            generalData['Pawley dmin'] = 1.0
        if 'Pawley neg wt' not in generalData:
            generalData['Pawley neg wt'] = 0.0
        if 'Algolrithm' in generalData.get('MCSA controls',{}) or \
            'MCSA controls' not in generalData:
            generalData['MCSA controls'] = {'Data source':'','Annealing':[50.,0.001,50],
            'dmin':2.0,'Algorithm':'log','Jump coeff':[0.95,0.5],'boltzmann':1.0,
            'fast parms':[1.0,1.0,1.0],'log slope':0.9,'Cycles':1,'Results':[],'newDmin':True}
        if 'AtomPtrs' not in generalData:
            generalData['AtomPtrs'] = [3,1,7,9]
            if generalData['Type'] == 'macromolecular':
                generalData['AtomPtrs'] = [6,4,10,12]
            elif generalData['Type'] == 'magnetic':
                generalData['AtomPtrs'] = [3,1,10,12]
        if generalData['Type'] in ['modulated',]:
            generalData['Modulated'] = True
            generalData['Type'] = 'nuclear'
            if 'Super' not in generalData:
                generalData['Super'] = 1
                generalData['SuperVec'] = [[0,0,.1],False,4]
                generalData['SSGData'] = {}
            if '4DmapData' not in generalData:
                generalData['4DmapData'] = mapDefault.copy()
                generalData['4DmapData'].update({'MapType':'Fobs'})
        if 'Modulated' not in generalData:
            generalData['Modulated'] = False
        if 'HydIds' not in generalData:
            generalData['HydIds'] = {}
# end of patches
        cx,ct,cs,cia = generalData['AtomPtrs']
        generalData['NoAtoms'] = {}
        generalData['BondRadii'] = []
        generalData['AngleRadii'] = []
        generalData['vdWRadii'] = []
        generalData['AtomMass'] = []
        generalData['Color'] = []
        if generalData['Type'] == 'magnetic':
            generalData['MagDmin'] = generalData.get('MagDmin',1.0)
            landeg = generalData.get('Lande g',[])
        generalData['Mydir'] = G2frame.dirname
        badList = {}
        for iat,atom in enumerate(atomData):
            atom[ct] = atom[ct].lower().capitalize()              #force to standard form
            if generalData['AtomTypes'].count(atom[ct]):
                generalData['NoAtoms'][atom[ct]] += atom[cx+3]*float(atom[cs+1])
            elif atom[ct] != 'UNK':
                Info = G2elem.GetAtomInfo(atom[ct])
                if not Info:
                    if atom[ct] not in badList:
                        badList[atom[ct]] = 0
                    badList[atom[ct]] += 1
                    atom[ct] = 'UNK'
                    continue
                atom[ct] = Info['Symbol'] # N.B. symbol might be changed by GetAtomInfo
                generalData['AtomTypes'].append(atom[ct])
                generalData['Z'] = Info['Z']
                generalData['Isotopes'][atom[ct]] = Info['Isotopes']
                generalData['BondRadii'].append(Info['Drad'])
                generalData['AngleRadii'].append(Info['Arad'])
                generalData['vdWRadii'].append(Info['Vdrad'])
                if atom[ct] in generalData['Isotope']:
                    if generalData['Isotope'][atom[ct]] not in generalData['Isotopes'][atom[ct]]:
                        isotope = generalData['Isotopes'][atom[ct]].keys()[-1]
                        generalData['Isotope'][atom[ct]] = isotope
                    generalData['AtomMass'].append(Info['Isotopes'][generalData['Isotope'][atom[ct]]]['Mass'])
                else:
                    generalData['Isotope'][atom[ct]] = 'Nat. Abund.'
                    if 'Nat. Abund.' not in generalData['Isotopes'][atom[ct]]:
                        isotope = generalData['Isotopes'][atom[ct]].keys()[-1]
                        generalData['Isotope'][atom[ct]] = isotope
                    generalData['AtomMass'].append(Info['Mass'])
                generalData['NoAtoms'][atom[ct]] = atom[cx+3]*float(atom[cs+1])
                generalData['Color'].append(Info['Color'])
                if generalData['Type'] == 'magnetic':
                    if len(landeg) < len(generalData['AtomTypes']):
                        landeg.append(2.0)
        if generalData['Type'] == 'magnetic':
            generalData['Lande g'] = landeg[:len(generalData['AtomTypes'])]
                        
        if badList:
            msg = 'Warning: element symbol(s) not found:'
            for key in badList:
                msg += '\n\t' + key
                if badList[key] > 1:
                    msg += ' (' + str(badList[key]) + ' times)'
            wx.MessageBox(msg,caption='Element symbol error')
        F000X = 0.
        F000N = 0.
        for i,elem in enumerate(generalData['AtomTypes']):
            F000X += generalData['NoAtoms'][elem]*generalData['Z']
            isotope = generalData['Isotope'][elem]
            F000N += generalData['NoAtoms'][elem]*generalData['Isotopes'][elem][isotope]['SL'][0]
        generalData['F000X'] = F000X
        generalData['F000N'] = F000N
        generalData['Mass'] = G2mth.getMass(generalData)
       

################################################################################
##### General phase routines
################################################################################

    def UpdateGeneral(Scroll=0):
        '''Draw the controls for the General phase data subpage
        '''
        
        """ This is the default dictionary structure for phase data
        (taken from GSASII.py)
        'General':{
            'Name':PhaseName
            'Type':'nuclear'
            'SGData':SGData
            'Cell':[False,10.,10.,10.,90.,90.,90,1000.]
            'AtomPtrs':[]
            'Pawley dmin':1.0,
            'Pawley neg wt':0.0}
        'Atoms':[]
        'Drawing':{}
        """        
        # UpdateGeneral execution starts here
        #General.DestroyChildren() # bad, deletes scrollbars on Mac!
        if General.GetSizer():
            General.GetSizer().Clear(True)
        phaseTypes = ['nuclear','magnetic','macromolecular','faulted']
        SetupGeneral()
        generalData = data['General']
        Map = generalData['Map']
        Flip = generalData['Flip']
        MCSAdata = generalData['MCSA controls']  
        PWDR = any(['PWDR' in item for item in data['Histograms'].keys()])
        # UpdateGeneral execution continues below
        
        def NameSizer():   
            
            def SetDefaultSSsymbol():
                if generalData['SGData']['SGLaue'] in '-1':
                    return '(abg)'
                elif generalData['SGData']['SGLaue'] in ['2/m']:
                    if generalData['SGData']['SGUniq'] == 'a':
                        return '(a00)'
                    elif generalData['SGData']['SGUniq'] == 'b':
                        return '(0b0)'
                    elif generalData['SGData']['SGUniq'] == 'c':
                        return '(00g)'
                else:
                    return '(00g)'
                                
            def OnPhaseName(event):
                event.Skip()
                oldName = generalData['Name']
                phaseRIdList,usedHistograms = G2frame.GetPhaseInfofromTree()
                phaseNameList = usedHistograms.keys() # phase names in use
                newName = NameTxt.GetValue().strip()
                if newName and newName != oldName:
                    newName = G2obj.MakeUniqueLabel(newName,phaseNameList)             
                    generalData['Name'] = newName
                    G2frame.G2plotNB.Rename(oldName,generalData['Name'])
                    G2frame.dataFrame.SetLabel('Phase Data for '+generalData['Name'])
                    G2frame.PatternTree.SetItemText(Item,generalData['Name'])
                    # change phase name key in Reflection Lists for each histogram
                    for hist in data['Histograms']:
                        ht = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,hist)
                        rt = G2gd.GetPatternTreeItemId(G2frame,ht,'Reflection Lists')
                        if not rt: continue
                        RfList = G2frame.PatternTree.GetItemPyData(rt)
                        if oldName not in RfList:
                            print('Warning: '+oldName+' not in Reflection List for '+
                                  hist)
                            continue
                        RfList[newName] = RfList[oldName]
                        del RfList[oldName]                            
                NameTxt.SetValue(generalData['Name'])
                                                
            def OnPhaseType(event):
                if not len(generalData['AtomTypes']):             #can change only if no atoms!
                    generalData['Type'] = TypeTxt.GetValue()
                    pages = [G2frame.dataDisplay.GetPageText(PageNum) for PageNum in range(G2frame.dataDisplay.GetPageCount())]
                    if generalData['Type'] == 'faulted':
                        G2frame.dataFrame.Bind(wx.EVT_MENU, OnLoadDIFFaX, id=G2gd.wxID_LOADDIFFAX)
                        G2frame.dataFrame.Bind(wx.EVT_MENU, OnSimulate, id=G2gd.wxID_LAYERSIMULATE)
                        G2frame.dataFrame.Bind(wx.EVT_MENU, OnSeqSimulate, id=G2gd.wxID_SEQUENCESIMULATE)
                        if 'Wave Data' in pages:
                            pass
#                            G2frame.dataDisplay.DeletePage(pages.index('Wave Data'))
                        if 'MC/SA' in pages:
                            pass
#                            G2frame.dataDisplay.DeletePage(pages.index('MC/SA'))
                        if 'RB Models' in pages:
                            pass
#                            G2frame.dataDisplay.DeletePage(pages.index('RB Models'))
                        if 'Layers' not in pages:
                            if 'Layers' not in data:
                                data['Layers'] = {'Laue':'-1','Cell':[False,1.,1.,1.,90.,90.,90,1.],
                                    'Width':[[1.,1.],[False,False]],'Toler':0.01,'AtInfo':{},
                                    'Layers':[],'Stacking':[],'Transitions':[]}
                            G2frame.layerData = wx.ScrolledWindow(G2frame.dataDisplay)
                            G2frame.dataDisplay.InsertPage(3,G2frame.layerData,'Layers')
                            Id = wx.NewId()
                            TabSelectionIdDict[Id] = 'Layers'
                        wx.CallAfter(UpdateGeneral)
                    elif generalData['Type'] == 'magnetic':
                        SGData = generalData['SGData']
                        Nops = len(SGData['SGOps'])*len(SGData['SGCen'])
                        if SGData['SGInv']:
                            Nops *= 2
                        SGData['SpnFlp'] = Nops*[1,]
                    else:
                        if 'Wave Data' in pages:
                            G2frame.dataDisplay.DeletePage(pages.index('Wave Data'))
                        if 'MC/SA' not in pages:
                            G2frame.MCSA = wx.ScrolledWindow(G2frame.dataDisplay)
                            G2frame.dataDisplay.InsertPage(7,G2frame.MCSA,'MC/SA')
                            Id = wx.NewId()
                            TabSelectionIdDict[Id] = 'MC/SA'
                        wx.CallAfter(UpdateGeneral)
                else:
                    G2frame.ErrorDialog('Phase type change error','Can change phase type only if there are no atoms')
                    TypeTxt.SetValue(generalData['Type'])                
                
            def OnSpaceGroup(event):
                event.Skip()
                Flds = SGTxt.GetValue().split()
                #get rid of extra spaces between fields first
                for fld in Flds: fld = fld.strip()
                SpcGp = ' '.join(Flds)
                # try a lookup on the user-supplied name
                SpGrpNorm = G2spc.StandardizeSpcName(SpcGp)
                if SpGrpNorm:
                    SGErr,SGData = G2spc.SpcGroup(SpGrpNorm)
                else:
                    SGErr,SGData = G2spc.SpcGroup(SpcGp)
                if SGErr:
                    text = [G2spc.SGErrors(SGErr)+'\nSpace Group set to previous']
                    SGTxt.SetValue(generalData['SGData']['SpGrp'])
                    msg = 'Space Group Error'
                    Style = wx.ICON_EXCLAMATION
                    Text = '\n'.join(text)
                    wx.MessageBox(Text,caption=msg,style=Style)
                else:
                    text,table = G2spc.SGPrint(SGData)
                    generalData['SGData'] = SGData
                    SGTxt.SetValue(generalData['SGData']['SpGrp'])
                    msg = 'Space Group Information'
                    G2gd.SGMessageBox(General,msg,text,table).Show()
                if generalData['Type'] == 'magnetic':
                    Nops = len(SGData['SGOps'])*len(SGData['SGCen'])
                    if SGData['SGInv']:
                        Nops *= 2
                    SGData['SpnFlp'] = Nops*[1,]
                if generalData['Modulated']:
                    generalData['SuperSg'] = SetDefaultSSsymbol()
                    generalData['SSGData'] = G2spc.SSpcGroup(generalData['SGData'],generalData['SuperSg'])[1]
                Atoms = data['Atoms']
                cx,ct,cs,cia = generalData['AtomPtrs']
                for atom in Atoms:
                    XYZ = atom[cx:cx+3]
                    Sytsym,Mult = G2spc.SytSym(XYZ,SGData)[:2]
                    atom[cs] = Sytsym
                    atom[cs+1] = Mult
                NShkl = len(G2spc.MustrainNames(SGData))
                NDij = len(G2spc.HStrainNames(SGData))
                UseList = data['Histograms']
                for hist in UseList:
                    UseList[hist]['Mustrain'][4:6] = [NShkl*[0.01,],NShkl*[False,]]
                    UseList[hist]['HStrain'] = [NDij*[0.0,],NDij*[False,]]
                wx.CallAfter(UpdateGeneral)
                
            def OnModulated(event):
                if not len(generalData['AtomTypes']):             #can change only if no atoms!
                    pages = [G2frame.dataDisplay.GetPageText(PageNum) for PageNum in range(G2frame.dataDisplay.GetPageCount())]
                    if generalData['Type'] in ['nuclear','magnetic']:
                        generalData['Modulated'] = modulated.GetValue()
                        if generalData['Modulated']:
                            if 'SuperSg' not in generalData:
                                generalData['SuperSg'] = SetDefaultSSsymbol()
                            generalData['SSGData'] = G2spc.SSpcGroup(generalData['SGData'],generalData['SuperSg'])[1]
                            if 'Super' not in generalData:
                                generalData['Super'] = 1
                                generalData['SuperVec'] = [[0,0,.1],False,4]
                                generalData['SSGData'] = {}
                            if '4DmapData' not in generalData:
                                generalData['4DmapData'] = mapDefault.copy()
                                generalData['4DmapData'].update({'MapType':'Fobs'})
                            if 'MC/SA' in pages:
                                pass
    #                            G2frame.dataDisplay.DeletePage(pages.index('MC/SA'))   #this crashes!!
                            if 'Layers' in pages:
                                pass
    #                            G2frame.dataDisplay.DeletePage(pages.index('Layers'))
                            if 'Wave Data' not in pages:
                                G2frame.waveData = wx.ScrolledWindow(G2frame.dataDisplay)
                                G2frame.dataDisplay.InsertPage(3,G2frame.waveData,'Wave Data')
                                Id = wx.NewId()
                                TabSelectionIdDict[Id] = 'Wave Data'
                        else:
                            if 'Wave Data' in pages:
                                G2frame.dataDisplay.DeletePage(pages.index('Wave Data'))
                        wx.CallAfter(UpdateGeneral)
                else:
                    G2frame.ErrorDialog('Modulation type change error','Can change modulation only if there are no atoms')
                    modulated.SetValue(generalData['Modulated'])                
                
            nameSizer = wx.BoxSizer(wx.HORIZONTAL)
            nameSizer.Add(wx.StaticText(General,-1,' Phase name: '),0,WACV)
            NameTxt = wx.TextCtrl(General,-1,value=generalData['Name'],style=wx.TE_PROCESS_ENTER)
            NameTxt.Bind(wx.EVT_TEXT_ENTER,OnPhaseName)
            NameTxt.Bind(wx.EVT_KILL_FOCUS,OnPhaseName)
            nameSizer.Add(NameTxt,0,WACV)
            nameSizer.Add(wx.StaticText(General,-1,'  Phase type: '),0,WACV)
            TypeTxt = wx.ComboBox(General,-1,value=generalData['Type'],choices=phaseTypes,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            TypeTxt.Bind(wx.EVT_COMBOBOX, OnPhaseType)
            nameSizer.Add(TypeTxt,0,WACV)
            nameSizer.Add(wx.StaticText(General,-1,'  Space group: '),0,WACV)
            SGTxt = wx.TextCtrl(General,-1,value=generalData['SGData']['SpGrp'],style=wx.TE_PROCESS_ENTER)
            SGTxt.Bind(wx.EVT_TEXT_ENTER,OnSpaceGroup)
            nameSizer.Add(SGTxt,0,WACV)
            if generalData['Type'] in ['nuclear','magnetic']:
                modulated = wx.CheckBox(General,label='Modulated? ')
                modulated.SetValue(generalData['Modulated'])
                modulated.Bind(wx.EVT_CHECKBOX,OnModulated)
                nameSizer.Add(modulated,0,WACV)           
            return nameSizer
            
        def CellSizer():
            
            cellGUIlist = [[['m3','m3m'],4,zip([" Unit cell: a = "," Vol = "],["%.5f","%.3f"],[True,False],[0,0])],
            [['3R','3mR'],6,zip([" a = "," alpha = "," Vol = "],["%.5f","%.3f","%.3f"],[True,True,False],[0,3,0])],
            [['3','3m1','31m','6/m','6/mmm','4/m','4/mmm'],6,zip([" a = "," c = "," Vol = "],["%.5f","%.5f","%.3f"],[True,True,False],[0,2,0])],
            [['mmm'],8,zip([" a = "," b = "," c = "," Vol = "],["%.5f","%.5f","%.5f","%.3f"],
                [True,True,True,False],[0,1,2,0])],
            [['2/m'+'a'],10,zip([" a = "," b = "," c = "," alpha = "," Vol = "],
                ["%.5f","%.5f","%.5f","%.3f","%.3f"],[True,True,True,True,False],[0,1,2,3,0])],
            [['2/m'+'b'],10,zip([" a = "," b = "," c = "," beta = "," Vol = "],
                ["%.5f","%.5f","%.5f","%.3f","%.3f"],[True,True,True,True,False],[0,1,2,4,0])],
            [['2/m'+'c'],10,zip([" a = "," b = "," c = "," gamma = "," Vol = "],
                ["%.5f","%.5f","%.5f","%.3f","%.3f"],[True,True,True,True,False],[0,1,2,5,0])],
            [['-1'],8,zip([" a = "," b = "," c = "," Vol = "," alpha = "," beta = "," gamma = "],
                ["%.5f","%.5f","%.5f","%.3f","%.3f","%.3f","%.3f"],
                [True,True,True,False,True,True,True],[0,1,2,0,3,4,5])]]
                
            def OnCellRef(event):
                generalData['Cell'][0] = cellRef.GetValue()
                
            def OnCellChange(event):
                event.Skip()
                SGData = generalData['SGData']
                laue = SGData['SGLaue']
                if laue == '2/m':
                    laue += SGData['SGUniq']
                cell = generalData['Cell']
                Obj = event.GetEventObject()
                ObjId = cellList.index(Obj.GetId())
                try:
                    value = max(1.0,float(Obj.GetValue()))
                except ValueError:
                    if ObjId < 3:               #bad cell edge - reset
                        value = cell[ObjId+1]
                    else:                       #bad angle
                        value = 90.
                if laue in ['m3','m3m']:
                    cell[1] = cell[2] = cell[3] = value
                    cell[4] = cell[5] = cell[6] = 90.0
                    Obj.SetValue("%.5f"%(cell[1]))
                elif laue in ['3R','3mR']:
                    if ObjId == 0:
                        cell[1] = cell[2] = cell[3] = value
                        Obj.SetValue("%.5f"%(cell[1]))
                    else:
                        cell[4] = cell[5] = cell[6] = value
                        Obj.SetValue("%.5f"%(cell[4]))
                elif laue in ['3','3m1','31m','6/m','6/mmm','4/m','4/mmm']:                    
                    cell[4] = cell[5] = 90.
                    cell[6] = 120.
                    if laue in ['4/m','4/mmm']:
                        cell[6] = 90.
                    if ObjId == 0:
                        cell[1] = cell[2] = value
                        Obj.SetValue("%.5f"%(cell[1]))
                    else:
                        cell[3] = value
                        Obj.SetValue("%.5f"%(cell[3]))
                elif laue in ['mmm']:
                    cell[ObjId+1] = value
                    cell[4] = cell[5] = cell[6] = 90.
                    Obj.SetValue("%.5f"%(cell[ObjId+1]))
                elif laue in ['2/m'+'a']:
                    cell[5] = cell[6] = 90.
                    if ObjId != 3:
                        cell[ObjId+1] = value
                        Obj.SetValue("%.5f"%(cell[ObjId+1]))
                    else:
                        cell[4] = value
                        Obj.SetValue("%.3f"%(cell[4]))
                elif laue in ['2/m'+'b']:
                    cell[4] = cell[6] = 90.
                    if ObjId != 3:
                        cell[ObjId+1] = value
                        Obj.SetValue("%.5f"%(cell[ObjId+1]))
                    else:
                        cell[5] = value
                        Obj.SetValue("%.3f"%(cell[5]))
                elif laue in ['2/m'+'c']:
                    cell[4] = cell[5] = 90.
                    if ObjId != 3:
                        cell[ObjId+1] = value
                        Obj.SetValue("%.5f"%(cell[ObjId+1]))
                    else:
                        cell[6] = value
                        Obj.SetValue("%.3f"%(cell[6]))
                else:
                    cell[ObjId+1] = value
                    if ObjId < 3:
                        Obj.SetValue("%.5f"%(cell[1+ObjId]))
                    else:
                        Obj.SetValue("%.3f"%(cell[1+ObjId]))                        
                cell[7] = G2lat.calc_V(G2lat.cell2A(cell[1:7]))
                volVal.SetValue("%.3f"%(cell[7]))
                density,mattCoeff = G2mth.getDensity(generalData)
                if denSizer:
                    denSizer[1].SetValue('%.3f'%(density))
                    if denSizer[2]:
                        denSizer[2].SetValue('%.3f'%(mattCoeff))
            
            cell = generalData['Cell']
            laue = generalData['SGData']['SGLaue']
            if laue == '2/m':
                laue += generalData['SGData']['SGUniq']
            for cellGUI in cellGUIlist:
                if laue in cellGUI[0]:
                    useGUI = cellGUI
            cellSizer = wx.FlexGridSizer(0,useGUI[1]+1,5,5)
            if PWDR:
                cellRef = wx.CheckBox(General,-1,label='Refine unit cell:')
                cellSizer.Add(cellRef,0,WACV)
                cellRef.Bind(wx.EVT_CHECKBOX, OnCellRef)
                cellRef.SetValue(cell[0])
            cellList = []
            for txt,fmt,ifEdit,Id in useGUI[2]:
                cellSizer.Add(wx.StaticText(General,label=txt),0,WACV)
                if ifEdit:          #a,b,c,etc.
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                    cellVal = wx.TextCtrl(General,value=(fmt%(cell[Id+1])),
                        style=wx.TE_PROCESS_ENTER)
                    cellVal.Bind(wx.EVT_TEXT_ENTER,OnCellChange)        
                    cellVal.Bind(wx.EVT_KILL_FOCUS,OnCellChange)
                    cellSizer.Add(cellVal,0,WACV)
                    cellList.append(cellVal.GetId())
                else:               #volume
                    volVal = wx.TextCtrl(General,value=(fmt%(cell[7])),style=wx.TE_READONLY)
                    volVal.SetBackgroundColour(VERY_LIGHT_GREY)
                    cellSizer.Add(volVal,0,WACV)
            return cellSizer
            
        def ElemSizer():
            
            def OnIsotope(event):
                Obj = event.GetEventObject()
                item = Indx[Obj.GetId()]
                isotope = Obj.GetValue()
                nCols = len(generalData['AtomTypes'])+1
                data['General']['Isotope'][item] = isotope
                indx = generalData['AtomTypes'].index(item)
                wt = generalData['Isotopes'][item][isotope]['Mass']
                elemSizer.GetChildren()[indx+3*nCols+1].Window.SetValue('%.3f'%(wt))    #tricky
                data['General']['AtomMass'][indx] = wt
                density,mattCoeff = G2mth.getDensity(generalData)
                denSizer[1].SetValue('%.3f'%(density))
                if denSizer[2]:
                    denSizer[2].SetValue('%.3f'%(mattCoeff))
                    
            elemSizer = wx.FlexGridSizer(0,len(generalData['AtomTypes'])+1,1,1)
            elemSizer.Add(wx.StaticText(General,label=' Elements'),0,WACV)
            for elem in generalData['AtomTypes']:
                typTxt = wx.TextCtrl(General,value=elem,style=wx.TE_READONLY)
                typTxt.SetBackgroundColour(VERY_LIGHT_GREY)
                elemSizer.Add(typTxt,0,WACV)
            elemSizer.Add(wx.StaticText(General,label=' Isotope'),0,WACV)
            for elem in generalData['AtomTypes']:
                choices = generalData['Isotopes'][elem].keys()
                isoSel = wx.ComboBox(General,-1,value=generalData['Isotope'][elem],choices=choices,
                    style=wx.CB_READONLY|wx.CB_DROPDOWN)
                isoSel.Bind(wx.EVT_COMBOBOX,OnIsotope)
                Indx[isoSel.GetId()] = elem
                elemSizer.Add(isoSel,1,WACV|wx.EXPAND)
            elemSizer.Add(wx.StaticText(General,label=' No. per cell'),0,WACV)
            for elem in generalData['AtomTypes']:
                numbTxt = wx.TextCtrl(General,value='%.1f'%(generalData['NoAtoms'][elem]),
                    style=wx.TE_READONLY)
                numbTxt.SetBackgroundColour(VERY_LIGHT_GREY)
                elemSizer.Add(numbTxt,0,WACV)
            elemSizer.Add(wx.StaticText(General,label=' Atom weight'),0,WACV)
            for wt in generalData['AtomMass']:
                wtTxt = wx.TextCtrl(General,value='%.3f'%(wt),style=wx.TE_READONLY)
                wtTxt.SetBackgroundColour(VERY_LIGHT_GREY)
                elemSizer.Add(wtTxt,0,WACV)
            elemSizer.Add(wx.StaticText(General,label=' Bond radii'),0,WACV)
            for rad in generalData['BondRadii']:
                bondRadii = wx.TextCtrl(General,value='%.2f'%(rad),style=wx.TE_READONLY)
                bondRadii.SetBackgroundColour(VERY_LIGHT_GREY)
                elemSizer.Add(bondRadii,0,WACV)
            elemSizer.Add(wx.StaticText(General,label=' Angle radii'),0,WACV)
            for rad in generalData['AngleRadii']:
                elemTxt = wx.TextCtrl(General,value='%.2f'%(rad),style=wx.TE_READONLY)
                elemTxt.SetBackgroundColour(VERY_LIGHT_GREY)
                elemSizer.Add(elemTxt,0,WACV)
            elemSizer.Add(wx.StaticText(General,label=' van der Waals radii'),0,WACV)
            for rad in generalData['vdWRadii']:
                elemTxt = wx.TextCtrl(General,value='%.2f'%(rad),style=wx.TE_READONLY)
                elemTxt.SetBackgroundColour(VERY_LIGHT_GREY)
                elemSizer.Add(elemTxt,0,WACV)
            elemSizer.Add(wx.StaticText(General,label=' Default color'),0,WACV)
            for R,G,B in generalData['Color']:
                colorTxt = wx.TextCtrl(General,value='',style=wx.TE_READONLY)
                colorTxt.SetBackgroundColour(wx.Colour(R,G,B))
                elemSizer.Add(colorTxt,0,WACV)
            if generalData['Type'] == 'magnetic':
                elemSizer.Add(wx.StaticText(General,label=' Lande g factor: '),0,WACV)
                for ig,elem in enumerate(generalData['AtomTypes']):
                    gfac = generalData['Lande g'][ig]
                    if gfac == None:
                        elemSizer.Add((5,0),)
                    else:
                        gfacTxt = G2G.ValidatedTxtCtrl(General,generalData['Lande g'],ig,
                            min=0.5,max=3.0,nDig=(10,2),typeHint=float)
                        elemSizer.Add(gfacTxt,0,WACV)
            return elemSizer
        
        def DenSizer():
            
            generalData['Mass'] = G2mth.getMass(generalData)
            density,mattCoeff = G2mth.getDensity(generalData)
            denSizer = wx.BoxSizer(wx.HORIZONTAL)
            denSizer.Add(wx.StaticText(General,-1,' Density: '),0,WACV)
            denTxt = wx.TextCtrl(General,-1,'%.3f'%(density),style=wx.TE_READONLY)
            denTxt.SetBackgroundColour(VERY_LIGHT_GREY)
            denSizer.Add(denTxt,0,WACV)
            mattTxt = None        
            if generalData['Type'] == 'macromolecular' and generalData['Mass'] > 0.0:
                denSizer.Add(wx.StaticText(General,-1,' Matthews coeff.: '),
                    0,WACV)
                mattTxt = wx.TextCtrl(General,-1,'%.3f'%(mattCoeff),style=wx.TE_READONLY)
                mattTxt.SetBackgroundColour(VERY_LIGHT_GREY)
                denSizer.Add(mattTxt,0,WACV)
            return denSizer,denTxt,mattTxt
            
        def MagSizer():
            
            def OnSpinOp(event):
                Obj = event.GetEventObject()
                isym = Indx[Obj.GetId()]
                spCode = {'red':-1,'black':1}                    
                SGData['SGSpin'][isym] = spCode[Obj.GetValue()]
                G2spc.CheckSpin(isym,SGData)
                wx.CallAfter(UpdateGeneral)
                
            def OnShowSpins(event):
                showSpins.SetValue(False)
                msg = 'Magnetic spin operators for '+SGData['MagSpGrp']
                text,table = G2spc.SGPrint(SGData,AddInv=True)
                text[0] = ' Magnetic Space Group: '+SGData['MagSpGrp']
                text[3] = ' The magnetic lattice point group is '+SGData['MagPtGp']
                G2gd.SGMagSpinBox(General,msg,text,table,OprNames,SpnFlp).Show()
                
            def OnDminVal(event):
                event.Skip()
                try:
                    val = float(dminVal.GetValue())
                    if val > 0.7:
                        generalData['MagDmin'] = val
                except ValueError:
                    pass
                dminVal.SetValue("%.4f"%(generalData['MagDmin']))
                
            SGData = generalData['SGData']            
            Indx = {}
            MagSym = generalData['SGData']['SpGrp'].split()
            magSizer = wx.BoxSizer(wx.VERTICAL)
            magSizer.Add(wx.StaticText(General,label=' Magnetic spin operator selection:'),0,WACV)
            if not len(GenSym):
                magSizer.Add(wx.StaticText(General,label=' No spin inversion allowed'),0,WACV)
                return magSizer
            spinSizer = wx.BoxSizer(wx.HORIZONTAL)
            spinColor = ['black','red']
            spCode = {-1:'red',1:'black'}
            for isym,sym in enumerate(GenSym):
                spinSizer.Add(wx.StaticText(General,label=' %s: '%(sym.strip())),0,WACV)                
                spinOp = wx.ComboBox(General,value=spCode[SGData['SGSpin'][isym]],choices=spinColor,
                    style=wx.CB_READONLY|wx.CB_DROPDOWN)                
                Indx[spinOp.GetId()] = isym
                spinOp.Bind(wx.EVT_COMBOBOX,OnSpinOp)
                spinSizer.Add(spinOp,0,WACV)
            MagSym = G2spc.MagSGSym(SGData)
            SGData['MagSpGrp'] = MagSym
            OprNames,SpnFlp = G2spc.GenMagOps(SGData)
            SGData['OprNames'] = OprNames
            SGData['SpnFlp'] = SpnFlp
            spinSizer.Add(wx.StaticText(General,label=' Magnetic space group: %s  '%(MagSym)),0,WACV)
            showSpins = wx.CheckBox(General,label=' Show spins?')
            showSpins.Bind(wx.EVT_CHECKBOX,OnShowSpins)
            spinSizer.Add(showSpins,0,WACV)
            magSizer.Add(spinSizer)
            dminSizer = wx.BoxSizer(wx.HORIZONTAL)
            dminSizer.Add(wx.StaticText(General,label=' Magnetic reflection d-min: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            dminVal = wx.TextCtrl(General,value='%.4f'%(generalData['MagDmin']),style=wx.TE_PROCESS_ENTER)
            dminVal.Bind(wx.EVT_TEXT_ENTER,OnDminVal)        
            dminVal.Bind(wx.EVT_KILL_FOCUS,OnDminVal)
            dminSizer.Add(dminVal,0,WACV)
            magSizer.Add(dminSizer,0,WACV)
            return magSizer
            
        def PawleySizer():
            
            def OnPawleyRef(event):
                generalData['doPawley'] = pawlRef.GetValue()
            
            pawleySizer = wx.BoxSizer(wx.HORIZONTAL)
            pawleySizer.Add(wx.StaticText(General,label=' Pawley controls: '),0,WACV)
            pawlRef = wx.CheckBox(General,-1,label=' Do Pawley refinement?')
            pawlRef.SetValue(generalData['doPawley'])
            pawlRef.Bind(wx.EVT_CHECKBOX,OnPawleyRef)
            pawleySizer.Add(pawlRef,0,WACV)
            pawleySizer.Add(wx.StaticText(General,label=' Pawley dmin: '),0,WACV)
            pawlVal = G2G.ValidatedTxtCtrl(General,generalData,'Pawley dmin',
                min=0.25,max=20.,nDig=(10,5),typeHint=float)
            pawleySizer.Add(pawlVal,0,WACV)
            pawleySizer.Add(wx.StaticText(General,label=' Pawley neg. wt.: '),0,WACV)
            pawlNegWt = G2G.ValidatedTxtCtrl(General,generalData,'Pawley neg wt',
                min=0.,max=1.,nDig=(10,4),typeHint=float)
            pawleySizer.Add(pawlNegWt,0,WACV)
            return pawleySizer
            
        def ModulatedSizer(name):
            
            def OnSuperGp(event):   #for HKLF needs to reject SSgps not agreeing with modVec!
                event.Skip()
                SSymbol = superGp.GetValue()
                E,SSGData = G2spc.SSpcGroup(generalData['SGData'],SSymbol)
                if SSGData:
                    Vec = generalData['SuperVec'][0]     #(3+1) only
                    modSymb = SSGData['modSymb']
                    generalData['SuperVec'][0] = G2spc.SSGModCheck(Vec,modSymb)[0]
                    text,table = G2spc.SSGPrint(generalData['SGData'],SSGData)
                    generalData['SSGData'] = SSGData
                    generalData['SuperSg'] = SSymbol
                    msg = 'Superspace Group Information'
                    G2gd.SGMessageBox(General,msg,text,table).Show()
                else:
                    text = [E+'\nSuperspace Group set to previous']
                    superGp.SetValue(generalData['SuperSg'])
                    msg = 'Superspace Group Error'
                    Style = wx.ICON_EXCLAMATION
                    Text = '\n'.join(text)
                    wx.MessageBox(Text,caption=msg,style=Style)
                wx.CallAfter(UpdateGeneral)                
            
            def OnVec(event):
                event.Skip()
                Obj = event.GetEventObject()
                ind = Indx[Obj.GetId()]
                val = Obj.GetValue()
                try:
                    val = min(2.0,max(-1.0,float(val)))
                except ValueError:
                    val = generalData['SuperVec'][0][ind]
                generalData['SuperVec'][0][ind] = val
                Obj.SetValue('%.4f'%(generalData['SuperVec'][0][ind])) 
                
            def OnVecRef(event):
                generalData['SuperVec'][1] = Ref.GetValue()
                
            def OnMax(event):
                generalData['SuperVec'][2] = int(Max.GetValue())
            
            Indx = {}
            ssSizer = wx.BoxSizer(wx.VERTICAL)
            modSizer = wx.BoxSizer(wx.HORIZONTAL)
            modSizer.Add(wx.StaticText(General,label=' '+name.capitalize()+' structure controls: '),0,WACV)
            modSizer.Add(wx.StaticText(General,label=' Superspace group: '+generalData['SGData']['SpGrp']),0,WACV)
            SSChoice = G2spc.ssdict.get(generalData['SGData']['SpGrp'],[])
            if SSChoice:
                superGp = wx.ComboBox(General,value=generalData['SuperSg'],choices=SSChoice,style=wx.CB_DROPDOWN|wx.TE_PROCESS_ENTER)
                superGp.Bind(wx.EVT_TEXT_ENTER,OnSuperGp)
                superGp.Bind(wx.EVT_COMBOBOX,OnSuperGp)
            else:   #nonstandard space group symbol not in my dictionary
                superGp = wx.TextCtrl(General,value=generalData['SuperSg'],style=wx.TE_PROCESS_ENTER)
                superGp.Bind(wx.EVT_TEXT_ENTER,OnSuperGp)                        
            modSizer.Add(superGp,0,WACV)
            if PWDR:
                modSizer.Add(wx.StaticText(General,label=' Max index: '),0,WACV)
                indChoice = ['1','2','3','4','5','6','7']
                Max = wx.ComboBox(General,-1,value='%d'%(generalData['SuperVec'][2]),choices=indChoice,
                    style=wx.CB_READONLY|wx.CB_DROPDOWN)
                Max.Bind(wx.EVT_COMBOBOX,OnMax)        
                modSizer.Add(Max,0,WACV)
            ssSizer.Add(modSizer,0,WACV)
            vecSizer = wx.FlexGridSizer(1,5,5,5)
            vecSizer.Add(wx.StaticText(General,label=' Modulation vector: '),0,WACV)
            modS = G2spc.splitSSsym(generalData['SuperSg'])[0]
            generalData['SuperVec'][0],ifShow = G2spc.SSGModCheck(generalData['SuperVec'][0],modS)
            for i,[val,show] in enumerate(zip(generalData['SuperVec'][0],ifShow)):
                if show:
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                    modVal = wx.TextCtrl(General,value=('%.4f'%(val)),
                        size=wx.Size(50,20),style=wx.TE_PROCESS_ENTER)
                    modVal.Bind(wx.EVT_TEXT_ENTER,OnVec)        
                    modVal.Bind(wx.EVT_KILL_FOCUS,OnVec)
                    vecSizer.Add(modVal,0,WACV)
                    Indx[modVal.GetId()] = i
                else:
                    modVal = wx.TextCtrl(General,value=('%.3f'%(val)),
                        size=wx.Size(50,20),style=wx.TE_READONLY)
                    modVal.SetBackgroundColour(VERY_LIGHT_GREY)
                    vecSizer.Add(modVal,0,WACV)
            if PWDR:
                Ref = wx.CheckBox(General,label='Refine?')
                Ref.SetValue(generalData['SuperVec'][1])
                Ref.Bind(wx.EVT_CHECKBOX, OnVecRef)
                vecSizer.Add(Ref,0,WACV)
            ssSizer.Add(vecSizer)
            return ssSizer
            
        def MapSizer():
            
            def OnMapType(event):
                Map['MapType'] = mapType.GetValue()
                
            def OnRefList(event):
                dlg = G2G.G2MultiChoiceDialog(G2frame, 'Select reflection sets to use',
                    'Use data',refsList)
                try:
                    if dlg.ShowModal() == wx.ID_OK:
                        Map['RefList'] = [refsList[i] for i in dlg.GetSelections()]
                    else:
                        return
                finally:
                    dlg.Destroy()
                wx.CallAfter(UpdateGeneral,General.GetScrollPos(wx.VERTICAL))                
                
            def OnResVal(event):
                event.Skip()
                try:
                    res = float(mapRes.GetValue())
                    if 0.25 <= res <= 20.:
                        Map['Resolution'] = res
                except ValueError:
                    pass
                mapRes.SetValue("%.2f"%(Map['Resolution']))          #reset in case of error
            
            def OnCutOff(event):
                event.Skip()
                try:
                    res = float(cutOff.GetValue())
                    if 1.0 <= res <= 100.:
                        Map['cutOff'] = res
                except ValueError:
                    pass
                cutOff.SetValue("%.1f"%(Map['cutOff']))          #reset in case of error
            
            #patch
            if 'cutOff' not in Map:
                Map['cutOff'] = 100.0
            mapTypes = ['Fobs','Fcalc','delt-F','2*Fo-Fc','Omit','2Fo-Fc Omit','Patterson']
            refsList = data['Histograms'].keys()
            if not generalData['AtomTypes']:
                 mapTypes = ['Patterson',]
                 Map['MapType'] = 'Patterson'
            mapSizer = wx.BoxSizer(wx.VERTICAL)
            lineSizer = wx.BoxSizer(wx.HORIZONTAL)
            lineSizer.Add(wx.StaticText(General,label=' Fourier map controls: Map type: '),0,WACV)
            mapType = wx.ComboBox(General,value=Map['MapType'],choices=mapTypes,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            mapType.Bind(wx.EVT_COMBOBOX,OnMapType)
            lineSizer.Add(mapType,0,WACV)
            lineSizer.Add(wx.StaticText(General,label=' Reflection sets: '),0,WACV)
            if 'list' not in str(type(Map['RefList'])):     #patch
                Map['RefList'] = [Map['RefList'],]
            lineSizer.Add(wx.ComboBox(General,value=Map['RefList'][0],choices=Map['RefList'],
                style=wx.CB_DROPDOWN|wx.CB_READONLY),0,WACV)
            refList = wx.Button(General,label='Select reflection sets')
            refList.Bind(wx.EVT_BUTTON,OnRefList)
            lineSizer.Add(refList,0,WACV)
            mapSizer.Add(lineSizer,0,WACV)
            line2Sizer = wx.BoxSizer(wx.HORIZONTAL)
            line2Sizer.Add(wx.StaticText(General,label=' Resolution: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            mapRes =  wx.TextCtrl(General,value='%.2f'%(Map['Resolution']),style=wx.TE_PROCESS_ENTER)
            mapRes.Bind(wx.EVT_TEXT_ENTER,OnResVal)        
            mapRes.Bind(wx.EVT_KILL_FOCUS,OnResVal)
            line2Sizer.Add(mapRes,0,WACV)
            line2Sizer.Add(wx.StaticText(General,label=' Peak cutoff %: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            cutOff =  wx.TextCtrl(General,value='%.1f'%(Map['cutOff']),style=wx.TE_PROCESS_ENTER)
            cutOff.Bind(wx.EVT_TEXT_ENTER,OnCutOff)        
            cutOff.Bind(wx.EVT_KILL_FOCUS,OnCutOff)
            line2Sizer.Add(cutOff,0,WACV)
            mapSizer.Add(line2Sizer,0,WACV)
            return mapSizer
                
        def FlipSizer():
            if 'k-Max' not in Flip: Flip['k-Max'] = 20.
            
            def OnRefList(event):
                dlg = G2G.G2MultiChoiceDialog(G2frame, 'Select reflection sets to use',
                    'Use data',refsList)
                try:
                    if dlg.ShowModal() == wx.ID_OK:
                        Flip['RefList'] = [refsList[i] for i in dlg.GetSelections()]
                    else:
                        return
                finally:
                    dlg.Destroy()
                wx.CallAfter(UpdateGeneral,General.GetScrollPos(wx.VERTICAL))                
                
            def OnNormElem(event):
                PE = G2elemGUI.PickElement(G2frame,ifNone=True)
                if PE.ShowModal() == wx.ID_OK:
                    Flip['Norm element'] = PE.Elem.strip()
                    normElem.SetLabel(Flip['Norm element'])
                PE.Destroy()                
                
            def OnResVal(event):
                event.Skip()
                try:
                    res = float(flipRes.GetValue())
                    if 0.25 <= res <= 20.:
                        Flip['Resolution'] = res
                except ValueError:
                    pass
                flipRes.SetValue("%.2f"%(Flip['Resolution']))          #reset in case of error
            
            def OnkFactor(event):
                event.Skip()
                try:
                    res = float(kFactor.GetValue())
                    if 0.1 <= res <= 1.2:
                        Flip['k-factor'] = res
                except ValueError:
                    pass
                kFactor.SetValue("%.3f"%(Flip['k-factor']))          #reset in case of error
            
            def OnkMax(event):
                event.Skip()
                try:
                    res = float(kMax.GetValue())
                    if res >= 10.:
                        Flip['k-Max'] = res
                except ValueError:
                    pass
                kMax.SetValue("%.1f"%(Flip['k-Max']))          #reset in case of error
                
            def OnTestHKL(event):
                event.Skip()
                Obj = event.GetEventObject()
                name = Obj.GetName()
                try:
                    vals = Obj.GetValue().split()
                    id = int(name.split('hkl')[1])
                    HKL = [int(val) for val in vals]
                    Flip['testHKL'][id] = HKL
                except ValueError:
                    HKL = Flip['testHKL'][id]
                Obj.SetValue('%3d %3d %3d'%(HKL[0],HKL[1],HKL[2]))

            refsList = data['Histograms'].keys()
            flipSizer = wx.BoxSizer(wx.VERTICAL)
            lineSizer = wx.BoxSizer(wx.HORIZONTAL)
            lineSizer.Add(wx.StaticText(General,label=' Charge flip controls: Reflection sets: '),0,WACV)
            if 'list' not in str(type(Flip['RefList'])):     #patch
                Flip['RefList'] = [Flip['RefList'],]
            lineSizer.Add(wx.ComboBox(General,value=Flip['RefList'][0],choices=Flip['RefList'],
                style=wx.CB_DROPDOWN|wx.CB_READONLY),0,WACV)
            refList = wx.Button(General,label='Select reflection sets')
            refList.Bind(wx.EVT_BUTTON,OnRefList)
            lineSizer.Add(refList,0,WACV)
            lineSizer.Add(wx.StaticText(General,label=' Normalizing element: '),0,WACV)
            normElem = wx.Button(General,label=Flip['Norm element'],style=wx.TE_READONLY)
            normElem.Bind(wx.EVT_BUTTON,OnNormElem)
            lineSizer.Add(normElem,0,WACV)
            flipSizer.Add(lineSizer,0,WACV)
            line2Sizer = wx.BoxSizer(wx.HORIZONTAL)
            line2Sizer.Add(wx.StaticText(General,label=' Resolution: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            flipRes =  wx.TextCtrl(General,value='%.2f'%(Flip['Resolution']),style=wx.TE_PROCESS_ENTER)
            flipRes.Bind(wx.EVT_TEXT_ENTER,OnResVal)        
            flipRes.Bind(wx.EVT_KILL_FOCUS,OnResVal)
            line2Sizer.Add(flipRes,0,WACV)
            line2Sizer.Add(wx.StaticText(General,label=' k-Factor (0.1-1.2): '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            kFactor =  wx.TextCtrl(General,value='%.3f'%(Flip['k-factor']),style=wx.TE_PROCESS_ENTER)
            kFactor.Bind(wx.EVT_TEXT_ENTER,OnkFactor)        
            kFactor.Bind(wx.EVT_KILL_FOCUS,OnkFactor)
            line2Sizer.Add(kFactor,0,WACV)
            line2Sizer.Add(wx.StaticText(General,label=' k-Max (>=10.0): '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            kMax = wx.TextCtrl(General,value='%.1f'%(Flip['k-Max']),style=wx.TE_PROCESS_ENTER)
            kMax.Bind(wx.EVT_TEXT_ENTER,OnkMax)        
            kMax.Bind(wx.EVT_KILL_FOCUS,OnkMax)
            line2Sizer.Add(kMax,0,WACV)
            flipSizer.Add(line2Sizer,0,WACV)
            line3Sizer = wx.BoxSizer(wx.HORIZONTAL)
            line3Sizer.Add(wx.StaticText(General,label=' Test HKLs:'),0,WACV)
            if len(Flip['testHKL']) < 5:
                Flip['testHKL'] += [[1,1,1],[0,2,0],[1,2,3]]
            HKL = Flip['testHKL']
            for ih,hkl in enumerate(Flip['testHKL']):                
                hkl = wx.TextCtrl(General,value='%3d %3d %3d'%(HKL[ih][0],HKL[ih][1],HKL[ih][2]),
                    style=wx.TE_PROCESS_ENTER,name='hkl%d'%(ih))
                hkl.Bind(wx.EVT_TEXT_ENTER,OnTestHKL)        
                hkl.Bind(wx.EVT_KILL_FOCUS,OnTestHKL)
                line3Sizer.Add(hkl,0,WACV)
            flipSizer.Add(line3Sizer)
            return flipSizer
            
        def MCSASizer():
            
            def OnRefList(event):
                MCSAdata['Data source'] = refList.GetValue()
            
            def OnDmin(event):
                event.Skip()
                try:
                    val = float(dmin.GetValue())
                    if 1.0 <= val < 5.0:
                        MCSAdata['dmin'] = val
                except ValueError:
                    pass
                dmin.SetValue("%.3f"%(MCSAdata['dmin']))          #reset in case of error
                MCSAdata['newDmin'] = True

            def OnCycles(event):
                MCSAdata['Cycles'] = int(cycles.GetValue())
                               
            def OnAlist(event):
                MCSAdata['Algorithm'] = Alist.GetValue()
                wx.CallAfter(UpdateGeneral,General.GetScrollPos(wx.VERTICAL))
                
            def OnSlope(event):
                event.Skip()
                try:
                    val = float(slope.GetValue())
                    if .25 <= val < 1.0:
                        MCSAdata['log slope'] = val
                except ValueError:
                    pass
                slope.SetValue("%.3f"%(MCSAdata['log slope']))          #reset in case of error                
            
            def OnAjump(event):
                event.Skip()
                Obj = event.GetEventObject()
                name,ind = Indx[Obj.GetId()]
                try:
                    val = float(Obj.GetValue())
                    if .0 <= val <= 1.0:
                        MCSAdata[name][ind] = val
                except ValueError:
                    pass
                Obj.SetValue("%.3f"%(MCSAdata[name][ind]))
                
            def OnRanStart(event):
                MCSAdata['ranStart'] = ranStart.GetValue()
                
#            def OnAutoRan(event):
#                MCSAdata['autoRan'] = autoRan.GetValue()
                
            def OnRanRange(event):
                event.Skip()
                try:
                    val = float(ranRange.GetValue())/100
                    if 0.01 <= val <= 0.99:
                        MCSAdata['ranRange'] = val
                except ValueError:
                    pass
                ranRange.SetValue('%.1f'%(MCSAdata['ranRange']*100.))
            
            def OnAnneal(event):
                event.Skip()
                Obj = event.GetEventObject()
                ind,fmt = Indx[Obj.GetId()]
                if ind == 2:        #No. trials
                    try:
                        val = int(Obj.GetValue())
                        if 1 <= val:
                            MCSAdata['Annealing'][ind] = val
                    except ValueError:
                        Obj.SetValue(fmt%(MCSAdata['Annealing'][ind]))
                else:
                    try:
                        val = float(Obj.GetValue())
                        if .0 <= val:
                            MCSAdata['Annealing'][ind] = val
                        Obj.SetValue(fmt%(MCSAdata['Annealing'][ind]))
                    except ValueError:
                        MCSAdata['Annealing'][ind] = None                    
                        Obj.SetValue(str(MCSAdata['Annealing'][ind]))
                       
            refList = []
            if len(data['Pawley ref']):
                refList = ['Pawley reflections']
            for item in data['Histograms'].keys():
                if 'HKLF' in item or 'PWDR' in item:
                    refList.append(item)
            mcsaSizer = wx.BoxSizer(wx.VERTICAL)
            lineSizer = wx.BoxSizer(wx.HORIZONTAL)
            lineSizer.Add(wx.StaticText(General,label=' Monte Carlo/Simulated Annealing controls: Reflection set from: '),0,WACV)
            refList = wx.ComboBox(General,-1,value=MCSAdata['Data source'],choices=refList,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            refList.Bind(wx.EVT_COMBOBOX,OnRefList)
            lineSizer.Add(refList,0,WACV)
            lineSizer.Add(wx.StaticText(General,label=' d-min: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            dmin = wx.TextCtrl(General,-1,value='%.3f'%(MCSAdata['dmin']),style=wx.TE_PROCESS_ENTER)
            dmin.Bind(wx.EVT_TEXT_ENTER,OnDmin)        
            dmin.Bind(wx.EVT_KILL_FOCUS,OnDmin)
            lineSizer.Add(dmin,0,WACV)
            mcsaSizer.Add(lineSizer)
            mcsaSizer.Add((5,5),)
            line2Sizer = wx.BoxSizer(wx.HORIZONTAL)
            line2Sizer.Add(wx.StaticText(General,label=' MC/SA runs: '),0,WACV)
            Cchoice = ['1','2','4','8','16','32','64','128','256']
            cycles = wx.ComboBox(General,-1,value=str(MCSAdata.get('Cycles',1)),choices=Cchoice,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            cycles.Bind(wx.EVT_COMBOBOX,OnCycles)        
            line2Sizer.Add(cycles,0,WACV)
            line2Sizer.Add((5,0),)
            ranStart = wx.CheckBox(General,-1,label=' MC/SA Refine at ')
            ranStart.Bind(wx.EVT_CHECKBOX, OnRanStart)
            ranStart.SetValue(MCSAdata.get('ranStart',False))
            line2Sizer.Add(ranStart,0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            ranRange = wx.TextCtrl(General,-1,value='%.1f'%(MCSAdata.get('ranRange',0.10)*100),style=wx.TE_PROCESS_ENTER)
            ranRange.Bind(wx.EVT_TEXT_ENTER,OnRanRange)        
            ranRange.Bind(wx.EVT_KILL_FOCUS,OnRanRange)
            line2Sizer.Add(ranRange,0,WACV)
            line2Sizer.Add(wx.StaticText(General,label='% of ranges. '),0,WACV)
#            autoRan = wx.CheckBox(General,-1,label=' Do auto range reduction? ')
#            autoRan.Bind(wx.EVT_CHECKBOX, OnAutoRan)
#            autoRan.SetValue(MCSAdata.get('autoRan',False))
#            line2Sizer.Add(autoRan,0,WACV)
            mcsaSizer.Add(line2Sizer)
            mcsaSizer.Add((5,5),)
            line3Sizer = wx.BoxSizer(wx.HORIZONTAL)
            Achoice = ['log','fast']                #these work
#            Achoice = ['log','fast','cauchy','boltzmann']
            line3Sizer.Add(wx.StaticText(General,label=' MC/SA schedule: '),0,WACV)
            Alist = wx.ComboBox(General,-1,value=MCSAdata['Algorithm'],choices=Achoice,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            Alist.Bind(wx.EVT_COMBOBOX,OnAlist)
            line3Sizer.Add(Alist,0,WACV)
            if MCSAdata['Algorithm'] in ['fast','boltzmann','cauchy']:
                Names = [' A-jump: ',' B-jump: ']
                parms = 'Jump coeff'
                if MCSAdata['Algorithm'] in ['boltzmann','cauchy']:
                    Names = [' A-jump: ']
                elif 'fast' in MCSAdata['Algorithm']:
                    Names = [' quench: ',' m-factor: ',' n-factor: ']
                    parms = 'fast parms'
                for i,name in enumerate(Names):
                    line3Sizer.Add(wx.StaticText(General,label=name),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                    Ajump =  wx.TextCtrl(General,-1,value='%.3f'%(MCSAdata[parms][i]),style=wx.TE_PROCESS_ENTER)
                    Ajump.Bind(wx.EVT_TEXT_ENTER,OnAjump)        
                    Ajump.Bind(wx.EVT_KILL_FOCUS,OnAjump)
                    Indx[Ajump.GetId()] = [parms,i]
                    line3Sizer.Add(Ajump,0,WACV)
            elif 'log' in MCSAdata['Algorithm']:
                line3Sizer.Add(wx.StaticText(General,label=' slope: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                slope =  wx.TextCtrl(General,-1,value='%.3f'%(MCSAdata['log slope']),style=wx.TE_PROCESS_ENTER)
                slope.Bind(wx.EVT_TEXT_ENTER,OnSlope)        
                slope.Bind(wx.EVT_KILL_FOCUS,OnSlope)
                line3Sizer.Add(slope,0,WACV)
            mcsaSizer.Add(line3Sizer)
            mcsaSizer.Add((5,5),)
            line3Sizer = wx.BoxSizer(wx.HORIZONTAL)
            line3Sizer.Add(wx.StaticText(General,label=' Annealing schedule: '),0,WACV)
            names = [' Start temp: ',' Final temp: ',' No. trials: ']
            fmts = ['%.1f','%.5f','%d']
            for i,[name,fmt] in enumerate(zip(names,fmts)):
                if MCSAdata['Annealing'][i]:
                    text = fmt%(MCSAdata['Annealing'][i])
                else:
                    text = 'None'
                line3Sizer.Add(wx.StaticText(General,label=name),0,WACV)
                anneal =  wx.TextCtrl(General,-1,value=text,style=wx.TE_PROCESS_ENTER)
                anneal.Bind(wx.EVT_TEXT_ENTER,OnAnneal)        
                anneal.Bind(wx.EVT_KILL_FOCUS,OnAnneal)
                Indx[anneal.GetId()] = [i,fmt]
                line3Sizer.Add(anneal,0,WACV)
            mcsaSizer.Add(line3Sizer)            
            return mcsaSizer

        # UpdateGeneral execution continues here
        if General.GetSizer():
            General.GetSizer().Clear(True)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add((5,5),0)
        mainSizer.Add(NameSizer(),0)
        mainSizer.Add((5,5),0)        
        mainSizer.Add(CellSizer(),0)
        mainSizer.Add((5,5),0)
        
        Indx = {}
        denSizer = None
        if len(generalData['AtomTypes']):
            denSizer = DenSizer()
            mainSizer.Add(denSizer[0])
            mainSizer.Add((5,5),0)            
            mainSizer.Add(ElemSizer())
        G2G.HorizontalLine(mainSizer,General)
        
        if generalData['Type'] == 'magnetic':
            GenSym,GenFlg = G2spc.GetGenSym(generalData['SGData'])
            generalData['SGData']['GenSym'] = GenSym
            generalData['SGData']['GenFlg'] = GenFlg
            mainSizer.Add(MagSizer())
            G2G.HorizontalLine(mainSizer,General)

        if generalData['Modulated']:
            G2frame.dataFrame.GeneralCalc.Enable(G2gd.wxID_SINGLEMCSA,False)
            G2frame.dataFrame.GeneralCalc.Enable(G2gd.wxID_MULTIMCSA,False)
            G2frame.dataFrame.GeneralCalc.Enable(G2gd.wxID_4DCHARGEFLIP,True)
            mainSizer.Add(ModulatedSizer(generalData['Type']))
            G2G.HorizontalLine(mainSizer,General)
        else:
            G2frame.dataFrame.GeneralCalc.Enable(G2gd.wxID_SINGLEMCSA,True)
            G2frame.dataFrame.GeneralCalc.Enable(G2gd.wxID_MULTIMCSA,True)
            G2frame.dataFrame.GeneralCalc.Enable(G2gd.wxID_4DCHARGEFLIP,False)

        mainSizer.Add(PawleySizer())
        G2G.HorizontalLine(mainSizer,General)
        
        mainSizer.Add(MapSizer())
        G2G.HorizontalLine(mainSizer,General)
        
        mainSizer.Add(FlipSizer())
        if generalData['Type'] in ['nuclear','macromolecular','faulted',]:
            G2G.HorizontalLine(mainSizer,General)
            mainSizer.Add(MCSASizer())
        G2frame.dataFrame.SetStatusText('')
        SetPhaseWindow(G2frame.dataFrame,General,mainSizer,Scroll)
        
    def OnTransform(event):
        dlg = G2gd.TransformDialog(G2frame,data)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                newPhase,Trans,Vec,ifMag,ifConstr = dlg.GetSelection()
            else:
                return
        finally:
            dlg.Destroy()
        phaseName = newPhase['General']['Name']
        newPhase,atCodes = G2lat.TransformPhase(data,newPhase,Trans,Vec,ifMag)
        detTrans = np.abs(nl.det(Trans))

        generalData = newPhase['General']
        SGData = generalData['SGData']
        Atoms = newPhase['Atoms']
        if ifMag:
            dlg = G2gd.UseMagAtomDialog(G2frame,Atoms,atCodes)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    newPhase['Atoms'],atCodes = dlg.GetSelection()
            finally:
                dlg.Destroy()
            SGData['GenSym'],SGData['GenFlg'] = G2spc.GetGenSym(SGData)
            SGData['MagSpGrp'] = G2spc.MagSGSym(SGData)
            SGData['OprNames'],SGData['SpnFlp'] = G2spc.GenMagOps(SGData)
            generalData['Lande g'] = len(generalData['AtomTypes'])*[2.,]
            
        NShkl = len(G2spc.MustrainNames(SGData))
        NDij = len(G2spc.HStrainNames(SGData))
        UseList = newPhase['Histograms']
        for hist in UseList:
            UseList[hist]['Scale'] /= detTrans      #scale by 1/volume ratio
            UseList[hist]['Mustrain'][4:6] = [NShkl*[0.01,],NShkl*[False,]]
            UseList[hist]['HStrain'] = [NDij*[0.0,],NDij*[False,]]
        newPhase['General']['Map'] = mapDefault.copy()
        sub = G2frame.PatternTree.AppendItem(parent=
            G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Phases'),text=phaseName)
        G2frame.PatternTree.SetItemPyData(sub,newPhase)
        if ifMag and ifConstr:
            G2cnstG.MagConstraints(G2frame,data,newPhase,Trans,Vec,atCodes)     #data is old phase
        G2frame.PatternTree.SelectItem(sub)
        
################################################################################
#####  Atom routines
################################################################################

    def FillAtomsGrid(Atoms):
        '''Display the contents of the Atoms tab
        '''
        def RefreshAtomGrid(event):

            r,c =  event.GetRow(),event.GetCol()
            if r < 0 and c < 0:
                for row in range(Atoms.GetNumberRows()):
                    Atoms.SelectRow(row,True)                    
            if r < 0:                          #double click on col label! Change all atoms!
                sel = -1
                noSkip = True
                if Atoms.GetColLabelValue(c) == 'refine':
                    Type = generalData['Type']
                    if Type in ['nuclear','macromolecular','faulted',]:
                        choice = ['F - site fraction','X - coordinates','U - thermal parameters']
                    elif Type in ['magnetic',]:
                        choice = ['F - site fraction','X - coordinates','U - thermal parameters','M - magnetic moment']
                    dlg = wx.MultiChoiceDialog(G2frame,'Select','Refinement controls',choice)
                    if dlg.ShowModal() == wx.ID_OK:
                        sel = dlg.GetSelections()
                        parms = ''
                        for x in sel:
                            parms += choice[x][0]
                    dlg.Destroy()
                elif Atoms.GetColLabelValue(c) == 'I/A':
                    choice = ['Isotropic','Anisotropic']
                    dlg = wx.SingleChoiceDialog(G2frame,'Select','Thermal Motion',choice)
                    if dlg.ShowModal() == wx.ID_OK:
                        sel = dlg.GetSelection()
                        parms = choice[sel][0]
                    dlg.Destroy()
                elif Atoms.GetColLabelValue(c) == 'Type':
                    choice = generalData['AtomTypes']
                    dlg = wx.SingleChoiceDialog(G2frame,'Select','Atom types',choice)
                    if dlg.ShowModal() == wx.ID_OK:
                        sel = dlg.GetSelection()
                        parms = choice[sel]
                        noSkip = False
                        Atoms.ClearSelection()
                        for row in range(Atoms.GetNumberRows()):
                            if parms == atomData[row][c]:
                                Atoms.SelectRow(row,True)
                    dlg.Destroy()
                    SetupGeneral()
                elif Atoms.GetColLabelValue(c) == 'residue':
                    choice = []
                    for r in range(Atoms.GetNumberRows()):
                        if str(atomData[r][c]) not in choice:
                            choice.append(str(atomData[r][c]))
                    choice.sort()
                    dlg = wx.SingleChoiceDialog(G2frame,'Select','Residue',choice)
                    if dlg.ShowModal() == wx.ID_OK:
                        sel = dlg.GetSelection()
                        parms = choice[sel]
                        noSkip = False
                        Atoms.ClearSelection()
                        for row in range(Atoms.GetNumberRows()):
                            if parms == atomData[row][c]:
                                Atoms.SelectRow(row,True)
                    dlg.Destroy()
                elif Atoms.GetColLabelValue(c) == 'res no':
                    choice = []
                    for r in range(Atoms.GetNumberRows()):
                        if str(atomData[r][c]) not in choice:
                            choice.append(str(atomData[r][c]))
                    dlg = wx.SingleChoiceDialog(G2frame,'Select','Residue no.',choice)
                    if dlg.ShowModal() == wx.ID_OK:
                        sel = dlg.GetSelection()
                        parms = choice[sel]
                        noSkip = False
                        Atoms.ClearSelection()
                        for row in range(Atoms.GetNumberRows()):
                            if int(parms) == atomData[row][c]:
                                Atoms.SelectRow(row,True)
                    dlg.Destroy()
                elif Atoms.GetColLabelValue(c) == 'chain':
                    choice = []
                    for r in range(Atoms.GetNumberRows()):
                        if atomData[r][c] not in choice:
                            choice.append(atomData[r][c])
                    dlg = wx.SingleChoiceDialog(G2frame,'Select','Chain',choice)
                    if dlg.ShowModal() == wx.ID_OK:
                        sel = dlg.GetSelection()
                        parms = choice[sel]
                        noSkip = False
                        Atoms.ClearSelection()
                        for row in range(Atoms.GetNumberRows()):
                            if parms == atomData[row][c]:
                                Atoms.SelectRow(row,True)
                    dlg.Destroy()
                elif Atoms.GetColLabelValue(c) == 'Uiso':       #this needs to ask for value
                    pass                                        #& then change all 'I' atoms
                if sel >= 0 and noSkip:
                    ui = colLabels.index('U11')
                    us = colLabels.index('Uiso')
                    ss = colLabels.index('site sym')
                    for r in range(Atoms.GetNumberRows()):
                        ID = atomData[r][ui+6]
                        if parms != atomData[r][c] and Atoms.GetColLabelValue(c) == 'I/A':
                            if parms == 'A':                #'I' --> 'A'
                                Uiso = float(Atoms.GetCellValue(r,us))
                                sytsym = atomData[r][ss]
                                CSI = G2spc.GetCSuinel(sytsym)
                                atomData[r][ui:ui+6] = Uiso*np.array(CSI[3])
                                atomData[r][us] = 0.0
                                Atoms.SetCellStyle(r,us,VERY_LIGHT_GREY,True)
                                for i in range(6):
                                    ci = ui+i
                                    Atoms.SetCellStyle(r,ci,VERY_LIGHT_GREY,True)
                                    if CSI[2][i]:
                                        Atoms.SetCellStyle(r,ci,WHITE,False)
                            else:                           #'A' --> 'I'
                                Uij = atomData[r][ui:ui+6]
                                Uiso = (Uij[0]+Uij[1]+Uij[2])/3.0   
                                atomData[r][us] = Uiso
                                Atoms.SetCellStyle(r,us,WHITE,False)
                                for i in range(6):
                                    ci = ui+i
                                    atomData[r][ci] = 0.0
                                    Atoms.SetCellStyle(r,ci,VERY_LIGHT_GREY,True)
                        if not Atoms.IsReadOnly(r,c):
                            if Atoms.GetColLabelValue(c) == 'refine':
                                rbExcl = rbAtmDict.get(atomData[r][ui+6],'')
                                if rbExcl:
                                    for excl in rbExcl:
                                        atomData[r][c] = parms.replace(excl,'')
                                else:
                                    atomData[r][c] = parms
                            else: 
                                atomData[r][c] = parms
                        if 'Atoms' in data['Drawing']:
                            DrawAtomsReplaceByID(data['Drawing'],ui+6,atomData[r],ID)
                    wx.CallAfter(Paint)
                    
        def ChangeAtomCell(event):

            def chkUij(Uij,CSI): #needs to do something!!!
                return Uij

            r,c =  event.GetRow(),event.GetCol()
            if r >= 0 and c >= 0:
                ci = colLabels.index('I/A')
                ID = atomData[r][ci+8]
                if Atoms.GetColLabelValue(c) in ['x','y','z']:
                    ci = colLabels.index('x')
                    XYZ = atomData[r][ci:ci+3]
                    if None in XYZ:
                        XYZ = [0,0,0]
                    SScol = colLabels.index('site sym')
                    Mulcol = colLabels.index('mult')
                    E,SGData = G2spc.SpcGroup(generalData['SGData']['SpGrp'])
                    Sytsym,Mult = G2spc.SytSym(XYZ,SGData)[:2]
                    atomData[r][SScol] = Sytsym
                    atomData[r][Mulcol] = Mult
                    if atomData[r][colLabels.index('I/A')] == 'A':
                        ui = colLabels.index('U11')
                        CSI = G2spc.GetCSuinel(Sytsym)
                        atomData[r][ui:ui+6] = chkUij(atomData[r][ui:ui+6],Sytsym)
                        for i in range(6):
                            ci = i+ui
                            Atoms.SetCellStyle(r,ci,VERY_LIGHT_GREY,True)
                            if CSI[2][i]:
                                Atoms.SetCellStyle(r,ci,WHITE,False)
                    SetupGeneral()
                elif Atoms.GetColLabelValue(c) == 'Type':
                    AtomTypeSelect(event)
                elif Atoms.GetColLabelValue(c) == 'I/A':            #note use of text color to make it vanish!
                    if atomData[r][c] == 'I':
                        Uij = atomData[r][c+2:c+8]
                        atomData[r][c+1] = (Uij[0]+Uij[1]+Uij[2])/3.0
                        Atoms.SetCellStyle(r,c+1,WHITE,False)
                        Atoms.SetCellTextColour(r,c+1,BLACK)
                        for i in range(6):
                            ci = i+colLabels.index('U11')
                            Atoms.SetCellStyle(r,ci,VERY_LIGHT_GREY,True)
                            Atoms.SetCellTextColour(r,ci,VERY_LIGHT_GREY)
                            atomData[r][ci] = 0.0
                    else:
                        value = atomData[r][c+1]
                        CSI = G2spc.GetCSuinel(atomData[r][colLabels.index('site sym')])
                        atomData[r][c+1] =  0.0
                        Atoms.SetCellStyle(r,c+1,VERY_LIGHT_GREY,True)
                        Atoms.SetCellTextColour(r,c+1,VERY_LIGHT_GREY)
                        for i in range(6):
                            ci = i+colLabels.index('U11')
                            atomData[r][ci] = value*CSI[3][i]
                            Atoms.SetCellStyle(r,ci,VERY_LIGHT_GREY,True)
                            Atoms.SetCellTextColour(r,ci,BLACK)
                            if CSI[2][i]:
                                Atoms.SetCellStyle(r,ci,WHITE,False)
                elif Atoms.GetColLabelValue(c) in ['U11','U22','U33','U12','U13','U23']:
                    value = atomData[r][c]
                    CSI = G2spc.GetCSuinel(atomData[r][colLabels.index('site sym')])
                    iUij = CSI[0][c-colLabels.index('U11')]
                    for i in range(6):
                        if iUij == CSI[0][i]:
                            atomData[r][i+colLabels.index('U11')] = value*CSI[1][i]
                elif Atoms.GetColLabelValue(c) == 'refine':
                    ci = colLabels.index('I/A')
                    atomData[r][c] = atomData[r][c].replace(rbAtmDict.get(atomData[r][ci+8],''),'')
                if 'Atoms' in data['Drawing']:
                    ci = colLabels.index('I/A')
                    DrawAtomsReplaceByID(data['Drawing'],ci+8,atomData[r],ID)
                wx.CallAfter(Paint)

        def AtomTypeSelect(event):
            r,c =  event.GetRow(),event.GetCol()
            if Atoms.GetColLabelValue(c) == 'Type':
                PE = G2elemGUI.PickElement(G2frame,ifMag=ifMag)
                if PE.ShowModal() == wx.ID_OK:
                    if PE.Elem != 'None':                        
                        atomData[r][c] = PE.Elem.strip()
                        name = atomData[r][c]
                        if len(name) in [2,4]:
                            atomData[r][c-1] = name[:2]+'%d'%(r+1)
                        else:
                            atomData[r][c-1] = name[:1]+'%d'%(r+1)
                PE.Destroy()
                SetupGeneral()
                wx.CallAfter(Paint)
                value = Atoms.GetCellValue(r,c)
                atomData[r][c] = value
                ci = colLabels.index('I/A')
                ID = atomData[r][ci+8]
                if 'Atoms' in data['Drawing']:
                    DrawAtomsReplaceByID(data['Drawing'],ci+8,atomData[r],ID)
                SetupGeneral()
            else:
                event.Skip()

        def RowSelect(event):
            r,c =  event.GetRow(),event.GetCol()
            if not (event.AltDown() or (event.ShiftDown() and event.ControlDown())):
                Atoms.frm = -1
                G2frame.dataFrame.SetStatusText('')                    
            if r < 0 and c < 0:
                if Atoms.IsSelection():
                    Atoms.ClearSelection()
            elif c < 0:                   #only row clicks
                ci = colLabels.index('I/A')
                if event.ControlDown() and not event.ShiftDown():                    
                    if r in Atoms.GetSelectedRows():
                        Atoms.DeselectRow(r)
                    else:
                        Atoms.SelectRow(r,True)
                elif event.ShiftDown() and not event.ControlDown():
                    indxs = Atoms.GetSelectedRows()
                    Atoms.ClearSelection()
                    ibeg = 0
                    if indxs:
                        ibeg = indxs[-1]
                    for row in range(ibeg,r+1):
                        Atoms.SelectRow(row,True)
                elif event.AltDown() or (event.ShiftDown() and event.ControlDown()):
                    if atomData[r][ci+8] in rbAtmDict:
                        G2frame.ErrorDialog('Atom move error','Atoms in rigid bodies can not be moved')
                        Atoms.frm = -1
                        Atoms.ClearSelection()
                    else:    
                        if Atoms.frm < 0:           #pick atom to be moved
                            Atoms.frm = r
                            Atoms.SelectRow(r,True)
                            n = colLabels.index('Name')
                            G2frame.dataFrame.SetStatusText('Atom '+atomData[r][n]+' is to be moved')
                        else:                       #move it
                            item = atomData.pop(Atoms.frm)
                            atomData.insert(r,item)
                            Atoms.frm = -1
                            G2frame.dataFrame.SetStatusText('')
                            wx.CallAfter(Paint)
                else:
                    Atoms.ClearSelection()
                    Atoms.SelectRow(r,True)
                
        def ChangeSelection(event):
            r,c =  event.GetRow(),event.GetCol()
            if r < 0 and c < 0:
                Atoms.ClearSelection()
            if c < 0:
                if r in Atoms.GetSelectedRows():
                    Atoms.DeselectRow(r)
                else:
                    Atoms.SelectRow(r,True)
            if r < 0:
                if c in Atoms.GetSelectedCols():
                    Atoms.DeselectCol(c)
                else:
                    Atoms.SelectCol(c,True)
                    
        def Paint():
        
            table = []
            rowLabels = []
            for i,atom in enumerate(atomData):
                table.append(atom)
                rowLabels.append(str(i))
            atomTable = G2G.Table(table,rowLabels=rowLabels,colLabels=colLabels,types=Types)
            Atoms.SetTable(atomTable, True)
            Atoms.frm = -1            
            colType = colLabels.index('Type')
            colR = colLabels.index('refine')
            colSS = colLabels.index('site sym')
            colX = colLabels.index('x')
            colIA = colLabels.index('I/A')
            colU11 = colLabels.index('U11')
            colUiso = colLabels.index('Uiso')
            colM = 0
            if 'Mx' in colLabels:
                colM = colLabels.index('Mx')
                atTypes = generalData['AtomTypes']
                Lande = generalData['Lande g']
                AtInfo = dict(zip(atTypes,Lande))
            attr = wx.grid.GridCellAttr()
            attr.IncRef()               #fix from Jim Hester
            attr.SetEditor(G2G.GridFractionEditor(Atoms))
            for c in range(colX,colX+3):
                attr = wx.grid.GridCellAttr()
                attr.IncRef()               #fix from Jim Hester
                attr.SetEditor(G2G.GridFractionEditor(Atoms))
                Atoms.SetColAttr(c, attr)
            for i in range(colU11-1,colU11+6):
                Atoms.SetColSize(i,50)            
            for row in range(Atoms.GetNumberRows()):
                atId = atomData[row][colIA+8]
                rbExcl = rbAtmDict.get(atId,'')
                Atoms.SetReadOnly(row,colSS,True)                         #site sym
                Atoms.SetReadOnly(row,colSS+1,True)                       #Mult
                if Atoms.GetCellValue(row,colIA) == 'A':
                    try:    #patch for sytsym name changes
                        CSI = G2spc.GetCSuinel(atomData[row][colSS])
                    except KeyError:
                        Sytsym = G2spc.SytSym(atomData[row][colX:colX+3],SGData)[0]
                        atomData[row][colSS] = Sytsym
                        CSI = G2spc.GetCSuinel(Sytsym)
                    Atoms.SetCellStyle(row,colUiso,VERY_LIGHT_GREY,True)
                    Atoms.SetCellTextColour(row,colUiso,VERY_LIGHT_GREY)
                    for i in range(6):
                        cj = colU11+i
                        Atoms.SetCellTextColour(row,cj,BLACK)
                        Atoms.SetCellStyle(row,cj,VERY_LIGHT_GREY,True)
                        if CSI[2][i] and 'U' not in rbExcl:
                            Atoms.SetCellStyle(row,cj,WHITE,False)
                else:
                    Atoms.SetCellStyle(row,colUiso,WHITE,False)
                    Atoms.SetCellTextColour(row,colUiso,BLACK)
                    if 'U' in rbExcl:
                        Atoms.SetCellStyle(row,colUiso,VERY_LIGHT_GREY,True)
                    for i in range(6):
                        cj = colU11+i
                        Atoms.SetCellStyle(row,cj,VERY_LIGHT_GREY,True)
                        Atoms.SetCellTextColour(row,cj,VERY_LIGHT_GREY)
                if colM:
                    SytSym,Mul,Nop,dupDir = G2spc.SytSym(atomData[row][colX:colX+3],SGData)
                    CSI = G2spc.GetCSpqinel(SytSym,SpnFlp,dupDir)
#                    print SytSym,Nop,SpnFlp[Nop],CSI,dupDir
                    for i in range(3):
                        ci = i+colM
                        Atoms.SetCellStyle(row,ci,VERY_LIGHT_GREY,True)
                        Atoms.SetCellTextColour(row,ci,VERY_LIGHT_GREY)
                        if CSI and CSI[1][i] and AtInfo and AtInfo[atomData[row][colType]]:
                            Atoms.SetCellStyle(row,ci,WHITE,False)
                            Atoms.SetCellTextColour(row,ci,BLACK)
                            
                if 'X' in rbExcl:
                    for c in range(0,colX+3):
                        if c != colR:
                            Atoms.SetCellStyle(row,c,VERY_LIGHT_GREY,True)
            Atoms.AutoSizeColumns(False)

        # FillAtomsGrid executable code starts here
        if not data['Drawing']:                 #if new drawing - no drawing data!
            SetupDrawingData()
        generalData = data['General']
        SpnFlp = generalData['SGData'].get('SpnFlp',[])
#        OprNames = generalData['SGData'].get('OprNames',[])
#        print OprNames
#        print SpnFlp
#        print generalData['SGData'].get('MagMom',[])
        atomData = data['Atoms']
        resRBData = data['RBModels'].get('Residue',[])
        vecRBData = data['RBModels'].get('Vector',[])
        rbAtmDict = {}
        for rbObj in resRBData+vecRBData:
            exclList = ['X' for i in range(len(rbObj['Ids']))]
            rbAtmDict.update(dict(zip(rbObj['Ids'],exclList)))
            if rbObj['ThermalMotion'][0] != 'None':
                for id in rbObj['Ids']:
                    rbAtmDict[id] += 'U'            
        # exclList will be 'x' or 'xu' if TLS used in RB
        Items = [G2gd.wxID_ATOMSEDITINSERT,G2gd.wxID_ATOMSEDITDELETE, 
            G2gd.wxID_ATOMSMODIFY,G2gd.wxID_ATOMSTRANSFORM,G2gd.wxID_MAKEMOLECULE,
            G2gd.wxID_ATOMVIEWINSERT,G2gd.wxID_ATOMMOVE,G2gd.wxID_ADDHATOM]
        if atomData:
            for item in Items:    
                G2frame.dataFrame.AtomsMenu.Enable(item,True)
        else:
            for item in Items:
                G2frame.dataFrame.AtomsMenu.Enable(item,False)
        Items = [G2gd.wxID_ATOMVIEWINSERT, G2gd.wxID_ATOMSVIEWADD,G2gd.wxID_ATOMMOVE]
        if 'showABC' in data['Drawing']:
            for item in Items:
                G2frame.dataFrame.AtomsMenu.Enable(item,True)
        else:
            for item in Items:
                G2frame.dataFrame.AtomsMenu.Enable(item,False)
        parmChoice = ': ,X,XU,U,F,FX,FXU,FU'
        if generalData['Type'] == 'magnetic':
            parmChoice += ',M,MX,MXU,MU,MF,MFX,MFXU,MFU'
        AAchoice = ": ,ALA,ARG,ASN,ASP,CYS,GLN,GLU,GLY,HIS,ILE,LEU,LYS,MET,PHE,PRO,SER,THR,TRP,TYR,VAL,MSE,HOH,UNK"
        Types = [wg.GRID_VALUE_STRING,wg.GRID_VALUE_STRING,wg.GRID_VALUE_CHOICE+parmChoice,]+ \
            3*[wg.GRID_VALUE_FLOAT+':10,5',]+[wg.GRID_VALUE_FLOAT+':10,4', #x,y,z,frac
            wg.GRID_VALUE_STRING,wg.GRID_VALUE_STRING,wg.GRID_VALUE_CHOICE+":I,A",]
        Types += 7*[wg.GRID_VALUE_FLOAT+':10,5',]
        colLabels = ['Name','Type','refine','x','y','z','frac','site sym','mult','I/A','Uiso','U11','U22','U33','U12','U13','U23']
        ifMag = False
        if generalData['Type'] == 'macromolecular':
            colLabels = ['res no','residue','chain'] + colLabels
            Types = [wg.GRID_VALUE_STRING,
                wg.GRID_VALUE_CHOICE+AAchoice,
                wg.GRID_VALUE_STRING] + Types
        elif generalData['Type'] == 'magnetic':
            ifMag = True
            colLabels = colLabels[:7]+['Mx','My','Mz']+colLabels[7:]
            Types = Types[:7]+3*[wg.GRID_VALUE_FLOAT+':10,4',]+Types[7:]
        SGData = data['General']['SGData']
        G2frame.dataFrame.SetStatusText('')
        if SGData['SGPolax']:
            G2frame.dataFrame.SetStatusText('Warning: The location of the origin is arbitrary in '+SGData['SGPolax'])
        Atoms.Bind(wg.EVT_GRID_CELL_CHANGE, ChangeAtomCell)
        Atoms.Bind(wg.EVT_GRID_CELL_LEFT_DCLICK, AtomTypeSelect)
        Atoms.Bind(wg.EVT_GRID_LABEL_LEFT_DCLICK, RefreshAtomGrid)
        Atoms.Bind(wg.EVT_GRID_LABEL_LEFT_CLICK, RowSelect)
        Atoms.Bind(wg.EVT_GRID_LABEL_RIGHT_CLICK, ChangeSelection)
        Atoms.SetMargins(0,0)
        
        G2frame.dataFrame.setSizePosLeft([700,300])
        Paint()

    def OnAtomAdd(event):
        Elem = 'H'
        if data['General']['Type'] == 'magnetic':
            Elem = 'Fe'
        AtomAdd(0,0,0,El=Elem)
        FillAtomsGrid(Atoms)
        event.StopPropagation()
        if data['Drawing']:
            G2plt.PlotStructure(G2frame,data)
        
    def OnAtomViewAdd(event):
        Elem = 'H'
        if data['General']['Type'] == 'magnetic':
            Elem = 'Fe'
        try:
            drawData = data['Drawing']
            x,y,z = drawData['viewPoint'][0]
            AtomAdd(x,y,z,El=Elem)
        except:
            AtomAdd(0,0,0,El=Elem)
        FillAtomsGrid(Atoms)
        event.StopPropagation()
        data['Drawing']['Atoms'] = []
        UpdateDrawAtoms()
        G2plt.PlotStructure(G2frame,data)
                
    def AtomAdd(x,y,z,El='H',Name='UNK'):
        atomData = data['Atoms']
        generalData = data['General']
        atId = ran.randint(0,sys.maxint)
        E,SGData = G2spc.SpcGroup(generalData['SGData']['SpGrp'])
        Sytsym,Mult = G2spc.SytSym([x,y,z],SGData)[:2]
        if generalData['Type'] == 'macromolecular':
            atomData.append([0,Name,'',Name,El,'',x,y,z,1.,Sytsym,Mult,'I',0.10,0,0,0,0,0,0,atId])
        elif generalData['Type'] in ['nuclear','faulted',]:
            if generalData['Modulated']:
                atomData.append([Name,El,'',x,y,z,1.,Sytsym,Mult,'I',0.01,0,0,0,0,0,0,atId,[],[],
                    {'SS1':{'waveType':'Fourier','Sfrac':[],'Spos':[],'Sadp':[],'Smag':[]}}])
            else:
                atomData.append([Name,El,'',x,y,z,1.,Sytsym,Mult,'I',0.01,0,0,0,0,0,0,atId])
        elif generalData['Type'] == 'magnetic':
            if generalData['Modulated']:
                atomData.append([Name,El,'',x,y,z,1.,0.,0.,0.,Sytsym,Mult,'I',0.01,0,0,0,0,0,0,atId,[],[],
                    {'SS1':{'waveType':'Fourier','Sfrac':[],'Spos':[],'Sadp':[],'Smag':[]}}])
            else:
                atomData.append([Name,El,'',x,y,z,1.,0.,0.,0.,Sytsym,Mult,'I',0.01,0,0,0,0,0,0,atId])
            
        SetupGeneral()
        data['Drawing']['Atoms'] = []
        UpdateDrawAtoms()
        G2plt.PlotStructure(G2frame,data)
#        if 'Atoms' in data['Drawing']:            
#            DrawAtomAdd(data['Drawing'],atomData[-1])

    def OnAtomInsert(event):
        '''Inserts a new atom into list immediately before every selected atom
        '''
        indx = GetSelectedAtoms()
        for a in reversed(sorted(indx)):
            AtomInsert(a,0,0,0)
        event.StopPropagation()
        FillAtomsGrid(Atoms)
        data['Drawing']['Atoms'] = []
        UpdateDrawAtoms()
        G2plt.PlotStructure(G2frame,data)
        
    def OnAtomViewInsert(event):
        if 'Drawing' in data:
            drawData = data['Drawing']
            x,y,z = drawData['viewPoint'][0]
            AtomAdd(x,y,z)
            FillAtomsGrid(Atoms)
        event.StopPropagation()
        
    def OnHydAtomAdd(event):
        '''Adds H atoms to fill out coordination sphere for selected atoms
        '''
        indx = GetSelectedAtoms()
        if not indx: return
        DisAglCtls = {}
        generalData = data['General']
        if 'DisAglCtls' in generalData:
            DisAglCtls = generalData['DisAglCtls']
            if 'H' not in DisAglCtls['AtomTypes']:
                DisAglCtls['AtomTypes'].append('H')
                DisAglCtls['AngleRadii'].append(0.5)
                DisAglCtls['BondRadii'].append(0.5)
        dlg = G2gd.DisAglDialog(G2frame,DisAglCtls,generalData,Reset=False)
        if dlg.ShowModal() == wx.ID_OK:
            DisAglCtls = dlg.GetData()
        else:
            dlg.Destroy()
            return
        dlg.Destroy()
        generalData['DisAglCtls'] = DisAglCtls
        cx,ct,cs,cia = generalData['AtomPtrs']
        atomData = data['Atoms']
        AtNames = [atom[ct-1] for atom in atomData]
        AtLookUp = G2mth.FillAtomLookUp(atomData,cia+8)
        Neigh = []
        AddHydIds = []
        for ind in indx:
            atom = atomData[ind]
            if atom[ct] not in ['C','N','O']:
                continue
            neigh = [atom[ct-1],G2mth.FindNeighbors(data,atom[ct-1],AtNames),0]
            if len(neigh[1][0]) > 3 or (atom[ct] == 'O' and len(neigh[1][0]) > 1):
                continue
            nH = 1      #for O atom
            if atom[ct] in ['C','N']:
                nH = 4-len(neigh[1][0])
            bonds = {item[0]:item[1:] for item in neigh[1][0]}
            nextName = ''
            if len(bonds) == 1:
                nextName = bonds.keys()[0]
            for bond in bonds:
                if 'C' in atom[ct]:
                    if 'C' in bond and bonds[bond][0] < 1.42:
                        nH -= 1
                        break
                    elif 'O' in bond and bonds[bond][0] < 1.3:
                        nH -= 1
                        break
                elif 'O' in atom[ct] and 'C' in bonds and bonds[bond][0] < 1.3:
                    nH -= 1
                    break
            nextneigh = []
            if nextName:
                nextneigh = G2mth.FindNeighbors(data,nextName,AtNames,notName=neigh[0])
                if nextneigh[0]:
                    neigh[1][1].append(nextneigh[1][1][0])
            neigh[2] = max(0,nH)  #set expected no. H's needed
            if len(neigh[1][0]):
                AddHydIds.append(neigh[1][1])
                Neigh.append(neigh)
        if Neigh:
            letters = ['A','B','C']
            HydIds = {}
            mapError = False
            dlg = G2gd.AddHatomDialog(G2frame,Neigh,data)
            if dlg.ShowModal() == wx.ID_OK:
                Nat = len(atomData)
                Neigh = dlg.GetData()
                mapData = generalData['Map']
                for ineigh,neigh in enumerate(Neigh):
                    AddHydIds[ineigh].append(neigh[2])
                    loc = AtLookUp[AddHydIds[ineigh][0]]+1
                    if 'O' in neigh[0] and (not len(mapData['rho']) or not 'delt-F' in mapData['MapType']):
                        mapError = True
                        continue                            
                    Hxyz,HU = G2mth.AddHydrogens(AtLookUp,generalData,atomData,AddHydIds[ineigh])
                    for iX,X in enumerate(Hxyz):
                        AtomInsert(loc+iX,X[0],X[1],X[2],'H','H%s'%(neigh[0][1:]+letters[iX]))
                        data['Atoms'][loc+iX][cia+1] = HU[iX]
                        Id = data['Atoms'][loc+iX][cia+8]
                        HydIds[Id] = [iX,AddHydIds[ineigh]]
                        Nat += 1
                        AtLookUp = G2mth.FillAtomLookUp(atomData,cia+8)
            if mapError:
                G2frame.ErrorDialog('Add H atom error','Adding O-H atoms requires delt-F map')
            SetupGeneral()
            data['General']['HydIds'].update(HydIds)
            G2frame.dataFrame.AtomEdit.Enable(G2gd.wxID_UPDATEHATOM,True)
            data['Drawing']['Atoms'] = []
            UpdateDrawAtoms()
            FillAtomsGrid(Atoms)
            dlg.Destroy()
            G2plt.PlotStructure(G2frame,data)
        else:
            wx.MessageBox('No candidates found',caption='Add H atom Error',style=wx.ICON_EXCLAMATION)
                
    def OnHydAtomUpdate(event):
        generalData = data['General']
        cx,ct,cs,cia = generalData['AtomPtrs']
        atomData = data['Atoms']
        AtLookUp = G2mth.FillAtomLookUp(atomData,cia+8)
        HydIds = data['General']['HydIds']
        delList = []
        for HId in HydIds:
            hydIds = HydIds[HId]
            num = hydIds[0]
            Hxyz,HU = G2mth.AddHydrogens(AtLookUp,generalData,atomData,hydIds[1])
            try:
                if data['Atoms'][AtLookUp[HId]][ct] != 'H':
                    raise KeyError
                data['Atoms'][AtLookUp[HId]][cx:cx+3] = Hxyz[num]
                data['Atoms'][AtLookUp[HId]][cia+1] = HU[num]
            except KeyError:
                delList.append(HId)
                continue
        for HId in delList: #clear out deleted H-atom pointers
            del HydIds[HId]
        if not len(HydIds):
            G2frame.dataFrame.AtomEdit.Enable(G2gd.wxID_UPDATEHATOM,False)
        data['Drawing']['Atoms'] = []
        UpdateDrawAtoms()
        FillAtomsGrid(Atoms)
        G2plt.PlotStructure(G2frame,data)
        
    def OnAtomMove(event):
        drawData = data['Drawing']
        atomData = data['Atoms']
        x,y,z = drawData['viewPoint'][0]
        colLabels = [Atoms.GetColLabelValue(c) for c in range(Atoms.GetNumberCols())]
        cx = colLabels.index('x')
        ci = colLabels.index('I/A')
        indx = GetSelectedAtoms()
        if len(indx) != 1:
            G2frame.ErrorDialog('Atom move error','Only one atom can be moved')
        elif atomData[indx[0]][ci+8] in rbAtmDict:
            G2frame.ErrorDialog('Atom move error','Atoms in rigid bodies can not be moved')
        else:
            atomData[indx[0]][cx:cx+3] = [x,y,z]
            SetupGeneral()
            FillAtomsGrid(Atoms)
            ID = atomData[indx[0]][ci+8]
            DrawAtomsReplaceByID(data['Drawing'],ci+8,atomData[indx[0]],ID)
            G2plt.PlotStructure(G2frame,data)
        event.StopPropagation()
            
    def DrawAtomsReplaceByID(drawingData,loc,atom,ID):
        IDs = [ID,]
        atomData = drawingData['Atoms']
        indx = G2mth.FindAtomIndexByIDs(atomData,loc,IDs)
        for ind in indx:
            atomData[ind] = MakeDrawAtom(atom,atomData[ind])
                
    def MakeDrawAtom(atom,oldatom=None):
        AA3letter = ['ALA','ARG','ASN','ASP','CYS','GLN','GLU','GLY','HIS','ILE',
            'LEU','LYS','MET','PHE','PRO','SER','THR','TRP','TYR','VAL','MSE','HOH','WAT','UNK']
        AA1letter = ['A','R','N','D','C','Q','E','G','H','I',
            'L','K','M','F','P','S','T','W','Y','V','M',' ',' ',' ']
        generalData = data['General']
        SGData = generalData['SGData']
        if generalData['Type'] in ['nuclear','faulted',]:
            if oldatom:
                opr = oldatom[5]
                if atom[9] == 'A':                    
                    X,U = G2spc.ApplyStringOps(opr,SGData,atom[3:6],atom[11:17])
                    atomInfo = [atom[:2]+list(X)+oldatom[5:9]+atom[9:11]+list(U)+oldatom[17:]][0]
                else:
                    X = G2spc.ApplyStringOps(opr,SGData,atom[3:6])
                    atomInfo = [atom[:2]+list(X)+oldatom[5:9]+atom[9:]+oldatom[17:]][0]
            else:
                atomInfo = [atom[:2]+atom[3:6]+['1',]+['vdW balls',]+
                    ['',]+[[255,255,255],]+atom[9:]+[[],[]]][0]
            ct,cs = [1,8]         #type & color
        elif  generalData['Type'] == 'magnetic':
            atomInfo = [atom[:2]+atom[3:6]+atom[7:10]+['1',]+['vdW balls',]+
                ['',]+[[255,255,255],]+atom[12:]+[[],[]]][0]
            ct,cs = [1,11]         #type & color
        elif generalData['Type'] == 'macromolecular':
            try:
                oneLetter = AA3letter.index(atom[1])
            except ValueError:
                oneLetter = -1
            atomInfo = [[atom[1].strip()+atom[0],]+
                [AA1letter[oneLetter]+atom[0],]+atom[2:5]+
                atom[6:9]+['1',]+['sticks',]+['',]+[[255,255,255],]+atom[12:]+[[],[]]][0]
            ct,cs = [4,11]         #type & color
        atNum = generalData['AtomTypes'].index(atom[ct])
        atomInfo[cs] = list(generalData['Color'][atNum])
        return atomInfo
        
    def AtomInsert(indx,x,y,z,El='H',Name='UNK'):
        atomData = data['Atoms']
        generalData = data['General']
        E,SGData = G2spc.SpcGroup(generalData['SGData']['SpGrp'])
        Sytsym,Mult = G2spc.SytSym([x,y,z],SGData)[:2]
        atId = ran.randint(0,sys.maxint)
        if generalData['Type'] == 'macromolecular':
            atomData.insert(indx,[0,Name,'',Name,El,'',x,y,z,1,Sytsym,Mult,'I',0.10,0,0,0,0,0,0,atId])
        elif generalData['Type'] in ['nuclear','faulted',]:
            if generalData['Modulated']:
                atomData.insert(indx,[Name,El,'',x,y,z,1,Sytsym,Mult,0,'I',0.01,0,0,0,0,0,0,atId,[],[],
                    {'SS1':{'waveType':'Fourier','Sfrac':[],'Spos':[],'Sadp':[],'Smag':[]}}])
            else:
                atomData.insert(indx,[Name,El,'',x,y,z,1,Sytsym,Mult,'I',0.01,0,0,0,0,0,0,atId])
            SetupGeneral()
        elif generalData['Type'] == 'magnetic':
            if generalData['Modulated']:
                atomData.insert(indx,[Name,El,'',x,y,z,1,0.,0.,0.,Sytsym,Mult,0,'I',0.01,0,0,0,0,0,0,atId,[],[],
                    {'SS1':{'waveType':'Fourier','Sfrac':[],'Spos':[],'Sadp':[],'Smag':[]}}])
            else:
                atomData.insert(indx,[Name,El,'',x,y,z,1,0.,0.,0.,Sytsym,Mult,'I',0.01,0,0,0,0,0,0,atId])
        data['Drawing']['Atoms'] = []
        UpdateDrawAtoms()
        G2plt.PlotStructure(G2frame,data)

    def AtomDelete(event):
        colLabels = [Atoms.GetColLabelValue(c) for c in range(Atoms.GetNumberCols())]
        HydIds = data['General']['HydIds']
        ci = colLabels.index('I/A')
        indx = GetSelectedAtoms()
        IDs = []
        if not indx: return
        atomData = data['Atoms']
        indx.reverse()
        for ind in indx:
            atom = atomData[ind]
            if atom[ci+8] in rbAtmDict:
                G2frame.dataFrame.SetStatusText('**** ERROR - atom is in a rigid body and can not be deleted ****')
            else:
                if atom[ci+8] in HydIds:    #remove Hs from Hatom update dict
                    del HydIds[atom[ci+8]]
                IDs.append(atom[ci+8])
                del atomData[ind]
        if 'Atoms' in data['Drawing']:
            Atoms.ClearSelection()
            DrawAtomsDeleteByIDs(IDs)
            data['Drawing']['Atoms'] = []
            UpdateDrawAtoms()
            wx.CallAfter(FillAtomsGrid,Atoms)
            G2plt.PlotStructure(G2frame,data)
        SetupGeneral()
        if not len(HydIds):
            G2frame.dataFrame.AtomEdit.Enable(G2gd.wxID_UPDATEHATOM,False)
        event.StopPropagation()

    def GetSelectedAtoms():
        '''Get all atoms that are selected by row or by having any cell selected.
        produce an error message if no atoms are selected.
        '''
        indx = list(set([row for row,col in Atoms.GetSelectedCells()]+Atoms.GetSelectedRows()))
        if indx:
            return indx
        else:
            G2G.G2MessageBox(G2frame,'Warning: no atoms were selected','Nothing selected')
        
    def AtomRefine(event):
        colLabels = [Atoms.GetColLabelValue(c) for c in range(Atoms.GetNumberCols())]
        c = colLabels.index('refine')
        indx = GetSelectedAtoms()
        if not indx: return
        atomData = data['Atoms']
        generalData = data['General']
        Type = generalData['Type']
        if Type in ['nuclear','macromolecular','faulted',]:
            choice = ['F - site fraction','X - coordinates','U - thermal parameters']
        elif Type in ['magnetic',]:
            choice = ['F - site fraction','X - coordinates','U - thermal parameters','M - magnetic moment']
        dlg = wx.MultiChoiceDialog(G2frame,'Select','Refinement controls',choice)
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelections()
            parms = ''
            for x in sel:
                parms += choice[x][0]
            for r in indx:
                if not Atoms.IsReadOnly(r,c):
                    atomData[r][c] = parms
            Atoms.ForceRefresh()
        dlg.Destroy()

    def AtomModify(event):
        indx = GetSelectedAtoms()
        if not indx: return
        atomData = data['Atoms']
        generalData = data['General']
        colLabels = [Atoms.GetColLabelValue(c) for c in range(Atoms.GetNumberCols())]
        ci = colLabels.index('I/A')
        choices = ['Type','Name','x','y','z','frac','I/A','Uiso']
        if generalData['Type'] == 'magnetic':
            choices += ['Mx','My','Mz',]
        dlg = wx.SingleChoiceDialog(G2frame,'Select','Atom parameter',choices)
        parm = ''
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelection()
            parm = choices[sel]
            cid = colLabels.index(parm)
        dlg.Destroy()
        if parm in ['Type']:
            dlg = G2elemGUI.PickElement(G2frame)
            if dlg.ShowModal() == wx.ID_OK:
                if dlg.Elem not in ['None']:
                    El = dlg.Elem.strip()
                    for r in indx:                        
                        if not Atoms.IsReadOnly(r,cid):
                            atomData[r][cid] = El
                            if len(El) in [2,4]:
                                atomData[r][cid-1] = El[:2]+'%d'%(r+1)
                            else:
                                atomData[r][cid-1] = El[:1]+'%d'%(r+1)
                    SetupGeneral()
                    if 'Atoms' in data['Drawing']:
                        for r in indx:
                            ID = atomData[r][ci+8]
                            DrawAtomsReplaceByID(data['Drawing'],ci+8,atomData[r],ID)
                FillAtomsGrid(Atoms)
            dlg.Destroy()
        elif parm in ['Name',]:
            dlg = wx.MessageDialog(G2frame,'Do you really want to rename the selected atoms?','Rename', 
                wx.YES_NO | wx.ICON_QUESTION)
            try:
                result = dlg.ShowModal()
                if result == wx.ID_YES:
                    for r in indx:
                        if not Atoms.IsReadOnly(r,cid+1):
                            El = atomData[r][cid+1]
                            if len(El) in [2,4]:
                                atomData[r][cid] = El[:2]+'%d'%(r+1)
                            else:
                                atomData[r][cid] = El[:1]+'%d'%(r+1)
                FillAtomsGrid(Atoms)
            finally:
                dlg.Destroy()

        elif parm in ['I/A']:
            choices = ['Isotropic','Anisotropic']
            dlg = wx.SingleChoiceDialog(G2frame,'Select','Thermal parameter model',choices)
            if dlg.ShowModal() == wx.ID_OK:
                sel = dlg.GetSelection()
                parm = choices[sel][0]
                for r in indx:                        
                    if not Atoms.IsReadOnly(r,cid):
                        atomData[r][cid] = parm
                FillAtomsGrid(Atoms)
            dlg.Destroy()
        elif parm in ['frac','Uiso']:
            limits = [0.,1.]
            val = 1.0
            if  parm in ['Uiso']:
                limits = [0.,0.25]
                val = 0.01
            dlg = G2G.SingleFloatDialog(G2frame,'New value','Enter new value for '+parm,val,limits)
            if dlg.ShowModal() == wx.ID_OK:
                parm = dlg.GetValue()
                for r in indx:                        
                    if not Atoms.IsReadOnly(r,cid):
                        atomData[r][cid] = parm
                SetupGeneral()
                FillAtomsGrid(Atoms)
            dlg.Destroy()
        elif parm in ['x','y','z']:
            limits = [-1.,1.]
            val = 0.
            dlg = G2G.SingleFloatDialog(G2frame,'Atom shift','Enter shift for '+parm,val,limits)
            if dlg.ShowModal() == wx.ID_OK:
                parm = dlg.GetValue()
                for r in indx:                        
                    if not Atoms.IsReadOnly(r,cid):
                        atomData[r][cid] += parm
                SetupGeneral()
                FillAtomsGrid(Atoms)
            dlg.Destroy()
        elif parm in ['Mx','My','Mz',]:
            limits = [-10.,10.]
            val = 0.
            dlg = G2G.SingleFloatDialog(G2frame,'Atom moment','Enter new value for '+parm,val,limits)
            if dlg.ShowModal() == wx.ID_OK:
                parm = dlg.GetValue()
                for r in indx:                        
                    if not Atoms.IsReadOnly(r,cid):
                        atomData[r][cid] = parm
                SetupGeneral()
                FillAtomsGrid(Atoms)
            dlg.Destroy()

        data['Drawing']['Atoms'] = []
        UpdateDrawAtoms()
        G2plt.PlotStructure(G2frame,data)

    def AtomTransform(event):
        indx = GetSelectedAtoms()
        if not indx: return
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])
        SpnFlp = generalData['SGData'].get('SpnFlp',[])
        colLabels = [Atoms.GetColLabelValue(c) for c in range(Atoms.GetNumberCols())]
        cx = colLabels.index('x')
        cuia = colLabels.index('I/A')
        cuij = colLabels.index('U11')
        css = colLabels.index('site sym')
        cmx = 0
        if 'Mx' in colLabels:
            cmx = colLabels.index('Mx')
        atomData = data['Atoms']
        SGData = generalData['SGData']
        dlg = G2gd.SymOpDialog(G2frame,SGData,True,True)
        New = False
        try:
            if dlg.ShowModal() == wx.ID_OK:
                Inv,Cent,Opr,Cell,New,Force = dlg.GetSelection()
                Cell = np.array(Cell)
                cent = SGData['SGCen'][Cent]
                M,T = SGData['SGOps'][Opr]
                for ind in indx:
                    XYZ = np.array(atomData[ind][cx:cx+3])
                    XYZ = np.inner(M,XYZ)+T
                    if Inv:
                        XYZ = -XYZ
                    XYZ = XYZ+cent+Cell
                    if Force:
                        XYZ,cell = G2spc.MoveToUnitCell(XYZ)
                        Cell += cell
                    if New:
                        atom = copy.copy(atomData[ind])
                    else:
                        atom = atomData[ind]
                    atom[cx:cx+3] = XYZ
                    atom[css:css+2] = G2spc.SytSym(XYZ,SGData)[:2]
                    OprNum = ((Opr+1)+100*Cent)*(1-2*Inv)
                    if atom[cuia] == 'A':
                        Uij = atom[cuij:cuij+6]
                        U = G2spc.Uij2U(Uij)
                        U = np.inner(np.inner(M,U),M)
                        Uij = G2spc.U2Uij(U)
                        atom[cuij:cuij+6] = Uij
                    if cmx:
                        opNum = G2spc.GetOpNum(OprNum,SGData)
                        mom = np.inner(np.array(atom[cmx:cmx+3]),Bmat)
                        atom[cmx:cmx+3] = np.inner(np.inner(mom,M),Amat)*nl.det(M)*SpnFlp[opNum-1]
                    if New:
                        atomData.append(atom)
        finally:
            dlg.Destroy()
        Atoms.ClearSelection()
        if New:
            FillAtomsGrid(Atoms)
        else:
            Atoms.ForceRefresh()
        data['Drawing']['Atoms'] = []
        UpdateDrawAtoms()
        G2plt.PlotStructure(G2frame,data)
            
#    def AtomRotate(event):
#        '''Currently not used - Bind commented out below
#        '''
#        Units = {'':np.zeros(3),
#            'xy':np.array([[i,j,0] for i in range(3) for j in range(3)])-np.array([1,1,0]),
#            'xz':np.array([[i,0,j] for i in range(3) for j in range(3)])-np.array([1,1,0]),
#            'yz':np.array([[0,i,j] for i in range(3) for j in range(3)])-np.array([1,1,0]),
#            'xyz':np.array([[i,j,k] for i in range(3) for j in range(3) for k in range(3)])-np.array([1,1,1])}
#        indx = GetSelectedAtoms()
#        if indx:
#            generalData = data['General']
#            A,B = G2lat.cell2AB(generalData['Cell'][1:7])
#            colLabels = [Atoms.GetColLabelValue(c) for c in range(Atoms.GetNumberCols())]
#            cx = colLabels.index('x')
#            cuia = colLabels.index('I/A')   #need to not do aniso atoms - stop with error? or force isotropic?
#            css = colLabels.index('site sym')
#            atomData = data['Atoms']
#            SGData = generalData['SGData']
#            dlg = G2gd.RotationDialog(G2frame)
#            try:
#                if dlg.ShowModal() == wx.ID_OK:
#                    M,T,Expand = dlg.GetSelection()
#                    Unit = Units[Expand]
#                    for ind in indx:
#                        XYZ = np.array(atomData[ind][cx:cx+3])
#                        XYZS = XYZ+Unit
#                        XYZS -= T
#                        XYZS = np.inner(A,XYZS).T   #to Cartesian
#                        XYZS = np.inner(M,XYZS).T   #rotate
#                        XYZS = np.inner(B,XYZS).T+T #back to crystal & translate
#                        GSASIIpath.IPyBreak()
#                        atomData[ind][cx:cx+3] = XYZ
#                        for unit in Unit:
#                            XYZ = np.copy(np.array(atomData[ind][cx:cx+3]))
#                            XYZ += unit 
#                            XYZ -= T
#                            XYZ = np.inner(A,XYZ)   #to Cartesian
#                            XYZ = np.inner(M,XYZ)   #rotate
#                            XYZ = np.inner(B,XYZ)+T #back to crystal & translate
#                            if np.all(XYZ>=0.) and np.all(XYZ<1.0):
#                                atomData[ind][cx:cx+3] = XYZ
##                                atom[css:css+2] = G2spc.SytSym(XYZ,SGData)[:2]
#                                break
#            finally:
#                dlg.Destroy()
#            Atoms.ClearSelection()
#            Atoms.ForceRefresh()
#        else:
#            print "select one or more rows of atoms"
#            G2frame.ErrorDialog('Select atom',"select one or more atoms then redo")
                
    def MakeMolecule(event):      
        indx = GetSelectedAtoms()
        DisAglCtls = {}
        if len(indx) == 1:
            generalData = data['General']
            if 'DisAglCtls' in generalData:
                DisAglCtls = generalData['DisAglCtls']
            dlg = G2gd.DisAglDialog(G2frame,DisAglCtls,generalData)
            if dlg.ShowModal() == wx.ID_OK:
                DisAglCtls = dlg.GetData()
            else:
                dlg.Destroy()
                return
            dlg.Destroy()
            generalData['DisAglCtls'] = DisAglCtls
            atomData = copy.deepcopy(data['Atoms'])
            result = G2mth.FindMolecule(indx[0],generalData,atomData)
            if 'str' in str(type(result)):
                G2frame.ErrorDialog('Assemble molecule',result)
            else:   
                data['Atoms'] = result
            Atoms.ClearSelection()
            data['Drawing']['Atoms'] = []
            OnReloadDrawAtoms(event)            
            FillAtomsGrid(Atoms)
#                G2frame.ErrorDialog('Distance/Angle calculation','try again but do "Reset" to fill in missing atom types')
        else:
            print "select one atom"
            G2frame.ErrorDialog('Select one atom',"select one atom to begin molecule build then redo")

    def OnDensity(event):
        'show the density for the current phase'
        density,mattCoeff = G2mth.getDensity(data['General'])
        msg = 'Density of phase {:s} = {:.3f} g/cc'.format(data['General']['Name'],density)
        print(msg)
        G2G.G2MessageBox(G2frame.dataFrame,msg,'Density')

    def OnSetAll(event):
        'set refinement flags for all atoms in table'
        for row in range(Atoms.GetNumberRows()):
            Atoms.SelectRow(row,True)
    
    def OnDistAnglePrt(event):
        'save distances and angles to a file'    
        fp = file(os.path.abspath(os.path.splitext(G2frame.GSASprojectfile)[0]+'.disagl'),'w')
        OnDistAngle(event,fp=fp)
        fp.close()
    
    def OnDistAngle(event,fp=None):
        'Compute distances and angles'    
        indx = GetSelectedAtoms()
        Oxyz = []
        xyz = []
        DisAglData = {}
        DisAglCtls = {}
        if indx:
            generalData = data['General']
            DisAglData['OrigIndx'] = indx
            if 'DisAglCtls' in generalData:
                DisAglCtls = generalData['DisAglCtls']
            dlg = G2gd.DisAglDialog(G2frame,DisAglCtls,generalData)
            if dlg.ShowModal() == wx.ID_OK:
                DisAglCtls = dlg.GetData()
            else:
                dlg.Destroy()
                return
            dlg.Destroy()
            generalData['DisAglCtls'] = DisAglCtls
            atomData = data['Atoms']
            colLabels = [Atoms.GetColLabelValue(c) for c in range(Atoms.GetNumberCols())]
            cx = colLabels.index('x')
            cn = colLabels.index('Name')
            for i,atom in enumerate(atomData):
                xyz.append([i,]+atom[cn:cn+2]+atom[cx:cx+3])
                if i in indx:
                    Oxyz.append([i,]+atom[cn:cn+2]+atom[cx:cx+3])
            DisAglData['OrigAtoms'] = Oxyz
            DisAglData['TargAtoms'] = xyz
            generalData = data['General']
            DisAglData['SGData'] = generalData['SGData']
            DisAglData['Cell'] = generalData['Cell'][1:] #+ volume
            if 'pId' in data:
                DisAglData['pId'] = data['pId']
                DisAglData['covData'] = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,G2frame.root, 'Covariance'))
            try:
                if fp:
                    G2stMn.PrintDistAngle(DisAglCtls,DisAglData,fp)
                else:    
                    G2stMn.PrintDistAngle(DisAglCtls,DisAglData)
            except KeyError:        # inside DistAngle for missing atom types in DisAglCtls
                G2frame.ErrorDialog('Distance/Angle calculation','try again but do "Reset" to fill in missing atom types')
        else:
            print "select one or more rows of atoms"
            G2frame.ErrorDialog('Select atom',"select one or more rows of atoms then redo")
                        
    def OnIsoDistortCalc(event):
        '''Compute the ISODISTORT mode values from the current coordinates.
        Called in response to the (Phase/Atoms tab) AtomCompute
        "Compute ISODISTORT mode values" menu item, which should be enabled
        only when Phase['ISODISTORT'] is defined. 
        '''
        def _onClose(event):
            dlg.EndModal(wx.ID_CANCEL)
        def fmtHelp(item,fullname):
            helptext = "A new variable"
            if item[-3]:
                helptext += " named "+str(item[-3])
            helptext += " is a linear combination of the following parameters:\n"
            first = True
            for term in item[:-3]:
                line = ''
                var = str(term[1])
                m = term[0]
                if first:
                    first = False
                    line += ' = '
                else:
                    if m >= 0:
                        line += ' + '
                    else:
                        line += ' - '
                    m = abs(m)
                line += '%.3f*%s '%(m,var)
                varMean = G2obj.fmtVarDescr(var)
                helptext += "\n" + line + " ("+ varMean + ")"
            helptext += '\n\nISODISTORT full name: '+str(fullname)
            return helptext

        if 'ISODISTORT' not in data:
            raise Exception,"Should not happen: 'ISODISTORT' not in data"
        if len(data.get('Histograms',[])) == 0:
            G2frame.ErrorDialog(
                'No data',
                'Sorry, this computation requires that a histogram first be added to the phase'
                )
            return
        Histograms,Phases = G2frame.GetUsedHistogramsAndPhasesfromTree() # init for constraint
        # make a lookup table for constraints
        sub = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Constraints') 
        Constraints = G2frame.PatternTree.GetItemPyData(sub)
        constDict = {}
        for item in Constraints:
            if item.startswith('_'): continue
            for c in Constraints[item]:
                if c[-1] != 'f' or not c[-3]: continue
                constDict[c[-3]] = c

        ISO = data['ISODISTORT']
        parmDict,varyList = G2frame.MakeLSParmDict()
            
        dlg = wx.Dialog(G2frame,wx.ID_ANY,'ISODISTORT mode values',#size=(630,400),
                           style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(wx.StaticText(dlg,wx.ID_ANY,
                                    'ISODISTORT mode computation for cordinates in phase '+
                                    str(data['General'].get('Name'))))
        aSizer = wx.BoxSizer(wx.HORIZONTAL)
        panel1 = wxscroll.ScrolledPanel(
            dlg, wx.ID_ANY,#size=(100,200),
            style = wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        subSizer1 = wx.FlexGridSizer(cols=2,hgap=5,vgap=2)
        panel2 = wxscroll.ScrolledPanel(
            dlg, wx.ID_ANY,#size=(100,200),
            style = wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER)
        subSizer2 = wx.FlexGridSizer(cols=3,hgap=5,vgap=2)
        subSizer1.Add(wx.StaticText(panel1,wx.ID_ANY,'Parameter name  '))
        subSizer1.Add(wx.StaticText(panel1,wx.ID_ANY,' value'),0,wx.ALIGN_RIGHT)
        subSizer2.Add((-1,-1))
        subSizer2.Add(wx.StaticText(panel2,wx.ID_ANY,'Mode name  '))
        subSizer2.Add(wx.StaticText(panel2,wx.ID_ANY,' value'),0,wx.ALIGN_RIGHT)
        
        if 'G2VarList' in ISO:
            deltaList = []
            for gv,Ilbl in zip(ISO['G2VarList'],ISO['IsoVarList']):
                dvar = gv.varname()
                var = dvar.replace('::dA','::A')
                albl = Ilbl[:Ilbl.rfind('_')]
                v = Ilbl[Ilbl.rfind('_')+1:]
                pval = ISO['ParentStructure'][albl][['dx','dy','dz'].index(v)]
                if var in parmDict:
                    cval = parmDict[var][0]
                else:
                    dlg.EndModal(wx.ID_CANCEL)
                    G2frame.ErrorDialog('Atom not found',"No value found for parameter "+str(var))
                    return
                deltaList.append(cval-pval)
            modeVals = np.inner(ISO['Var2ModeMatrix'],deltaList)
            for lbl,xyz,var,val,G2var in zip(ISO['IsoVarList'],deltaList,
                                             ISO['IsoModeList'],modeVals,ISO['G2ModeList']):
                if G2var in constDict:
                    ch = G2G.HelpButton(panel2,fmtHelp(constDict[G2var],var))
                    subSizer2.Add(ch,0,wx.LEFT|wx.RIGHT|WACV|wx.ALIGN_CENTER,1)
                else:
                    subSizer2.Add((-1,-1))
                subSizer1.Add(wx.StaticText(panel1,wx.ID_ANY,str(lbl)))
                try:
                    value = G2py3.FormatSigFigs(xyz)
                except TypeError:
                    value = str(xyz)            
                subSizer1.Add(wx.StaticText(panel1,wx.ID_ANY,value),0,wx.ALIGN_RIGHT)
                subSizer2.Add(wx.StaticText(panel2,wx.ID_ANY,str(var)))
                try:
                    value = G2py3.FormatSigFigs(val)
                except TypeError:
                    value = str(val)            
                subSizer2.Add(wx.StaticText(panel2,wx.ID_ANY,value),0,wx.ALIGN_RIGHT)
        if 'G2OccVarList' in ISO:
            deltaList = []
            for gv,Ilbl in zip(ISO['G2OccVarList'],ISO['OccVarList']):
                var = gv.varname()
                albl = Ilbl[:Ilbl.rfind('_')]
                #v = Ilbl[Ilbl.rfind('_')+1:]
                pval = ISO['BaseOcc'][albl]
                if var in parmDict:
                    cval = parmDict[var][0]
                else:
                    dlg.EndModal(wx.ID_CANCEL)
                    G2frame.ErrorDialog('Atom not found',"No value found for parameter "+str(var))
                    return
                deltaList.append(cval-pval)
            modeVals = np.inner(ISO['Var2OccMatrix'],deltaList)
            for lbl,xyz,var,val,G2var in zip(ISO['OccVarList'],deltaList,
                                             ISO['OccModeList'],modeVals,ISO['G2OccModeList']):
                if G2var in constDict:
                    ch = G2G.HelpButton(panel2,fmtHelp(constDict[G2var],var))
                    subSizer2.Add(ch,0,wx.LEFT|wx.RIGHT|WACV|wx.ALIGN_CENTER,1)
                else:
                    subSizer2.Add((-1,-1))
                subSizer1.Add(wx.StaticText(panel1,wx.ID_ANY,str(lbl)))
                try:
                    value = G2py3.FormatSigFigs(xyz)
                except TypeError:
                    value = str(xyz)            
                subSizer1.Add(wx.StaticText(panel1,wx.ID_ANY,value),0,wx.ALIGN_RIGHT)
                #subSizer.Add((10,-1))
                subSizer2.Add(wx.StaticText(panel2,wx.ID_ANY,str(var)))
                try:
                    value = G2py3.FormatSigFigs(val)
                except TypeError:
                    value = str(val)            
                subSizer2.Add(wx.StaticText(panel2,wx.ID_ANY,value),0,wx.ALIGN_RIGHT)

        # finish up ScrolledPanel
        panel1.SetSizer(subSizer1)
        panel2.SetSizer(subSizer2)
        panel1.SetAutoLayout(1)
        panel1.SetupScrolling()
        panel2.SetAutoLayout(1)
        panel2.SetupScrolling()
        # Allow window to be enlarged but not made smaller
        dlg.SetSizer(mainSizer)
        w1,l1 = subSizer1.GetSize()
        w2,l2 = subSizer2.GetSize()
        panel1.SetMinSize((w1+10,200))
        panel2.SetMinSize((w2+20,200))
        aSizer.Add(panel1,1, wx.ALL|wx.EXPAND,1)
        aSizer.Add(panel2,2, wx.ALL|wx.EXPAND,1)
        mainSizer.Add(aSizer,1, wx.ALL|wx.EXPAND,1)

        # make OK button 
        btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        btn = wx.Button(dlg, wx.ID_CLOSE) 
        btn.Bind(wx.EVT_BUTTON,_onClose)
        btnsizer.Add(btn)
        mainSizer.Add(btnsizer, 0, wx.ALIGN_CENTER|wx.ALL, 5)

        mainSizer.Fit(dlg)
        dlg.SetMinSize(dlg.GetSize())
        dlg.ShowModal()
        dlg.Destroy()
        
    def OnReImport(event):
        generalData = data['General']
        cx,ct,cs,cia = generalData['AtomPtrs']
        reqrdr = G2frame.dataFrame.ReImportMenuId.get(event.GetId())
        rdlist = G2frame.OnImportGeneric(reqrdr,
            G2frame.ImportPhaseReaderlist,'phase')
        if len(rdlist) == 0: return
        # rdlist is only expected to have one element
        rd = rdlist[0]
        G2frame.OnFileSave(event)
        # rd contains all info for a phase
        PhaseName = rd.Phase['General']['Name']
        print 'Read phase '+str(PhaseName)+' from file '+str(G2frame.lastimport)
        atomData = data['Atoms']
        atomNames = []
        All = False
        for atom in atomData:
            atomNames.append(''.join(atom[:ct+1]).capitalize())  #eliminate spurious differences
        for atom in rd.Phase['Atoms']:
            try:
                idx = atomNames.index(''.join(atom[:ct+1]).capitalize())  #eliminate spurious differences
                atId = atom[cia+8]
                atomData[idx][:-1] = atom[:-1]
                atomData[idx][cia+8] = atId
            except ValueError:
                if All:
                    atomData.append(atom)
                else:
                    dlg = wx.MessageDialog(G2frame,'Some atoms not in List; do you want to append them all',   \
                        'Unknown atom '+atom[0],wx.YES_NO|wx.ICON_QUESTION)
                    try:
                        result = dlg.ShowModal()
                        if result in [wx.ID_YES,]:
                            All = True
                            atomData.append(atom)
                        else:
                            print atom[:ct+1], 'not in Atom array; not updated'
                    finally:
                        dlg.Destroy()
        SetupGeneral()
        wx.CallAfter(FillAtomsGrid,Atoms)
        
################################################################################
#### Layer Data page
################################################################################
        
    def UpdateLayerData(Scroll=0):
        
        laueChoice = ['-1','2/m(ab)','2/m(c)','mmm','-3','-3m','4/m','4/mmm',
            '6/m','6/mmm','unknown']
        colLabels = ['Name','Type','x','y','z','frac','Uiso']
        transLabels = ['Prob','Dx','Dy','Dz','refine','plot']
        colTypes = [wg.GRID_VALUE_STRING,wg.GRID_VALUE_STRING,]+ \
            3*[wg.GRID_VALUE_FLOAT+':10,5',]+2*[wg.GRID_VALUE_FLOAT+':10,4',] #x,y,z,frac,Uiso
        transTypes = [wg.GRID_VALUE_FLOAT+':10,3',]+3*[wg.GRID_VALUE_FLOAT+':10,5',]+ \
            [wg.GRID_VALUE_CHOICE+": ,P,Dx,Dy,Dz",wg.GRID_VALUE_BOOL,]
        plotDefaults = {'oldxy':[0.,0.],'Quaternion':[0.,0.,0.,1.],'cameraPos':30.,'viewDir':[0,0,1],
            'viewPoint':[[0.,0.,0.],[]],}
        Indx = {}
        
#        def SetCell(laue,cell):
#            if laue in ['-3','-3m','6/m','6/mmm','4/m','4/mmm']:                    
#                cell[4] = cell[5] = 90.
#                cell[6] = 120.
#                if laue in ['4/m','4/mmm']:
#                    cell[6] = 90.
#                if ObjId == 0:
#                    cell[1] = cell[2] = value
#                    Obj.SetValue("%.5f"%(cell[1]))
#                else:
#                    cell[3] = value
#                    Obj.SetValue("%.5f"%(cell[3]))
#            elif laue in ['mmm']:
#                cell[ObjId+1] = value
#                cell[4] = cell[5] = cell[6] = 90.
#                Obj.SetValue("%.5f"%(cell[ObjId+1]))
#            elif laue in ['2/m','-1']:
#                cell[4] = cell[5] = 90.
#                if ObjId != 3:
#                    cell[ObjId+1] = value
#                    Obj.SetValue("%.5f"%(cell[ObjId+1]))
#                else:
#                    cell[6] = value
#                    Obj.SetValue("%.3f"%(cell[6]))
#            cell[7] = G2lat.calc_V(G2lat.cell2A(cell[1:7]))

        def OnLaue(event):
            Obj = event.GetEventObject()
            data['Layers']['Laue'] = Obj.GetValue()
            wx.CallAfter(UpdateLayerData)
        
        def OnToler(event): #used when Laue = unknown
            event.Skip()
            try:
                val = float(toler.GetValue())
            except ValueError:
                val = Layers['Toler']
            Layers['Toler'] = val
            toler.SetValue('%.3f'%(Layers['Toler']))
            
        def OnSadpPlot(event):
            sadpPlot.SetValue(False)
            labels = Layers['Sadp']['Plane']
            lmax = float(Layers['Sadp']['Lmax'])
            XY = 2*lmax*np.mgrid[0:256:256j,0:256:256j]/256.-lmax
            G2frame.Cmax = 1.0
            G2plt.PlotXYZ(G2frame,XY,Layers['Sadp']['Img'].T,labelX=labels[:-1],
                labelY=labels[-1],newPlot=False,Title=Layers['Sadp']['Plane'])
                
        def OnSeqPlot(event):
            seqPlot.SetValue(False)
            resultXY,resultXY2,seqNames = Layers['seqResults']
            pName = Layers['seqCodes'][0]
            G2plt.PlotXY(G2frame,resultXY,XY2=resultXY2,labelX=r'$\mathsf{2\theta}$',
                labelY='Intensity',newPlot=True,Title='Sequential simulations on '+pName,
                lines=False,names=seqNames)
            
        def CellSizer():
            
            cellGUIlist = [
                [['-3','-3m','6/m','6/mmm','4/m','4/mmm'],6,zip([" a = "," c = "],["%.5f","%.5f",],[True,True],[0,2])],
                [['mmm'],8,zip([" a = "," b = "," c = "],["%.5f","%.5f","%.5f"],[True,True,True],[0,1,2,])],
                [['2/m(ab)','2/m(c)','-1','axial','unknown'],10,zip([" a = "," b = "," c = "," gamma = "],
                    ["%.5f","%.5f","%.5f","%.3f"],[True,True,True,True],[0,1,2,5])]]
                
            def OnCellRef(event):
                data['Layers']['Cell'][0] = cellRef.GetValue()
                
            def OnCellChange(event):
                event.Skip()
                laue = data['Layers']['Laue']
                cell = data['Layers']['Cell']
                Obj = event.GetEventObject()
                ObjId = cellList.index(Obj.GetId())
                try:
                    value = max(1.0,float(Obj.GetValue()))
                except ValueError:
                    if ObjId < 3:               #bad cell edge - reset
                        value = cell[ObjId+1]
                    else:                       #bad angle
                        value = 90.
                if laue in ['-3','-3m','6/m','6/mmm','4/m','4/mmm']:                    
                    cell[4] = cell[5] = 90.
                    cell[6] = 120.
                    if laue in ['4/m','4/mmm']:
                        cell[6] = 90.
                    if ObjId == 0:
                        cell[1] = cell[2] = value
                        Obj.SetValue("%.5f"%(cell[1]))
                    else:
                        cell[3] = value
                        Obj.SetValue("%.5f"%(cell[3]))
                elif laue in ['mmm']:
                    cell[ObjId+1] = value
                    cell[4] = cell[5] = cell[6] = 90.
                    Obj.SetValue("%.5f"%(cell[ObjId+1]))
                elif laue in ['2/m','-1']:
                    cell[4] = cell[5] = 90.
                    if ObjId != 3:
                        cell[ObjId+1] = value
                        Obj.SetValue("%.5f"%(cell[ObjId+1]))
                    else:
                        cell[6] = value
                        Obj.SetValue("%.3f"%(cell[6]))
                cell[7] = G2lat.calc_V(G2lat.cell2A(cell[1:7]))
                volVal.SetLabel(' Vol = %.3f'%(cell[7]))
            
            cell = data['Layers']['Cell']
            laue = data['Layers']['Laue']
            for cellGUI in cellGUIlist:
                if laue in cellGUI[0]:
                    useGUI = cellGUI
            cellSizer = wx.FlexGridSizer(0,useGUI[1]+1,5,5)
            cellRef = wx.CheckBox(layerData,-1,label='Refine unit cell:')
            cellSizer.Add(cellRef,0,WACV)
            cellRef.Bind(wx.EVT_CHECKBOX, OnCellRef)
            cellRef.SetValue(cell[0])
            cellList = []
            for txt,fmt,ifEdit,Id in useGUI[2]:
                cellSizer.Add(wx.StaticText(layerData,label=txt),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                cellVal = wx.TextCtrl(layerData,value=(fmt%(cell[Id+1])),
                    style=wx.TE_PROCESS_ENTER)
                cellVal.Bind(wx.EVT_TEXT_ENTER,OnCellChange)        
                cellVal.Bind(wx.EVT_KILL_FOCUS,OnCellChange)
                cellSizer.Add(cellVal,0,WACV)
                cellList.append(cellVal.GetId())
            volVal = wx.StaticText(layerData,label=' Vol = %.3f'%(cell[7]))
            cellSizer.Add(volVal,0,WACV)
            return cellSizer
            
        def WidthSizer():
            
            def OnWidthChange(event):
                event.Skip()
                Obj = event.GetEventObject()
                id = Indx[Obj]
                try:
                    Layers['Width'][0][id] = max(0.005,min(1.0,float(Obj.GetValue())))
                except ValueError:
                    pass
                Obj.SetValue('%.3f'%(Layers['Width'][0][id]))
                
            def OnRefWidth(event):
                id = Indx[event.GetEventObject()]
                Layers['Width'][1][id] = not Layers['Width'][1][id]
            
            Labels = ['a','b']
            widths = Layers['Width'][0]
            flags = Layers['Width'][1]
            widthSizer = wx.BoxSizer(wx.HORIZONTAL)
            for i in range(2):
                widthSizer.Add(wx.StaticText(layerData,label=u' layer width(%s) (<= 1\xb5m): '%(Labels[i])),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                widthVal = wx.TextCtrl(layerData,value='%.3f'%(widths[i]),style=wx.TE_PROCESS_ENTER)
                widthVal.Bind(wx.EVT_TEXT_ENTER,OnWidthChange)        
                widthVal.Bind(wx.EVT_KILL_FOCUS,OnWidthChange)
                Indx[widthVal] = i
                widthSizer.Add(widthVal,0,WACV)
                widthRef = wx.CheckBox(layerData,label='Refine?')
                widthRef.SetValue(flags[i])
                Indx[widthRef] = i
                widthRef.Bind(wx.EVT_CHECKBOX, OnRefWidth)
                widthSizer.Add(widthRef,0,WACV)
            return widthSizer
            
        def OnNewLayer(event):
            data['Layers']['Layers'].append({'Name':'Unk','SameAs':'','Symm':'None','Atoms':[]})
            Trans = data['Layers']['Transitions']
            if len(Trans):
                Trans.append([[0.,0.,0.,0.,'',False] for trans in Trans])
                for trans in Trans:
                    trans.append([0.,0.,0.,0.,'',False])
            else:
                Trans = [[[1.,0.,0.,0.,'',False],],]
            data['Layers']['Transitions'] = Trans
            UpdateLayerData()
            
        def OnDeleteLast(event):
            del(data['Layers']['Layers'][-1])
            del(data['Layers']['Transitions'][-1])
            for trans in data['Layers']['Transitions']:
                del trans[-1]
            UpdateLayerData()
                
        def OnImportLayer(event):
            dlg = wx.FileDialog(G2frame, 'Choose GSAS-II project file', 
                wildcard='GSAS-II project file (*.gpx)|*.gpx',style=wx.OPEN| wx.CHANGE_DIR)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    GPXFile = dlg.GetPath()
                    phaseNames = G2strIO.GetPhaseNames(GPXFile)
                else:
                    return
            finally:
                dlg.Destroy()
            dlg = wx.SingleChoiceDialog(G2frame,'Phase to use for layer','Select',phaseNames)
            if dlg.ShowModal() == wx.ID_OK:
                sel = dlg.GetSelection()
                PhaseName = phaseNames[sel]
            else:
                return
            Phase = G2strIO.GetAllPhaseData(GPXFile,PhaseName)
            #need cell compatibility check here
            Layer = {'Name':Phase['General']['Name'],'SameAs':'','Symm':'None'}
            cx,ct,cs,cia = Phase['General']['AtomPtrs']
            atoms = Phase['Atoms']
            Atoms = []
            for atom in atoms:
                x,y,z,f = atom[cx:cx+4]
                u = atom[cia+1]
                if not u: u = 0.01
                Atoms.append([atom[ct-1],atom[ct],x,y,z,f,u])
                if atom[ct] not in data['Layers']['AtInfo']:
                    data['Layers']['AtInfo'][atom[ct]] = G2elem.GetAtomInfo(atom[ct])
            Layer['Atoms'] = Atoms
            data['Layers']['Layers'].append(Layer)
            Trans = data['Layers']['Transitions']
            if len(Trans):
                Trans.append([[0.,0.,0.,0.,'',False] for trans in Trans])
                for trans in Trans:
                    trans.append([0.,0.,0.,0.,'',False])
            else:
                Trans = [[[1.,0.,0.,0.,'',False],],]
            data['Layers']['Transitions'] = Trans
            UpdateLayerData()
            
        def LayerSizer(il,Layer):
            
            def OnNameChange(event):
                event.Skip()
                Layer['Name'] = layerName.GetValue()                
                UpdateLayerData()
                
            def OnAddAtom(event):
                Layer['Atoms'].append(['Unk','Unk',0.,0.,0.,1.,0.01])
                UpdateLayerData()
                
            def OnSymm(event):
                Layer['Symm'] = symm.GetValue()
            
            def AtomTypeSelect(event):
                r,c =  event.GetRow(),event.GetCol()
                if atomGrid.GetColLabelValue(c) == 'Type':
                    PE = G2elemGUI.PickElement(G2frame)
                    if PE.ShowModal() == wx.ID_OK:
                        if PE.Elem != 'None':
                            atType = PE.Elem.strip()       
                            Layer['Atoms'][r][c] = atType
                            name = Layer['Atoms'][r][c]
                            if len(name) in [2,4]:
                                Layer['Atoms'][r][c-1] = name[:2]+'%d'%(r+1)
                            else:
                                Layer['Atoms'][r][c-1] = name[:1]+'%d'%(r+1)
                            if atType not in data['Layers']['AtInfo']:
                                data['Layers']['AtInfo'][atType] = G2elem.GetAtomInfo(atType)
                    PE.Destroy()
                    UpdateLayerData()
                else:
                    event.Skip()
                    
            def OnDrawLayer(event):
                drawLayer.SetValue(False)
                G2plt.PlotLayers(G2frame,Layers,[il,],plotDefaults)
                
            def OnSameAs(event):
                Layer['SameAs'] = sameas.GetValue()
                wx.CallAfter(UpdateLayerData)
                    
            layerSizer = wx.BoxSizer(wx.VERTICAL)
            nameSizer = wx.BoxSizer(wx.HORIZONTAL)            
            nameSizer.Add(wx.StaticText(layerData,label=' Layer name: '),0,WACV)
            layerName = wx.TextCtrl(layerData,value=Layer['Name'],style=wx.TE_PROCESS_ENTER)
            layerName.Bind(wx.EVT_TEXT_ENTER,OnNameChange)        
            layerName.Bind(wx.EVT_KILL_FOCUS,OnNameChange)
            nameSizer.Add(layerName,0,WACV)
            if il:
                nameSizer.Add(wx.StaticText(layerData,label=' Same as: '),0,WACV)
                sameas = wx.ComboBox(layerData,value=Layer['SameAs'],choices=['',]+layerNames[:-1],
                    style=wx.CB_READONLY|wx.CB_DROPDOWN)
                sameas.Bind(wx.EVT_COMBOBOX, OnSameAs)
                nameSizer.Add(sameas,0,WACV)
                if Layer['SameAs']:
                    indx = layerNames.index(Layer['SameAs'])
                    if indx < il:    #previously used : same layer
                        layerSizer.Add(nameSizer)
                        return layerSizer
            nameSizer.Add(wx.StaticText(layerData,label=' Layer symmetry: '),0,WACV)
            symmChoice = ['-1','None']
            symm = wx.ComboBox(layerData,value=Layer['Symm'],choices=symmChoice,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            symm.Bind(wx.EVT_COMBOBOX,OnSymm)
            nameSizer.Add(symm,0,WACV)
            addAtom = wx.CheckBox(layerData,label=' Add atom? ')
            addAtom.Bind(wx.EVT_CHECKBOX, OnAddAtom)
            nameSizer.Add(addAtom,0,WACV)
            drawLayer = wx.CheckBox(layerData,label=' Draw layer? ')
            drawLayer.Bind(wx.EVT_CHECKBOX, OnDrawLayer)
            nameSizer.Add(drawLayer,0,WACV)
            layerSizer.Add(nameSizer)
            table = []
            rowLabels = []
            for i,atom in enumerate(Layer['Atoms']):
                table.append(atom)
                rowLabels.append(str(i))
            atomTable = G2G.Table(table,rowLabels=rowLabels,colLabels=colLabels,types=colTypes)
            atomGrid = G2G.GSGrid(layerData)
            atomGrid.SetTable(atomTable,True)
            atomGrid.SetScrollRate(0,0)    #get rid of automatic scroll bars
            for c in range(2,5):
                attr = wx.grid.GridCellAttr()
                attr.IncRef()               #fix from Jim Hester
                attr.SetEditor(G2G.GridFractionEditor(atomGrid))
                atomGrid.SetColAttr(c, attr)
            atomGrid.Bind(wg.EVT_GRID_CELL_LEFT_DCLICK, AtomTypeSelect)
            atomGrid.AutoSizeColumns(True)
            layerSizer.Add(atomGrid)
            return layerSizer
            
        def TransSizer():
            
            def PlotSelect(event):
                Obj = event.GetEventObject()
                Yi = Indx[Obj.GetId()]               
                Xi,c =  event.GetRow(),event.GetCol()
                if Xi >= 0 and c == 5:   #plot column
                    G2plt.PlotLayers(G2frame,Layers,[Yi,Xi,],plotDefaults)
                else:
                    Psum = 0.
                    for Xi in range(len(transArray)):
                        Psum += transArray[Xi][Xi][0]
                    Psum /= len(transArray)
                    totalFault.SetLabel(' Total fault density = %.3f'%(1.-Psum))
                    event.Skip()
                    
            def OnNormProb(event):
                for Yi,Yname in enumerate(Names):
                    Psum = 0.
                    for Xi,Xname in enumerate(Names):
                        Psum += transArray[Yi][Xi][0]
                    if not Psum:
                        transArray[Yi][0][0] = 1.0
                        Psum = 1.0
                    for Xi,Xname in enumerate(Names):
                        transArray[Yi][Xi][0] /= Psum
                wx.CallAfter(UpdateLayerData)
                
            def OnSymProb(event):
                if symprob.GetValue():
                    Nx = len(Names)-1
                    Layers['SymTrans'] = True
                    for Yi,Yname in enumerate(Names):
                        for Xi,Xname in enumerate(Names):
                            if transArray[Nx-Yi][Nx-Xi][0] != transArray[Yi][Xi][0]:
                                Layers['SymTrans'] = False
                                symprob.SetValue(False)
                                wx.MessageBox('%s-%s not equal %s-%s'%(Yname,Xname,Xname,Yname),
                                    caption='Probability symmetry error',style=wx.ICON_EXCLAMATION)
                                break
                else:
                    Layers['SymTrans'] = False
            
            transSizer = wx.BoxSizer(wx.VERTICAL)
            transSizer.Add(wx.StaticText(layerData,label=' Layer-Layer transition probabilities: '),0,WACV)
            topSizer = wx.BoxSizer(wx.HORIZONTAL)
            normprob = wx.CheckBox(layerData,label=' Normalize probabilities?')
            normprob.Bind(wx.EVT_CHECKBOX,OnNormProb)
            topSizer.Add(normprob,0,WACV)
            symprob = wx.CheckBox(layerData,label=' Symmetric probabilities?')
            symprob.SetValue(Layers.get('SymTrans',False))
            symprob.Bind(wx.EVT_CHECKBOX,OnSymProb)
            topSizer.Add(symprob,0,WACV)
            transSizer.Add(topSizer,0,WACV)
            Names = [layer['Name'] for layer in Layers['Layers']]
            transArray = Layers['Transitions']
            layerData.transGrids = []
            if not Names or not transArray:
                return transSizer
            diagSum = 0.
            for Yi,Yname in enumerate(Names):
                transSizer.Add(wx.StaticText(layerData,label=' From %s to:'%(Yname)),0,WACV)
                table = []
                rowLabels = []
                diagSum += transArray[Yi][Yi][0]
                for Xi,Xname in enumerate(Names):
                    table.append(transArray[Yi][Xi])
                    rowLabels.append(Xname)
                    if transArray[Yi][Xi][0] > 0.:
                        Layers['allowedTrans'].append([str(Yi+1),str(Xi+1)])
                transTable = G2G.Table(table,rowLabels=rowLabels,colLabels=transLabels,types=transTypes)
                transGrid = G2G.GSGrid(layerData)
                transGrid.SetTable(transTable,True)
                transGrid.SetScrollRate(0,0)    #get rid of automatic scroll bars
                Indx[transGrid.GetId()] = Yi
                for c in range(0,4):
                    attr = wx.grid.GridCellAttr()
                    attr.IncRef()               #fix from Jim Hester
                    attr.SetEditor(G2G.GridFractionEditor(transGrid))
                    transGrid.SetColAttr(c, attr)
                transGrid.Bind(wg.EVT_GRID_CELL_LEFT_CLICK, PlotSelect)
                transGrid.AutoSizeColumns(True)
                transSizer.Add(transGrid)
                layerData.transGrids.append(transGrid)
            if len(transArray):
                diagSum /= len(transArray)
                totalFault = wx.StaticText(layerData,
                    label=' Total fault density = %.3f'%(1.-diagSum))
                transSizer.Add(totalFault,0,WACV)
            return transSizer
            
        def PlotSizer():
            
            def OnPlotSeq(event):
                event.Skip()
                vals = plotSeq.GetValue().split()
                try:
                    vals = [int(val)-1 for val in vals]
                    if not all([0 <= val < len(Names) for val in vals]):
                        raise ValueError
                except ValueError:
                    plotSeq.SetValue('Error in string '+plotSeq.GetValue())
                    return
                G2plt.PlotLayers(G2frame,Layers,vals,plotDefaults)
            
            Names = [' %s: %d,'%(layer['Name'],iL+1) for iL,layer in enumerate(Layers['Layers'])]
            plotSizer = wx.BoxSizer(wx.VERTICAL)
            Str = ' Using sequence nos. from:'
            for name in Names:
                Str += name
            plotSizer.Add(wx.StaticText(layerData,label=Str[:-1]),0,WACV)
            lineSizer = wx.BoxSizer(wx.HORIZONTAL)
            lineSizer.Add(wx.StaticText(layerData,label=' Enter sequence of layers to plot:'),0,WACV)
            plotSeq = wx.TextCtrl(layerData,value = '',style=wx.TE_PROCESS_ENTER)
            plotSeq.Bind(wx.EVT_TEXT_ENTER,OnPlotSeq)        
            plotSeq.Bind(wx.EVT_KILL_FOCUS,OnPlotSeq)
            lineSizer.Add(plotSeq,0,WACV)
            plotSizer.Add(lineSizer,0,WACV)
            return plotSizer
            
        def StackSizer():
            
            stackChoice = ['recursive','explicit',]
            seqChoice = ['random','list',]
                      
            def OnStackType(event):
                newType = stackType.GetValue()
                if newType == data['Layers']['Stacking'][0]:
                    return                    
                data['Layers']['Stacking'][0] = newType
                if newType == 'recursive':
                    data['Layers']['Stacking'][1] = 'infinite'
                else:  #explicit
                    data['Layers']['Stacking'][1] = 'random'
                    data['Layers']['Stacking'][2] = '250'
                wx.CallAfter(UpdateLayerData)
                
            def OnSeqType(event):
                newType = seqType.GetValue()
                if newType == data['Layers']['Stacking'][1]:
                    return
                data['Layers']['Stacking'][1] = newType
                if newType == 'random':
                    data['Layers']['Stacking'][2] = '250'
                else: #List
                    data['Layers']['Stacking'][2] = ''
                wx.CallAfter(UpdateLayerData)
                
            def OnNumLayers(event):
                event.Skip()
                val = numLayers.GetValue()
                if val == 'infinite':
                    data['Layers']['Stacking'][1] = val
                else:
                    try:
                        if 0 < int(val) < 1023:
                            data['Layers']['Stacking'][1] = val
                        else:
                            data['Layers']['Stacking'][1] = 'infinite'
                    except ValueError:
                        pass
                numLayers.SetValue(data['Layers']['Stacking'][1])
                
            def OnNumRan(event):
                event.Skip()
                val = numRan.GetValue()
                try:
                    if 0 > int(val) > 1022:
                        raise ValueError
                    else:
                        data['Layers']['Stacking'][2] = val
                except ValueError:
                    val = data['Layers']['Stacking'][2]
                numRan.SetValue(val)
                
            def OnStackList(event):
                event.Skip()
                stack = stackList.GetValue()
                stack = stack.replace('\n',' ').strip().strip('\n')
                nstar = stack.count('*')
                if nstar:
                    try:
                        newstack = ''
                        Istar = 0
                        for star in range(nstar):
                            Istar = stack.index('*',Istar+1)
                            iB = stack[:Istar].rfind(' ')
                            if iB == -1:
                                mult = int(stack[:Istar])
                            else:
                                mult = int(stack[iB:Istar])
                            pattern = stack[Istar+2:stack.index(')',Istar)]+' '
                            newstack += mult*pattern
                        stack = newstack
                    except ValueError:
                        stack += ' Error in string'
                Slist = stack.split()
                if len(Slist) < 2:
                    stack = 'Error in sequence - too short!'
                OKlist = [Slist[i:i+2] in Layers['allowedTrans'] for i in range(len(Slist[:-1]))]
                if all(OKlist):
                    data['Layers']['Stacking'][2] = stack
                else:
                    stack = 'Improbable sequence or bad string'
                stackList.SetValue(stack)
            
            stackSizer = wx.BoxSizer(wx.VERTICAL)
            stackSizer.Add(wx.StaticText(layerData,label=' Layer stacking parameters:'),0,WACV)
            if not Layers['Stacking']:
                Layers['Stacking'] = ['recursive','infinite','']
            topLine = wx.BoxSizer(wx.HORIZONTAL)
            topLine.Add(wx.StaticText(layerData,label=' Stacking type: '),0,WACV)
            stackType = wx.ComboBox(layerData,value=Layers['Stacking'][0],choices=stackChoice,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            stackType.Bind(wx.EVT_COMBOBOX,OnStackType)
            topLine.Add(stackType,0,WACV)
            if Layers['Stacking'][0] == 'recursive':
                topLine.Add(wx.StaticText(layerData,label=' number of layers (<1022 or "infinite"): '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                numLayers = wx.TextCtrl(layerData,value=data['Layers']['Stacking'][1],style=wx.TE_PROCESS_ENTER)
                numLayers.Bind(wx.EVT_TEXT_ENTER,OnNumLayers)        
                numLayers.Bind(wx.EVT_KILL_FOCUS,OnNumLayers)
                topLine.Add(numLayers,0,WACV)
                stackSizer.Add(topLine)
            elif Layers['Stacking'][0] == 'explicit':
                topLine.Add(wx.StaticText(layerData,label=' layer sequence: '),0,WACV)
                seqType = wx.ComboBox(layerData,value=data['Layers']['Stacking'][1],choices=seqChoice,
                    style=wx.CB_READONLY|wx.CB_DROPDOWN)
                seqType.Bind(wx.EVT_COMBOBOX,OnSeqType)
                topLine.Add(seqType,0,WACV)
                if Layers['Stacking'][1] == 'list':
                    stackSizer.Add(topLine,0,WACV)
                    Names = [' %s: %d,'%(layer['Name'],iL+1) for iL,layer in enumerate(Layers['Layers'])]
                    stackSizer.Add(wx.StaticText(layerData,label=' Explicit layer sequence; enter space delimited list of numbers:'),0,WACV)
                    Str = ' Use sequence nos. from:'
                    for name in Names:
                        Str += name
                    stackSizer.Add(wx.StaticText(layerData,label=Str[:-1]+' Repeat sequences can be used: e.g. 6*(1 2) '),0,WACV)
                    stackSizer.Add(wx.StaticText(layerData,label=' Zero probability sequences not allowed'),0,WACV)    
                    stackList = wx.TextCtrl(layerData,value=Layers['Stacking'][2],size=(600,-1),
                        style=wx.TE_MULTILINE|wx.TE_PROCESS_ENTER)
                    stackList.Bind(wx.EVT_TEXT_ENTER,OnStackList)        
                    stackList.Bind(wx.EVT_KILL_FOCUS,OnStackList)
                    stackSizer.Add(stackList,0,wx.ALL|wx.EXPAND|WACV,8)
                else:   #random
                    topLine.Add(wx.StaticText(layerData,label=' Length of random sequence: '),0,WACV)
                    numRan = wx.TextCtrl(layerData,value=Layers['Stacking'][2],style=wx.TE_PROCESS_ENTER)
                    numRan.Bind(wx.EVT_TEXT_ENTER,OnNumRan)        
                    numRan.Bind(wx.EVT_KILL_FOCUS,OnNumRan)
                    topLine.Add(numRan,0,WACV)
                    stackSizer.Add(topLine,0,WACV)
            return stackSizer
            
        Layers = data['Layers']
        layerNames = []
        Layers['allowedTrans'] = []
        if len(Layers['Layers']):
            layerNames = [layer['Name'] for layer in Layers['Layers']]
        G2frame.dataFrame.SetStatusText('')
        layerData = G2frame.layerData
        if layerData.GetSizer():
            layerData.GetSizer().Clear(True)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        topSizer = wx.BoxSizer(wx.VERTICAL)   
        bottomSizer = wx.BoxSizer(wx.VERTICAL)
        headSizer = wx.BoxSizer(wx.HORIZONTAL)  
        headSizer.Add(wx.StaticText(layerData,label=' Global layer description:  '),0,WACV)
        if 'Sadp' in Layers:
            sadpPlot = wx.CheckBox(layerData,label=' Plot selected area diffraction?')
            sadpPlot.Bind(wx.EVT_CHECKBOX,OnSadpPlot)
            headSizer.Add(sadpPlot,0,WACV)
        if 'seqResults' in Layers:
            seqPlot = wx.CheckBox(layerData,label=' Plot sequential result?')
            seqPlot.Bind(wx.EVT_CHECKBOX,OnSeqPlot)
            headSizer.Add(seqPlot,0,WACV)
        topSizer.Add(headSizer)
        laueSizer = wx.BoxSizer(wx.HORIZONTAL)
        laueSizer.Add(wx.StaticText(layerData,label=' Diffraction Laue symmetry:'),0,WACV)
        laue = wx.ComboBox(layerData,value=Layers['Laue'],choices=laueChoice,
            style=wx.CB_READONLY|wx.CB_DROPDOWN)
        laue.Bind(wx.EVT_COMBOBOX,OnLaue)
        laueSizer.Add(laue,0,WACV)
        if Layers['Laue'] == 'unknown':
            laueSizer.Add(wx.StaticText(layerData,label=' Diffraction symmetry tolerance: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            toler = wx.TextCtrl(layerData,value='%.3f'%(Layers['Toler']),style=wx.TE_PROCESS_ENTER)
            toler.Bind(wx.EVT_TEXT_ENTER,OnToler)        
            toler.Bind(wx.EVT_KILL_FOCUS,OnToler)
            laueSizer.Add(toler,0,WACV)
        topSizer.Add(laueSizer,0,WACV)
        topSizer.Add(wx.StaticText(layerData,label=' Reference unit cell for all layers:'),0,WACV)
        topSizer.Add(CellSizer(),0,WACV)
        topSizer.Add(WidthSizer())
        topSizer.Add(wx.StaticText(layerData,label=' NB: stacking fault refinement currently not available'),0,WACV)
        G2G.HorizontalLine(topSizer,layerData)
        titleSizer = wx.BoxSizer(wx.HORIZONTAL)
        titleSizer.Add(wx.StaticText(layerData,label=' Layer descriptions: '),0,WACV)
        newLayer = wx.CheckBox(layerData,label=' Add new layer?')
        newLayer.Bind(wx.EVT_CHECKBOX, OnNewLayer)
        titleSizer.Add(newLayer,0,WACV)
        importLayer = wx.CheckBox(layerData,label=' Import new layer?')
        importLayer.Bind(wx.EVT_CHECKBOX, OnImportLayer)
        titleSizer.Add(importLayer,0,WACV)
        deleteLast = wx.CheckBox(layerData,label=' Delete last layer?')
        deleteLast.Bind(wx.EVT_CHECKBOX, OnDeleteLast)
        titleSizer.Add(deleteLast,0,WACV)
        topSizer.Add(titleSizer,0,WACV)
        for il,layer in enumerate(Layers['Layers']):
            topSizer.Add(LayerSizer(il,layer))
        G2G.HorizontalLine(topSizer,layerData)
        mainSizer.Add(topSizer)
        bottomSizer.Add(TransSizer())
        G2G.HorizontalLine(bottomSizer,layerData)
        bottomSizer.Add(PlotSizer(),0,WACV)
        G2G.HorizontalLine(bottomSizer,layerData)
        bottomSizer.Add(StackSizer())
        mainSizer.Add(bottomSizer)
        SetPhaseWindow(G2frame.dataFrame,G2frame.layerData,mainSizer,Scroll)
        
    def OnCopyPhase(event):
        dlg = wx.FileDialog(G2frame, 'Choose GSAS-II project file', 
            wildcard='GSAS-II project file (*.gpx)|*.gpx',style=wx.OPEN| wx.CHANGE_DIR)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                GPXFile = dlg.GetPath()
                phaseNames = G2strIO.GetPhaseNames(GPXFile)
            else:
                return
        finally:
            dlg.Destroy()
        dlg = wx.SingleChoiceDialog(G2frame,'Phase to use for cell data','Select',phaseNames)
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelection()
            PhaseName = phaseNames[sel]
        else:
            return
        General = G2strIO.GetAllPhaseData(GPXFile,PhaseName)['General']
        data['Layers']['Cell'] = General['Cell']
        wx.CallAfter(UpdateLayerData)

    def OnLoadDIFFaX(event):
        if len(data['Layers']['Layers']):
            dlg = wx.MessageDialog(G2frame,'Do you really want to replace the Layer data?','Load DIFFaX file', 
                wx.YES_NO | wx.ICON_QUESTION)
            try:
                result = dlg.ShowModal()
                if result == wx.ID_NO:
                    return
            finally:
                dlg.Destroy()
        dlg = wx.FileDialog(G2frame, 'Choose DIFFaX file name to read', '.', '',
            'DIFFaX file (*.*)|*.*',style=wx.OPEN | wx.CHANGE_DIR)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                DIFFaXfile = dlg.GetPath()
                data['Layers'] = G2IO.ReadDIFFaX(DIFFaXfile)
        finally:
            dlg.Destroy()
        wx.CallAfter(UpdateLayerData)
        
    def OnSimulate(event):
        debug = False       #set True to run DIFFax to compare/debug (must be in bin)
        idebug = 0
        if debug: idebug = 1
        ctrls = ''
        dlg = G2gd.DIFFaXcontrols(G2frame,ctrls)
        if dlg.ShowModal() == wx.ID_OK:
            simCodes = dlg.GetSelection()
        else:
            return
        if 'PWDR' in  simCodes[0]:    #powder pattern
            data['Layers']['selInst'] = simCodes[1]
            UseList = []
            for item in data['Histograms']:
                if 'PWDR' in item:
                    UseList.append(item)
            if not UseList:
                wx.MessageBox('No PWDR data for this phase to simulate',caption='Data error',style=wx.ICON_EXCLAMATION)
                return
            dlg = wx.SingleChoiceDialog(G2frame,'Data to simulate','Select',UseList)
            if dlg.ShowModal() == wx.ID_OK:
                sel = dlg.GetSelection()
                HistName = UseList[sel]
            else:
                return
            dlg.Destroy()
            G2frame.PatternId = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,HistName)
            sample = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(
                G2frame,G2frame.PatternId, 'Sample Parameters'))
            scale = sample['Scale'][0]
            background = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(
                G2frame,G2frame.PatternId, 'Background'))        
            limits = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(
                G2frame,G2frame.PatternId, 'Limits'))[1]
            inst = G2frame.PatternTree.GetItemPyData(
                G2gd.GetPatternTreeItemId(G2frame,G2frame.PatternId, 'Instrument Parameters'))[0]
            if 'T' in inst['Type'][0]:
                wx.MessageBox("Can't simulate neutron TOF patterns yet",caption='Data error',style=wx.ICON_EXCLAMATION)
                return            
            profile = G2frame.PatternTree.GetItemPyData(G2frame.PatternId)[1]
            G2pwd.CalcStackingPWDR(data['Layers'],scale,background,limits,inst,profile,debug)
            if debug:
                ctrls = '0\n%d\n3\n'%(idebug)
                G2pwd.StackSim(data['Layers'],ctrls,scale,background,limits,inst,profile)
                test1 = np.copy(profile[3])
                test1 = np.where(test1,test1,1.0)
                G2pwd.CalcStackingPWDR(data['Layers'],scale,background,limits,inst,profile,debug)
                test2 = np.copy(profile[3])
                rat = test1-test2
                XY = np.vstack((profile[0],rat))
                G2plt.PlotXY(G2frame,[XY,],XY2=[],labelX=r'$\mathsf{2\theta}$',
                    labelY='difference',newPlot=True,Title='DIFFaX vs GSASII',lines=True)
#            GSASIIpath.IPyBreak()
            G2plt.PlotPatterns(G2frame,plotType='PWDR')
        else:   #selected area
            data['Layers']['Sadp'] = {}
            data['Layers']['Sadp']['Plane'] = simCodes[1]
            data['Layers']['Sadp']['Lmax'] = simCodes[2]
            if debug:
                planeChoice = ['h0l','0kl','hhl','h-hl',]
                lmaxChoice = [str(i+1) for i in range(6)]
                ctrls = '0\n%d\n4\n1\n%d\n%d\n16\n1\n1\n0\nend\n'%    \
                    (idebug,planeChoice.index(simCodes[1])+1,lmaxChoice.index(simCodes[2])+1)
                G2pwd.StackSim(data['Layers'],ctrls)
            G2pwd.CalcStackingSADP(data['Layers'],debug)
        wx.MessageBox('Simulation finished',caption='Stacking fault simulation',style=wx.ICON_EXCLAMATION)
        wx.CallAfter(UpdateLayerData)
        
    def OnSeqSimulate(event):
        
        cellSel = ['cellA','cellB','cellC','cellG']
        transSel = ['TransP','TransX','TransY','TransZ']
        ctrls = ''
        cell = data['Layers']['Cell']
        data['Layers']['seqResults'] = []
        data['Layers']['seqCodes'] = []
        Parms = G2pwd.GetStackParms(data['Layers'])
        dlg = G2gd.DIFFaXcontrols(G2frame,ctrls,Parms)
        if dlg.ShowModal() == wx.ID_OK:
            simCodes = dlg.GetSelection()
        else:
            return
        UseList = []
        for item in data['Histograms']:
            if 'PWDR' in item:
                UseList.append(item)
        if not UseList:
            wx.MessageBox('No PWDR data for this phase to simulate',caption='Data error',style=wx.ICON_EXCLAMATION)
            return
        dlg = wx.SingleChoiceDialog(G2frame,'Data to simulate','Select',UseList)
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelection()
            HistName = UseList[sel]
        else:
            return
        dlg.Destroy()
        G2frame.PatternId = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,HistName)
        sample = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(
            G2frame,G2frame.PatternId, 'Sample Parameters'))
        scale = sample['Scale'][0]
        background = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(
            G2frame,G2frame.PatternId, 'Background'))        
        limits = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(
            G2frame,G2frame.PatternId, 'Limits'))[1]
        inst = G2frame.PatternTree.GetItemPyData(
            G2gd.GetPatternTreeItemId(G2frame,G2frame.PatternId, 'Instrument Parameters'))[0]
        if 'T' in inst['Type'][0]:
            wx.MessageBox("Can't simulate neutron TOF patterns yet",caption='Data error',style=wx.ICON_EXCLAMATION)
            return            
        profile = np.copy(G2frame.PatternTree.GetItemPyData(G2frame.PatternId)[1])
        resultXY2 = []
        resultXY = [np.vstack((profile[0],profile[1])),]    #observed data
        data['Layers']['selInst'] = simCodes[1]
        data['Layers']['seqCodes'] = simCodes[2:]
        Layers = copy.deepcopy(data['Layers'])
        pName = simCodes[2]
        BegFin = simCodes[3]
        nSteps = simCodes[4]
        laue = Layers['Laue']
        vals = np.linspace(BegFin[0],BegFin[1],nSteps+1,True)
        simNames = []
        for val in vals:
            print ' Stacking simulation step for '+pName+' = %.5f'%(val)
            simNames.append('%.3f'%(val))
            if 'cell' in pName:
                cellId = cellSel.index(pName)
                cell = Layers['Cell']
                cell[cellId+1] = val
                if laue in ['-3','-3m','6/m','6/mmm','4/m','4/mmm']:                    
                    cell[2] = cell[1]
                cell[7] = G2lat.calc_V(G2lat.cell2A(cell[1:7]))
                Layers['Cell'] = cell
            elif 'Trans' in pName:
                names = pName.split(';')
                transId = transSel.index(names[0])
                iY = int(names[1])
                iX = int(names[2])
                Trans = Layers['Transitions'][iY]
                Nx = len(Trans)-1
                if not transId:     #i.e. probability
                    osum = 1.-Trans[iX][0]
                    nsum = 1.-val
                    for i in range(Nx+1):
                        if i != iX:
                            Trans[i][0] *= (nsum/osum)
                    Trans[iX][0] = val
                    if Layers.get('SymTrans',False):
                        Layers['Transitions'][Nx-iX][Nx-iY][0] = val
                        for i in range(Nx+1):
                            Layers['Transitions'][Nx-iY][Nx-i][0] = Layers['Transitions'][iY][i][0]
                    print ' Transition matrix:'
                    for trans in Layers['Transitions']:
                        line = str([' %.3f'%(item[0]) for item in trans])
                        print line[1:-2].replace("'",'')
                else:
                    Trans[iX][transId] = val
            G2pwd.CalcStackingPWDR(Layers,scale,background,limits,inst,profile,False)
            resultXY2.append([np.vstack((profile[0],profile[3])),][0])
        data['Layers']['seqResults'] = [resultXY,resultXY2,simNames]
        wx.MessageBox('Sequential simulation finished',caption='Stacking fault simulation',style=wx.ICON_EXCLAMATION)
        wx.CallAfter(UpdateLayerData)
        
################################################################################
#### Wave Data page
################################################################################

    def UpdateWavesData(Scroll=0):
        
        generalData = data['General']
        cx,ct,cs,cia = generalData['AtomPtrs']
        typeNames = {'Sfrac':' Site fraction','Spos':' Position','Sadp':' Thermal motion','Smag':' Magnetic moment'}
        numVals = {'Sfrac':2,'Spos':6,'Sadp':12,'Smag':6,'ZigZag':5,'Block':5}
        posNames = ['Xsin','Ysin','Zsin','Xcos','Ycos','Zcos','Tmin','Tmax','Xmax','Ymax','Zmax']
        adpNames = ['U11sin','U22sin','U33sin','U12sin','U13sin','U23sin',
            'U11cos','U22cos','U33cos','U12cos','U13cos','U23cos']
        magNames = ['MXsin','MYsin','MZsin','MXcos','MYcos','MZcos']
        fracNames = ['Fsin','Fcos','Fzero','Fwid']
        waveTypes = ['Fourier','ZigZag','Block','Crenel/Fourier']
        Labels = {'Spos':posNames,'Sfrac':fracNames,'Sadp':adpNames,'Smag':magNames}
        Indx = {}
        waveData = G2frame.waveData
        G2frame.dataFrame.SetStatusText('')
        generalData = data['General']
        SGData = generalData['SGData']
        SSGData = generalData['SSGData']
        cx,ct,cs,cia = generalData['AtomPtrs']
        atomData = data['Atoms']
        D4Map = generalData['4DmapData']
        if waveData.GetSizer():
            waveData.GetSizer().Clear(True)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        topSizer = wx.BoxSizer(wx.HORIZONTAL)   
        topSizer.Add(wx.StaticText(waveData,label=' Incommensurate propagation wave data: Select atom to edit: '),0,WACV)
        atNames = []
        for atm in atomData:
            atNames.append(atm[ct-1])
        if not atNames:
            return
        if G2frame.atmSel not in atNames:
            G2frame.atmSel = atNames[0]
        
        def OnAtmSel(event):
            Obj = event.GetEventObject()
            G2frame.atmSel = Obj.GetValue()
            RepaintAtomInfo()
            
        def RepaintAtomInfo(Scroll=0):
#            mainSizer.Detach(G2frame.bottomSizer)
            G2frame.bottomSizer.Clear(True)
            G2frame.bottomSizer = ShowAtomInfo()
            mainSizer.Add(G2frame.bottomSizer)
            mainSizer.Layout()
            G2frame.dataFrame.Refresh()
            waveData.SetVirtualSize(mainSizer.GetMinSize())
            waveData.Scroll(0,Scroll)
            G2frame.dataFrame.SendSizeEvent()
            
        def ShowAtomInfo():
            
            def AtomSizer(atom):
                
                def OnWaveType(event):
                    atom[-1]['SS1']['waveType'] = waveType.GetValue()
                    atom[-1]['SS1']['Spos'] = []
                    RepaintAtomInfo(G2frame.waveData.GetScrollPos(wx.VERTICAL))                
                    
                def OnShowWave(event):
                    Obj = event.GetEventObject()
                    atom = Indx[Obj.GetId()]               
                    Ax = Obj.GetValue()
                    G2plt.ModulationPlot(G2frame,data,atom,Ax)
                    
                atomSizer = wx.BoxSizer(wx.HORIZONTAL)
                atomSizer.Add(wx.StaticText(waveData,label=
                ' Modulation data for atom: %s  Site sym: %s  WaveType: '%(atom[0],atom[cs].strip())),0,WACV)            
                waveType = wx.ComboBox(waveData,value=atom[-1]['SS1']['waveType'],choices=waveTypes,
                    style=wx.CB_READONLY|wx.CB_DROPDOWN)
                waveType.Bind(wx.EVT_COMBOBOX,OnWaveType)
                atomSizer.Add(waveType,0,WACV)
                axchoice = ['x','y','z']
                if len(D4Map['rho']):
                    atomSizer.Add(wx.StaticText(waveData,label=' Show contour map for axis: '),0,WACV)
                    mapSel = wx.ComboBox(waveData,value=' ',choices=axchoice,
                        style=wx.CB_READONLY|wx.CB_DROPDOWN)
                    mapSel.Bind(wx.EVT_COMBOBOX,OnShowWave)
                    Indx[mapSel.GetId()] = atom
                    atomSizer.Add(mapSel,0,WACV)
                return atomSizer
                
            def WaveSizer(iatm,waveType,waveBlk,Stype,typeName,Names):
                
                def OnAddWave(event):
                    Obj = event.GetEventObject()
                    iatm,item = Indx[Obj.GetId()]
                    nt = numVals[Stype]
                    if not len(atomData[iatm][-1]['SS1'][item]) and waveType in ['ZigZag','Block'] and Stype == 'Spos':
                        nt = numVals[waveType]
                    atomData[iatm][-1]['SS1'][item].append([[0.0 for i in range(nt)],False])
                    RepaintAtomInfo(G2frame.waveData.GetScrollPos(wx.VERTICAL))
                    
                def OnWaveVal(event):
                    event.Skip()
                    Obj = event.GetEventObject()
                    iatm,item,iwave,ival = Indx[Obj.GetId()]
                    try:
                        val = float(Obj.GetValue())
                        if waveType in ['ZigZag','Block'] and Stype == 'Spos' and ival < 2 and not iwave:
                            if ival == 1: #Tmax
                                val = min(1.0,max(0.0,val))
                            elif ival == 0: #Tmin
                                val = max(-1.,min(val,atomData[iatm][-1]['SS1'][item][iwave][0][1]))
                    except ValueError:
                        val = atomData[iatm][-1]['SS1'][item][iwave][0][ival]
                    Obj.SetValue('%.5f'%val)
                    atomData[iatm][-1]['SS1'][item][iwave][0][ival] = val
                    
                def OnRefWave(event):
                    Obj = event.GetEventObject()
                    iatm,item,iwave = Indx[Obj.GetId()]
                    atomData[iatm][-1]['SS1'][item][iwave][1] = not atomData[iatm][-1]['SS1'][item][iwave][1]
                    
                def OnDelWave(event):
                    Obj = event.GetEventObject()
                    iatm,item,iwave = Indx[Obj.GetId()]
                    del atomData[iatm][-1]['SS1'][item][iwave]
                    RepaintAtomInfo(G2frame.waveData.GetScrollPos(wx.VERTICAL))                
                
                waveSizer = wx.BoxSizer(wx.VERTICAL)
                waveHead = wx.BoxSizer(wx.HORIZONTAL)
                waveHead.Add(wx.StaticText(waveData,label=typeName+' modulation parameters: '),0,WACV)
                waveAdd = wx.CheckBox(waveData,label='Add wave?')
                waveAdd.Bind(wx.EVT_CHECKBOX, OnAddWave)
                Indx[waveAdd.GetId()] = [iatm,Stype]
                waveHead.Add(waveAdd,0,WACV)
                waveSizer.Add(waveHead)
                if len(waveBlk):
                    nx = 0
                    for iwave,wave in enumerate(waveBlk):
                        if not iwave:
                            if waveType in ['ZigZag','Block']:
                                nx = 1
                            CSI = G2spc.GetSSfxuinel(waveType,1,xyz,SGData,SSGData)
                        else:
                            CSI = G2spc.GetSSfxuinel('Fourier',iwave+1-nx,xyz,SGData,SSGData)
                        waveName = 'Fourier'
                        if Stype == 'Sfrac':
                            if 'Crenel' in waveType and not iwave:
                                waveName = 'Crenel'
                                names = Names[2:]
                            else:
                                names = Names[:2]
                            Waves = wx.FlexGridSizer(0,4,5,5)
                        elif Stype == 'Spos':
                            if waveType in ['ZigZag','Block'] and not iwave:
                                names = Names[6:]
                                Waves = wx.FlexGridSizer(0,7,5,5)
                                waveName = waveType
                            else:
                                names = Names[:6]
                                Waves = wx.FlexGridSizer(0,8,5,5)
                        else:
                            names = Names
                            Waves = wx.FlexGridSizer(0,8,5,5)
                        waveSizer.Add(wx.StaticText(waveData,label=' %s  parameters: %s'%(waveName,str(names).rstrip(']').lstrip('[').replace("'",''))),0,WACV)
                        for ival,val in enumerate(wave[0]):
                            if np.any(CSI[Stype][0][ival]):
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                                waveVal = wx.TextCtrl(waveData,value='%.5f'%(val),style=wx.TE_PROCESS_ENTER)
                                waveVal.Bind(wx.EVT_TEXT_ENTER,OnWaveVal)
                                waveVal.Bind(wx.EVT_KILL_FOCUS,OnWaveVal)
                                Indx[waveVal.GetId()] = [iatm,Stype,iwave,ival]
                            else:
                                waveVal = wx.TextCtrl(waveData,value='%.5f'%(val),style=wx.TE_READONLY)
                                waveVal.SetBackgroundColour(VERY_LIGHT_GREY)
                            Waves.Add(waveVal,0,WACV)
                            if len(wave[0]) > 6 and ival == 5:
                                Waves.Add((5,5),0)
                                Waves.Add((5,5),0)
                        waveRef = wx.CheckBox(waveData,label='Refine?')
                        waveRef.SetValue(wave[1])
                        Indx[waveRef.GetId()] = [iatm,Stype,iwave]
                        waveRef.Bind(wx.EVT_CHECKBOX, OnRefWave)
                        Waves.Add(waveRef,0,WACV)
                        if iwave < len(waveBlk)-1:
                            Waves.Add((5,5),0)                
                        else:
                            waveDel = wx.CheckBox(waveData,label='Delete?')
                            Indx[waveDel.GetId()] = [iatm,Stype,iwave]
                            waveDel.Bind(wx.EVT_CHECKBOX, OnDelWave)
                            Waves.Add(waveDel,0,WACV)
                        waveSizer.Add(Waves)                    
                return waveSizer

            iatm = atNames.index(G2frame.atmSel)
            atm = atomData[iatm]
            xyz = atm[cx:cx+3]
            atomSizer = wx.BoxSizer(wx.VERTICAL)
            G2G.HorizontalLine(atomSizer,waveData)
            atomSizer.Add(AtomSizer(atm))
            for Stype in ['Sfrac','Spos','Sadp','Smag']:
                if atm[cia] != 'A' and Stype == 'Sadp':    #Uiso can't have modulations! (why not?)
                    continue
                if generalData['Type'] != 'magnetic' and Stype == 'Smag':
                    break
                atomSizer.Add(WaveSizer(iatm,atm[-1]['SS1']['waveType'],atm[-1]['SS1'][Stype],Stype,typeNames[Stype],Labels[Stype]))                        
            return atomSizer

        atms = wx.ComboBox(waveData,value=G2frame.atmSel,choices=atNames,
            style=wx.CB_READONLY|wx.CB_DROPDOWN)
        atms.Bind(wx.EVT_COMBOBOX,OnAtmSel)
        topSizer.Add(atms,0,WACV)
        mainSizer.Add(topSizer,0,WACV)
        G2frame.bottomSizer = ShowAtomInfo()
        mainSizer.Add(G2frame.bottomSizer)
        SetPhaseWindow(G2frame.dataFrame,G2frame.waveData,mainSizer,Scroll)
    
    def OnWaveVary(event):
        generalData = data['General']
        cx,ct,cs,cia = generalData['AtomPtrs']
        atomData = data['Atoms']
        atNames = []
        names = ['Sfrac','Spos','Sadp','Smag']
        flags = dict(zip(names,[[],[],[],[]]))
        for atom in atomData:
            atNames.append(atom[ct-1])
            waves = atom[-1]['SS1']
            for name in names:
                if waves[name]:
                    flags[name].append(True)
                else:
                    flags[name].append(False)
        dlg = G2G.FlagSetDialog(G2frame,'Wave refinement flags',['Atom',]+names,atNames,flags)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                flags = dlg.GetSelection()
                for ia,atom in enumerate(atomData):
                    for name in names:
                        for wave in atom[-1]['SS1'][name]:
                            wave[1] = flags[name][ia]
        finally:
            dlg.Destroy()
        UpdateWavesData()

################################################################################
#### Structure drawing GUI stuff                
################################################################################

    def SetupDrawingData():
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])
        atomData = data['Atoms']
        defaultDrawing = {'viewPoint':[[0.5,0.5,0.5],[]],'showHydrogen':True,
            'backColor':[0,0,0],'depthFog':False,'Zclip':50.0,'cameraPos':50.,'Zstep':0.5,
            'radiusFactor':0.85,'contourLevel':1.,'bondRadius':0.1,'ballScale':0.33,
            'vdwScale':0.67,'ellipseProb':50,'sizeH':0.50,'unitCellBox':True,
            'showABC':True,'selectedAtoms':[],'Atoms':[],'oldxy':[],
            'bondList':{},'viewDir':[1,0,0],'Plane':[[0,0,1],False,False,0.0,[255,255,0]]}
        V0 = np.array([0,0,1])
        V = np.inner(Amat,V0)
        V /= np.sqrt(np.sum(V**2))
        A = np.arccos(np.sum(V*V0))
        defaultDrawing['Quaternion'] = G2mth.AV2Q(A,[0,1,0])
        try:
            drawingData = data['Drawing']
        except KeyError:
            data['Drawing'] = {}
            drawingData = data['Drawing']
        if not drawingData:                 #fill with defaults if empty
            drawingData = defaultDrawing.copy()
        if 'Zstep' not in drawingData:
            drawingData['Zstep'] = 0.5
        if 'contourLevel' not in drawingData:
            drawingData['contourLevel'] = 1.
        if 'viewDir' not in drawingData:
            drawingData['viewDir'] = [0,0,1]
        if 'Quaternion' not in drawingData:
            drawingData['Quaternion'] = G2mth.AV2Q(2*np.pi,np.inner(Amat,[0,0,1]))
        if 'showRigidBodies' not in drawingData:
            drawingData['showRigidBodies'] = True
        if 'Plane' not in drawingData:
            drawingData['Plane'] = [[0,0,1],False,False,0.0,[255,255,0]]
        cx,ct,cs,ci = [0,0,0,0]
        if generalData['Type'] in ['nuclear','faulted',]:
            cx,ct,cs,ci = [2,1,6,17]         #x, type, style & index
        elif generalData['Type'] == 'macromolecular':
            cx,ct,cs,ci = [5,4,9,20]         #x, type, style & index
        elif generalData['Type'] == 'magnetic':
            cx,ct,cs,ci = [2,1,9,20]         #x, type, style & index
        drawingData['atomPtrs'] = [cx,ct,cs,ci]
        if not drawingData.get('Atoms'):
            for atom in atomData:
                DrawAtomAdd(drawingData,atom)
            data['Drawing'] = drawingData
        if len(drawingData['Plane']) < 5:
            drawingData['Plane'].append([255,255,0])
            
    def DrawAtomAdd(drawingData,atom):
        drawingData['Atoms'].append(MakeDrawAtom(atom))
        
    def OnRestraint(event):        
        indx = drawAtoms.GetSelectedRows()
        restData = G2frame.PatternTree.GetItemPyData(   
            G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Restraints'))
        drawingData = data['Drawing']
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])            
        cx,ct,cs,ci = drawingData['atomPtrs']
        atomData = drawingData['Atoms']
        atXYZ = []
        atSymOp = []
        atIndx = []
        for item in indx:
            atXYZ.append(np.array(atomData[item][cx:cx+3]))
            atSymOp.append(atomData[item][cs-1])
            atIndx.append(atomData[item][ci])
        if event.GetId() == G2gd.wxID_DRAWRESTRBOND and len(indx) == 2:
            try:
                bondData = restData[PhaseName]['Bond']
            except KeyError:
                bondData = {'wtFactor':1.0,'Bonds':[],'Use':True}
                restData[PhaseName] = {}
                restData[PhaseName]['Bond'] = bondData
            bondData['Bonds'].append([atIndx,atSymOp,1.54,0.01])
        elif event.GetId() == G2gd.wxID_DRAWRESTRANGLE and len(indx) == 3:
            try:
                angleData = restData[PhaseName]['Angle']
            except KeyError:
                angleData = {'wtFactor':1.0,'Angles':[],'Use':True}
                restData[PhaseName] = {}
                restData[PhaseName]['Angle'] = angleData
            angleData['Angles'].append([atIndx,atSymOp,109.5,1.0])            
        elif event.GetId() == G2gd.wxID_DRAWRESTRPLANE and len(indx) > 3:
            try:
                planeData = restData[PhaseName]['Plane']
            except KeyError:
                planeData = {'wtFactor':1.0,'Planes':[],'Use':True}
                restData[PhaseName] = {}
                restData[PhaseName]['Plane'] = planeData
            planeData['Planes'].append([atIndx,atSymOp,0.0,0.01])            
        elif event.GetId() == G2gd.wxID_DRAWRESTRCHIRAL and len(indx) == 4:
            try:
                chiralData = restData[PhaseName]['Chiral']
            except KeyError:
                chiralData = {'wtFactor':1.0,'Volumes':[],'Use':True}
                restData[PhaseName] = {}
                restData[PhaseName]['Chiral'] = chiralData
            chiralData['Volumes'].append([atIndx,atSymOp,2.5,0.1])            
        else:
            print '**** ERROR wrong number of atoms selected for this restraint'
            return
        G2frame.PatternTree.SetItemPyData(   
            G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Restraints'),restData)

    def OnDefineRB(event):
        indx = drawAtoms.GetSelectedRows()
        indx.sort()
        RBData = G2frame.PatternTree.GetItemPyData(   
            G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Rigid bodies'))
        drawingData = data['Drawing']
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])            
        cx,ct,cs,ci = drawingData['atomPtrs']
        atomData = drawingData['Atoms']
        rbXYZ = []
        rbType = []
        atNames = []
        AtInfo = RBData['Residue']['AtInfo']
        for i,item in enumerate(indx):
            rbtype = atomData[item][ct]
            atNames.append(rbtype+str(i))
            rbType.append(rbtype)
            if rbtype not in AtInfo:
                Info = G2elem.GetAtomInfo(rbtype)
                AtInfo[rbtype] = [Info['Drad'],Info['Color']]
            rbXYZ.append(np.inner(np.array(atomData[item][cx:cx+3]),Amat))
        rbXYZ = np.array(rbXYZ)
        rbXYZ -= rbXYZ[0]
        rbId = ran.randint(0,sys.maxint)
        rbName = 'UNKRB'
        dlg = wx.TextEntryDialog(G2frame,'Enter the name for the new rigid body',
            'Edit rigid body name',rbName ,style=wx.OK)
        if dlg.ShowModal() == wx.ID_OK:
            rbName = dlg.GetValue()
        dlg.Destroy()
        RBData['Residue'][rbId] = {'RBname':rbName,'rbXYZ':rbXYZ,'rbTypes':rbType,
            'atNames':atNames,'rbRef':[0,1,2,False],'rbSeq':[],'SelSeq':[0,0],'useCount':0}
        RBData['RBIds']['Residue'].append(rbId)
        G2frame.dataFrame.SetStatusText('New rigid body UNKRB added to set of Residue rigid bodies')

################################################################################
##### Atom draw routines
################################################################################
            
    def UpdateDrawAtoms(atomStyle=''):
        def RefreshAtomGrid(event):
            def SetChoice(name,c,n=0):
                choice = []
                for r in range(len(atomData)):
                    if n:
                        srchStr = str(atomData[r][c][:n])
                    else:
                        srchStr = str(atomData[r][c])
                    if srchStr not in choice:
                        if n:
                            choice.append(str(atomData[r][c][:n]))
                        else:
                            choice.append(str(atomData[r][c]))
                choice.sort()

                dlg = wx.MultiChoiceDialog(G2frame,'Select',name,choice)
                if dlg.ShowModal() == wx.ID_OK:
                    sel = dlg.GetSelections()
                    parms = []
                    for x in sel:
                        parms.append(choice[x])
                    drawAtoms.ClearSelection()
                    drawingData['selectedAtoms'] = []
                    for row in range(len(atomData)):
                        test = atomData[row][c]
                        if n:
                            test = test[:n]
                        if  test in parms:
                            drawAtoms.SelectRow(row,True)
                            drawingData['selectedAtoms'].append(row)
                    G2plt.PlotStructure(G2frame,data)                    
                dlg.Destroy()
                
            r,c =  event.GetRow(),event.GetCol()
            if r < 0 and c < 0:
                for row in range(drawAtoms.GetNumberRows()):
                    drawingData['selectedAtoms'].append(row)
                    drawAtoms.SelectRow(row,True)                    
            elif r < 0:                          #dclick on col label
                sel = -1
                if drawAtoms.GetColLabelValue(c) == 'Style':
                    dlg = wx.SingleChoiceDialog(G2frame,'Select','Atom drawing style',styleChoice)
                    if dlg.ShowModal() == wx.ID_OK:
                        sel = dlg.GetSelection()
                        parms = styleChoice[sel]
                        for r in range(len(atomData)):
                            atomData[r][c] = parms
                            drawAtoms.SetCellValue(r,c,parms)
                        FindBondsDraw(data)
                        G2plt.PlotStructure(G2frame,data)
                    dlg.Destroy()
                elif drawAtoms.GetColLabelValue(c) == 'Label':
                    dlg = wx.SingleChoiceDialog(G2frame,'Select','Atom labelling style',labelChoice)
                    if dlg.ShowModal() == wx.ID_OK:
                        sel = dlg.GetSelection()
                        parms = labelChoice[sel]
                        for r in range(len(atomData)):
                            atomData[r][c] = parms
                            drawAtoms.SetCellValue(r,c,parms)
                    dlg.Destroy()                    
                elif drawAtoms.GetColLabelValue(c) == 'Color':
                    dlg = wx.ColourDialog(G2frame)
                    if dlg.ShowModal() == wx.ID_OK:
                        color = dlg.GetColourData().GetColour()
                        attr = wg.GridCellAttr()                #needs to be here - gets lost if outside loop!
                        attr.SetReadOnly(True)
                        attr.SetBackgroundColour(color)
                        for r in range(len(atomData)):
                            atomData[r][c] = color
                            drawingData['Atoms'][r][c] = color
                            drawAtoms.SetAttr(r,c,attr)
                        UpdateDrawAtoms()
                    dlg.Destroy()
                elif drawAtoms.GetColLabelValue(c) == 'Residue':
                    SetChoice('Residue',c,3)
                elif drawAtoms.GetColLabelValue(c) == '1-letter':
                    SetChoice('1-letter',c,1)
                elif drawAtoms.GetColLabelValue(c) == 'Chain':
                    SetChoice('Chain',c)
                elif drawAtoms.GetColLabelValue(c) == 'Name':
                    SetChoice('Name',c)
                elif drawAtoms.GetColLabelValue(c) == 'Sym Op':
                    SetChoice('Name',c)
                elif drawAtoms.GetColLabelValue(c) == 'Type':
                    SetChoice('Type',c)
                elif drawAtoms.GetColLabelValue(c) in ['x','y','z','I/A']:
                    drawAtoms.ClearSelection()
            else:
                if drawAtoms.GetColLabelValue(c) in ['Style','Label']:
                    atomData[r][c] = drawAtoms.GetCellValue(r,c)
                    FindBondsDraw(data)
                elif drawAtoms.GetColLabelValue(c) == 'Color':
                    dlg = wx.ColourDialog(G2frame)
                    if dlg.ShowModal() == wx.ID_OK:
                        color = dlg.GetColourData().GetColour()
                        attr = wg.GridCellAttr()                #needs to be here - gets lost if outside loop!
                        attr.SetReadOnly(True)
                        attr.SetBackgroundColour(color)
                        atomData[r][c] = color
                        drawingData['Atoms'][r][c] = color
                        drawAtoms.SetAttr(i,cs+2,attr)
                    dlg.Destroy()
                    UpdateDrawAtoms()
            G2plt.PlotStructure(G2frame,data)
                    
        def RowSelect(event):
            r,c =  event.GetRow(),event.GetCol()
            if r < 0 and c < 0:
                if drawAtoms.IsSelection():
                    drawAtoms.ClearSelection()
            elif c < 0:                   #only row clicks
                if event.ControlDown():                    
                    if r in drawAtoms.GetSelectedRows():
                        drawAtoms.DeselectRow(r)
                    else:
                        drawAtoms.SelectRow(r,True)
                elif event.ShiftDown():
                    indxs = drawAtoms.GetSelectedRows()
                    drawAtoms.ClearSelection()
                    ibeg = 0
                    if indxs:
                        ibeg = indxs[-1]
                    for row in range(ibeg,r+1):
                        drawAtoms.SelectRow(row,True)
                else:
                    drawAtoms.ClearSelection()
                    drawAtoms.SelectRow(r,True)                
            drawingData['selectedAtoms'] = []
            drawingData['selectedAtoms'] = drawAtoms.GetSelectedRows()
            G2plt.PlotStructure(G2frame,data)                    

        # UpdateDrawAtoms executable code starts here
        G2frame.dataFrame.SetStatusText('')
        generalData = data['General']
        SetupDrawingData()
        drawingData = data['Drawing']
        cx,ct,cs,ci = drawingData['atomPtrs']
        atomData = drawingData['Atoms']
        if atomStyle:
            for atom in atomData:
                atom[cs] = atomStyle
        Types = [wg.GRID_VALUE_STRING,wg.GRID_VALUE_STRING,]+3*[wg.GRID_VALUE_FLOAT+':10,5',]+ \
            [wg.GRID_VALUE_STRING,wg.GRID_VALUE_CHOICE+": ,lines,vdW balls,sticks,balls & sticks,ellipsoids,polyhedra",
            wg.GRID_VALUE_CHOICE+": ,type,name,number",wg.GRID_VALUE_STRING,wg.GRID_VALUE_STRING,]
        styleChoice = [' ','lines','vdW balls','sticks','balls & sticks','ellipsoids','polyhedra']
        labelChoice = [' ','type','name','number']
        colLabels = ['Name','Type','x','y','z','Sym Op','Style','Label','Color','I/A']
        if generalData['Type'] == 'macromolecular':
            colLabels = ['Residue','1-letter','Chain'] + colLabels
            Types = 3*[wg.GRID_VALUE_STRING,]+Types
            Types[8] = wg.GRID_VALUE_CHOICE+": ,lines,vdW balls,sticks,balls & sticks,ellipsoids,backbone,ribbons,schematic"
            styleChoice = [' ','lines','vdW balls','sticks','balls & sticks','ellipsoids','backbone','ribbons','schematic']
            labelChoice = [' ','type','name','number','residue','1-letter','chain']
            Types[9] = wg.GRID_VALUE_CHOICE+": ,type,name,number,residue,1-letter,chain"
        elif generalData['Type'] == 'magnetic':
            colLabels = colLabels[:5]+['Mx','My','Mz']+colLabels[5:]
            Types = Types[:5]+3*[wg.GRID_VALUE_FLOAT+':10,4',]+Types[5:]
        table = []
        rowLabels = []
        for i,atom in enumerate(drawingData['Atoms']):
            table.append(atom[:colLabels.index('I/A')+1])
            rowLabels.append(str(i))

        G2frame.atomTable = G2G.Table(table,rowLabels=rowLabels,colLabels=colLabels,types=Types)
        drawAtoms.SetTable(G2frame.atomTable, True)
        drawAtoms.SetMargins(0,0)
        drawAtoms.AutoSizeColumns(True)
        drawAtoms.SetColSize(colLabels.index('Style'),80)
        drawAtoms.SetColSize(colLabels.index('Color'),50)
        drawAtoms.Bind(wg.EVT_GRID_CELL_CHANGE, RefreshAtomGrid)
        drawAtoms.Bind(wg.EVT_GRID_LABEL_LEFT_DCLICK, RefreshAtomGrid)
        drawAtoms.Bind(wg.EVT_GRID_CELL_LEFT_DCLICK, RefreshAtomGrid)
        drawAtoms.Bind(wg.EVT_GRID_LABEL_LEFT_CLICK, RowSelect)
        for i,atom in enumerate(drawingData['Atoms']):
            attr = wg.GridCellAttr()                #needs to be here - gets lost if outside loop!
            attr.SetReadOnly(True)
            attr.SetBackgroundColour(atom[cs+2])
            drawAtoms.SetAttr(i,cs+2,attr)
            drawAtoms.SetCellValue(i,cs+2,'')
        indx = drawingData['selectedAtoms']
        if indx:
            for r in range(len(atomData)):
                if r in indx:
                    drawAtoms.SelectRow(r)
        for c in range(len(colLabels)):
           attr = wg.GridCellAttr()                #needs to be here - gets lost if outside loop!
           attr.SetReadOnly(True)
           attr.SetBackgroundColour(VERY_LIGHT_GREY)
           if colLabels[c] not in ['Style','Label','Color']:
                drawAtoms.SetColAttr(c,attr)
        G2frame.dataFrame.setSizePosLeft([600,300])

        FindBondsDraw(data)
        drawAtoms.ClearSelection()
#        G2plt.PlotStructure(G2frame,data)

    def DrawAtomStyle(event):
        indx = drawAtoms.GetSelectedRows()
        if indx:
            generalData = data['General']
            atomData = data['Drawing']['Atoms']
            cx,ct,cs,ci = data['Drawing']['atomPtrs']
            styleChoice = [' ','lines','vdW balls','sticks','balls & sticks','ellipsoids','polyhedra']
            if generalData['Type'] == 'macromolecular':
                styleChoice = [' ','lines','vdW balls','sticks','balls & sticks','ellipsoids',
                'backbone','ribbons','schematic']
            dlg = wx.SingleChoiceDialog(G2frame,'Select','Atom drawing style',styleChoice)
            if dlg.ShowModal() == wx.ID_OK:
                sel = dlg.GetSelection()
                parms = styleChoice[sel]
                for r in indx:
                    atomData[r][cs] = parms
                    drawAtoms.SetCellValue(r,cs,parms)
            dlg.Destroy()
            FindBondsDraw(data)
            drawAtoms.ClearSelection()
            G2plt.PlotStructure(G2frame,data)

    def DrawAtomLabel(event):
        indx = drawAtoms.GetSelectedRows()
        if indx:
            generalData = data['General']
            atomData = data['Drawing']['Atoms']
            cx,ct,cs,ci = data['Drawing']['atomPtrs']
            styleChoice = [' ','type','name','number']
            if generalData['Type'] == 'macromolecular':
                styleChoice = [' ','type','name','number','residue','1-letter','chain']
            dlg = wx.SingleChoiceDialog(G2frame,'Select','Atom label style',styleChoice)
            if dlg.ShowModal() == wx.ID_OK:
                sel = dlg.GetSelection()
                parms = styleChoice[sel]
                for r in indx:
                    atomData[r][cs+1] = parms
                    drawAtoms.SetCellValue(r,cs+1,parms)
            dlg.Destroy()
            drawAtoms.ClearSelection()
            G2plt.PlotStructure(G2frame,data)
            
    def DrawAtomColor(event):

        indx = drawAtoms.GetSelectedRows()
        if indx:
            if len(indx) > 1:
                G2frame.dataFrame.SetStatusText('Select Custom Color, change color, Add to Custom Colors, then OK')
            else:
                G2frame.dataFrame.SetStatusText('Change color, Add to Custom Colors, then OK')
            atomData = data['Drawing']['Atoms']
            cx,ct,cs,ci = data['Drawing']['atomPtrs']
            atmColors = []
            atmTypes = []
            for r in indx:
                if atomData[r][cs+2] not in atmColors:
                    atmColors.append(atomData[r][cs+2])
                    atmTypes.append(atomData[r][ct])
                    if len(atmColors) > 16:
                        break
            colors = wx.ColourData()
            colors.SetChooseFull(True)
            dlg = wx.ColourDialog(G2frame)
            if dlg.ShowModal() == wx.ID_OK:
                for i in range(len(atmColors)):                    
                    atmColors[i] = dlg.GetColourData().GetColour()
                colorDict = dict(zip(atmTypes,atmColors))
                for r in indx:
                    color = colorDict[atomData[r][ct]]
                    atomData[r][cs+2] = color
                    attr = wg.GridCellAttr()                #needs to be here - gets lost if outside loop!
                    attr.SetBackgroundColour(color)
                    drawAtoms.SetAttr(r,cs+2,attr)
                    data['Drawing']['Atoms'][r][cs+2] = color
            drawAtoms.ClearSelection()
            dlg.Destroy()
            G2frame.dataFrame.SetStatusText('')
            G2plt.PlotStructure(G2frame,data)
            
    def ResetAtomColors(event):
        generalData = data['General']
        atomData = data['Drawing']['Atoms']
        cx,ct,cs,ci = data['Drawing']['atomPtrs']
        for atom in atomData:            
            atNum = generalData['AtomTypes'].index(atom[ct])
            atom[cs+2] = list(generalData['Color'][atNum])
        UpdateDrawAtoms()
        drawAtoms.ClearSelection()
        G2plt.PlotStructure(G2frame,data) 
        
    def OnEditAtomRadii(event):
        DisAglCtls = {}
        generalData = data['General']
        if 'DisAglCtls' in generalData:
            DisAglCtls = generalData['DisAglCtls']
        dlg = G2gd.DisAglDialog(G2frame,DisAglCtls,generalData,Angle=False)
        if dlg.ShowModal() == wx.ID_OK:
            DisAglCtls = dlg.GetData()
        dlg.Destroy()
        generalData['DisAglCtls'] = DisAglCtls
        FindBondsDraw(data)
        G2plt.PlotStructure(G2frame,data)         
        
    def SetViewPoint(event):
        indx = drawAtoms.GetSelectedRows()
        if indx:
            atomData = data['Drawing']['Atoms']
            cx = data['Drawing']['atomPtrs'][0]
            data['Drawing']['viewPoint'] = [atomData[indx[0]][cx:cx+3],[indx[0],0]]
            drawAtoms.ClearSelection()                                  #do I really want to do this?
            G2plt.PlotStructure(G2frame,data)
            
    def noDuplicate(xyz,atomData):                  #be careful where this is used - it's slow
        cx = data['Drawing']['atomPtrs'][0]
        if True in [np.allclose(np.array(xyz),np.array(atom[cx:cx+3]),atol=0.0002) for atom in atomData]:
            return False
        else:
            return True
                
    def AddSymEquiv(event):
        indx = drawAtoms.GetSelectedRows()
        indx.sort()
        if indx:
            colLabels = [drawAtoms.GetColLabelValue(c) for c in range(drawAtoms.GetNumberCols())]
            cx,ct,cs,cui = data['Drawing']['atomPtrs']
            cuij = cui+2
            cmx = 0
            if 'Mx' in colLabels:
                cmx = colLabels.index('Mx')
            atomData = data['Drawing']['Atoms']
            generalData = data['General']
            Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])
            SGData = generalData['SGData']
            SpnFlp = SGData.get('SpnFlp',[])
            dlg = G2gd.SymOpDialog(G2frame,SGData,False,True)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    Inv,Cent,Opr,Cell,New,Force = dlg.GetSelection()
                    Cell = np.array(Cell)
                    cent = SGData['SGCen'][Cent]
                    M,T = SGData['SGOps'][Opr]
                    for ind in indx:
                        XYZ = np.array(atomData[ind][cx:cx+3])
                        XYZ = np.inner(M,XYZ)+T
                        if Inv:
                            XYZ = -XYZ
                        XYZ = XYZ+cent+Cell
                        if Force:
                            XYZ %= 1.       #G2spc.MoveToUnitCell(XYZ)
                        if noDuplicate(XYZ,atomData):
                            atom = copy.copy(atomData[ind])
                            atom[cx:cx+3] = XYZ
                            atomOp = atom[cs-1]
                            OprNum = ((Opr+1)+100*Cent)*(1-2*Inv)
                            newOp = str(OprNum)+'+'+ \
                                str(int(Cell[0]))+','+str(int(Cell[1]))+','+str(int(Cell[2]))                            
                            atom[cs-1] = G2spc.StringOpsProd(atomOp,newOp,SGData)
                            if cmx:
                                opNum = G2spc.GetOpNum(OprNum,SGData)
                                mom = np.inner(np.array(atom[cmx:cmx+3]),Bmat)
#                                print OprNum,newOp,opNum,SpnFlp
                                atom[cmx:cmx+3] = np.inner(np.inner(mom,M),Amat)*nl.det(M)*SpnFlp[opNum-1]
                            if atom[cui] == 'A':
                                Uij = atom[cuij:cuij+6]
                                Uij = G2spc.U2Uij(np.inner(np.inner(M,G2spc.Uij2U(Uij)),M))
                                atom[cuij:cuij+6] = Uij
                            atomData.append(atom[:cuij+9])  #not SS stuff
            finally:
                dlg.Destroy()
            UpdateDrawAtoms()
            drawAtoms.ClearSelection()
            G2plt.PlotStructure(G2frame,data)
            
    def AddSphere(event):
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])
        atomData = data['Drawing']['Atoms']
        numAtoms = len(atomData)
        cx,ct,cs,ci = data['Drawing']['atomPtrs']
        cuij = cs+5
        colLabels = [drawAtoms.GetColLabelValue(c) for c in range(drawAtoms.GetNumberCols())]
        cmx = 0
        if 'Mx' in colLabels:
            cmx = colLabels.index('Mx')
        generalData = data['General']
        SGData = generalData['SGData']
        SpnFlp = SGData.get('SpnFlp',[])
        cellArray = G2lat.CellBlock(1)
        indx = drawAtoms.GetSelectedRows()
        indx.sort()
        dlg = G2gd.SphereEnclosure(G2frame,data['General'],data['Drawing'],indx)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                centers,radius,targets = dlg.GetSelection()
                for orig in centers:
                    xyzA = np.array(orig)
                    for atomB in atomData[:numAtoms]:
                        if atomB[ct] not in targets:
                            continue
                        xyzB = np.array(atomB[cx:cx+3])
                        Uij = atomB[cuij:cuij+6]
#                        GSASIIpath.IPyBreak()
                        result = G2spc.GenAtom(xyzB,SGData,False,Uij,True)
                        for item in result:
                            atom = copy.copy(atomB)
                            atom[cx:cx+3] = item[0]
                            Opr = abs(item[2])%100
                            M = SGData['SGOps'][Opr-1][0]
                            if cmx:
                                opNum = G2spc.GetOpNum(item[2],SGData)
                                mom = np.inner(np.array(atom[cmx:cmx+3]),Bmat)
                                atom[cmx:cmx+3] = np.inner(np.inner(mom,M),Amat)*nl.det(M)*SpnFlp[opNum-1]
                            atom[cs-1] = str(item[2])+'+'
                            atom[cuij:cuij+6] = item[1]
                            for xyz in cellArray+np.array(atom[cx:cx+3]):
                                dist = np.sqrt(np.sum(np.inner(Amat,xyz-xyzA)**2))
                                if 0 < dist <= radius:
                                    if noDuplicate(xyz,atomData):
                                        C = xyz-atom[cx:cx+3]+item[3]
                                        newAtom = atom[:]
                                        newAtom[cx:cx+3] = xyz
                                        newAtom[cs-1] += str(int(round(C[0])))+','+str(int(round(C[1])))+','+str(int(round(C[2])))
                                        atomData.append(newAtom)
        finally:
            dlg.Destroy()
        UpdateDrawAtoms()
        drawAtoms.ClearSelection()
        G2plt.PlotStructure(G2frame,data)
            
    def TransformSymEquiv(event):
        indx = drawAtoms.GetSelectedRows()
        indx.sort()
        if indx:
            atomData = data['Drawing']['Atoms']
            colLabels = [drawAtoms.GetColLabelValue(c) for c in range(drawAtoms.GetNumberCols())]
            cx,ct,cs,ci = data['Drawing']['atomPtrs']
            cuij = ci+2
            cmx = 0
            if 'Mx' in colLabels:
                cmx = colLabels.index('Mx')
            atomData = data['Drawing']['Atoms']
            generalData = data['General']
            Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])
            SGData = generalData['SGData']
            SpnFlp = SGData.get('SpnFlp',[])
            dlg = G2gd.SymOpDialog(G2frame,SGData,False,True)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    Inv,Cent,Opr,Cell,New,Force = dlg.GetSelection()
                    Cell = np.array(Cell)
                    cent = SGData['SGCen'][Cent]
                    M,T = SGData['SGOps'][Opr]
                    for ind in indx:
                        XYZ = np.array(atomData[ind][cx:cx+3])
                        XYZ = np.inner(M,XYZ)+T
                        if Inv:
                            XYZ = -XYZ
                        XYZ = XYZ+cent+Cell
                        if Force:
                            XYZ,cell = G2spc.MoveToUnitCell(XYZ)
                            Cell += cell
                        atom = atomData[ind]
                        atom[cx:cx+3] = XYZ
                        OprNum = ((Opr+1)+100*Cent)*(1-2*Inv)
                        if cmx:
                            opNum = G2spc.GetOpNum(OprNum,SGData)
                            mom = np.inner(np.array(atom[cmx:cmx+3]),Bmat)
                            atom[cmx:cmx+3] = np.inner(np.inner(mom,M),Amat)*nl.det(M)*SpnFlp[opNum-1]
                        atomOp = atom[cs-1]
                        newOp = str(((Opr+1)+100*Cent)*(1-2*Inv))+'+'+ \
                            str(int(Cell[0]))+','+str(int(Cell[1]))+','+str(int(Cell[2]))
                        atom[cs-1] = G2spc.StringOpsProd(atomOp,newOp,SGData)
                        if atom[ci] == 'A':
                            Uij = atom[cuij:cuij+6]
                            U = G2spc.Uij2U(Uij)
                            U = np.inner(np.inner(M,U),M)
                            Uij = G2spc.U2Uij(U)
                            atom[cuij:cuij+6] = Uij
                    data['Drawing']['Atoms'] = atomData
            finally:
                dlg.Destroy()
            UpdateDrawAtoms()
            drawAtoms.ClearSelection()
            G2plt.PlotStructure(G2frame,data)
            
    def FillCoordSphere(event):
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])
        radii = generalData['BondRadii']
        atomTypes = generalData['AtomTypes']
        try:
            indH = atomTypes.index('H')
            radii[indH] = 0.5
        except:
            pass            
        indx = drawAtoms.GetSelectedRows()
        if indx:
            indx.sort()
            atomData = data['Drawing']['Atoms']
            numAtoms = len(atomData)
            cx,ct,cs,ci = data['Drawing']['atomPtrs']
            cij = ci+2
            SGData = generalData['SGData']
            cellArray = G2lat.CellBlock(1)
            wx.BeginBusyCursor()
            try:
                for ind in indx:
                    atomA = atomData[ind]
                    xyzA = np.array(atomA[cx:cx+3])
                    indA = atomTypes.index(atomA[ct])
                    for atomB in atomData[:numAtoms]:
                        indB = atomTypes.index(atomB[ct])
                        sumR = radii[indA]+radii[indB]
                        xyzB = np.array(atomB[cx:cx+3])
                        for xyz in cellArray+xyzB:
                            dist = np.sqrt(np.sum(np.inner(Amat,xyz-xyzA)**2))
                            if 0 < dist <= data['Drawing']['radiusFactor']*sumR:
                                if noDuplicate(xyz,atomData):
                                    oprB = atomB[cs-1]
                                    C = xyz-xyzB
                                    newOp = '1+'+str(int(round(C[0])))+','+str(int(round(C[1])))+','+str(int(round(C[2])))
                                    newAtom = atomB[:]
                                    newAtom[cx:cx+3] = xyz
                                    newAtom[cs-1] = G2spc.StringOpsProd(oprB,newOp,SGData)
                                    atomData.append(newAtom[:cij+9])  #not SS stuff
            finally:
                wx.EndBusyCursor()
            data['Drawing']['Atoms'] = atomData
            UpdateDrawAtoms()
            drawAtoms.ClearSelection()
            G2plt.PlotStructure(G2frame,data)
            
    def FillUnitCell(event):
        indx = drawAtoms.GetSelectedRows()
        indx.sort()
        if indx:
            atomData = data['Drawing']['Atoms']
            colLabels = [drawAtoms.GetColLabelValue(c) for c in range(drawAtoms.GetNumberCols())]
            cx,ct,cs,ci = data['Drawing']['atomPtrs']
            cmx = 0
            if 'Mx' in colLabels:
                cmx = colLabels.index('Mx')
            cuij = cs+5
            generalData = data['General']
            Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])            
            SGData = generalData['SGData']
            SpnFlp = SGData.get('SpnFlp',[])
#            MagMom = SGData.get('MagMom',[])
            wx.BeginBusyCursor()
            try:
                for ind in indx:
                    atom = atomData[ind]
                    XYZ = np.array(atom[cx:cx+3])
                    Uij = atom[cuij:cuij+6]
                    result = G2spc.GenAtom(XYZ,SGData,False,Uij,True)
                    for item in result:
                        atom = copy.copy(atomData[ind])
                        atom[cx:cx+3] = item[0]
                        if cmx:
                            Opr = abs(item[2])%100
                            M = SGData['SGOps'][Opr-1][0]
                            opNum = G2spc.GetOpNum(item[2],SGData)
                            mom = np.inner(np.array(atom[cmx:cmx+3]),Bmat)
                            atom[cmx:cmx+3] = np.inner(np.inner(mom,M),Amat)*nl.det(M)*SpnFlp[opNum-1]
                        atom[cs-1] = str(item[2])+'+' \
                            +str(item[3][0])+','+str(item[3][1])+','+str(item[3][2])
                        atom[cuij:cuij+6] = item[1]
                        Opp = G2spc.Opposite(item[0])
                        for key in Opp:
                            if noDuplicate(Opp[key],atomData):
                                unit = np.array(eval(key))*1.-item[3]
                                cell = '%d+%d,%d,%d'%(item[2],unit[0],unit[1],unit[2])
                                atom[cx:cx+3] = Opp[key]
                                atom[cs-1] = cell
                                atomData.append(atom[:cuij+9])  #not SS stuff
 #                       GSASIIpath.IPyBreak()
                    data['Drawing']['Atoms'] = atomData
            finally:
                wx.EndBusyCursor()
            UpdateDrawAtoms()
            drawAtoms.ClearSelection()
            G2plt.PlotStructure(G2frame,data)
            
    def DrawAtomsDelete(event):   
        indx = drawAtoms.GetSelectedRows()
        indx.sort()
        if indx:
            atomData = data['Drawing']['Atoms']
            indx.reverse()
            for ind in indx:
                del atomData[ind]
            UpdateDrawAtoms()
            drawAtoms.ClearSelection()
            G2plt.PlotStructure(G2frame,data)
        event.StopPropagation()
        
    def OnReloadDrawAtoms(event):
        atomData = data['Atoms']
        cx,ct,cs,ci = data['General']['AtomPtrs']
        for atom in atomData:
            ID = atom[ci+8]
            DrawAtomsReplaceByID(data['Drawing'],ci+8,atom,ID)
        UpdateDrawAtoms()
        drawAtoms.ClearSelection()
        G2plt.PlotStructure(G2frame,data)
        event.StopPropagation()
        
    def DrawAtomsDeleteByIDs(IDs):
        atomData = data['Drawing']['Atoms']
        cx,ct,cs,ci = data['General']['AtomPtrs']
        loc = ci+8
        indx = G2mth.FindAtomIndexByIDs(atomData,loc,IDs)
        indx.reverse()
        for ind in indx:
            del atomData[ind]
            
    def ChangeDrawAtomsByIDs(colName,IDs,value):
        atomData = data['Drawing']['Atoms']
        cx,ct,cs,ci = data['Drawing']['atomPtrs']
        if colName == 'Name':
            col = ct-1
        elif colName == 'Type':
            col = ct
        elif colName == 'I/A':
            col = cs
        indx = G2mth.FindAtomIndexByIDs(atomData,ci+8,IDs)
        for ind in indx:
            atomData[ind][col] = value
                
    def OnDrawPlane(event):
        indx = drawAtoms.GetSelectedRows()
        if len(indx) < 4:
            print '**** ERROR - need 4+ atoms for plane calculation'
            return
        PlaneData = {}
        drawingData = data['Drawing']
        atomData = drawingData['Atoms']
        colLabels = [drawAtoms.GetColLabelValue(c) for c in range(drawAtoms.GetNumberCols())]
        cx = colLabels.index('x')
        cn = colLabels.index('Name')
        xyz = []
        for i,atom in enumerate(atomData):
            if i in indx:
                xyz.append([i,]+atom[cn:cn+2]+atom[cx:cx+3])
        generalData = data['General']
        PlaneData['Name'] = generalData['Name']
        PlaneData['Atoms'] = xyz
        PlaneData['Cell'] = generalData['Cell'][1:] #+ volume
        G2stMn.BestPlane(PlaneData)
        
    def OnDrawDistVP(event):
        # distance to view point
        indx = drawAtoms.GetSelectedRows()
        if not indx:
            print '***** ERROR - no atoms selected'
            return
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])            
        drawingData = data['Drawing']
        viewPt = np.array(drawingData['viewPoint'][0])
        print ' Distance from view point at %.3f %.3f %.3f to:'%(viewPt[0],viewPt[1],viewPt[2])
        atomDData = drawingData['Atoms']
        colLabels = [drawAtoms.GetColLabelValue(c) for c in range(drawAtoms.GetNumberCols())]
        cx = colLabels.index('x')
        cn = colLabels.index('Name')
        for i in indx:
            atom = atomDData[i]
            Dx = np.array(atom[cx:cx+3])-viewPt
            dist = np.sqrt(np.sum(np.inner(Amat,Dx)**2,axis=0))
            print 'Atom: %8s (%12s) distance = %.3f'%(atom[cn],atom[cx+3],dist)
    
    def OnDrawDAT(event):
        #distance, angle, torsion 
        indx = drawAtoms.GetSelectedRows()
        if len(indx) not in [2,3,4]:
            print '**** ERROR - wrong number of atoms for distance, angle or torsion calculation'
            return
        DATData = {}
        ocx,oct,ocs,cia = data['General']['AtomPtrs']
        drawingData = data['Drawing']
        atomData = data['Atoms']
        atomDData = drawingData['Atoms']
        colLabels = [drawAtoms.GetColLabelValue(c) for c in range(drawAtoms.GetNumberCols())]
        cx = colLabels.index('x')
        cn = colLabels.index('Name')
        cid = colLabels.index('I/A')+8
        xyz = []
        Oxyz = []
        DATData['Natoms'] = len(indx)
        for i in indx:
            atom = atomDData[i]
            xyz.append([i,]+atom[cn:cn+2]+atom[cx:cx+4]) #also gets Sym Op
            id = G2mth.FindAtomIndexByIDs(atomData,cid,[atom[cid],],False)[0]
            Oxyz.append([id,]+atomData[id][cx+1:cx+4])
        DATData['Datoms'] = xyz
        DATData['Oatoms'] = Oxyz
        generalData = data['General']
        DATData['Name'] = generalData['Name']
        DATData['SGData'] = generalData['SGData']
        DATData['Cell'] = generalData['Cell'][1:] #+ volume
        if 'pId' in data:
            DATData['pId'] = data['pId']
            DATData['covData'] = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,G2frame.root, 'Covariance'))
        G2stMn.DisAglTor(DATData)
                        
################################################################################
#### Draw Options page
################################################################################

    def UpdateDrawOptions():
        import wx.lib.colourselect as wcs
        def SlopSizer():            
            def OnCameraPos(event):
                drawingData['cameraPos'] = cameraPos.GetValue()
                cameraPosTxt.SetLabel(' Camera Distance: '+'%.2f'%(drawingData['cameraPos']))
                ZclipTxt.SetLabel(' Z clipping: '+'%.2fA'%(drawingData['Zclip']*drawingData['cameraPos']/100.))
                G2plt.PlotStructure(G2frame,data)

            def OnZclip(event):
                drawingData['Zclip'] = Zclip.GetValue()
                ZclipTxt.SetLabel(' Z clipping: '+'%.2fA'%(drawingData['Zclip']*drawingData['cameraPos']/100.))
                G2plt.PlotStructure(G2frame,data)
                
            def OnZstep(event):
                event.Skip()
                try:
                    step = float(Zstep.GetValue())
                    if not (0.01 <= step <= 1.0):
                        raise ValueError
                except ValueError:
                    step = drawingData['Zstep']
                drawingData['Zstep'] = step
                Zstep.SetValue('%.2fA'%(drawingData['Zstep']))
                
            def OnMoveZ(event):
                move = MoveZ.GetValue()*drawingData['Zstep']
                MoveZ.SetValue(0)
                VP = np.inner(Amat,np.array(drawingData['viewPoint'][0]))
                VD = np.inner(Amat,np.array(drawingData['viewDir']))
                VD /= np.sqrt(np.sum(VD**2))
                VP += move*VD
                VP = np.inner(Bmat,VP)
                drawingData['viewPoint'][0] = VP
                panel = drawOptions.GetChildren()
                names = [child.GetName() for child in panel]
                panel[names.index('viewPoint')].SetValue('%.3f %.3f %.3f'%(VP[0],VP[1],VP[2]))                
                G2plt.PlotStructure(G2frame,data)
                
            def OnVdWScale(event):
                drawingData['vdwScale'] = vdwScale.GetValue()/100.
                vdwScaleTxt.SetLabel(' van der Waals scale: '+'%.2f'%(drawingData['vdwScale']))
                G2plt.PlotStructure(G2frame,data)
    
            def OnEllipseProb(event):
                drawingData['ellipseProb'] = ellipseProb.GetValue()
                ellipseProbTxt.SetLabel(' Ellipsoid probability: '+'%d%%'%(drawingData['ellipseProb']))
                G2plt.PlotStructure(G2frame,data)
    
            def OnBallScale(event):
                drawingData['ballScale'] = ballScale.GetValue()/100.
                ballScaleTxt.SetLabel(' Ball scale: '+'%.2f'%(drawingData['ballScale']))
                G2plt.PlotStructure(G2frame,data)

            def OnBondRadius(event):
                drawingData['bondRadius'] = bondRadius.GetValue()/100.
                bondRadiusTxt.SetLabel(' Bond radius, A: '+'%.2f'%(drawingData['bondRadius']))
                G2plt.PlotStructure(G2frame,data)
                
            def OnContourLevel(event):
                drawingData['contourLevel'] = contourLevel.GetValue()/100.
                contourLevelTxt.SetLabel(' Contour level: '+'%.2f'%(drawingData['contourLevel']*generalData['Map']['rhoMax']))
                G2plt.PlotStructure(G2frame,data)

            def OnMapSize(event):
                drawingData['mapSize'] = mapSize.GetValue()/10.
                mapSizeTxt.SetLabel(' Map radius, A: '+'%.1f'%(drawingData['mapSize']))
                G2plt.PlotStructure(G2frame,data)

            
            slopSizer = wx.BoxSizer(wx.HORIZONTAL)
            slideSizer = wx.FlexGridSizer(0,2)
            slideSizer.AddGrowableCol(1,1)
    
            cameraPosTxt = wx.StaticText(drawOptions,-1,
                ' Camera Distance: '+'%.2f'%(drawingData['cameraPos']),name='cameraPos')
            G2frame.dataDisplay.cameraPosTxt = cameraPosTxt
            slideSizer.Add(cameraPosTxt,0,WACV)
            cameraPos = wx.Slider(drawOptions,style=wx.SL_HORIZONTAL,value=drawingData['cameraPos'],name='cameraSlider')
            cameraPos.SetRange(10,500)
            cameraPos.Bind(wx.EVT_SLIDER, OnCameraPos)
            G2frame.dataDisplay.cameraSlider = cameraPos
            slideSizer.Add(cameraPos,1,wx.EXPAND|wx.RIGHT)
            
            ZclipTxt = wx.StaticText(drawOptions,-1,' Z clipping: '+'%.2fA'%(drawingData['Zclip']*drawingData['cameraPos']/100.))
            slideSizer.Add(ZclipTxt,0,WACV)
            Zclip = wx.Slider(drawOptions,style=wx.SL_HORIZONTAL,value=drawingData['Zclip'])
            Zclip.SetRange(1,99)
            Zclip.Bind(wx.EVT_SLIDER, OnZclip)
            slideSizer.Add(Zclip,1,wx.EXPAND|wx.RIGHT)
            
            ZstepSizer = wx.BoxSizer(wx.HORIZONTAL)
            ZstepSizer.Add(wx.StaticText(drawOptions,-1,' Z step:'),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            Zstep = wx.TextCtrl(drawOptions,value='%.2f'%(drawingData['Zstep']),
                style=wx.TE_PROCESS_ENTER)
            Zstep.Bind(wx.EVT_TEXT_ENTER,OnZstep)
            Zstep.Bind(wx.EVT_KILL_FOCUS,OnZstep)
            ZstepSizer.Add(Zstep,0,WACV)
            slideSizer.Add(ZstepSizer)
            MoveSizer = wx.BoxSizer(wx.HORIZONTAL)
            MoveSizer.Add(wx.StaticText(drawOptions,-1,'   Press to step:'),0,WACV)
            MoveZ = wx.SpinButton(drawOptions,style=wx.SP_HORIZONTAL,size=wx.Size(100,20))
            MoveZ.SetValue(0)
            MoveZ.SetRange(-1,1)
            MoveZ.Bind(wx.EVT_SPIN, OnMoveZ)
            MoveSizer.Add(MoveZ)
            slideSizer.Add(MoveSizer,1,wx.EXPAND|wx.RIGHT)
            
            vdwScaleTxt = wx.StaticText(drawOptions,-1,' van der Waals scale: '+'%.2f'%(drawingData['vdwScale']))
            slideSizer.Add(vdwScaleTxt,0,WACV)
            vdwScale = wx.Slider(drawOptions,style=wx.SL_HORIZONTAL,value=int(100*drawingData['vdwScale']))
            vdwScale.Bind(wx.EVT_SLIDER, OnVdWScale)
            slideSizer.Add(vdwScale,1,wx.EXPAND|wx.RIGHT)
    
            ellipseProbTxt = wx.StaticText(drawOptions,-1,' Ellipsoid probability: '+'%d%%'%(drawingData['ellipseProb']))
            slideSizer.Add(ellipseProbTxt,0,WACV)
            ellipseProb = wx.Slider(drawOptions,style=wx.SL_HORIZONTAL,value=drawingData['ellipseProb'])
            ellipseProb.SetRange(1,99)
            ellipseProb.Bind(wx.EVT_SLIDER, OnEllipseProb)
            slideSizer.Add(ellipseProb,1,wx.EXPAND|wx.RIGHT)
    
            ballScaleTxt = wx.StaticText(drawOptions,-1,' Ball scale: '+'%.2f'%(drawingData['ballScale']))
            slideSizer.Add(ballScaleTxt,0,WACV)
            ballScale = wx.Slider(drawOptions,style=wx.SL_HORIZONTAL,value=int(100*drawingData['ballScale']))
            ballScale.Bind(wx.EVT_SLIDER, OnBallScale)
            slideSizer.Add(ballScale,1,wx.EXPAND|wx.RIGHT)
    
            bondRadiusTxt = wx.StaticText(drawOptions,-1,' Bond radius, A: '+'%.2f'%(drawingData['bondRadius']))
            slideSizer.Add(bondRadiusTxt,0,WACV)
            bondRadius = wx.Slider(drawOptions,style=wx.SL_HORIZONTAL,value=int(100*drawingData['bondRadius']))
            bondRadius.SetRange(1,25)
            bondRadius.Bind(wx.EVT_SLIDER, OnBondRadius)
            slideSizer.Add(bondRadius,1,wx.EXPAND|wx.RIGHT)
            
            if generalData['Map']['rhoMax']:
                contourLevelTxt = wx.StaticText(drawOptions,-1,' Contour level: '+'%.2f'%(drawingData['contourLevel']*generalData['Map']['rhoMax']))
                slideSizer.Add(contourLevelTxt,0,WACV)
                contourLevel = wx.Slider(drawOptions,style=wx.SL_HORIZONTAL,value=int(100*drawingData['contourLevel']))
                contourLevel.SetRange(1,100)
                contourLevel.Bind(wx.EVT_SLIDER, OnContourLevel)
                slideSizer.Add(contourLevel,1,wx.EXPAND|wx.RIGHT)
                mapSizeTxt = wx.StaticText(drawOptions,-1,' Map radius, A: '+'%.1f'%(drawingData['mapSize']))
                slideSizer.Add(mapSizeTxt,0,WACV)
                mapSize = wx.Slider(drawOptions,style=wx.SL_HORIZONTAL,value=int(10*drawingData['mapSize']))
                mapSize.SetRange(1,100)
                mapSize.Bind(wx.EVT_SLIDER, OnMapSize)
                slideSizer.Add(mapSize,1,wx.EXPAND|wx.RIGHT)
            
            slopSizer.Add(slideSizer,1,wx.EXPAND|wx.RIGHT)
            slopSizer.Add((10,5),0)
            slopSizer.SetMinSize(wx.Size(350,10))
            return slopSizer
            
        def ShowSizer():
            
            def OnBackColor(event):
                drawingData['backColor'] = event.GetValue()
                G2plt.PlotStructure(G2frame,data)
    
            def OnShowABC(event):
                drawingData['showABC'] = showABC.GetValue()
                G2plt.PlotStructure(G2frame,data)
    
            def OnShowUnitCell(event):
                drawingData['unitCellBox'] = unitCellBox.GetValue()
                G2plt.PlotStructure(G2frame,data)
    
            def OnShowHyd(event):
                drawingData['showHydrogen'] = showHydrogen.GetValue()
                FindBondsDraw(data)
                G2plt.PlotStructure(G2frame,data)
                
            def OnShowRB(event):
                drawingData['showRigidBodies'] = showRB.GetValue()
                FindBondsDraw(data)
                G2plt.PlotStructure(G2frame,data)
                
            def OnViewPoint(event):
                event.Skip()
                Obj = event.GetEventObject()
                viewPt = Obj.GetValue().split()
                try:
                    VP = [float(viewPt[i]) for i in range(3)]
                except (ValueError,IndexError):
                    VP = drawingData['viewPoint'][0]
                Obj.SetValue('%.3f %.3f %.3f'%(VP[0],VP[1],VP[2]))
                drawingData['viewPoint'][0] = VP
                G2plt.PlotStructure(G2frame,data)
                
            def OnViewDir(event):
                event.Skip()
                Obj = event.GetEventObject()
                viewDir = Obj.GetValue().split()
                try:
                    Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])
                    VD = np.array([float(viewDir[i]) for i in range(3)])
                    VC = np.inner(Amat,VD)
                    VC /= np.sqrt(np.sum(VC**2))
                    V = np.array(drawingData['viewDir'])
                    VB = np.inner(Amat,V)
                    VB /= np.sqrt(np.sum(VB**2))
                    VX = np.cross(VC,VB)
                    A = acosd(max((2.-np.sum((VB-VC)**2))/2.,-1.))
                    QV = G2mth.AVdeg2Q(A,VX)
                    Q = drawingData['Quaternion']
                    drawingData['Quaternion'] = G2mth.prodQQ(Q,QV)
                except (ValueError,IndexError):
                    VD = drawingData['viewDir']
                Obj.SetValue('%.3f %.3f %.3f'%(VD[0],VD[1],VD[2]))
                drawingData['viewDir'] = VD
                G2plt.PlotStructure(G2frame,data)
                                
            showSizer = wx.BoxSizer(wx.VERTICAL)            
            lineSizer = wx.BoxSizer(wx.HORIZONTAL)
            lineSizer.Add(wx.StaticText(drawOptions,-1,' Background color:'),0,WACV)
            backColor = wcs.ColourSelect(drawOptions, -1,colour=drawingData['backColor'],size=wx.Size(25,25))
            backColor.Bind(wcs.EVT_COLOURSELECT, OnBackColor)
            lineSizer.Add(backColor,0,WACV)
            lineSizer.Add(wx.StaticText(drawOptions,-1,' View Dir.:'),0,WACV)
            VD = drawingData['viewDir']
            viewDir = wx.TextCtrl(drawOptions,value='%.3f %.3f %.3f'%(VD[0],VD[1],VD[2]),
                style=wx.TE_PROCESS_ENTER,size=wx.Size(140,20),name='viewDir')
            viewDir.Bind(wx.EVT_TEXT_ENTER,OnViewDir)
            viewDir.Bind(wx.EVT_KILL_FOCUS,OnViewDir)
            G2frame.dataDisplay.viewDir = viewDir
            lineSizer.Add(viewDir,0,WACV)
            showSizer.Add(lineSizer)
            showSizer.Add((0,5),0)
            
            lineSizer = wx.BoxSizer(wx.HORIZONTAL)
            showABC = wx.CheckBox(drawOptions,-1,label=' Show view point?')
            showABC.Bind(wx.EVT_CHECKBOX, OnShowABC)
            showABC.SetValue(drawingData['showABC'])
            lineSizer.Add(showABC,0,WACV)
            lineSizer.Add(wx.StaticText(drawOptions,-1,' View Point:'),0,WACV)
            VP = drawingData['viewPoint'][0]
            viewPoint = wx.TextCtrl(drawOptions,value='%.3f %.3f %.3f'%(VP[0],VP[1],VP[2]),
                style=wx.TE_PROCESS_ENTER,size=wx.Size(140,20),name='viewPoint')
            G2frame.dataDisplay.viewPoint = viewPoint
            viewPoint.Bind(wx.EVT_TEXT_ENTER,OnViewPoint)
            viewPoint.Bind(wx.EVT_KILL_FOCUS,OnViewPoint)
            lineSizer.Add(viewPoint,0,WACV)
            showSizer.Add(lineSizer)
            showSizer.Add((0,5),0)
            
            line2Sizer = wx.BoxSizer(wx.HORIZONTAL)
    
            unitCellBox = wx.CheckBox(drawOptions,-1,label=' Show unit cell?')
            unitCellBox.Bind(wx.EVT_CHECKBOX, OnShowUnitCell)
            unitCellBox.SetValue(drawingData['unitCellBox'])
            line2Sizer.Add(unitCellBox,0,WACV)
    
            showHydrogen = wx.CheckBox(drawOptions,-1,label=' Show hydrogens?')
            showHydrogen.Bind(wx.EVT_CHECKBOX, OnShowHyd)
            showHydrogen.SetValue(drawingData['showHydrogen'])
            line2Sizer.Add(showHydrogen,0,WACV)
            
            showRB = wx.CheckBox(drawOptions,-1,label=' Show rigid Bodies?')
            showRB.Bind(wx.EVT_CHECKBOX, OnShowRB)
            showRB.SetValue(drawingData['showRigidBodies'])
            line2Sizer.Add(showRB,0,WACV)
            
            showSizer.Add(line2Sizer)
            return showSizer
            
        def RadSizer():
            
            def OnSizeHatoms(event):
                event.Skip()
                try:
                    value = max(0.1,min(1.2,float(sizeH.GetValue())))
                except ValueError:
                    value = 0.5
                drawingData['sizeH'] = value
                sizeH.SetValue("%.2f"%(value))
                G2plt.PlotStructure(G2frame,data)
                
            def OnRadFactor(event):
                event.Skip()
                try:
                    value = max(0.1,min(1.2,float(radFactor.GetValue())))
                except ValueError:
                    value = 0.85
                drawingData['radiusFactor'] = value
                radFactor.SetValue("%.2f"%(value))
                FindBondsDraw(data)
                G2plt.PlotStructure(G2frame,data)
            
            radSizer = wx.BoxSizer(wx.HORIZONTAL)
            radSizer.Add(wx.StaticText(drawOptions,-1,' Hydrogen radius, A:  '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            sizeH = wx.TextCtrl(drawOptions,-1,value='%.2f'%(drawingData['sizeH']),size=wx.Size(60,20),style=wx.TE_PROCESS_ENTER)
            sizeH.Bind(wx.EVT_TEXT_ENTER,OnSizeHatoms)
            sizeH.Bind(wx.EVT_KILL_FOCUS,OnSizeHatoms)
            radSizer.Add(sizeH,0,WACV)
    
            radSizer.Add(wx.StaticText(drawOptions,-1,' Bond search factor:  '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            radFactor = wx.TextCtrl(drawOptions,value='%.2f'%(drawingData['radiusFactor']),size=wx.Size(60,20),style=wx.TE_PROCESS_ENTER)
            radFactor.Bind(wx.EVT_TEXT_ENTER,OnRadFactor)
            radFactor.Bind(wx.EVT_KILL_FOCUS,OnRadFactor)
            radSizer.Add(radFactor,0,WACV)
            return radSizer
            
        def PlaneSizer():
            
            def OnPlane(event):
                event.Skip()
                vals = plane.GetValue().split()
                try:
                    hkl = [int(vals[i]) for i in range(3)]
                    if not np.any(np.array(hkl)):       #can't be all zeros!
                        raise ValueError
                except (ValueError,IndexError):
                    hkl = drawingData['Plane'][0]
                drawingData['Plane'][0] = hkl
                plane.SetValue('%3d %3d %3d'%(hkl[0],hkl[1],hkl[2]))
                G2plt.PlotStructure(G2frame,data)
                
            def OnShowPlane(event):
                drawingData['Plane'][1] = showPlane.GetValue()
                G2plt.PlotStructure(G2frame,data)
                
            def OnShowStack(event):
                drawingData['Plane'][2] = showStack.GetValue()
                G2plt.PlotStructure(G2frame,data)
                
            def OnPhase(event):
                event.Skip()
                try:
                    val = float(phase.GetValue())
                except ValueError:
                    val = drawingData['Plane'][3]
                drawingData['Plane'][3] = val
                phase.SetValue('%.2f'%(val))
                G2plt.PlotStructure(G2frame,data)
            
            def OnPlaneColor(event):
                drawingData['Plane'][4] = event.GetValue()
                G2plt.PlotStructure(G2frame,data)

            planeSizer = wx.BoxSizer(wx.VERTICAL)
            planeSizer1 = wx.BoxSizer(wx.HORIZONTAL)
            planeSizer1.Add(wx.StaticText(drawOptions,label=' Plane: '),0,WACV)
            H = drawingData['Plane'][0]
            plane = wx.TextCtrl(drawOptions,value='%3d %3d %3d'%(H[0],H[1],H[2]),
                style=wx.TE_PROCESS_ENTER)
            plane.Bind(wx.EVT_TEXT_ENTER,OnPlane)
            plane.Bind(wx.EVT_KILL_FOCUS,OnPlane)
            planeSizer1.Add(plane,0,WACV)
            showPlane = wx.CheckBox(drawOptions,label=' Show plane?')
            showPlane.SetValue(drawingData['Plane'][1])
            showPlane.Bind(wx.EVT_CHECKBOX, OnShowPlane)
            planeSizer1.Add(showPlane,0,WACV)
            showStack = wx.CheckBox(drawOptions,label=' As a stack?')
            showStack.SetValue(drawingData['Plane'][2])
            showStack.Bind(wx.EVT_CHECKBOX, OnShowStack)
            planeSizer1.Add(showStack,0,WACV)
            planeSizer2 = wx.BoxSizer(wx.HORIZONTAL)
            planeSizer2.Add(wx.StaticText(drawOptions,label=' Phase shift (deg): '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            phase = wx.TextCtrl(drawOptions,value='%.2f'%(drawingData['Plane'][3]),
                style=wx.TE_PROCESS_ENTER)
            phase.Bind(wx.EVT_TEXT_ENTER,OnPhase)
            phase.Bind(wx.EVT_KILL_FOCUS,OnPhase)
            planeSizer2.Add(phase,0,WACV)
            planeSizer2.Add(wx.StaticText(drawOptions,-1,' Plane color: '),0,WACV)
            planeColor = wcs.ColourSelect(drawOptions, -1,colour=drawingData['Plane'][4],size=wx.Size(25,25))
            planeColor.Bind(wcs.EVT_COLOURSELECT, OnPlaneColor)
            planeSizer2.Add(planeColor,0,WACV)
            planeSizer.Add(planeSizer1)
            planeSizer.Add(planeSizer2)
            return planeSizer
            

        # UpdateDrawOptions exectable code starts here
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])
        SetupDrawingData()
        drawingData = data['Drawing']

        G2frame.dataFrame.SetStatusText('')
        if drawOptions.GetSizer():
            drawOptions.GetSizer().Clear(True)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add((5,5),0)
        mainSizer.Add(wx.StaticText(drawOptions,-1,' Drawing controls:'),0,WACV)
        mainSizer.Add((5,5),0)        
        mainSizer.Add(SlopSizer(),0)
        mainSizer.Add((5,5),0)
        mainSizer.Add(ShowSizer(),0,)
        mainSizer.Add((5,5),0)
        mainSizer.Add(RadSizer(),0,)
        mainSizer.Add((5,5),0)
        mainSizer.Add(PlaneSizer(),0,)
        SetPhaseWindow(G2frame.dataFrame,drawOptions,mainSizer)

################################################################################
####  Texture routines
################################################################################
        
    def UpdateTexture():
                
        def SetSHCoef():
            cofNames = G2lat.GenSHCoeff(SGData['SGLaue'],SamSym[textureData['Model']],textureData['Order'])
            newSHCoef = dict(zip(cofNames,np.zeros(len(cofNames))))
            SHCoeff = textureData['SH Coeff'][1]
            for cofName in SHCoeff:
                if cofName in  cofNames:
                    newSHCoef[cofName] = SHCoeff[cofName]
            return newSHCoef
        
        def OnShOrder(event):
            Obj = event.GetEventObject()
            textureData['Order'] = int(Obj.GetValue())
            textureData['SH Coeff'][1] = SetSHCoef()
            wx.CallLater(100,UpdateTexture)
            wx.CallAfter(G2plt.PlotTexture,G2frame,data)
                        
        def OnShModel(event):
            Obj = event.GetEventObject()
            textureData['Model'] = Obj.GetValue()
            textureData['SH Coeff'][1] = SetSHCoef()
            wx.CallLater(100,UpdateTexture)
            wx.CallAfter(G2plt.PlotTexture,G2frame,data)
            
        def OnSHRefine(event):
            Obj = event.GetEventObject()
            textureData['SH Coeff'][0] = Obj.GetValue()
            
        def OnSHShow(event):
            Obj = event.GetEventObject()
            textureData['SHShow'] = Obj.GetValue()
            wx.CallLater(100,UpdateTexture)
            
        def OnProjSel(event):
            Obj = event.GetEventObject()
            G2frame.Projection = Obj.GetValue()
            wx.CallAfter(G2plt.PlotTexture,G2frame,data)
            
        def OnColorSel(event):
            Obj = event.GetEventObject()
            G2frame.ContourColor = Obj.GetValue()
            wx.CallAfter(G2plt.PlotTexture,G2frame,data)
            
        def OnAngRef(event):
            Obj = event.GetEventObject()
            textureData[angIndx[Obj.GetId()]][0] = Obj.GetValue()
            
        def OnAngValue(event):
            event.Skip()
            Obj = event.GetEventObject()
            try:
                value =  float(Obj.GetValue())
            except ValueError:
                value = textureData[valIndx[Obj.GetId()]][1]
            Obj.SetValue('%8.2f'%(value))
            textureData[valIndx[Obj.GetId()]][1] = value
            
        def OnODFValue(event): 
            event.Skip()
            Obj = event.GetEventObject()
            try:
                value =  float(Obj.GetValue())
            except ValueError:
                value = textureData['SH Coeff'][1][ODFIndx[Obj.GetId()]]
            Obj.SetValue('%8.3f'%(value))
            textureData['SH Coeff'][1][ODFIndx[Obj.GetId()]] = value
            wx.CallAfter(G2plt.PlotTexture,G2frame,data)
            
        def OnPfType(event):
            Obj = event.GetEventObject()
            textureData['PlotType'] = Obj.GetValue()
            wx.CallLater(100,UpdateTexture)
            wx.CallAfter(G2plt.PlotTexture,G2frame,data)
            
        def OnPFValue(event):
            event.Skip()
            Obj = event.GetEventObject()
            Saxis = Obj.GetValue().split()
            if textureData['PlotType'] in ['Pole figure','Axial pole distribution','3D pole distribution']:                
                try:
                    hkl = [int(Saxis[i]) for i in range(3)]
                except (ValueError,IndexError):
                    hkl = textureData['PFhkl']
                if not np.any(np.array(hkl)):       #can't be all zeros!
                    hkl = textureData['PFhkl']
                Obj.SetValue('%d %d %d'%(hkl[0],hkl[1],hkl[2]))
                textureData['PFhkl'] = hkl
            else:
                try:
                    xyz = [float(Saxis[i]) for i in range(3)]
                except (ValueError,IndexError):
                    xyz = textureData['PFxyz']
                if not np.any(np.array(xyz)):       #can't be all zeros!
                    xyz = textureData['PFxyz']
                Obj.SetValue('%3.1f %3.1f %3.1f'%(xyz[0],xyz[1],xyz[2]))
                textureData['PFxyz'] = xyz
            wx.CallAfter(G2plt.PlotTexture,G2frame,data)
            
        def OnpopLA(event):
            pfName = PhaseName
            cell = generalData['Cell'][1:7]
            PH = np.array(textureData['PFhkl'])
            phi,beta = G2lat.CrsAng(PH,cell,SGData)
            SHCoef = textureData['SH Coeff'][1]
            ODFln = G2lat.Flnh(True,SHCoef,phi,beta,SGData)
            pfName = PhaseName+'%d%d%d.gpf'%(PH[0],PH[1],PH[2])
            pth = G2G.GetExportPath(G2frame)
            dlg = wx.FileDialog(G2frame, 'Choose popLA pole figure file name', pth, pfName, 
                'popLA file (*.gpf)|*.gpf',wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    pfFile = dlg.GetPath()
            finally:
                dlg.Destroy()
            print 'popLA save '+pfFile
            if pfFile:
                pf = open(pfFile,'w')
                pf.write(PhaseName+'\n')
                str = ' %d%d%d   5.0 90.0  5.0360.0 1 1 2 1 3  100    1'%(PH[0],PH[1],PH[2])
                pf.write(str+'\n')
                Psi,Gam = np.mgrid[0:19,0:72]
                Psi = Psi.flatten()*5.
                Gam = Gam.flatten()*5.
                Z = np.array(G2lat.polfcal(ODFln,SamSym[textureData['Model']],Psi,Gam)*100.,dtype='int')
                Z = np.where(Z>0,Z,0)
                Z = np.where(Z<9999,Z,9999)
                for i in range(76):
                    iBeg = i*18
                    iFin = iBeg+18
                    np.savetxt(pf,Z[iBeg:iFin],fmt='%4d',newline='')
                    pf.write('\n')                
                pf.close()
                print ' popLA %d %d %d pole figure saved to %s'%(PH[0],PH[1],PH[2],pfFile)

        def OnCSV(event):
            pfName = PhaseName
            pfFile = ''
            cell = generalData['Cell'][1:7]
            if 'Inverse' in textureData['PlotType']:
                SHCoef = textureData['SH Coeff'][1]
                PX = np.array(textureData['PFxyz'])
                gam = atan2d(PX[0],PX[1])
                xy = np.sqrt(PX[0]**2+PX[1]**2)
                xyz = np.sqrt(PX[0]**2+PX[1]**2+PX[2]**2)
                psi = asind(xy/xyz)
                IODFln = G2lat.Glnh(True,SHCoef,psi,gam,SamSym[textureData['Model']])
                pfName = PhaseName+'%d%d%dIPF.csv'%(int(PX[0]),int(PX[1]),int(PX[2]))
                pth = G2G.GetExportPath(G2frame)
                dlg = wx.FileDialog(G2frame, 'Choose CSV inverse pole figure file name', pth, pfName, 
                    'CSV file (*.csv)|*.csv',wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
            else:    
                PH = np.array(textureData['PFhkl'])
                phi,beta = G2lat.CrsAng(PH,cell,SGData)
                SHCoef = textureData['SH Coeff'][1]
                ODFln = G2lat.Flnh(True,SHCoef,phi,beta,SGData)
                pfName = PhaseName+'%d%d%dPF.csv'%(PH[0],PH[1],PH[2])
                pth = G2G.GetExportPath(G2frame)
                dlg = wx.FileDialog(G2frame, 'Choose CSV pole figure file name', pth, pfName, 
                    'CSV file (*.csv)|*.csv',wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    pfFile = dlg.GetPath()
                    print 'CSV save '+pfFile
            finally:
                dlg.Destroy()
            if pfFile:
                pf = open(pfFile,'w')
                pf.write('"%s"\n'%(PhaseName))
                if 'Inverse' in textureData['PlotType']:
                    pf.write('" %s %d %d %d inverse pole figure"\n'%(PhaseName,int(PX[0]),int(PX[1]),int(PX[2])))
                    P,R = np.mgrid[0:19,0:72]
                    pf.write('"phi/beta",')
                    np.savetxt(pf,np.linspace(0.,90.,19,True),fmt='%10.4f,',newline='')
                    pf.write('\n')
                    P = P.flatten()*5.
                    R = R.flatten()*5.
                    Z = G2lat.invpolfcal(IODFln,SGData,P,R)
                    Z = np.reshape(Z,(19,72)).T
                    for i,row in enumerate(Z):
                        pf.write('%8d,  '%(i*5))
                        np.savetxt(pf,row,fmt='%10.4f,',newline='')
                        pf.write('\n')                
                    pf.close()
                    print ' %s %d %d %d inverse pole figure saved to %s'%(PhaseName,int(PX[0]),int(PX[1]),int(PX[2]),pfFile)
                else:
                    pf.write('" %s %d %d %d pole figure"\n'%(PhaseName,PH[0],PH[1],PH[2]))
                    Psi,Gam = np.mgrid[0:19,0:72]
                    pf.write('"psi/gam",')
                    np.savetxt(pf,np.linspace(0.,90.,19,True),fmt='%10.4f,',newline='')
                    pf.write('\n')
                    Psi = Psi.flatten()*5.
                    Gam = Gam.flatten()*5.
                    Z = np.array(G2lat.polfcal(ODFln,SamSym[textureData['Model']],Psi,Gam))
                    Z = np.reshape(Z,(19,72)).T
                    for i,row in enumerate(Z):
                        pf.write('%8d, '%(i*5))
                        np.savetxt(pf,row,fmt='%10.4f,',newline='')
                        pf.write('\n')               
                    pf.close()
                    print ' %s %d %d %d pole figure saved to %s'%(PhaseName,PH[0],PH[1],PH[2],pfFile)

        def SHPenalty(Penalty):
            
            def OnHKLList(event):
                event.Skip()
                dlg = G2G.G2MultiChoiceDialog(G2frame, 'Select penalty hkls',
                    'Penalty hkls',hkls,filterBox=False)
                try:
                    if dlg.ShowModal() == wx.ID_OK:
                        Penalty[0] = [hkls[i] for i in dlg.GetSelections()]
                        if not Penalty[0]:
                            Penalty[0] = ['',]
                    else:
                        return
                finally:
                    dlg.Destroy()
                wx.CallLater(100,UpdateTexture)
                
            def OnshToler(event):
                event.Skip()
                try:
                    value = float(shToler.GetValue())
                    Penalty[1] = value
                except ValueError:
                    pass
                shToler.SetValue('%.2f'%(Penalty[1]))
            
            A = G2lat.cell2A(generalData['Cell'][1:7])
            hkls = G2lat.GenPfHKLs(10,SGData,A)    
            shPenalty = wx.BoxSizer(wx.HORIZONTAL)
            shPenalty.Add(wx.StaticText(Texture,wx.ID_ANY,' Negative MRD penalty list: '),0,WACV)
            shPenalty.Add(wx.ComboBox(Texture,value=Penalty[0][0],choices=Penalty[0],
                style=wx.CB_DROPDOWN|wx.CB_READONLY),0,WACV)
            hklList = wx.Button(Texture,label='Select penalty hkls')
            hklList.Bind(wx.EVT_BUTTON,OnHKLList)
            shPenalty.Add(hklList,0,WACV)
            shPenalty.Add(wx.StaticText(Texture,wx.ID_ANY,' Zero MRD tolerance: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            shToler = wx.TextCtrl(Texture,wx.ID_ANY,'%.2f'%(Penalty[1]),style=wx.TE_PROCESS_ENTER)
            shToler.Bind(wx.EVT_TEXT_ENTER,OnshToler)
            shToler.Bind(wx.EVT_KILL_FOCUS,OnshToler)
            shPenalty.Add(shToler,0,WACV)
            return shPenalty    
        
        # UpdateTexture executable starts here
        #Texture.DestroyChildren() # bad, deletes scrollbars on Mac!
        if Texture.GetSizer():
            Texture.GetSizer().Clear(True)
        G2frame.dataFrame.SetStatusText('')
        generalData = data['General']        
        SGData = generalData['SGData']
        try:
            textureData = generalData['SH Texture']
        except KeyError:            #fix old files!
            textureData = generalData['SH Texture'] = {'Order':0,'Model':'cylindrical',
                'Sample omega':[False,0.0],'Sample chi':[False,0.0],'Sample phi':[False,0.0],
                'SH Coeff':[False,{}],'SHShow':False,'PFhkl':[0,0,1],
                'PFxyz':[0,0,1.],'PlotType':'Pole figure'}
        if 'SHShow' not in textureData:
            textureData.update({'SHShow':False,'PFhkl':[0,0,1],'PFxyz':[0,0,1.],'PlotType':'Pole figure'})
        if 'PlotType' not in textureData:
            textureData.update({'PFxyz':[0,0,1.],'PlotType':'Pole figure'})
        if 'Penalty' not in textureData:
            textureData['Penalty'] = [['',],0.1,False,1.0]
        shModels = ['cylindrical','none','shear - 2/m','rolling - mmm']
        SamSym = dict(zip(shModels,['0','-1','2/m','mmm']))
        if Texture.GetSizer():
            Texture.GetSizer().Clear(True)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        titleSizer = wx.BoxSizer(wx.HORIZONTAL)
        titleSizer.Add(wx.StaticText(Texture,-1,' Spherical harmonics texture data for '+PhaseName+':'),0,WACV)
        titleSizer.Add(wx.StaticText(Texture,-1,
            ' Texture Index J = %7.3f'%(G2lat.textureIndex(textureData['SH Coeff'][1]))),
            0,WACV)
        mainSizer.Add(titleSizer,0)
        mainSizer.Add((0,5),0)
        shSizer = wx.FlexGridSizer(0,6,5,5)
        shSizer.Add(wx.StaticText(Texture,-1,' Texture model: '),0,WACV)
        shModel = wx.ComboBox(Texture,-1,value=textureData['Model'],choices=shModels,
            style=wx.CB_READONLY|wx.CB_DROPDOWN)
        shModel.Bind(wx.EVT_COMBOBOX,OnShModel)
        shSizer.Add(shModel,0,WACV)
        shSizer.Add(wx.StaticText(Texture,-1,'  Harmonic order: '),0,WACV)
        shOrder = wx.ComboBox(Texture,-1,value=str(textureData['Order']),choices=[str(2*i) for i in range(18)],
            style=wx.CB_READONLY|wx.CB_DROPDOWN)
        shOrder.Bind(wx.EVT_COMBOBOX,OnShOrder)
        shSizer.Add(shOrder,0,WACV)
        shRef = wx.CheckBox(Texture,-1,label=' Refine texture?')
        shRef.SetValue(textureData['SH Coeff'][0])
        shRef.Bind(wx.EVT_CHECKBOX, OnSHRefine)
        shSizer.Add(shRef,0,WACV)
        shShow = wx.CheckBox(Texture,-1,label=' Show coeff.?')
        shShow.SetValue(textureData['SHShow'])
        shShow.Bind(wx.EVT_CHECKBOX, OnSHShow)
        shSizer.Add(shShow,0,WACV)
        mainSizer.Add(shSizer,0,0)
        mainSizer.Add((0,5),0)
        PTSizer = wx.FlexGridSizer(0,5,5,5)
        PTSizer.Add(wx.StaticText(Texture,-1,' Texture plot type: '),0,WACV)
        choices = ['Axial pole distribution','Pole figure','Inverse pole figure','3D pole distribution']            
        pfType = wx.ComboBox(Texture,-1,value=str(textureData['PlotType']),choices=choices,
            style=wx.CB_READONLY|wx.CB_DROPDOWN)
        pfType.Bind(wx.EVT_COMBOBOX,OnPfType)
        PTSizer.Add(pfType,0,WACV)
        if 'Axial' not in textureData['PlotType'] and '3D' not in textureData['PlotType']:
            PTSizer.Add(wx.StaticText(Texture,-1,' Projection type: '),0,WACV)
            projSel = wx.ComboBox(Texture,-1,value=G2frame.Projection,choices=['equal area','stereographic'],
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            projSel.Bind(wx.EVT_COMBOBOX,OnProjSel)
            PTSizer.Add(projSel,0,WACV)
            PTSizer.Add((0,5),0)
        if textureData['PlotType'] in ['Pole figure','Axial pole distribution','3D pole distribution']:
            PTSizer.Add(wx.StaticText(Texture,-1,' Pole figure HKL: '),0,WACV)
            PH = textureData['PFhkl']
            pfVal = wx.TextCtrl(Texture,-1,'%d %d %d'%(PH[0],PH[1],PH[2]),style=wx.TE_PROCESS_ENTER)
        else:
            PTSizer.Add(wx.StaticText(Texture,-1,' Inverse pole figure XYZ: '),0,WACV)
            PX = textureData['PFxyz']
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            pfVal = wx.TextCtrl(Texture,-1,'%3.1f %3.1f %3.1f'%(PX[0],PX[1],PX[2]),style=wx.TE_PROCESS_ENTER)
        pfVal.Bind(wx.EVT_TEXT_ENTER,OnPFValue)
        pfVal.Bind(wx.EVT_KILL_FOCUS,OnPFValue)
        PTSizer.Add(pfVal,0,WACV)
        if 'Axial' not in textureData['PlotType'] and '3D' not in textureData['PlotType']:
            PTSizer.Add(wx.StaticText(Texture,-1,' Color scheme'),0,WACV)
            choice = [m for m in mpl.cm.datad.keys() if not m.endswith("_r")]
            choice.sort()
            colorSel = wx.ComboBox(Texture,-1,value=G2frame.ContourColor,choices=choice,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            colorSel.Bind(wx.EVT_COMBOBOX,OnColorSel)
            PTSizer.Add(colorSel,0,WACV)
            if 'figure' in textureData['PlotType']:
                popLA = wx.Button(Texture,-1,"Make CSV file")
                popLA.Bind(wx.EVT_BUTTON, OnCSV)
                PTSizer.Add(popLA,0,WACV)
        mainSizer.Add(PTSizer,0,WACV)
        mainSizer.Add((0,5),0)
        if textureData['SHShow']:
            mainSizer.Add(wx.StaticText(Texture,-1,' Spherical harmonic coefficients: '),0,WACV)
            mainSizer.Add((0,5),0)
            ODFSizer = wx.FlexGridSizer(0,8,2,2)
            ODFIndx = {}
            ODFkeys = textureData['SH Coeff'][1].keys()
            ODFkeys.sort()
            for item in ODFkeys:
                ODFSizer.Add(wx.StaticText(Texture,-1,item),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                ODFval = wx.TextCtrl(Texture,wx.ID_ANY,'%8.3f'%(textureData['SH Coeff'][1][item]),style=wx.TE_PROCESS_ENTER)
                ODFIndx[ODFval.GetId()] = item
                ODFval.Bind(wx.EVT_TEXT_ENTER,OnODFValue)
                ODFval.Bind(wx.EVT_KILL_FOCUS,OnODFValue)
                ODFSizer.Add(ODFval,0,WACV)
            mainSizer.Add(ODFSizer,0,WACV)
            mainSizer.Add((0,5),0)
        mainSizer.Add((0,5),0)
        mainSizer.Add(wx.StaticText(Texture,-1,' Sample orientation angle zeros: '),0,WACV)
        mainSizer.Add((0,5),0)
        angSizer = wx.BoxSizer(wx.HORIZONTAL)
        angIndx = {}
        valIndx = {}
        for item in ['Sample omega','Sample chi','Sample phi']:
            angRef = wx.CheckBox(Texture,-1,label=item+': ')
            angRef.SetValue(textureData[item][0])
            angIndx[angRef.GetId()] = item
            angRef.Bind(wx.EVT_CHECKBOX, OnAngRef)
            angSizer.Add(angRef,0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            angVal = wx.TextCtrl(Texture,wx.ID_ANY,'%8.2f'%(textureData[item][1]),style=wx.TE_PROCESS_ENTER)
            valIndx[angVal.GetId()] = item
            angVal.Bind(wx.EVT_TEXT_ENTER,OnAngValue)
            angVal.Bind(wx.EVT_KILL_FOCUS,OnAngValue)
            angSizer.Add(angVal,0,WACV|wx.LEFT,5)
        mainSizer.Add(angSizer,0,WACV|wx.LEFT,5)
#        mainSizer.Add(SHPenalty(textureData['Penalty']),0,WACV|wx.LEFT,5)  for future
        SetPhaseWindow(G2frame.dataFrame,Texture,mainSizer)

################################################################################
##### DData routines - GUI stuff in GSASIIddataGUI.py
################################################################################
        
    def OnHklfAdd(event):
        UseList = data['Histograms']
        keyList = UseList.keys()
        TextList = []
        if not G2frame.PatternTree.GetCount():
            return
        
        item, cookie = G2frame.PatternTree.GetFirstChild(G2frame.root)
        while item:
            name = G2frame.PatternTree.GetItemText(item)
            if name not in keyList and 'HKLF' in name:
                TextList.append(name)
            item, cookie = G2frame.PatternTree.GetNextChild(G2frame.root, cookie)                        
        dlg = G2G.G2MultiChoiceDialog(G2frame, 'Select reflection sets to use',
            'Use data',TextList)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                result = dlg.GetSelections()
            else:
                return
        finally:
            dlg.Destroy()

        # get the histograms used in other phases
        phaseRIdList,usedHistograms = G2frame.GetPhaseInfofromTree()
        usedHKLFhists = [] # used single-crystal histograms
        for p in usedHistograms:
            for h in usedHistograms[p]:
                if h.startswith('HKLF ') and h not in usedHKLFhists:
                    usedHKLFhists.append(h)
        # check that selected single crystal histograms are not already in use!
        for i in result:
            used = [TextList[i] for i in result if TextList[i] in usedHKLFhists]
            if used:
                msg = 'The following single crystal histogram(s) are already in use'
                for i in used:
                    msg += '\n  '+str(i)
                msg += '\nAre you sure you want to add them to this phase? '
                msg += 'Associating a single crystal dataset to >1 histogram is usually an error, '
                msg += 'so No is suggested here.'
                if G2frame.ErrorDialog('Likely error',msg,G2frame,wtype=wx.YES_NO) != wx.ID_YES: return

        wx.BeginBusyCursor()
        for i in result:
            histoName = TextList[i]
            Id = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,histoName)
            refDict,reflData = G2frame.PatternTree.GetItemPyData(Id)
            UseList[histoName] = {'Histogram':histoName,'Show':False,'Scale':[1.0,True],
                'Babinet':{'BabA':[0.0,False],'BabU':[0.0,False]},
                'Extinction':['Lorentzian','None',
                {'Tbar':0.1,'Cos2TM':0.955,'Eg':[1.e-7,False],'Es':[1.e-7,False],'Ep':[1.e-7,False]},],
                'Flack':[0.0,False],'Twins':[[np.array([[1,0,0],[0,1,0],[0,0,1]]),[1.0,False,0]],]}                        
            if 'TwMax' in reflData:     #nonmerohedral twins present
                UseList[histoName]['Twins'] = []
                for iT in range(reflData['TwMax'][0]+1):
                    if iT in reflData['TwMax'][1]:
                        UseList[histoName]['Twins'].append([False,0.0])
                    else:
                        UseList[histoName]['Twins'].append([np.array([[1,0,0],[0,1,0],[0,0,1]]),[1.0,False,reflData['TwMax'][0]]])
            else:   #no nonmerohedral twins
                UseList[histoName]['Twins'] = [[np.array([[1,0,0],[0,1,0],[0,0,1]]),[1.0,False,0]],]
            UpdateHKLFdata(histoName)
            data['Histograms'] = UseList
        wx.CallAfter(G2ddG.UpdateDData,G2frame,DData,data)
        wx.EndBusyCursor()
        
    def OnDataUse(event):
        UseList = data['Histograms']
        hist = G2frame.hist
        keyList = G2frame.GetHistogramNames(hist[:4])
        if UseList:
            dlg = G2G.G2MultiChoiceDialog(G2frame.dataFrame, 'Use histograms', 
                'Use which histograms?',keyList)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    sel = dlg.GetSelections()
                    for id,item in enumerate(keyList):
                        if id in sel:
                            UseList[item]['Use'] = True
                        else:
                            UseList[item]['Use'] = False                        
            finally:
                dlg.Destroy()
        wx.CallAfter(G2ddG.UpdateDData,G2frame,DData,data)
                
    def UpdateHKLFdata(histoName):
        generalData = data['General']
        Id = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,histoName)
        refDict,reflData = G2frame.PatternTree.GetItemPyData(Id)
        SGData = generalData['SGData']
        Cell = generalData['Cell'][1:7]
        G,g = G2lat.cell2Gmat(Cell)
        for iref,ref in enumerate(reflData['RefList']):
            H = list(ref[:3])
            ref[4] = np.sqrt(1./G2lat.calc_rDsq2(H,G))
            iabsnt,ref[3],Uniq,phi = G2spc.GenHKLf(H,SGData)
        
    def OnDataCopy(event):
        UseList = data['Histograms']
        hist = G2frame.hist
        keyList = G2frame.GetHistogramNames(hist[:4])
        sourceDict = UseList[hist]
        if 'HKLF' in sourceDict['Histogram']:
            copyNames = ['Scale','Extinction','Babinet','Flack','Twins']
        else:  #PWDR  
            copyNames = ['Scale','Pref.Ori.','Size','Mustrain','HStrain','Extinction','Babinet']
        copyDict = {}
        for name in copyNames: 
            copyDict[name] = copy.deepcopy(sourceDict[name])        #force copy
        if UseList:
            dlg = G2G.G2MultiChoiceDialog(G2frame.dataFrame, 'Copy parameters', 
                'Copy parameters to which histograms?',keyList)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    for sel in dlg.GetSelections():
                        UseList[keyList[sel]].update(copy.deepcopy(copyDict))
            finally:
                dlg.Destroy()
        
    def OnDataCopyFlags(event):
        UseList = data['Histograms']
        hist = G2frame.hist
        sourceDict = UseList[hist]
        copyDict = {}
        if 'HKLF' in sourceDict['Histogram']:
            copyNames = ['Scale','Extinction','Babinet','Flack','Twins']
        else:  #PWDR  
            copyNames = ['Scale','Pref.Ori.','Size','Mustrain','HStrain','Extinction','Babinet']
        babNames = ['BabA','BabU']
        for name in copyNames:
            if name in ['Scale','Extinction','HStrain','Flack','Twins']:
                if name == 'Extinction' and 'HKLF' in sourceDict['Histogram']:
                    copyDict[name] = {name:[sourceDict[name][:2]]}
                    for item in ['Eg','Es','Ep']:
                        copyDict[name][item] = sourceDict[name][2][item][1]
                elif name == 'Twins':
                    copyDict[name] = sourceDict[name][0][1][1]
                else:
                    copyDict[name] = sourceDict[name][1]
            elif name in ['Size','Mustrain']:
                copyDict[name] = [sourceDict[name][0],sourceDict[name][2],sourceDict[name][4]]
            elif name == 'Pref.Ori.':
                copyDict[name] = [sourceDict[name][0],sourceDict[name][2]]
                if sourceDict[name][0] == 'SH':
                    SHterms = sourceDict[name][5]
                    SHflags = {}
                    for item in SHterms:
                        SHflags[item] = SHterms[item]
                    copyDict[name].append(SHflags)
            elif name == 'Babinet':
                copyDict[name] = {}
                for bab in babNames:
                    copyDict[name][bab] = sourceDict[name][bab][1]                       
        keyList = G2frame.GetHistogramNames(hist[:4])
        if UseList:
            dlg = G2G.G2MultiChoiceDialog(G2frame.dataFrame, 'Copy parameters', 
                'Copy parameters to which histograms?', 
                keyList)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    for sel in dlg.GetSelections():
                        item = keyList[sel]
                        UseList[item]
                        for name in copyNames:
                            if name in ['Scale','Extinction','HStrain','Flack','Twins']:
                                if name == 'Extinction' and 'HKLF' in sourceDict['Histogram']:
                                    UseList[item][name][:2] = copy.deepcopy(sourceDict[name][:2])
                                    for itm in ['Eg','Es','Ep']:
                                        UseList[item][name][2][itm][1] = copy.deepcopy(copyDict[name][itm])
                                elif name == 'Twins':
                                    UseList[item]['Twins'][0][1][1] = copyDict['Twins']
                                else:
                                    UseList[item][name][1] = copy.deepcopy(copyDict[name])
                            elif name in ['Size','Mustrain']:
                                UseList[item][name][0] = copy.deepcopy(copyDict[name][0])
                                UseList[item][name][2] = copy.deepcopy(copyDict[name][1])
                                UseList[item][name][4] = copy.deepcopy(copyDict[name][2])
                            elif name == 'Pref.Ori.':
                                UseList[item][name][0] = copy.deepcopy(copyDict[name][0])
                                UseList[item][name][2] = copy.deepcopy(copyDict[name][1])
                                if sourceDict[name][0] == 'SH':
                                   SHflags = copy.deepcopy(copyDict[name][2])
                                   SHterms = copy.deepcopy(sourceDict[name][5])
                                   UseList[item][name][6] = copy.deepcopy(sourceDict[name][6])
                                   UseList[item][name][7] = copy.deepcopy(sourceDict[name][7])
                            elif name == 'Babinet':
                                for bab in babNames:
                                    UseList[item][name][bab][1] = copy.deepcopy(copyDict[name][bab])                                              
            finally:
                dlg.Destroy()
        
    def OnSelDataCopy(event):
        UseList = data['Histograms']
        hist = G2frame.hist
        keyList = G2frame.GetHistogramNames(hist[:4])
        sourceDict = UseList[hist]
        copyDict = {}
        if 'HKLF' in sourceDict['Histogram']:
            copyNames = ['Scale','Extinction','Babinet','Flack','Twins']
        else:  #PWDR  
            copyNames = ['Scale','Pref.Ori.','Size','Mustrain','HStrain','Extinction','Babinet']
        dlg = G2G.G2MultiChoiceDialog(G2frame.dataFrame,'Select which parameters to copy',
            'Select phase data parameters', copyNames)
        selectedItems = []
        try:
            if dlg.ShowModal() == wx.ID_OK:
                selectedItems = [copyNames[i] for i in dlg.GetSelections()]
        finally:
            dlg.Destroy()
        if not selectedItems: return # nothing to copy
        copyDict = {}
        for parm in selectedItems:
            copyDict[parm] = copy.deepcopy(sourceDict[parm])
        if UseList:
            dlg = G2G.G2MultiChoiceDialog(G2frame.dataFrame, 'Copy parameters', 
                    'Copy parameters to which histograms?',keyList)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    for sel in dlg.GetSelections():
                        UseList[keyList[sel]].update(copy.deepcopy(copyDict))
            finally:
                dlg.Destroy()            
        
    def OnPwdrAdd(event):
        generalData = data['General']
        SGData = generalData['SGData']
        UseList = data['Histograms']
        newList = []
        NShkl = len(G2spc.MustrainNames(SGData))
        NDij = len(G2spc.HStrainNames(SGData))
        keyList = UseList.keys()
        TextList = []
        if G2frame.PatternTree.GetCount():
            item, cookie = G2frame.PatternTree.GetFirstChild(G2frame.root)
            while item:
                name = G2frame.PatternTree.GetItemText(item)
                if name not in keyList and 'PWDR' in name:
                    TextList.append(name)
                item, cookie = G2frame.PatternTree.GetNextChild(G2frame.root, cookie)
            dlg = G2G.G2MultiChoiceDialog(G2frame, 'Select reflection sets to use',
                    'Use data',TextList)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    result = dlg.GetSelections()
                    for i in result: newList.append(TextList[i])
                    if 'All PWDR' in newList:
                        newList = TextList[1:]
                    for histoName in newList:
                        Id = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,histoName)
                        UseList[histoName] = {'Histogram':histoName,'Show':False,
                            'Scale':[1.0,False],'Pref.Ori.':['MD',1.0,False,[0,0,1],0,{},['',],0.1],
                            'Size':['isotropic',[1.,1.,1.],[False,False,False],[0,0,1],
                                [1.,1.,1.,0.,0.,0.],6*[False,]],
                            'Mustrain':['isotropic',[1000.0,1000.0,1.0],[False,False,False],[0,0,1],
                                NShkl*[0.01,],NShkl*[False,]],
                            'HStrain':[NDij*[0.0,],NDij*[False,]],                          
                            'Extinction':[0.0,False],'Babinet':{'BabA':[0.0,False],'BabU':[0.0,False]}}
                        refList = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,Id,'Reflection Lists'))
                        refList[generalData['Name']] = {}                       
                    data['Histograms'] = UseList
                    wx.CallAfter(G2ddG.UpdateDData,G2frame,DData,data)
            finally:
                dlg.Destroy()
                
    def OnDataDelete(event):
        UseList = data['Histograms']
        keyList = ['All',]+UseList.keys()
        keyList.sort()
        DelList = []
        if UseList:
            DelList = []
            dlg = wx.MultiChoiceDialog(G2frame, 
                'Which histogram to delete from this phase?', 'Delete histogram', 
                keyList, wx.CHOICEDLG_STYLE)
            try:
                if dlg.ShowModal() == wx.ID_OK:
                    result = dlg.GetSelections()
                    for i in result: 
                        DelList.append(keyList[i])
                    if 'All' in DelList:
                        DelList = keyList[1:]
                    for i in DelList:
                        del UseList[i]
                    data['Histograms'] = UseList
                    wx.CallAfter(G2ddG.UpdateDData,G2frame,DData,data)
            finally:
                dlg.Destroy()
                
################################################################################
##### Rigid bodies
################################################################################

    def FillRigidBodyGrid(refresh=True):
        '''Fill the Rigid Body Phase information tab page.
        Note that the page is a ScrolledWindow, not a Grid
        '''
        def OnThermSel(event):       #needs to be seen by VecRbSizer!
            Obj = event.GetEventObject()
            RBObj = Indx[Obj.GetId()]
            val = Obj.GetValue()
            Ttype = 'A'
            if val == 'Uiso':
                Ttype = 'I'
                RBObj['ThermalMotion'][0] = 'Uiso'
            elif val == 'T':
                RBObj['ThermalMotion'][0] = 'T'
            elif val == 'TL':
                RBObj['ThermalMotion'][0] = 'TL'
            elif val == 'TLS':
                RBObj['ThermalMotion'][0] = 'TLS'
            wx.CallAfter(FillRigidBodyGrid,True)
            if val != 'None':
                cia = data['General']['AtomPtrs'][3]
                for i,id in enumerate(RBObj['Ids']):
                    data['Atoms'][AtLookUp[id]][cia] = Ttype
            G2plt.PlotStructure(G2frame,data)
            
        def ThermDataSizer(RBObj,rbType):
            
            def OnThermval(event):
                event.Skip()
                Obj = event.GetEventObject()
                item = Indx[Obj.GetId()]
                try:
                    val = float(Obj.GetValue())
                    RBObj['ThermalMotion'][1][item] = val
                except ValueError:
                    pass
                Obj.SetValue('%8.4f'%(RBObj['ThermalMotion'][1][item]))
                Cart = G2mth.UpdateRBXYZ(Bmat,RBObj,RBData,rbType)[1]
                Uout = G2mth.UpdateRBUIJ(Bmat,Cart,RBObj)
                cia = data['General']['AtomPtrs'][3]
                for i,id in enumerate(RBObj['Ids']):
                    if Uout[i][0] == 'I':
                        data['Atoms'][AtLookUp[id]][cia+1] = Uout[i][1]
                    else:
                        data['Atoms'][AtLookUp[id]][cia+2:cia+8] = Uout[i][2:8]
                G2plt.PlotStructure(G2frame,data)
                
            def OnTLSRef(event):
                Obj = event.GetEventObject()
                item = Indx[Obj.GetId()]
                RBObj['ThermalMotion'][2][item] = Obj.GetValue()
            
            thermSizer = wx.FlexGridSizer(0,9,5,5)
            model = RBObj['ThermalMotion']
            if model[0] == 'Uiso':
                names = ['Uiso',]
            elif 'T' in model[0]:
                names = ['T11','T22','T33','T12','T13','T23']
            if 'L' in model[0]:
                names += ['L11','L22','L33','L12','L13','L23']
            if 'S' in model[0]:
                names += ['S12','S13','S21','S23','S31','S32','SAA','SBB']
            for i,name in enumerate(names):
                thermSizer.Add(wx.StaticText(RigidBodies,-1,name+': '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                thermVal = wx.TextCtrl(RigidBodies,-1,value='%8.4f'%(model[1][i]),
                    style=wx.TE_PROCESS_ENTER)
                thermVal.Bind(wx.EVT_TEXT_ENTER,OnThermval)
                thermVal.Bind(wx.EVT_KILL_FOCUS,OnThermval)
                Indx[thermVal.GetId()] = i
                thermSizer.Add(thermVal)
                Tcheck = wx.CheckBox(RigidBodies,-1,'Refine?')
                Tcheck.Bind(wx.EVT_CHECKBOX,OnTLSRef)
                Tcheck.SetValue(model[2][i])
                Indx[Tcheck.GetId()] = i
                thermSizer.Add(Tcheck,0,WACV)
            return thermSizer
            
        def LocationSizer(RBObj,rbType):
            
            def OnOrigRef(event):
                RBObj['Orig'][1] = Ocheck.GetValue()
             
            def OnOrienRef(event):
                RBObj['Orient'][1] = Qcheck.GetValue()
                
            def OnOrigX(event):
                event.Skip()
                Obj = event.GetEventObject()
                item = Indx[Obj.GetId()]
                try:
                    val = float(Obj.GetValue())
                    RBObj['Orig'][0][item] = val
                    Obj.SetValue('%8.5f'%(val))
                    newXYZ = G2mth.UpdateRBXYZ(Bmat,RBObj,RBData,rbType)[0]
                    for i,id in enumerate(RBObj['Ids']):
                        data['Atoms'][AtLookUp[id]][cx:cx+3] = newXYZ[i]
                    data['Drawing']['Atoms'] = []
                    UpdateDrawAtoms(atomStyle)
                    G2plt.PlotStructure(G2frame,data)
                except ValueError:
                    pass
                
            def OnOrien(event):
                event.Skip()
                Obj = event.GetEventObject()
                item = Indx[Obj.GetId()]
                A,V = G2mth.Q2AVdeg(RBObj['Orient'][0])
                V = np.inner(Bmat,V)
                try:
                    val = float(Obj.GetValue())
                    if item:
                        V[item-1] = val
                    else:
                        A = val
                    Obj.SetValue('%8.5f'%(val))
                    V = np.inner(Amat,V)
                    Q = G2mth.AVdeg2Q(A,V)
                    if not any(Q):
                        raise ValueError
                    RBObj['Orient'][0] = Q
                    newXYZ = G2mth.UpdateRBXYZ(Bmat,RBObj,RBData,rbType)[0]
                    for i,id in enumerate(RBObj['Ids']):
                        data['Atoms'][AtLookUp[id]][cx:cx+3] = newXYZ[i]
                    data['Drawing']['Atoms'] = []
                    UpdateDrawAtoms(atomStyle)
                    G2plt.PlotStructure(G2frame,data)
                except ValueError:
                    pass
                
            topSizer = wx.FlexGridSizer(0,6,5,5)
            Orig = RBObj['Orig'][0]
            Orien,OrienV = G2mth.Q2AVdeg(RBObj['Orient'][0])
            Orien = [Orien,]
            Orien.extend(OrienV/nl.norm(OrienV))
            topSizer.Add(wx.StaticText(RigidBodies,-1,'Origin x,y,z:'),0,WACV)
            for ix,x in enumerate(Orig):
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                origX = wx.TextCtrl(RigidBodies,-1,value='%8.5f'%(x),style=wx.TE_PROCESS_ENTER)
                origX.Bind(wx.EVT_TEXT_ENTER,OnOrigX)
                origX.Bind(wx.EVT_KILL_FOCUS,OnOrigX)
                Indx[origX.GetId()] = ix
                topSizer.Add(origX,0,WACV)
            topSizer.Add((5,0),)
            Ocheck = wx.CheckBox(RigidBodies,-1,'Refine?')
            Ocheck.Bind(wx.EVT_CHECKBOX,OnOrigRef)
            Ocheck.SetValue(RBObj['Orig'][1])
            topSizer.Add(Ocheck,0,WACV)
            topSizer.Add(wx.StaticText(RigidBodies,-1,'Rotation angle, vector:'),0,WACV)
            for ix,x in enumerate(Orien):
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                orien = wx.TextCtrl(RigidBodies,-1,value='%8.4f'%(x),style=wx.TE_PROCESS_ENTER)
                orien.Bind(wx.EVT_TEXT_ENTER,OnOrien)
                orien.Bind(wx.EVT_KILL_FOCUS,OnOrien)
                Indx[orien.GetId()] = ix
                topSizer.Add(orien,0,WACV)
            Qcheck = wx.ComboBox(RigidBodies,-1,value='',choices=[' ','A','AV'],
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            Qcheck.Bind(wx.EVT_COMBOBOX,OnOrienRef)
            Qcheck.SetValue(RBObj['Orient'][1])
            topSizer.Add(Qcheck)
            return topSizer
                         
        def ResrbSizer(RBObj):
            G2frame.dataFrame.SetStatusText('NB: Rotation vector is in crystallographic space')
             
            def OnTorsionRef(event):
                Obj = event.GetEventObject()
                item = Indx[Obj.GetId()]
                RBObj['Torsions'][item][1] = Obj.GetValue()                
                
            def OnTorsion(event):
                event.Skip()
                Obj = event.GetEventObject()
                item = Indx[Obj.GetId()]
                try:
                    val = float(Obj.GetValue())
                    RBObj['Torsions'][item][0] = val
                    newXYZ = G2mth.UpdateRBXYZ(Bmat,RBObj,RBData,'Residue')[0]
                    for i,id in enumerate(RBObj['Ids']):
                        data['Atoms'][AtLookUp[id]][cx:cx+3] = newXYZ[i]
                except ValueError:
                    pass
                Obj.SetValue("%10.3f"%(RBObj['Torsions'][item][0]))                
                data['Drawing']['Atoms'] = []
                UpdateDrawAtoms(atomStyle)
                drawAtoms.ClearSelection()
                G2plt.PlotStructure(G2frame,data)
                
            def OnDelResRB(event):
                Obj = event.GetEventObject()
                RBId = Indx[Obj.GetId()]
                RBData['Residue'][RBId]['useCount'] -= 1
                RBObjs = data['RBModels']['Residue']
                for rbObj in RBObjs:
                    if RBId == rbObj['RBId']:
                       data['RBModels']['Residue'].remove(rbObj)                 
                G2plt.PlotStructure(G2frame,data)
                wx.CallAfter(FillRigidBodyGrid,True)
                
            resrbSizer = wx.BoxSizer(wx.VERTICAL)
            resrbSizer.Add(wx.StaticText(RigidBodies,-1,120*'-'))
            topLine = wx.BoxSizer(wx.HORIZONTAL)
            topLine.Add(wx.StaticText(RigidBodies,-1,
                'Name: '+RBObj['RBname']+RBObj['numChain']+'   '),0,WACV)
            rbId = RBObj['RBId']
            delRB = wx.CheckBox(RigidBodies,-1,'Delete?')
            delRB.Bind(wx.EVT_CHECKBOX,OnDelResRB)
            Indx[delRB.GetId()] = rbId
            topLine.Add(delRB,0,WACV)
            resrbSizer.Add(topLine)
            resrbSizer.Add(LocationSizer(RBObj,'Residue'))
            resrbSizer.Add(wx.StaticText(RigidBodies,-1,'Torsions:'),0,WACV)
            torSizer = wx.FlexGridSizer(0,6,5,5)
            for itors,tors in enumerate(RBObj['Torsions']):
                torSizer.Add(wx.StaticText(RigidBodies,-1,'Torsion '+'%d'%(itors)),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                torsTxt = wx.TextCtrl(RigidBodies,-1,value='%.3f'%(tors[0]),style=wx.TE_PROCESS_ENTER)
                torsTxt.Bind(wx.EVT_TEXT_ENTER,OnTorsion)
                torsTxt.Bind(wx.EVT_KILL_FOCUS,OnTorsion)
                Indx[torsTxt.GetId()] = itors
                torSizer.Add(torsTxt)
                torCheck = wx.CheckBox(RigidBodies,-1,'Refine?')
                torCheck.Bind(wx.EVT_CHECKBOX,OnTorsionRef)
                torCheck.SetValue(tors[1])
                Indx[torCheck.GetId()] = itors
                torSizer.Add(torCheck,0,WACV)
            resrbSizer.Add(torSizer)
            tchoice = ['None','Uiso','T','TL','TLS']
            thermSizer = wx.BoxSizer(wx.HORIZONTAL)
            thermSizer.Add(wx.StaticText(RigidBodies,-1,'Rigid body thermal motion model: '),0,WACV)
            thermSel = wx.ComboBox(RigidBodies,-1,value=RBObj['ThermalMotion'][0],choices=tchoice,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            Indx[thermSel.GetId()] = RBObj
            thermSel.Bind(wx.EVT_COMBOBOX,OnThermSel)
            thermSizer.Add(thermSel,0,WACV)
            thermSizer.Add(wx.StaticText(RigidBodies,-1,' Units: T A^2, L deg^2, S deg-A'),0,WACV)
            resrbSizer.Add(thermSizer)
            if RBObj['ThermalMotion'][0] != 'None':
                resrbSizer.Add(ThermDataSizer(RBObj,'Residue'))
            return resrbSizer
            
        def VecrbSizer(RBObj):
            G2frame.dataFrame.SetStatusText('NB: Rotation vector is in crystallographic space')
                   
            def OnDelVecRB(event):
                Obj = event.GetEventObject()
                RBId = Indx[Obj.GetId()]
                RBData['Vector'][RBId]['useCount'] -= 1                
                RBObjs = data['RBModels']['Vector']
                for rbObj in RBObjs:
                    if RBId == rbObj['RBId']:
                       data['RBModels']['Vector'].remove(rbObj)                 
                G2plt.PlotStructure(G2frame,data)
                wx.CallAfter(FillRigidBodyGrid,True)
             
            vecrbSizer = wx.BoxSizer(wx.VERTICAL)
            vecrbSizer.Add(wx.StaticText(RigidBodies,-1,120*'-'))
            topLine = wx.BoxSizer(wx.HORIZONTAL)
            topLine.Add(wx.StaticText(RigidBodies,-1,
                'Name: '+RBObj['RBname']+'   '),0,WACV)
            rbId = RBObj['RBId']
            delRB = wx.CheckBox(RigidBodies,-1,'Delete?')
            delRB.Bind(wx.EVT_CHECKBOX,OnDelVecRB)
            Indx[delRB.GetId()] = rbId
            topLine.Add(delRB,0,WACV)
            vecrbSizer.Add(topLine)
            vecrbSizer.Add(LocationSizer(RBObj,'Vector'))
            tchoice = ['None','Uiso','T','TL','TLS']
            thermSizer = wx.BoxSizer(wx.HORIZONTAL)
            thermSizer.Add(wx.StaticText(RigidBodies,-1,'Rigid body thermal motion model: '),0,WACV)
            thermSel = wx.ComboBox(RigidBodies,-1,value=RBObj['ThermalMotion'][0],choices=tchoice,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            Indx[thermSel.GetId()] = RBObj
            thermSel.Bind(wx.EVT_COMBOBOX,OnThermSel)
            thermSizer.Add(thermSel,0,WACV)
            thermSizer.Add(wx.StaticText(RigidBodies,-1,' Units: T A^2, L deg^2, S deg-A'),0,WACV)
            vecrbSizer.Add(thermSizer)
            if RBObj['ThermalMotion'][0] != 'None':
                vecrbSizer.Add(ThermDataSizer(RBObj,'Vector'))
            return vecrbSizer                
        
        # FillRigidBodyGrid executable code starts here
        if refresh:
            #RigidBodies.DestroyChildren() # bad, deletes scrollbars on Mac!
            if RigidBodies.GetSizer():
                RigidBodies.GetSizer().Clear(True)
        general = data['General']
        cx,ct,cs,cia = general['AtomPtrs']
        AtLookUp = G2mth.FillAtomLookUp(data['Atoms'],cia+8)
        Amat,Bmat = G2lat.cell2AB(general['Cell'][1:7])
        Id = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Rigid bodies')
        if not Id:
            return
        RBData = G2frame.PatternTree.GetItemPyData(Id)
        Indx = {}
        atomStyle = 'balls & sticks'
        if 'macro' in general['Type']:
            atomStyle = 'sticks'
        G2frame.dataFrame.SetStatusText('')
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        if not data['RBModels']:
            mainSizer.Add((5,5),0)
            mainSizer.Add(wx.StaticText(RigidBodies,-1,'No rigid body models:'),0,WACV)
            mainSizer.Add((5,5),0)
        if 'Residue' in data['RBModels']:
            mainSizer.Add((5,5),0)
            mainSizer.Add(wx.StaticText(RigidBodies,-1,'Residue rigid bodies:'),0,WACV)
            mainSizer.Add((5,5),0)
            for RBObj in data['RBModels']['Residue']:
                mainSizer.Add(ResrbSizer(RBObj))
        if 'Vector' in data['RBModels']:
            mainSizer.Add((5,5),0)
            mainSizer.Add(wx.StaticText(RigidBodies,-1,'Vector rigid bodies:'),0,WACV)
            mainSizer.Add((5,5),0)
            for RBObj in data['RBModels']['Vector']:
                mainSizer.Add(VecrbSizer(RBObj))

        SetPhaseWindow(G2frame.dataFrame,RigidBodies,mainSizer)

    def OnRBCopyParms(event):
        RBObjs = []
        for rbType in ['Vector','Residue']:            
            RBObjs += data['RBModels'].get(rbType,[])
        if not len(RBObjs):
            print '**** ERROR - no rigid bodies defined ****'
            return
        if len(RBObjs) == 1:
            print '**** INFO - only one rigid body defined; nothing to copy to ****'
            return
        Source = []
        sourceRB = {}
        for RBObj in RBObjs:
            Source.append(RBObj['RBname'])
        dlg = wx.SingleChoiceDialog(G2frame,'Select source','Copy rigid body parameters',Source)
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelection()
            for item in ['Orig','Orient','ThermalMotion']: 
                sourceRB.update({item:RBObjs[sel][item],})
        dlg.Destroy()
        if not sourceRB:
            return
        dlg = wx.MultiChoiceDialog(G2frame,'Select targets','Copy rigid body parameters',Source)
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelections()
            for x in sel:
                RBObjs[x].update(copy.copy(sourceRB))
        G2plt.PlotStructure(G2frame,data)
        wx.CallAfter(FillRigidBodyGrid(True))
                
    def OnRBAssign(event):
        
        G2frame.dataFrame.SetStatusText('')
        RBData = G2frame.PatternTree.GetItemPyData(   
            G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Rigid bodies'))
        rbNames = {}
        for rbVec in RBData['Vector']:
            if rbVec != 'AtInfo':
                rbNames[RBData['Vector'][rbVec]['RBname']] =['Vector',rbVec]
        for rbRes in RBData['Residue']:
            if rbRes != 'AtInfo':
                rbNames[RBData['Residue'][rbRes]['RBname']] = ['Residue',rbRes]
        if not rbNames:
            print '**** ERROR - no rigid bodies defined ****'
            return
        general = data['General']
        Amat,Bmat = G2lat.cell2AB(general['Cell'][1:7])
        cx,ct = general['AtomPtrs'][:2]
        atomData = data['Atoms']
        Indx = {}
        atInd = [-1,-1,-1]
        data['testRBObj'] = {}
            
        def Draw():
            
            def OnOk(event):
                rbType = data['testRBObj']['rbType']
                RBObjs = data['RBModels'].get(rbType,[])
                rbObj = data['testRBObj']['rbObj']
                rbId = rbObj['RBId']
                newXYZ = G2mth.UpdateRBXYZ(Bmat,rbObj,RBData,rbType)[0]
                Ids = []
                dmax = 0.0
                oldXYZ = G2mth.getAtomXYZ(atomData,cx)
                for xyz in newXYZ:
                    dist = G2mth.GetXYZDist(xyz,oldXYZ,Amat)
                    dmax = max(dmax,np.min(dist))
                    id = np.argmin(dist)
                    Ids.append(atomData[id][-1])
                    atomData[id][cx:cx+3] = xyz
                if dmax > 1.0:
                    print '**** WARNING - some atoms not found or misidentified ****'
                    print '****           check torsion angles & try again      ****'
                    OkBtn.SetLabel('Not Ready')
                    OkBtn.Enable(False)
                    return
                rbObj['Ids'] = Ids
                rbObj['ThermalMotion'] = ['None',[0. for i in range(21)],[False for i in range(21)]] #type,values,flags
                rbObj['RBname'] += ':'+str(RBData[rbType][rbId]['useCount'])
                RBObjs.append(rbObj)
                data['RBModels'][rbType] = RBObjs
                RBData[rbType][rbId]['useCount'] += 1
                del data['testRBObj']
                G2plt.PlotStructure(G2frame,data)
                FillRigidBodyGrid(True)
                
            def OnCancel(event):
                del data['testRBObj']
                FillRigidBodyGrid(True)
                
            def OnRBSel(event):
                selection = rbSel.GetValue()
                rbType,rbId = rbNames[selection]
                data['testRBObj']['rbAtTypes'] = RBData[rbType][rbId]['rbTypes']
                data['testRBObj']['AtInfo'] = RBData[rbType]['AtInfo']
                data['testRBObj']['rbType'] = rbType
                data['testRBObj']['rbData'] = RBData
                data['testRBObj']['Sizers'] = {}
                rbRef = RBData[rbType][rbId]['rbRef']
                data['testRBObj']['rbRef'] = rbRef
                refType = []
                refName = []
                for ref in rbRef[:3]:
                    reftype = data['testRBObj']['rbAtTypes'][ref]
                    refType.append(reftype)
                    refName.append(reftype+' '+str(rbRef[0]))
                atNames,AtNames = fillAtNames(refType,atomData,ct)
                data['testRBObj']['atNames'] = atNames
                data['testRBObj']['AtNames'] = AtNames
                data['testRBObj']['rbObj'] = {'Orig':[[0,0,0],False],
                    'Orient':[[0.,0.,0.,1.],' '],'Ids':[],'RBId':rbId,'Torsions':[],
                    'numChain':'','RBname':RBData[rbType][rbId]['RBname']}
                data['testRBObj']['torAtms'] = []                
                for item in RBData[rbType][rbId].get('rbSeq',[]):
                    data['testRBObj']['rbObj']['Torsions'].append([item[2],False])
                    data['testRBObj']['torAtms'].append([-1,-1,-1])
                Draw()
                
            def fillAtNames(refType,atomData,ct):
                atNames = [{},{},{}]
                AtNames = {}
                for iatm,atom in enumerate(atomData):
                    AtNames[atom[ct-1]] = iatm
                    for i,reftype in enumerate(refType):
                        if atom[ct] == reftype:
                            atNames[i][atom[ct-1]] = iatm
                return atNames,AtNames
                
            def OnAtOrigPick(event):
                Obj = event.GetEventObject()
                item = Indx[Obj.GetId()]
                atName = Obj.GetValue()
                rbType = data['testRBObj']['rbType']
                atInd[0] = atNames[item][atName]
                if 'Vector' in rbType:
                    rbObj = data['testRBObj']['rbObj']
                    rbId = rbObj['RBId']
                    rbRef = data['testRBObj']['rbRef']
                    rbXYZ = -RBData[rbType][rbId]['rbXYZ']
                    nref = atNames[item][atName]
                    Oxyz = np.inner(Bmat,np.array(rbXYZ[rbRef[0]]))
                    Nxyz = np.array(atomData[nref][cx:cx+3])
                    Orig = Nxyz-Oxyz
                    data['testRBObj']['rbObj']['Orig'][0] = Orig   
                else:
                    Orig = atomData[atNames[item][atName]][cx:cx+3]
                    data['testRBObj']['rbObj']['Orig'][0] = Orig
                for x,item in zip(Orig,Xsizers):
                    item.SetLabel('%10.5f'%(x))
                G2plt.PlotStructure(G2frame,data)
                
            def OnAtQPick(event):
                Obj = event.GetEventObject()
                item = Indx[Obj.GetId()]
                atName = Obj.GetValue()
                atInd[item] = atNames[item][atName]
                if any([x<0 for x in atInd]):
                    return
                OkBtn.SetLabel('OK')
                OkBtn.Enable(True)
                rbType = data['testRBObj']['rbType']
                rbObj = data['testRBObj']['rbObj']
                rbId = rbObj['RBId']
                rbRef = data['testRBObj']['rbRef']
                rbXYZ = RBData[rbType][rbId]['rbXYZ']
                rbOrig = rbXYZ[rbRef[0]]
                VAR = rbXYZ[rbRef[1]]-rbOrig
                VBR = rbXYZ[rbRef[2]]-rbOrig
                if rbType == 'Vector':
                    Orig = np.array(atomData[atInd[0]][cx:cx+3])
                else:
                    Orig = np.array(data['testRBObj']['rbObj']['Orig'][0])                
                VAC = np.inner(Amat,np.array(atomData[atInd[1]][cx:cx+3])-Orig)
                VBC = np.inner(Amat,np.array(atomData[atInd[2]][cx:cx+3])-Orig)
                VCC = np.cross(VAR,VAC)
                QuatA = G2mth.makeQuat(VAR,VAC,VCC)[0]
                VAR = G2mth.prodQVQ(QuatA,VAR)
                VBR = G2mth.prodQVQ(QuatA,VBR)
                QuatB = G2mth.makeQuat(VBR,VBC,VAR)[0]
                QuatC = G2mth.prodQQ(QuatB,QuatA)
                data['testRBObj']['rbObj']['Orient'] = [QuatC,' ']
                for x,item in zip(QuatC,Osizers):
                    item.SetLabel('%10.4f'%(x))                
                if rbType == 'Vector':
                    Oxyz = np.inner(Bmat,G2mth.prodQVQ(QuatC,rbOrig))
                    Nxyz = np.array(atomData[atInd[0]][cx:cx+3])
                    Orig = Nxyz-Oxyz
                    data['testRBObj']['rbObj']['Orig'][0] = Orig
                    for x,item in zip(Orig,Xsizers):
                        item.SetLabel('%10.5f'%(x))
                G2plt.PlotStructure(G2frame,data)
                
            def OnTorAngle(event):
                event.Skip()
                OkBtn.SetLabel('OK')
                OkBtn.Enable(True)
                Obj = event.GetEventObject()
                [tor,torSlide] = Indx[Obj.GetId()]
                Tors = data['testRBObj']['rbObj']['Torsions'][tor]
                try:
                    value = float(Obj.GetValue())
                except ValueError:
                    value = Tors[0]
                Tors[0] = value
                Obj.SetValue('%8.3f'%(value))
                torSlide.SetValue(int(value*10))
                G2plt.PlotStructure(G2frame,data)
                
            def OnTorSlide(event):
                OkBtn.SetLabel('OK')
                OkBtn.Enable(True)
                Obj = event.GetEventObject()
                tor,ang = Indx[Obj.GetId()]
                Tors = data['testRBObj']['rbObj']['Torsions'][tor]
                val = float(Obj.GetValue())/10.
                Tors[0] = val
                ang.SetValue('%8.3f'%(val))
                G2plt.PlotStructure(G2frame,data)

            if len(data['testRBObj']):
                G2plt.PlotStructure(G2frame,data)
                    
            #RigidBodies.DestroyChildren() # bad, deletes scrollbars on Mac!
            if RigidBodies.GetSizer():
                RigidBodies.GetSizer().Clear(True)
            mainSizer = wx.BoxSizer(wx.VERTICAL)
            mainSizer.Add((5,5),0)
            if data['testRBObj']:
                Xsizers = []
                Osizers = []
                rbObj = data['testRBObj']['rbObj']
                rbName = rbObj['RBname']
                rbId = rbObj['RBId']
                Orig = rbObj['Orig'][0]
                Orien = rbObj['Orient'][0]
                rbRef = data['testRBObj']['rbRef']
                Torsions = rbObj['Torsions']
                refName = []
                for ref in rbRef:
                    refName.append(data['testRBObj']['rbAtTypes'][ref]+str(ref))
                atNames = data['testRBObj']['atNames']
                mainSizer.Add(wx.StaticText(RigidBodies,-1,'Locate rigid body : '+rbName),
                    0,WACV)
                mainSizer.Add((5,5),0)
                OriSizer = wx.FlexGridSizer(0,5,5,5)
                OriSizer.Add(wx.StaticText(RigidBodies,-1,'Origin x,y,z: '),0,WACV)
                for ix,x in enumerate(Orig):
                    origX = wx.StaticText(RigidBodies,-1,'%10.5f'%(x))
                    OriSizer.Add(origX,0,WACV)
                    Xsizers.append(origX)
                OriSizer.Add((5,0),)
                if len(atomData):
                    choice = atNames[0].keys()
                    choice.sort()
                    data['testRBObj']['Sizers']['Xsizers'] = Xsizers
                OriSizer.Add(wx.StaticText(RigidBodies,-1,'Orientation quaternion: '),0,WACV)
                for ix,x in enumerate(Orien):
                    orien = wx.StaticText(RigidBodies,-1,'%10.4f'%(x))
                    OriSizer.Add(orien,0,WACV)
                    Osizers.append(orien)
                data['testRBObj']['Sizers']['Osizers'] = Osizers
                mainSizer.Add(OriSizer)
                mainSizer.Add((5,5),0)
                RefSizer = wx.FlexGridSizer(0,7,5,5)
                if len(atomData):
                    RefSizer.Add(wx.StaticText(RigidBodies,-1,'Location setting: Select match to'),0,WACV)
                    for i in [0,1,2]:
                        choice = ['',]+atNames[i].keys()
                        choice.sort()
                        RefSizer.Add(wx.StaticText(RigidBodies,-1,' '+refName[i]+': '),0,WACV)
                        atPick = wx.ComboBox(RigidBodies,-1,value='',
                            choices=choice[1:],style=wx.CB_READONLY|wx.CB_DROPDOWN)
                        if i:
                            atPick.Bind(wx.EVT_COMBOBOX, OnAtQPick)
                        else:
                            atPick.Bind(wx.EVT_COMBOBOX, OnAtOrigPick)                            
                        Indx[atPick.GetId()] = i
                        RefSizer.Add(atPick,0,WACV)
                mainSizer.Add(RefSizer)
                mainSizer.Add((5,5),0)
                if Torsions:                    
                    rbSeq = RBData['Residue'][rbId]['rbSeq']
                    TorSizer = wx.FlexGridSizer(0,4)
                    TorSizer.AddGrowableCol(1,1)
                    for t,[torsion,seq] in enumerate(zip(Torsions,rbSeq)):
                        torName = ''
                        for item in [seq[0],seq[1],seq[3][0]]:
                            torName += data['testRBObj']['rbAtTypes'][item]+str(item)+' '
                        TorSizer.Add(wx.StaticText(RigidBodies,-1,'Side chain torsion for rb seq: '+torName),0,WACV)
                        torSlide = wx.Slider(RigidBodies,style=wx.SL_HORIZONTAL)
                        torSlide.SetRange(0,3600)
                        torSlide.SetValue(int(torsion[0]*10.))
                        torSlide.Bind(wx.EVT_SLIDER, OnTorSlide)
                        TorSizer.Add(torSlide,1,wx.EXPAND|wx.RIGHT)
                        TorSizer.Add(wx.StaticText(RigidBodies,-1,' Angle: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                        ang = wx.TextCtrl(RigidBodies,-1,value='%8.3f'%(torsion[0]),style=wx.TE_PROCESS_ENTER)
                        ang.Bind(wx.EVT_TEXT_ENTER,OnTorAngle)
                        ang.Bind(wx.EVT_KILL_FOCUS,OnTorAngle)
                        Indx[torSlide.GetId()] = [t,ang]
                        Indx[ang.GetId()] = [t,torSlide]
                        TorSizer.Add(ang,0,WACV)                            
                    mainSizer.Add(TorSizer,1,wx.EXPAND|wx.RIGHT)
                else:
                    mainSizer.Add(wx.StaticText(RigidBodies,-1,'No side chain torsions'),0,WACV)
            else:
                mainSizer.Add(wx.StaticText(RigidBodies,-1,'Assign rigid body:'),0,WACV)
                mainSizer.Add((5,5),0)
                topSizer = wx.BoxSizer(wx.HORIZONTAL)
                topSizer.Add(wx.StaticText(RigidBodies,-1,'Select rigid body model'),0,WACV)
                rbSel = wx.ComboBox(RigidBodies,-1,value='',choices=rbNames.keys(),
                    style=wx.CB_READONLY|wx.CB_DROPDOWN)
                rbSel.Bind(wx.EVT_COMBOBOX, OnRBSel)
                topSizer.Add((5,5),0)
                topSizer.Add(rbSel,0,WACV)
                mainSizer.Add(topSizer)                
                
            OkBtn = wx.Button(RigidBodies,-1,"Not ready")
            OkBtn.Bind(wx.EVT_BUTTON, OnOk)
            OkBtn.Enable(False)
            CancelBtn = wx.Button(RigidBodies,-1,'Cancel')
            CancelBtn.Bind(wx.EVT_BUTTON, OnCancel)
            btnSizer = wx.BoxSizer(wx.HORIZONTAL)
            btnSizer.Add((20,20),1)
            btnSizer.Add(OkBtn)
            btnSizer.Add(CancelBtn)
            btnSizer.Add((20,20),1)
            mainSizer.Add(btnSizer,0,wx.EXPAND|wx.BOTTOM|wx.TOP, 10)
            SetPhaseWindow(G2frame.dataFrame,RigidBodies,mainSizer)
        Draw()
        
    def OnAutoFindResRB(event):
        RBData = G2frame.PatternTree.GetItemPyData(   
            G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Rigid bodies'))
        rbKeys = RBData['Residue'].keys()
        rbKeys.remove('AtInfo')
        if not len(rbKeys):
            print '**** ERROR - no residue rigid bodies are defined ****'
            return
        RBNames = [RBData['Residue'][k]['RBname'] for k in rbKeys]
        RBIds = dict(zip(RBNames,rbKeys))
        general = data['General']
        cx,ct,cs,cia = general['AtomPtrs']
        Amat,Bmat = G2lat.cell2AB(general['Cell'][1:7])
        Atoms = data['Atoms']
        AtLookUp = G2mth.FillAtomLookUp(Atoms,cia+8)
        if 'macro' not in general['Type']:
            print '**** ERROR - this phase is not a macromolecule ****'
            return
        if not len(Atoms):
            print '**** ERROR - this phase has no atoms ****'
            return
        RBObjs = []
        cx,ct = general['AtomPtrs'][:2]
        iatm = 0
        wx.BeginBusyCursor()
        try:
            while iatm < len(Atoms):
                atom = Atoms[iatm]
                res = atom[1].strip()
                numChain = ' %s %s'%(atom[0],atom[2])
                if res not in RBIds or atom[ct-1] == 'OXT':
                    iatm += 1
                    continue        #skip for OXT, water molecules, etc.
                rbRes = RBData['Residue'][RBIds[res]]
                rbRef = rbRes['rbRef']
                VAR = rbRes['rbXYZ'][rbRef[1]]-rbRes['rbXYZ'][rbRef[0]]
                VBR = rbRes['rbXYZ'][rbRef[2]]-rbRes['rbXYZ'][rbRef[0]]
                rbObj = {'RBname':rbRes['RBname']+':'+str(rbRes['useCount']),'numChain':numChain}
                rbAtoms = []
                rbIds = []
                for iratm in range(len(rbRes['atNames'])):
                    rbAtoms.append(np.array(Atoms[iatm][cx:cx+3]))
                    rbIds.append(Atoms[iatm][20])
                    iatm += 1    #puts this at beginning of next residue?
                Orig = rbAtoms[rbRef[0]]
                rbObj['RBId'] = RBIds[res]
                rbObj['Ids'] = rbIds
                rbObj['Orig'] = [Orig,False]
#                print ' residue '+rbRes['RBname']+str(atom[0]).strip()+ \
#                    ' origin at: ','%.5f %.5f %.5f'%(Orig[0],Orig[1],Orig[2])
                VAC = np.inner(Amat,rbAtoms[rbRef[1]]-Orig)
                VBC = np.inner(Amat,rbAtoms[rbRef[2]]-Orig)
                VCC = np.cross(VAR,VAC)
                QuatA = G2mth.makeQuat(VAR,VAC,VCC)[0]
                VAR = G2mth.prodQVQ(QuatA,VAR)
                VBR = G2mth.prodQVQ(QuatA,VBR)
                QuatB = G2mth.makeQuat(VBR,VBC,VAR)[0]
                QuatC = G2mth.prodQQ(QuatB,QuatA)
                rbObj['Orient'] = [QuatC,' ']
                rbObj['ThermalMotion'] = ['None',[0. for i in range(21)],[False for i in range(21)]] #type,values,flags
                SXYZ = []
                TXYZ = []
                rbObj['Torsions'] = []
                for i,xyz in enumerate(rbRes['rbXYZ']):
                    SXYZ.append(G2mth.prodQVQ(QuatC,xyz))                
                    TXYZ.append(np.inner(Amat,rbAtoms[i]-Orig))
                for Oatm,Patm,x,Riders in rbRes['rbSeq']:
                    VBR = SXYZ[Oatm]-SXYZ[Patm]
                    VAR = SXYZ[Riders[0]]-SXYZ[Patm]
                    VAC = TXYZ[Riders[0]]-TXYZ[Patm]
                    QuatA,D = G2mth.makeQuat(VAR,VAC,VBR)
                    ang = 180.*D/np.pi
                    rbObj['Torsions'].append([ang,False])
                    for ride in Riders:
                        SXYZ[ride] = G2mth.prodQVQ(QuatA,SXYZ[ride]-SXYZ[Patm])+SXYZ[Patm]
                rbRes['useCount'] += 1
                RBObjs.append(rbObj)
            data['RBModels']['Residue'] = RBObjs
            for RBObj in RBObjs:
                newXYZ = G2mth.UpdateRBXYZ(Bmat,RBObj,RBData,'Residue')[0]
                for i,id in enumerate(RBObj['Ids']):
                    data['Atoms'][AtLookUp[id]][cx:cx+3] = newXYZ[i]
        finally:
            wx.EndBusyCursor()
        wx.CallAfter(FillRigidBodyGrid,True)
        
    def OnRBRemoveAll(event):
        data['RBModels']['Residue'] = []
        data['RBModels']['Vector'] = []
        RBData = G2frame.PatternTree.GetItemPyData(   
            G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Rigid bodies'))
        for RBType in ['Vector','Residue']:
            for rbId in RBData[RBType]:
                RBData[RBType][rbId]['useCount'] = 0        
        FillRigidBodyGrid(True)
        
    def OnGlobalResRBTherm(event):
        RBObjs = data['RBModels']['Residue']
        names = ['None','Uiso','T','TL','TLS']
        cia = data['General']['AtomPtrs'][3]
        AtLookUp = G2mth.FillAtomLookUp(data['Atoms'],cia+8)
        dlg = wx.SingleChoiceDialog(G2frame,'Select','Residue thermal motion model',names)
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelection()
            parm = names[sel]
            Ttype = 'A'
            if parm == 'Uiso':
                Ttype = 'I'        
            for rbObj in RBObjs:
                rbObj['ThermalMotion'][0] = parm
                if parm != 'None':
                    for i,id in enumerate(rbObj['Ids']):
                        data['Atoms'][AtLookUp[id]][cia] = Ttype
        dlg.Destroy()
        wx.CallAfter(FillRigidBodyGrid,True)

    def OnGlobalResRBRef(event):
        RBObjs = data['RBModels']['Residue']
        names = ['Origin','Orient. angle','Full Orient.']
        nTor = 0
        for rbObj in RBObjs:
            nTor = max(nTor,len(rbObj['Torsions']))
        names += ['Torsion '+str(i) for i in range(nTor)]
        if np.any([rbObj['ThermalMotion'][0] == 'Uiso' for rbObj in RBObjs]):
           names += ['Uiso',]
        if np.any([rbObj['ThermalMotion'][0] == 'TLS' for rbObj in RBObjs]):
           names += ['Tii','Tij','Lii','Lij','Sij']
        elif np.any([rbObj['ThermalMotion'][0] == 'TL' for rbObj in RBObjs]):
           names += ['Tii','Tij','Lii','Lij']
        elif np.any([rbObj['ThermalMotion'][0] == 'T' for rbObj in RBObjs]):
           names += ['Tii','Tij']

        dlg = wx.MultiChoiceDialog(G2frame,'Select','Refinement controls',names)
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelections()
            parms = []
            for x in sel:
                parms.append(names[x])
            wx.BeginBusyCursor()
            try:
                for rbObj in RBObjs:
                    if 'Origin' in parms:
                        rbObj['Orig'][1] = True
                    else:
                        rbObj['Orig'][1] = False
                    if 'Full Orient.' in parms:
                        rbObj['Orient'][1] = 'AV'
                    elif 'Orient. angle' in parms:
                        rbObj['Orient'][1] = 'A'
                    else:
                        rbObj['Orient'][1] = ' '
                    for i in range(len(rbObj['Torsions'])):
                        if 'Torsion '+str(i) in parms:
                            rbObj['Torsions'][i][1] = True
                        else:
                            rbObj['Torsions'][i][1] = False
                    if rbObj['ThermalMotion'][0] == 'Uiso':
                        if 'Uiso' in parms:
                           rbObj['ThermalMotion'][2][0] = True
                        else:
                           rbObj['ThermalMotion'][2][0] = False
                    elif 'T' in rbObj['ThermalMotion'][0]:
                        if 'Tii' in parms:
                            rbObj['ThermalMotion'][2][0:2] = [True,True,True]
                        else:
                            rbObj['ThermalMotion'][2][0:2] = [False,False,False]
                        if 'Tij' in parms:
                            rbObj['ThermalMotion'][2][3:6] = [True,True,True]
                        else:
                            rbObj['ThermalMotion'][2][3:6] = [False,False,False]
                    elif 'L' in rbObj['ThermalMotion'][0]:
                        if 'Lii' in parms:
                            rbObj['ThermalMotion'][2][6:9] = [True,True,True]
                        else:
                            rbObj['ThermalMotion'][2][6:9] = [False,False,False]
                        if 'Lij' in parms:
                            rbObj['ThermalMotion'][2][9:12] = [True,True,True]
                        else:
                            rbObj['ThermalMotion'][2][9:12] = [False,False,False]
                    elif 'S' in rbObj['ThermalMotion'][0]:
                        if 'Sij' in parms:
                            rbObj['ThermalMotion'][2][12:20] = [True,True,True,True,True,True,True,True]
                        else:
                            rbObj['ThermalMotion'][2][12:20] = [False,False,False,False,False,False,False,False]
            finally:
                wx.EndBusyCursor()
            FillRigidBodyGrid()
            
################################################################################
##### MC/SA routines
################################################################################

    def UpdateMCSA(Scroll=0):
        Indx = {}
        
        def OnPosRef(event):
            Obj = event.GetEventObject()
            model,item,ix = Indx[Obj.GetId()]
            model[item][1][ix] = Obj.GetValue()
            
        def OnPosVal(event):
            event.Skip()
            Obj = event.GetEventObject()
            model,item,ix = Indx[Obj.GetId()]
            try:
                model[item][0][ix] = float(Obj.GetValue())
            except ValueError:
                pass
            Obj.SetValue("%.4f"%(model[item][0][ix]))
            G2plt.PlotStructure(G2frame,data)
            
        def OnPosRange(event):
            event.Skip()
            Obj = event.GetEventObject()
            model,item,ix = Indx[Obj.GetId()]
            Range = Obj.GetValue().split()
            try:
                rmin,rmax = [float(Range[i]) for i in range(2)]
                if rmin >= rmax:
                    raise ValueError
            except (ValueError,IndexError):
                rmin,rmax = model[item][2][ix]
            model[item][2][ix] = [rmin,rmax]
            Obj.SetValue('%.3f %.3f'%(rmin,rmax))                 
                
        def atomSizer(model):
            
            atomsizer = wx.FlexGridSizer(0,7,5,5)
            atomsizer.Add(wx.StaticText(G2frame.MCSA,-1,' Atom: '+model['name']+': '),0,WACV)
            for ix,item in enumerate(['x','y','z']):
                posRef = wx.CheckBox(G2frame.MCSA,-1,label=item+': ')
                posRef.SetValue(model['Pos'][1][ix])
                posRef.Bind(wx.EVT_CHECKBOX,OnPosRef)
                Indx[posRef.GetId()] = [model,'Pos',ix]
                atomsizer.Add(posRef,0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                posVal = wx.TextCtrl(G2frame.MCSA,-1,'%.4f'%(model['Pos'][0][ix]),style=wx.TE_PROCESS_ENTER)
                posVal.Bind(wx.EVT_TEXT_ENTER,OnPosVal)
                posVal.Bind(wx.EVT_KILL_FOCUS,OnPosVal)
                Indx[posVal.GetId()] = [model,'Pos',ix]
                atomsizer.Add(posVal,0,WACV)
            atomsizer.Add((5,5),0)
            for ix,item in enumerate(['x','y','z']):
                atomsizer.Add(wx.StaticText(G2frame.MCSA,-1,' Range: '),0,WACV)
                rmin,rmax = model['Pos'][2][ix]
                posRange = wx.TextCtrl(G2frame.MCSA,-1,'%.3f %.3f'%(rmin,rmax),style=wx.TE_PROCESS_ENTER)
                Indx[posRange.GetId()] = [model,'Pos',ix]
                posRange.Bind(wx.EVT_TEXT_ENTER,OnPosRange)
                posRange.Bind(wx.EVT_KILL_FOCUS,OnPosRange)
                atomsizer.Add(posRange,0,WACV)
            return atomsizer
            
        def rbSizer(model):
            
            def OnOrVar(event):
                Obj = event.GetEventObject()
                model = Indx[Obj.GetId()]
                model['Ovar'] = Obj.GetValue()
            
            def OnOriVal(event):
                event.Skip()
                Obj = event.GetEventObject()
                model,ix,ObjA,ObjV = Indx[Obj.GetId()]
                A = model['Ori'][0][0]
                V = model['Ori'][0][1:]
                if ix:
                    Anew = A
                    Vec = ObjV.GetValue().split()
                    try:
                        Vnew = [float(Vec[i]) for i in range(3)]
                    except ValueError:
                        Vnew = V
                else:
                    Vnew = V
                    try:
                        Anew = float(ObjA.GetValue())
                        if not Anew:    #==0.0!
                            Anew = 360.
                    except ValueError:
                        Anew = A
                Q = G2mth.AVdeg2Q(Anew,Vnew)
                A,V = G2mth.Q2AVdeg(Q)
                model['Ori'][0][0] = A
                model['Ori'][0][1:] = V
                if ix:
                    ObjV.SetValue('%.3f %.3f %.3f'%(V[0],V[1],V[2]))
                else:
                    ObjA.SetValue('%.5f'%(A))
                    ObjV.SetValue('%.3f %.3f %.3f'%(V[0],V[1],V[2]))
                G2plt.PlotStructure(G2frame,data)
#                UpdateMCSA()

            def OnMolCent(event):
                Obj = event.GetEventObject()
                model = Indx[Obj.GetId()]
                model['MolCent'][1] = Obj.GetValue()
                if model['MolCent'][1]:
                    G2mth.SetMolCent(model,RBData)                
                G2plt.PlotStructure(G2frame,data)
            
            rbsizer = wx.BoxSizer(wx.VERTICAL)
            rbsizer1 = wx.FlexGridSizer(0,7,5,5)
            rbsizer1.Add(wx.StaticText(G2frame.MCSA,-1,model['Type']+': '+model['name']+': '),0,WACV)
            for ix,item in enumerate(['x','y','z']):
                posRef = wx.CheckBox(G2frame.MCSA,-1,label=item+': ')
                posRef.SetValue(model['Pos'][1][ix])
                posRef.Bind(wx.EVT_CHECKBOX,OnPosRef)
                Indx[posRef.GetId()] = [model,'Pos',ix]
                rbsizer1.Add(posRef,0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                posVal = wx.TextCtrl(G2frame.MCSA,-1,'%.4f'%(model['Pos'][0][ix]),style=wx.TE_PROCESS_ENTER)
                posVal.Bind(wx.EVT_TEXT_ENTER,OnPosVal)
                posVal.Bind(wx.EVT_KILL_FOCUS,OnPosVal)
                Indx[posVal.GetId()] = [model,'Pos',ix]
                rbsizer1.Add(posVal,0,WACV)
            molcent = wx.CheckBox(G2frame.MCSA,-1,label=' Use mol. center? ')
            molcent.SetValue(model['MolCent'][1])
            molcent.Bind(wx.EVT_CHECKBOX,OnMolCent)
            Indx[molcent.GetId()] = model
            rbsizer1.Add(molcent,0,WACV)
            for ix,item in enumerate(['x','y','z']):
                rbsizer1.Add(wx.StaticText(G2frame.MCSA,-1,' Range: '),0,WACV)
                rmin,rmax = model['Pos'][2][ix]
                posRange = wx.TextCtrl(G2frame.MCSA,-1,'%.3f %.3f'%(rmin,rmax),style=wx.TE_PROCESS_ENTER)
                Indx[posRange.GetId()] = [model,'Pos',ix]
                posRange.Bind(wx.EVT_TEXT_ENTER,OnPosRange)
                posRange.Bind(wx.EVT_KILL_FOCUS,OnPosRange)
                rbsizer1.Add(posRange,0,WACV)
                
            rbsizer2 = wx.FlexGridSizer(0,6,5,5)
            Ori = model['Ori'][0]
            rbsizer2.Add(wx.StaticText(G2frame.MCSA,-1,'Oa: '),0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            angVal = wx.TextCtrl(G2frame.MCSA,-1,'%.5f'%(Ori[0]),style=wx.TE_PROCESS_ENTER)
            angVal.Bind(wx.EVT_TEXT_ENTER,OnOriVal)
            angVal.Bind(wx.EVT_KILL_FOCUS,OnOriVal)
            rbsizer2.Add(angVal,0,WACV)
            rbsizer2.Add(wx.StaticText(G2frame.MCSA,-1,'Oi,Oj,Ok: '),0,WACV)
            vecVal = wx.TextCtrl(G2frame.MCSA,-1,'%.3f %.3f %.3f'%(Ori[1],Ori[2],Ori[3]),style=wx.TE_PROCESS_ENTER)
            vecVal.Bind(wx.EVT_TEXT_ENTER,OnOriVal)
            vecVal.Bind(wx.EVT_KILL_FOCUS,OnOriVal)
            Indx[angVal.GetId()] = [model,0,angVal,vecVal]
            Indx[vecVal.GetId()] = [model,1,angVal,vecVal]
            rbsizer2.Add(vecVal,0,WACV)
            rbsizer2.Add(wx.StaticText(G2frame.MCSA,-1,' Vary? '),0,WACV)
            choice = [' ','A','AV']
            orvar = wx.ComboBox(G2frame.MCSA,-1,value=model['Ovar'],choices=choice,
                style=wx.CB_READONLY|wx.CB_DROPDOWN)
            orvar.Bind(wx.EVT_COMBOBOX, OnOrVar)
            Indx[orvar.GetId()] = model
            rbsizer2.Add(orvar,0,WACV)
            rbsizer2.Add(wx.StaticText(G2frame.MCSA,-1,' Range: Oa: '),0,WACV)
            Rge = model['Ori'][2]
            angRange = wx.TextCtrl(G2frame.MCSA,-1,'%.3f %.3f'%(Rge[0][0],Rge[0][1]),style=wx.TE_PROCESS_ENTER)
            Indx[angRange.GetId()] = [model,'Ori',0]
            angRange.Bind(wx.EVT_TEXT_ENTER,OnPosRange)
            angRange.Bind(wx.EVT_KILL_FOCUS,OnPosRange)
            rbsizer2.Add(angRange,0,WACV)
            rbsizer2.Add(wx.StaticText(G2frame.MCSA,-1,'Oi,Oj,Ok: '),0,WACV)
            for io,item in enumerate(['Oi','Oj','Ok']):
                rmin,rmax = Rge[io+1]
                vecRange = wx.TextCtrl(G2frame.MCSA,-1,'%.3f %.3f '%(rmin,rmax),style=wx.TE_PROCESS_ENTER)
                Indx[vecRange.GetId()] = [model,'Ori',io+1]
                vecRange.Bind(wx.EVT_TEXT_ENTER,OnPosRange)
                vecRange.Bind(wx.EVT_KILL_FOCUS,OnPosRange)
                rbsizer2.Add(vecRange,0,WACV)
            rbsizer.Add(rbsizer1)    
            rbsizer.Add(rbsizer2)    
            if model['Type'] == 'Residue':
                atNames = RBData['Residue'][model['RBId']]['atNames']
                rbsizer.Add(wx.StaticText(G2frame.MCSA,-1,'Torsions:'),0,WACV)
                rbsizer3 = wx.FlexGridSizer(0,8,5,5)
                for it,tor in enumerate(model['Tor'][0]):
                    iBeg,iFin = RBData['Residue'][model['RBId']]['rbSeq'][it][:2]
                    name = atNames[iBeg]+'-'+atNames[iFin]
                    torRef = wx.CheckBox(G2frame.MCSA,-1,label=' %s: '%(name))
                    torRef.SetValue(model['Tor'][1][it])
                    torRef.Bind(wx.EVT_CHECKBOX,OnPosRef)
                    Indx[torRef.GetId()] = [model,'Tor',it]
                    rbsizer3.Add(torRef,0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
                    torVal = wx.TextCtrl(G2frame.MCSA,-1,'%.4f'%(tor),style=wx.TE_PROCESS_ENTER)
                    torVal.Bind(wx.EVT_TEXT_ENTER,OnPosVal)
                    torVal.Bind(wx.EVT_KILL_FOCUS,OnPosVal)
                    Indx[torVal.GetId()] = [model,'Tor',it]
                    rbsizer3.Add(torVal,0,WACV)
                    rbsizer3.Add(wx.StaticText(G2frame.MCSA,-1,' Range: '),0,WACV)
                    rmin,rmax = model['Tor'][2][it]
                    torRange = wx.TextCtrl(G2frame.MCSA,-1,'%.3f %.3f'%(rmin,rmax),style=wx.TE_PROCESS_ENTER)
                    Indx[torRange.GetId()] = [model,'Tor',it]
                    torRange.Bind(wx.EVT_TEXT_ENTER,OnPosRange)
                    torRange.Bind(wx.EVT_KILL_FOCUS,OnPosRange)
                    rbsizer3.Add(torRange,0,WACV)
                rbsizer.Add(rbsizer3)
                
            return rbsizer
            
        def MDSizer(POData):
            
            def OnPORef(event):
                POData['Coef'][1] = poRef.GetValue()
                
            def OnPOVal(event):
                event.Skip()
                try:
                    mdVal = float(poVal.GetValue())
                    if mdVal > 0:
                        POData['Coef'][0] = mdVal
                except ValueError:
                    pass
                poVal.SetValue("%.3f"%(POData['Coef'][0]))
                
            def OnPORange(event):
                event.Skip()
                Range = poRange.GetValue().split()
                try:
                    rmin,rmax = [float(Range[i]) for i in range(2)]
                    if 0. < rmin < rmax:
                        pass
                    else:
                        raise ValueError
                except (ValueError,IndexError):
                    rmin,rmax = POData['Coef'][2]
                POData['Coef'][2] = [rmin,rmax]
                poRange.SetValue('%.3f %.3f'%(rmin,rmax))                 
                
            def OnPOAxis(event):
                event.Skip()
                Saxis = poAxis.GetValue().split()
                try:
                    hkl = [int(Saxis[i]) for i in range(3)]
                except (ValueError,IndexError):
                    hkl = POData['axis']
                if not np.any(np.array(hkl)):
                    hkl = POData['axis']
                POData['axis'] = hkl
                h,k,l = hkl
                poAxis.SetValue('%3d %3d %3d'%(h,k,l))                 
                
            poSizer = wx.BoxSizer(wx.HORIZONTAL)
            poRef = wx.CheckBox(G2frame.MCSA,-1,label=' March-Dollase ratio: ')
            poRef.SetValue(POData['Coef'][1])
            poRef.Bind(wx.EVT_CHECKBOX,OnPORef)
            poSizer.Add(poRef,0,WACV)
#        azmthOff = G2G.ValidatedTxtCtrl(G2frame.dataDisplay,data,'azmthOff',nDig=(10,2),typeHint=float,OnLeave=OnAzmthOff)
            poVal = wx.TextCtrl(G2frame.MCSA,-1,'%.3f'%(POData['Coef'][0]),style=wx.TE_PROCESS_ENTER)
            poVal.Bind(wx.EVT_TEXT_ENTER,OnPOVal)
            poVal.Bind(wx.EVT_KILL_FOCUS,OnPOVal)
            poSizer.Add(poVal,0,WACV)
            poSizer.Add(wx.StaticText(G2frame.MCSA,-1,' Range: '),0,WACV)
            rmin,rmax = POData['Coef'][2]
            poRange = wx.TextCtrl(G2frame.MCSA,-1,'%.3f %.3f'%(rmin,rmax),style=wx.TE_PROCESS_ENTER)
            poRange.Bind(wx.EVT_TEXT_ENTER,OnPORange)
            poRange.Bind(wx.EVT_KILL_FOCUS,OnPORange)
            poSizer.Add(poRange,0,WACV)                       
            poSizer.Add(wx.StaticText(G2frame.MCSA,-1,' Unique axis, H K L: '),0,WACV)
            h,k,l = POData['axis']
            poAxis = wx.TextCtrl(G2frame.MCSA,-1,'%3d %3d %3d'%(h,k,l),style=wx.TE_PROCESS_ENTER)
            poAxis.Bind(wx.EVT_TEXT_ENTER,OnPOAxis)
            poAxis.Bind(wx.EVT_KILL_FOCUS,OnPOAxis)
            poSizer.Add(poAxis,0,WACV)
            return poSizer
            
        def ResultsSizer(Results):
            
            def OnCellChange(event):
                r,c = event.GetRow(),event.GetCol()
                if c == 0:
                    for row in range(resultsGrid.GetNumberRows()):
                        resultsTable.SetValue(row,c,False)
                        Results[row][0] = False
                    result = Results[r]
                    Models = data['MCSA']['Models']
                    SetSolution(result,Models)
                    Results[r][0] = True
                    resultsTable.SetValue(r,0,True)
                    G2plt.PlotStructure(G2frame,data)
                    wx.CallAfter(UpdateMCSA,G2frame.MCSA.GetScrollPos(wx.VERTICAL))
                    resultsGrid.ForceRefresh()
                elif c == 1:
                    if Results[r][1]:
                        Results[r][1] = False
                    else:
                        Results[r][1] = True
                    resultsTable.SetValue(r,c,Results[r][1])
                    resultsGrid.ForceRefresh()
                
            resultsSizer = wx.BoxSizer(wx.VERTICAL)
            maxVary = 0
            resultVals = []
            for result in Results:
                maxVary = max(maxVary,len(result[-1]))
                resultVals.append(result[:-1])
            rowLabels = []
            for i in range(len(Results)): rowLabels.append(str(i))
            colLabels = ['Select','Keep','Residual','Tmin',]
            for item in result[-1]: colLabels.append(item)   #from last result from for loop above
            Types = [wg.GRID_VALUE_BOOL,wg.GRID_VALUE_BOOL,wg.GRID_VALUE_FLOAT+':10,4',
                wg.GRID_VALUE_FLOAT+':10,4',]+maxVary*[wg.GRID_VALUE_FLOAT+':10,5',]
            resultsTable = G2G.Table(resultVals,rowLabels=rowLabels,colLabels=colLabels,types=Types)
            resultsGrid = G2G.GSGrid(G2frame.MCSA)
            resultsGrid.SetTable(resultsTable, True)
            resultsGrid.Bind(wg.EVT_GRID_CELL_LEFT_CLICK, OnCellChange)
            resultsGrid.AutoSizeColumns(True)
            for r in range(resultsGrid.GetNumberRows()):
                for c in range(resultsGrid.GetNumberCols()):
                    if c in [0,1]:
                        resultsGrid.SetReadOnly(r,c,isReadOnly=False)
                    else:
                        resultsGrid.SetCellStyle(r,c,VERY_LIGHT_GREY,True)
            resultsSizer.Add(resultsGrid)
            return resultsSizer
        
        # UpdateMCSA executable code starts here
        #G2frame.MCSA.DestroyChildren() # bad, deletes scrollbars on Mac!
        if G2frame.MCSA.GetSizer():
            G2frame.MCSA.GetSizer().Clear(True)
        if not data['Drawing']:                 #if new drawing - no drawing data!
            SetupDrawingData()
        general = data['General']
        Amat,Bmat = G2lat.cell2AB(general['Cell'][1:7])
        Id = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Rigid bodies')
        if not Id:
            return
        RBData = G2frame.PatternTree.GetItemPyData(Id)
        Indx = {}
#        atomStyle = 'balls & sticks'
#        if 'macro' in general['Type']:
#            atomStyle = 'sticks'
        G2frame.dataFrame.SetStatusText('')
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        if not data['MCSA']['Models']:
            mainSizer.Add((5,5),0)
            mainSizer.Add(wx.StaticText(G2frame.MCSA,-1,'No MC/SA models:'),0,WACV)
            mainSizer.Add((5,5),0)
        else:
            mainSizer.Add((5,5),0)
            mainSizer.Add(wx.StaticText(G2frame.MCSA,-1,'MC/SA models:'),0,WACV)
            mainSizer.Add((5,5),0)
            for model in data['MCSA']['Models']:
                Xsize = 500
                if model['Type'] == 'MD':
                    mainSizer.Add(MDSizer(model))
                elif model['Type'] == 'Atom':
                    Asizer = atomSizer(model)
                    mainSizer.Add(Asizer)
                    Xsize = max(Asizer.GetMinSize()[0],Xsize)
                else:
                    Rsizer = rbSizer(model)
                    mainSizer.Add(Rsizer)
                    Xsize = max(Rsizer.GetMinSize()[0],Xsize)
                G2G.HorizontalLine(mainSizer,G2frame.MCSA)
                
        if not data['MCSA']['Results']:
            mainSizer.Add((5,5),0)
            mainSizer.Add(wx.StaticText(G2frame.MCSA,-1,'No MC/SA results:'),0,WACV)
            mainSizer.Add((5,5),0)
        else:
            mainSizer.Add((5,5),0)
            mainSizer.Add(wx.StaticText(G2frame.MCSA,-1,'MC/SA results:'),0,WACV)
            mainSizer.Add((5,5),0)
            Results = data['MCSA']['Results']
            mainSizer.Add(ResultsSizer(Results))
            
        SetPhaseWindow(G2frame.dataFrame,G2frame.MCSA,mainSizer)
        Size = G2frame.MCSA.GetSize()
        Size[0] = Xsize+40
        G2frame.dataFrame.setSizePosLeft(Size)
        G2frame.MCSA.Scroll(0,Scroll)
        
    def SetSolution(result,Models):
        for key,val in zip(result[-1],result[4:-1]):
            vals = key.split(':')
            nObj,name = int(vals[0]),vals[1]
            if 'A' in name:
                ind = ['Ax','Ay','Az'].index(name)
                Models[nObj]['Pos'][0][ind] = val                            
            elif 'Q' in name:
                ind = ['Qa','Qi','Qj','Qk'].index(name)
                Models[nObj]['Ori'][0][ind] = val
            elif 'P' in name:
                ind = ['Px','Py','Pz'].index(name)
                Models[nObj]['Pos'][0][ind] = val                            
            elif 'T' in name:
                tnum = int(name.split('Tor')[1])
                Models[nObj]['Tor'][0][tnum] = val                                                        
            else:       #March Dollase
                Models[0]['Coef'][0] = val
            
    def OnRunMultiMCSA(event):
        RunMCSA('multi')
        
    def OnRunSingleMCSA(event):
        RunMCSA('single')

    def RunMCSA(process):
        generalData = data['General']
        mcsaControls = generalData['MCSA controls']
        reflName = mcsaControls['Data source']
        phaseName = generalData['Name']
        MCSAdata = data['MCSA']
        saveResult = []
        for result in MCSAdata['Results']:
            if result[1]:       #keep?
                saveResult.append(result)
        MCSAdata['Results'] = saveResult           
        covData = {}
        if 'PWDR' in reflName:
            PatternId = G2gd.GetPatternTreeItemId(G2frame,G2frame.root, reflName)
            reflSets = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,PatternId,'Reflection Lists'))
            try:        #patch for old reflection data
                reflData = reflSets[phaseName]['RefList']
            except TypeError:
                reflData = reflSets[phaseName]
            reflType = 'PWDR'
        elif 'HKLF' in reflName:
            PatternId = G2gd.GetPatternTreeItemId(G2frame,G2frame.root, reflName)
            try:
                reflData = G2frame.PatternTree.GetItemPyData(PatternId)[1]['RefList']
            except TypeError:
                reflData = G2frame.PatternTree.GetItemPyData(PatternId)[1]
            reflType = 'HKLF'
        elif reflName == 'Pawley reflections':
            reflData = data['Pawley ref']
            covData = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,G2frame.root, 'Covariance'))
            reflType = 'Pawley'
        else:
            print '**** ERROR - No data defined for MC/SA run'
            return
        print 'MC/SA run:'
        print 'Reflection type:',reflType,' Total No. reflections: ',len(reflData)
        RBdata = G2frame.PatternTree.GetItemPyData(   
            G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Rigid bodies'))
        MCSAmodels = MCSAdata['Models']
        if not len(MCSAmodels):
            print '**** ERROR - no models defined for MC/SA run****'
            return
        time1 = time.time()
        if process == 'single':
            pgbar = wx.ProgressDialog('MC/SA','Residual Rcf =',101.0, 
                style = wx.PD_ELAPSED_TIME|wx.PD_AUTO_HIDE|wx.PD_CAN_ABORT)
            screenSize = wx.ClientDisplayRect()
            Size = pgbar.GetSize()
            if 50 < Size[0] < 500: # sanity check on size, since this fails w/Win & wx3.0
                pgbar.SetSize((int(Size[0]*1.2),Size[1])) # increase size a bit along x
                pgbar.SetPosition(wx.Point(screenSize[2]-Size[0]-305,screenSize[1]+5))
        else:
            pgbar = None
        try:
            tsf = 0.
            nCyc = mcsaControls['Cycles']
            if process == 'single':
                for i in range(nCyc):
                    pgbar.SetTitle('MC/SA run '+str(i+1)+' of '+str(nCyc))
                    Result,tsum = G2mth.mcsaSearch(data,RBdata,reflType,reflData,covData,pgbar)
                    MCSAdata['Results'].append(Result)
                    print ' MC/SA run completed: %d residual: %.3f%% SFcalc time: %.2fs'%(i,100*Result[2],tsum)
                    tsf += tsum
                print ' Structure factor time: %.2f'%(tsf)
            else:
                MCSAdata['Results'] = G2mth.MPmcsaSearch(nCyc,data,RBdata,reflType,reflData,covData)
            print ' MC/SA run time: %.2f'%(time.time()-time1)
        finally:
            if process == 'single':
                pgbar.Destroy()
        MCSAdata['Results'] = G2mth.sortArray(MCSAdata['Results'],2,reverse=False)
        MCSAdata['Results'][0][0] = True
        SetSolution(MCSAdata['Results'][0],data['MCSA']['Models'])
        G2frame.dataDisplay.SetFocus()
        Page = G2frame.dataDisplay.FindPage('MC/SA')
        G2frame.dataDisplay.SetSelection(Page)
        G2plt.PlotStructure(G2frame,data)
        wx.CallAfter(UpdateMCSA)

    def OnMCSAaddAtom(event):
        dlg = G2elemGUI.PickElement(G2frame)
        if dlg.ShowModal() == wx.ID_OK:
            El = dlg.Elem.strip()
            Info = G2elem.GetAtomInfo(El)
        dlg.Destroy()
        
        atom = {'Type':'Atom','atType':El,'Pos':[[0.,0.,0.],
            [False,False,False],[[0.,1.],[0.,1.],[0.,1.]]],
            'name':El+'('+str(len(data['MCSA']['Models']))+')'}      
        data['MCSA']['Models'].append(atom)
        data['MCSA']['AtInfo'][El] = [Info['Drad'],Info['Color']]
        G2plt.PlotStructure(G2frame,data)
        UpdateMCSA()
        
    def OnMCSAaddRB(event):
        rbData = G2frame.PatternTree.GetItemPyData(   
            G2gd.GetPatternTreeItemId(G2frame,G2frame.root,'Rigid bodies'))
        rbNames = {}
        for rbVec in rbData['Vector']:
            if rbVec != 'AtInfo':
                rbNames[rbData['Vector'][rbVec]['RBname']] = ['Vector',rbVec]
        for rbRes in rbData['Residue']:
            if rbRes != 'AtInfo':
                rbNames[rbData['Residue'][rbRes]['RBname']] = ['Residue',rbRes]
        if not rbNames:
            print '**** ERROR - no rigid bodies defined ****'
            return
        dlg = wx.SingleChoiceDialog(G2frame.dataFrame,'Select','Rigid body',rbNames.keys())
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelection()
            rbname = rbNames.keys()[sel]
            rbType,rbId = rbNames[rbname]
            RB = rbData[rbType][rbId]
        body = {'name':RB['RBname']+'('+str(len(data['MCSA']['Models']))+')','RBId':rbId,'Type':rbType,
            'Pos':[[0.,0.,0.],[False,False,False],[[0.,1.],[0.,1.],[0.,1.]]],'Ovar':'','MolCent':[[0.,0.,0.],False],
            'Ori':[[180.,0.,0.,1.],[False,False,False,False],[[0.,360.],[-1.,1.],[-1.,1.],[-1.,1.]]]}
        if rbType == 'Residue':
            body['Tor'] = [[],[],[]]
            for i,tor in enumerate(RB['rbSeq']):
                body['Tor'][0].append(0.0)
                body['Tor'][1].append(False)
                body['Tor'][2].append([0.,360.])
        data['MCSA']['Models'].append(body)
        data['MCSA']['rbData'] = rbData
        data['MCSA']['AtInfo'].update(rbData[rbType]['AtInfo'])
        G2plt.PlotStructure(G2frame,data)
        UpdateMCSA()
        
    def OnMCSAclear(event):
        data['MCSA'] = {'Models':[{'Type':'MD','Coef':[1.0,False,[.8,1.2],],'axis':[0,0,1]}],'Results':[],'AtInfo':{}}
        G2plt.PlotStructure(G2frame,data)
        UpdateMCSA()
        
    def OnMCSAmove(event):
        general = data['General']
        Amat,Bmat = G2lat.cell2AB(general['Cell'][1:7])
        xyz,aTypes = G2mth.UpdateMCSAxyz(Bmat,data['MCSA'])
        for iat,atype in enumerate(aTypes):
            x,y,z = xyz[iat]
            AtomAdd(x,y,z,atype,Name=atype+'(%d)'%(iat+1))            
        G2plt.PlotStructure(G2frame,data)
        
    def OnClearResults(event):
        data['MCSA']['Results'] = []
        UpdateMCSA()
        
################################################################################
##### Pawley routines
################################################################################

    def FillPawleyReflectionsGrid():
        def KeyEditPawleyGrid(event):
            colList = G2frame.PawleyRefl.GetSelectedCols()
            rowList = G2frame.PawleyRefl.GetSelectedRows()
            PawleyPeaks = data['Pawley ref']
            if event.GetKeyCode() == wx.WXK_RETURN:
                event.Skip(True)
            elif event.GetKeyCode() == wx.WXK_CONTROL:
                event.Skip(True)
            elif event.GetKeyCode() == wx.WXK_SHIFT:
                event.Skip(True)
            elif colList:
                G2frame.PawleyRefl.ClearSelection()
                key = event.GetKeyCode()
                for col in colList:
                    if PawleyTable.GetTypeName(0,col) == wg.GRID_VALUE_BOOL:
                        if key == 89: #'Y'
                            for row in range(PawleyTable.GetNumberRows()): PawleyPeaks[row][col]=True
                        elif key == 78:  #'N'
                            for row in range(PawleyTable.GetNumberRows()): PawleyPeaks[row][col]=False
                        FillPawleyReflectionsGrid()
            elif rowList:
                if event.GetKeyCode() == wx.WXK_DELETE:
                    rowList.reverse()
                    for row in rowList:
                        del(PawleyPeaks[row])
                    FillPawleyReflectionsGrid()
            
        # FillPawleyReflectionsGrid executable starts here
        G2frame.dataFrame.SetStatusText('To delete a Pawley reflection: select row & press Delete')                        
        generalData = data['General']
        if 'Pawley ref' in data:
            PawleyPeaks = data['Pawley ref']                        
            rowLabels = []
            for i in range(len(PawleyPeaks)): rowLabels.append(str(i))
            if generalData['Modulated']:
                colLabels = ['h','k','l','m','mul','d','refine','Fsq(hkl)','sig(Fsq)']
                Types = 5*[wg.GRID_VALUE_LONG,]+[wg.GRID_VALUE_FLOAT+':10,4',wg.GRID_VALUE_BOOL,]+ \
                    2*[wg.GRID_VALUE_FLOAT+':10,2',]
                pos = [6,7]
            else:    
                colLabels = ['h','k','l','mul','d','refine','Fsq(hkl)','sig(Fsq)']
                Types = 4*[wg.GRID_VALUE_LONG,]+[wg.GRID_VALUE_FLOAT+':10,4',wg.GRID_VALUE_BOOL,]+ \
                    2*[wg.GRID_VALUE_FLOAT+':10,2',]
                pos = [5,6]
            PawleyTable = G2G.Table(PawleyPeaks,rowLabels=rowLabels,colLabels=colLabels,types=Types)
            G2frame.PawleyRefl.SetTable(PawleyTable, True)
            G2frame.PawleyRefl.Bind(wx.EVT_KEY_DOWN, KeyEditPawleyGrid)                 
            for r in range(G2frame.PawleyRefl.GetNumberRows()):
                for c in range(G2frame.PawleyRefl.GetNumberCols()):
                    if c in pos:
                        G2frame.PawleyRefl.SetReadOnly(r,c,isReadOnly=False)
                    else:
                        G2frame.PawleyRefl.SetCellStyle(r,c,VERY_LIGHT_GREY,True)
            G2frame.PawleyRefl.SetMargins(0,0)
            G2frame.PawleyRefl.AutoSizeColumns(False)
            G2frame.dataFrame.setSizePosLeft([450,300])
                    
    def OnPawleySet(event):
        '''Set Pawley parameters and optionally recompute
        '''
        #GSASIIpath.IPyBreak()
        
        def DisablePawleyOpts(*args):
            pawlVal.Enable(generalData['doPawley'])
            pawlNegWt.Enable(generalData['doPawley'])
        generalData = data['General']
        startDmin = generalData['Pawley dmin']
        General = wx.Dialog(G2frame.dataFrame,wx.ID_ANY,'Set Pawley Parameters',
                        style=wx.DEFAULT_DIALOG_STYLE)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(wx.StaticText(General,wx.ID_ANY,
                                    'Set Pawley Extraction Parameters for phase '+
                                    generalData.get('Name','?')))
        mainSizer.Add([5,10])
        pawleySizer = wx.BoxSizer(wx.HORIZONTAL)
        pawleySizer.Add(wx.StaticText(General,label=' Do Pawley refinement?: '),0,WACV)
        pawlRef = G2G.G2CheckBox(General,'',generalData,'doPawley',
                             DisablePawleyOpts)
        pawleySizer.Add(pawlRef,0,WACV)
        mainSizer.Add(pawleySizer)
        pawleySizer = wx.BoxSizer(wx.HORIZONTAL)
        pawleySizer.Add(wx.StaticText(General,label=' Pawley dmin: '),0,WACV)
        def d2Q(*a,**kw):
            temp['Qmax'] = 2 * math.pi / generalData['Pawley dmin']
            pawlQVal.SetValue(temp['Qmax'])
        pawlVal = G2G.ValidatedTxtCtrl(General,generalData,'Pawley dmin',
               min=0.25,max=20.,nDig=(10,5),typeHint=float,OnLeave=d2Q)
        pawleySizer.Add(pawlVal,0,WACV)
        pawleySizer.Add(wx.StaticText(General,label='   Qmax: '),0,WACV)
        temp = {'Qmax':2 * math.pi / generalData['Pawley dmin']}
        def Q2D(*args,**kw):
            generalData['Pawley dmin'] = 2 * math.pi / temp['Qmax']
            pawlVal.SetValue(generalData['Pawley dmin'])        
        pawlQVal = G2G.ValidatedTxtCtrl(General,temp,'Qmax',
               min=0.314,max=25.,nDig=(10,5),typeHint=float,OnLeave=Q2D)
        pawleySizer.Add(pawlQVal,0,WACV)
        mainSizer.Add(pawleySizer)
        pawleySizer = wx.BoxSizer(wx.HORIZONTAL)
        pawleySizer.Add(wx.StaticText(General,label=' Pawley neg. wt.: '),0,WACV)
        pawlNegWt = G2G.ValidatedTxtCtrl(General,generalData,'Pawley neg wt',
                    min=0.,max=1.,nDig=(10,4),typeHint=float)
        pawleySizer.Add(pawlNegWt,0,WACV)
        mainSizer.Add(pawleySizer)

        # make OK button
        def OnOK(event): General.EndModal(wx.ID_OK)
        mainSizer.Add([5,5])
        btnsizer = wx.StdDialogButtonSizer()
        btn = wx.Button(General, wx.ID_OK)
        btn.Bind(wx.EVT_BUTTON, OnOK)
        btn.SetDefault()
        btnsizer.AddButton(btn)
        btn = wx.Button(General, wx.ID_CANCEL) 
        btnsizer.AddButton(btn)
        btnsizer.Realize()
        mainSizer.Add(btnsizer, 0, wx.ALIGN_CENTER|wx.ALL, 5)

        General.SetSizer(mainSizer)
        mainSizer.Fit(General)
        General.CenterOnParent()
        res = General.ShowModal()
        General.Destroy()

        if generalData['doPawley'] and res == wx.ID_OK and startDmin != generalData['Pawley dmin']:
            dlg = wx.MessageDialog(G2frame,'Do you want to initialize the Pawley reflections with the new Dmin value?','Initialize Pawley?', 
                wx.YES_NO | wx.ICON_QUESTION)
            try:
                result = dlg.ShowModal()
                if result == wx.ID_NO:
                    return
            finally:
                dlg.Destroy()
            OnPawleyLoad(event)
            
    def OnPawleyLoad(event):
        generalData = data['General']
        histograms = data['Histograms'].keys()
        cell = generalData['Cell'][1:7]
        A = G2lat.cell2A(cell)
        SGData = generalData['SGData']
        dmin = generalData['Pawley dmin']
        for hist in histograms:
            if 'PWDR' in hist[:4]:
                Id = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,hist)
                inst = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(
                    G2frame,Id, 'Instrument Parameters'))[0]
                limits = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,Id, 'Limits'))
                Tmin = G2lat.Dsp2pos(inst,dmin)
                if 'T' in inst['Type'][0]:
                    limits[1][0] = max(limits[0][0],Tmin)
                else:
                    limits[1][1] = min(limits[0][1],Tmin)
        PawleyPeaks = []
        HKLd = np.array(G2lat.GenHLaue(dmin,SGData,A))
        if generalData['Modulated']:
            Vec,x,maxH = generalData['SuperVec']
            SSGData = G2spc.SSpcGroup(SGData,generalData['SuperSg'])[1]
            wx.BeginBusyCursor()
            try:
                HKLd = G2lat.GenSSHLaue(dmin,SGData,SSGData,Vec,maxH,A)
                for h,k,l,m,d in HKLd:
                    ext,mul = G2spc.GenHKLf([h,k,l],SGData)[:2]
                    if m or not ext:
                        mul *= 2        #for powder multiplicity
                        PawleyPeaks.append([h,k,l,m,mul,d,False,100.0,1.0])
                PawleyPeaks = G2mth.sortArray(PawleyPeaks,5,reverse=True)
            finally:
                wx.EndBusyCursor()
        else:
            wx.BeginBusyCursor()
            try:
                for h,k,l,d in HKLd:
                    ext,mul = G2spc.GenHKLf([h,k,l],SGData)[:2]
                    if not ext:
                        mul *= 2        #for powder multiplicity
                        PawleyPeaks.append([h,k,l,mul,d,False,100.0,1.0])
                PawleyPeaks = G2mth.sortArray(PawleyPeaks,4,reverse=True)
            finally:
                wx.EndBusyCursor()
        data['Pawley ref'] = PawleyPeaks
        FillPawleyReflectionsGrid()
        
    def OnPawleyEstimate(event):
        #Algorithm thanks to James Hester
        try:
            Refs = data['Pawley ref']
            Histograms = data['Histograms']
        except KeyError:
            G2frame.ErrorDialog('Pawley estimate','No histograms defined for this phase')
            return
        Vst = 1.0/data['General']['Cell'][7]     #Get volume
        generalData = data['General']
        im = 0
        if generalData['Modulated']:
            im = 1
        HistoNames = filter(lambda a:Histograms[a]['Use']==True,Histograms.keys())
        PatternId = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,HistoNames[0])
        xdata = G2frame.PatternTree.GetItemPyData(PatternId)[1]
        Inst = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,PatternId,'Instrument Parameters'))[0]
        Sample = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,PatternId,'Sample Parameters'))
        wave = G2mth.getWave(Inst)
        const = 9.e-2/(np.pi*Sample['Gonio. radius'])                  #shifts in microns
        gconst = 2.35482 # sqrt(8 ln 2)
        
        wx.BeginBusyCursor()
        try:
            for ref in Refs:
                pos = 2.0*asind(wave/(2.0*ref[4+im]))
                if 'Bragg' in Sample['Type']:
                    pos -= const*(4.*Sample['Shift'][0]*cosd(pos/2.0)+ \
                        Sample['Transparency'][0]*sind(pos)*100.0)            #trans(=1/mueff) in cm
                else:               #Debye-Scherrer - simple but maybe not right
                    pos -= const*(Sample['DisplaceX'][0]*cosd(pos)+Sample['DisplaceY'][0]*sind(pos))
                indx = np.searchsorted(xdata[0],pos)
                try:
                    FWHM = max(0.001,G2pwd.getFWHM(pos,Inst))
                    # We want to estimate Pawley F^2 as a drop-in replacement for F^2 calculated by the structural 
                    # routines, which use Icorr * F^2 * peak profile, where peak profile has an area of 1.  So
                    # we multiply the observed peak height by sqrt(8 ln 2)/(FWHM*sqrt(pi)) to determine the value of Icorr*F^2 
                    # then divide by Icorr to get F^2.
                    ref[6+im] = (xdata[1][indx]-xdata[4][indx])*gconst/(FWHM*np.sqrt(np.pi))  #Area of Gaussian is height * FWHM * sqrt(pi)
                    Lorenz = 1./(2.*sind(xdata[0][indx]/2.)**2*cosd(xdata[0][indx]/2.))           #Lorentz correction
                    pola = 1.0
                    if 'X' in Inst['Type']:
                        pola,dIdPola = G2pwd.Polarization(Inst['Polariz.'][1],xdata[0][indx],Inst['Azimuth'][1])
                    else:
                        pola = 1.0
                    # Include histo scale and volume in calculation
                    ref[6+im] /= (Sample['Scale'][0] * Vst * Lorenz * pola * ref[3+im])
                except IndexError:
                    pass
        finally:
            wx.EndBusyCursor()
        FillPawleyReflectionsGrid()

    def OnPawleyUpdate(event):
        '''This is the place for any reflection modification trick
        Patterson squared, leBail extraction, etc.
        '''
        try:
            Refs = data['Pawley ref']
            Histograms = data['Histograms']
        except KeyError:
            G2frame.ErrorDialog('Pawley update','No histograms defined for this phase')
            return
        HistoNames = Histograms.keys()
        PatternId = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,HistoNames[0])
        refData = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,  \
            PatternId,'Reflection Lists'))[PhaseName]['RefList']
        im = 0
        if data['General']['Modulated']:
            im = 1
        Inv = data['General']['SGData']['SGInv']
        mult = 0.5
        if Inv:
            mult = 0.3
        wx.BeginBusyCursor()
        try:
            for iref,ref in enumerate(Refs):
                try:
                    if ref[6+im] < 0.:
                        ref[6+im] *= -mult
                        refData[iref][8+im] *= -mult
                        refData[iref][9+im] *= -mult
                        ref[5+im] = False
                        ref[7+im] = 1.0
                except IndexError:
                    print 'skipped',ref
                    pass
        finally:
            wx.EndBusyCursor()
        wx.CallAfter(FillPawleyReflectionsGrid)
    def OnPawleySelAll(event):
        refcol = [G2frame.PawleyRefl.GetColLabelValue(c) for c in range(G2frame.PawleyRefl.GetNumberCols())].index('refine')
        for r in range(G2frame.PawleyRefl.GetNumberRows()):
            G2frame.PawleyRefl.GetTable().SetValue(r,refcol,True)
        G2frame.PawleyRefl.ForceRefresh()
    def OnPawleySelNone(event):
        refcol = [G2frame.PawleyRefl.GetColLabelValue(c) for c in range(G2frame.PawleyRefl.GetNumberCols())].index('refine')
        for r in range(G2frame.PawleyRefl.GetNumberRows()):
            G2frame.PawleyRefl.GetTable().SetValue(r,refcol,False)
        G2frame.PawleyRefl.ForceRefresh()
    def OnPawleyToggle(event):
        raise Exception        

        refcol = [G2frame.PawleyRefl.GetColLabelValue(c) for c in range(G2frame.PawleyRefl.GetNumberCols())].index('refine')
        for r in range(G2frame.PawleyRefl.GetNumberRows()):
            G2frame.PawleyRefl.GetTable().SetValue(
                r,refcol,
                not G2frame.PawleyRefl.GetTable().GetValueAsBool(r,refcol))
        G2frame.PawleyRefl.ForceRefresh()
                            
################################################################################
##### Fourier routines
################################################################################

    def FillMapPeaksGrid():
                        
        def RowSelect(event):
            r,c =  event.GetRow(),event.GetCol()
            if r < 0 and c < 0:
                if MapPeaks.IsSelection():
                    MapPeaks.ClearSelection()
                else:
                    for row in range(MapPeaks.GetNumberRows()):
                        MapPeaks.SelectRow(row,True)
                    
            elif c < 0:                   #only row clicks
                if event.ControlDown():                    
                    if r in MapPeaks.GetSelectedRows():
                        MapPeaks.DeselectRow(r)
                    else:
                        MapPeaks.SelectRow(r,True)
                elif event.ShiftDown():
                    indxs = MapPeaks.GetSelectedRows()
                    MapPeaks.ClearSelection()
                    ibeg = 0
                    if indxs:
                        ibeg = indxs[-1]
                    for row in range(ibeg,r+1):
                        MapPeaks.SelectRow(row,True)
                else:
                    MapPeaks.ClearSelection()
                    MapPeaks.SelectRow(r,True)
            elif r < 0:                 #a column pick
                mapPeaks = data['Map Peaks']
                c =  event.GetCol()
                if colLabels[c] == 'mag':   #big to small order
                    mapPeaks = G2mth.sortArray(mapPeaks,c,reverse=True)
                elif colLabels[c] in ['x','y','z','dzero','dcent']:     #small to big
                    mapPeaks = G2mth.sortArray(mapPeaks,c)
                else:
                    return
                data['Map Peaks'] = mapPeaks
                wx.CallAfter(FillMapPeaksGrid)
            G2plt.PlotStructure(G2frame,data)                    
            
        G2frame.dataFrame.setSizePosLeft([500,300])
        G2frame.dataFrame.SetStatusText('')
        if 'Map Peaks' in data:
            G2frame.dataFrame.SetStatusText('Double click any column heading to sort')
            mapPeaks = data['Map Peaks']                        
            rowLabels = []
            for i in range(len(mapPeaks)): rowLabels.append(str(i))
            colLabels = ['mag','x','y','z','dzero','dcent']
            Types = 6*[wg.GRID_VALUE_FLOAT+':10,4',]
            G2frame.MapPeaksTable = G2G.Table(mapPeaks,rowLabels=rowLabels,colLabels=colLabels,types=Types)
            MapPeaks.SetTable(G2frame.MapPeaksTable, True)
            MapPeaks.Bind(wg.EVT_GRID_LABEL_LEFT_CLICK, RowSelect)
            for r in range(MapPeaks.GetNumberRows()):
                for c in range(MapPeaks.GetNumberCols()):
                    MapPeaks.SetCellStyle(r,c,VERY_LIGHT_GREY,True)
            MapPeaks.SetMargins(0,0)
            MapPeaks.AutoSizeColumns(False)
                    
    def OnPeaksMove(event):
        if 'Map Peaks' in data:
            mapPeaks = np.array(data['Map Peaks'])
            peakMax = np.max(mapPeaks.T[0])
            Ind = MapPeaks.GetSelectedRows()
            for ind in Ind:
                mag,x,y,z = mapPeaks[ind][:4]
                AtomAdd(x,y,z,'H',Name='M '+'%d'%(int(100*mag/peakMax)))
            G2plt.PlotStructure(G2frame,data)
    
    def OnPeaksClear(event):
        data['Map Peaks'] = []
        FillMapPeaksGrid()
        G2plt.PlotStructure(G2frame,data)
        
    def OnPeaksDelete(event):
        if 'Map Peaks' in data:
            mapPeaks = data['Map Peaks']
            Ind = MapPeaks.GetSelectedRows()
            Ind.sort()
            Ind.reverse()
            for ind in Ind:
                mapPeaks = np.delete(mapPeaks,ind,0)
            data['Map Peaks'] = mapPeaks
        FillMapPeaksGrid()
        G2plt.PlotStructure(G2frame,data)
        
    def OnPeaksEquiv(event):
        if 'Map Peaks' in data:
            Ind = MapPeaks.GetSelectedRows()
            if Ind:
                wx.BeginBusyCursor()
                try:
                    Ind = G2mth.PeaksEquiv(data,Ind)
                    for r in range(MapPeaks.GetNumberRows()):
                        if r in Ind:
                            MapPeaks.SelectRow(r,addToSelected=True)
                        else:
                            MapPeaks.DeselectRow(r)
                finally:
                    wx.EndBusyCursor()
                G2plt.PlotStructure(G2frame,data)

    def OnShowBonds(event):
        generalData = data['General']
        if generalData['Map'].get('Show bonds',False):
            generalData['Map']['Show bonds'] = False
            G2frame.dataFrame.MapPeaksEdit.SetLabel(G2gd.wxID_SHOWBONDS,'Show bonds')
        else:
            generalData['Map']['Show bonds'] = True
            G2frame.dataFrame.MapPeaksEdit.SetLabel(G2gd.wxID_SHOWBONDS,'Hide bonds')
        FillMapPeaksGrid()
        G2plt.PlotStructure(G2frame,data)
                
    def OnPeaksUnique(event):
        if 'Map Peaks' in data:
            mapPeaks = data['Map Peaks']
            Ind = MapPeaks.GetSelectedRows()
            if Ind:
                wx.BeginBusyCursor()
                try:
                    Ind = G2mth.PeaksUnique(data,Ind)
                    print ' No. unique peaks: ',len(Ind),   \
                        ' Unique peak fraction: %.3f'%(float(len(Ind))/len(mapPeaks))
                    for r in range(MapPeaks.GetNumberRows()):
                        if r in Ind:
                            MapPeaks.SelectRow(r,addToSelected=True)
                        else:
                            MapPeaks.DeselectRow(r)
                finally:
                    wx.EndBusyCursor()
                G2plt.PlotStructure(G2frame,data)
                
    def OnPeaksViewPoint(event):
        # set view point
        indx = MapPeaks.GetSelectedRows()
        if not indx:
            G2frame.ErrorDialog('Set viewpoint','No peaks selected')
            return
        mapPeaks = data['Map Peaks']
        drawingData = data['Drawing']
        drawingData['viewPoint'][0] = mapPeaks[indx[0]][1:4]
        G2plt.PlotStructure(G2frame,data)
    
    def OnPeaksDistVP(event):
        # distance to view point
        indx = MapPeaks.GetSelectedRows()
        if not indx:
            G2frame.ErrorDialog('Peak distance','No peaks selected')
            return
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])            
        mapPeaks = data['Map Peaks']
        drawingData = data['Drawing']
        viewPt = np.array(drawingData['viewPoint'][0])
        print ' Distance from view point at %.3f %.3f %.3f to:'%(viewPt[0],viewPt[1],viewPt[2])
        colLabels = [MapPeaks.GetColLabelValue(c) for c in range(MapPeaks.GetNumberCols())]
        cx = colLabels.index('x')
        cm = colLabels.index('mag')
        for i in indx:
            peak = mapPeaks[i]
            Dx = np.array(peak[cx:cx+3])-viewPt
            dist = np.sqrt(np.sum(np.inner(Amat,Dx)**2,axis=0))
            print 'Peak: %5d mag= %8.2f distance = %.3f'%(i,peak[cm],dist)

    def OnPeaksDA(event):
        #distance, angle 
        indx = MapPeaks.GetSelectedRows()
        if len(indx) not in [2,3]:
            G2frame.ErrorDialog('Peak distance/angle','Wrong number of atoms for distance or angle calculation')
            return
        generalData = data['General']
        Amat,Bmat = G2lat.cell2AB(generalData['Cell'][1:7])            
        mapPeaks = data['Map Peaks']
        xyz = []
        for i in indx:
            xyz.append(mapPeaks[i][1:4])
        if len(indx) == 2:
            print ' distance for atoms %s = %.3f'%(str(indx),G2mth.getRestDist(xyz,Amat))
        else:
            print ' angle for atoms %s = %.2f'%(str(indx),G2mth.getRestAngle(xyz,Amat))
                                    
    def OnFourierMaps(event):
        generalData = data['General']
        mapData = generalData['Map']
        reflNames = mapData['RefList']
        if not generalData['Map']['MapType']:
            G2frame.ErrorDialog('Fourier map error','Fourier map type not defined')
            return
        if not len(reflNames):
            G2frame.ErrorDialog('Fourier map error','No reflections defined for Fourier map')
            return
        phaseName = generalData['Name']
        ReflData = GetReflData(G2frame,phaseName,reflNames)
        if ReflData == None: return
        if 'Omit' in mapData['MapType']:
            dim = '3D '
            pgbar = wx.ProgressDialog('Omit map','Blocks done',65, 
            style = wx.PD_ELAPSED_TIME|wx.PD_AUTO_HIDE)
            mapData.update(G2mth.OmitMap(data,ReflData,pgbar))
            pgbar.Destroy()
        else:
            if generalData['Modulated']:
                dim = '4D '
                G2mth.Fourier4DMap(data,ReflData)
            else:
                dim = '3D '
                G2mth.FourierMap(data,ReflData)
        mapData['Flip'] = False
        mapSig = np.std(mapData['rho'])
        if not data['Drawing']:                 #if new drawing - no drawing data!
            SetupDrawingData()
        data['Drawing']['contourLevel'] = 1.
        data['Drawing']['mapSize'] = 10.
        print dim+mapData['MapType']+' computed: rhomax = %.3f rhomin = %.3f sigma = %.3f'%(np.max(mapData['rho']),np.min(mapData['rho']),mapSig)
        UpdateDrawAtoms()
        G2plt.PlotStructure(G2frame,data)
        
    def OnFourClear(event):
        generalData = data['General']
        generalData['Map'] = mapDefault.copy()
        G2plt.PlotStructure(G2frame,data)
        
# map printing for testing purposes
    def printRho(SGLaue,rho,rhoMax):                          
        dim = len(rho.shape)
        if dim == 2:
            ix,jy = rho.shape
            for j in range(jy):
                line = ''
                if SGLaue in ['3','3m1','31m','6/m','6/mmm']:
                    line += (jy-j)*'  '
                for i in range(ix):
                    r = int(100*rho[i,j]/rhoMax)
                    line += '%4d'%(r)
                print line+'\n'
        else:
            ix,jy,kz = rho.shape
            for k in range(kz):
                print 'k = ',k
                for j in range(jy):
                    line = ''
                    if SGLaue in ['3','3m1','31m','6/m','6/mmm']:
                        line += (jy-j)*'  '
                    for i in range(ix):
                        r = int(100*rho[i,j,k]/rhoMax)
                        line += '%4d'%(r)
                    print line+'\n'
## keep this                
    
    def OnSearchMaps(event):
                                    
        print ' Begin fourier map search - can take some time'
        time0 = time.time()
        generalData = data['General']
        drawingData = data['Drawing']
        mapData = generalData['Map']
        if len(mapData['rho']):
            wx.BeginBusyCursor()
            try:
                peaks,mags,dzeros,dcents = G2mth.SearchMap(generalData,drawingData)
                if 'N' in mapData['Type']:      #look for negatives in neutron maps
                    npeaks,nmags,ndzeros,ndcents = G2mth.SearchMap(generalData,drawingData,Neg=True)
                    peaks = np.concatenate((peaks,npeaks))
                    mags = np.concatenate((mags,nmags))
                    dzeros = np.concatenate((dzeros,ndzeros))
                    dcents = np.concatenate((dcents,ndcents))
            finally:
                wx.EndBusyCursor()
            if len(peaks):
                mapPeaks = np.concatenate((mags,peaks,dzeros,dcents),axis=1)
                data['Map Peaks'] = G2mth.sortArray(mapPeaks,0,reverse=True)            
            print ' Map search finished, time = %.2fs'%(time.time()-time0)
            print ' No.peaks found:',len(peaks)    
            Page = G2frame.dataDisplay.FindPage('Map peaks')
            G2frame.dataDisplay.SetSelection(Page)
            wx.CallAfter(FillMapPeaksGrid)
            UpdateDrawAtoms()
        else:
            print 'No map available'
            
    def On4DChargeFlip(event):
        generalData = data['General']
        mapData = generalData['Map']
        map4DData = generalData['4DmapData']
        flipData = generalData['Flip']
        reflNames = flipData['RefList']
        if not len(reflNames):
            G2frame.ErrorDialog('Charge flip error','No reflections defined for charge flipping')
            return
        phaseName = generalData['Name']
        ReflData = GetReflData(G2frame,phaseName,reflNames)
        if ReflData == None: return
        pgbar = wx.ProgressDialog('Charge flipping','Residual Rcf =',101.0, 
            style = wx.PD_ELAPSED_TIME|wx.PD_AUTO_HIDE|wx.PD_CAN_ABORT)
        screenSize = wx.ClientDisplayRect()
        Size = pgbar.GetSize()
        if 50 < Size[0] < 500: # sanity check on size, since this fails w/Win & wx3.0
            pgbar.SetSize((int(Size[0]*1.2),Size[1])) # increase size a bit along x
            pgbar.SetPosition(wx.Point(screenSize[2]-Size[0]-305,screenSize[1]+5))
        try:
            newMap,new4Dmap = G2mth.SSChargeFlip(data,ReflData,pgbar)
        finally:
            pgbar.Destroy()
        mapData.update(newMap)
        map4DData.update(new4Dmap)
        mapData['Flip'] = True        
        mapSig = np.std(mapData['rho'])
        if not data['Drawing']:                 #if new drawing - no drawing data!
            SetupDrawingData()
        data['Drawing']['contourLevel'] = 1.
        data['Drawing']['mapSize'] = 10.
        print ' 4D Charge flip map computed: rhomax = %.3f rhomin = %.3f sigma = %.3f'%(np.max(mapData['rho']),np.min(mapData['rho']),mapSig)
        if mapData['Rcf'] < 99.:
            OnSearchMaps(event)             #does a plot structure at end
        else:
            print 'Bad charge flip map - no peak search done'
        
    def OnChargeFlip(event):
        generalData = data['General']
        mapData = generalData['Map']
        flipData = generalData['Flip']
        reflNames = flipData['RefList']
        if not len(reflNames):
            G2frame.ErrorDialog('Charge flip error','No reflections defined for charge flipping')
            return
        phaseName = generalData['Name']
        ReflData = GetReflData(G2frame,phaseName,reflNames)
        if ReflData == None: return
        pgbar = wx.ProgressDialog('Charge flipping','Residual Rcf =',101.0, 
            style = wx.PD_ELAPSED_TIME|wx.PD_AUTO_HIDE|wx.PD_CAN_ABORT)
        screenSize = wx.ClientDisplayRect()
        Size = pgbar.GetSize()
        testNames = ['%3d%3d%3d'%(h,k,l) for h,k,l in flipData['testHKL']]
        if 50 < Size[0] < 500: # sanity check on size, since this fails w/Win & wx3.0
            pgbar.SetSize((int(Size[0]*1.2),Size[1])) # increase size a bit along x
            pgbar.SetPosition(wx.Point(screenSize[2]-Size[0]-305,screenSize[1]+5))
        try:
            result = G2mth.ChargeFlip(data,ReflData,pgbar)
            mapData.update(result[0])
            X = range(len(result[1]))
            Y = 180.*np.array(result[1]).T/np.pi
            XY = [[X,y] for y in Y]
            XY = np.array(XY).reshape((5,2,-1))
            G2plt.PlotXY(G2frame,XY,labelX='charge flip cycle',labelY='phase, deg',newPlot=True,
                Title='Test HKL phases',lines=True,names=testNames)
        finally:
            pgbar.Destroy()
        mapData['Flip'] = True        
        mapSig = np.std(mapData['rho'])
        if not data['Drawing']:                 #if new drawing - no drawing data!
            SetupDrawingData()
        data['Drawing']['contourLevel'] = 1.
        data['Drawing']['mapSize'] = 10.
        print ' Charge flip map computed: rhomax = %.3f rhomin = %.3f sigma = %.3f'%(np.max(mapData['rho']),np.min(mapData['rho']),mapSig)
        if mapData['Rcf'] < 99.:
            OnSearchMaps(event)             #does a plot structure at end
        else:
            print 'Bad charge flip map - no peak search done'
                            
    def OnTextureRefine(event):
        General = data['General']
        phaseName = General['Name']
        keyList = G2frame.GetHistogramNames('PWDR')
        histNames = []
        refData = {}
        Gangls = {}
        for name in keyList:
            if 'PWDR' in name:
                im = 0
                it = 0
                histNames.append(name)
                Id = G2gd.GetPatternTreeItemId(G2frame,G2frame.root,name)
                Inst = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,Id,'Instrument Parameters'))
                Sample = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,Id,'Sample Parameters'))
                Gangls[name] = copy.copy([Sample[item] for item in['Phi','Chi','Omega','Azimuth']])
                RefDict = G2frame.PatternTree.GetItemPyData(G2gd.GetPatternTreeItemId(G2frame,Id,'Reflection Lists'))[phaseName]
                Refs = RefDict['RefList'].T  #np.array!
                if RefDict['Super']: im = 1     #(3+1) offset for m
                if 'T' in RefDict['Type']: 
                    it = 3  #TOF offset for alp, bet, wave
                    tth = np.ones_like(Refs[0])*Inst[0]['2-theta'][0]
                    refData[name] = np.column_stack((Refs[0],Refs[1],Refs[2],tth,Refs[8+im],Refs[12+im+it],np.zeros_like(Refs[0])))
                else:   # xray - typical caked 2D image data
                    refData[name] = np.column_stack((Refs[0],Refs[1],Refs[2],Refs[5+im],Refs[8+im],Refs[12+im+it],np.zeros_like(Refs[0])))
        pgbar = wx.ProgressDialog('Texture fit','Residual = %5.2f'%(101.0),101.0, 
            style = wx.PD_ELAPSED_TIME|wx.PD_AUTO_HIDE)
        Error = G2mth.FitTexture(General,Gangls,refData,keyList,pgbar)
        pgbar.Destroy()
        if Error:
            wx.MessageBox(Error,caption='Fit Texture Error',style=wx.ICON_EXCLAMATION)
#        x = []
#        y = []
        XY = []
        for hist in keyList:
            x = refData[hist].T[5].T
            y = refData[hist].T[6].T
            xy = [x,y]
            XY.append(np.array(xy))
        XY = np.array(XY)
        G2plt.PlotXY(G2frame,XY,XY2=[],labelX='POobs',labelY='POcalc',newPlot=False,Title='Texture fit error')
        UpdateTexture()
        G2plt.PlotTexture(G2frame,data,Start=False)            
            
    def OnTextureClear(event):
        print 'clear texture? - does nothing'

    def FillSelectPageMenu(TabSelectionIdDict, menuBar):
        '''Fill "Select tab" menu with menu items for each tab and assign
        bindings to the menu ietm to switch between phase tabs
        '''
        def OnSelectPage(event):
            'Called when an item is selected from the Select page menu'
            # lookup the menu item that called us and get its text
            tabname = TabSelectionIdDict.get(event.GetId())
            if not tabname:
                print 'Warning: menu item not in dict! id=',event.GetId()
                return                
            # find the matching tab
            for PageNum in range(G2frame.dataDisplay.GetPageCount()):
                if tabname == G2frame.dataDisplay.GetPageText(PageNum):
                    G2frame.dataDisplay.SetSelection(PageNum)
                    return
            else:
                print "Warning: tab "+tabname+" was not found"
        mid = menuBar.FindMenu('Select tab')
        menu = menuBar.GetMenu(mid)
        for ipage,page in enumerate(Pages):
            if menu.FindItem(page) < 0: # is tab already in menu?
                Id = wx.NewId()
                TabSelectionIdDict[Id] = page
                menu.Append(id=Id,kind=wx.ITEM_NORMAL,text=page)
                G2frame.Bind(wx.EVT_MENU, OnSelectPage, id=Id)
        
    def OnPageChanged(event):
        '''This is called every time that a Notebook tab button is pressed
        on a Phase data item window
        '''
        for page in G2frame.dataDisplay.gridList: # clear out all grids, forcing edits in progress to complete
            page.ClearGrid()
        wx.Frame.Unbind(G2frame.dataFrame,wx.EVT_SIZE) # ignore size events during this routine
        page = event.GetSelection()
        ChangePage(page)
        
    def ChangePage(page):
        text = G2frame.dataDisplay.GetPageText(page)
        G2frame.dataDisplayPhaseText = text
        if text == 'General':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.DataGeneral)
            UpdateGeneral()
        elif text == 'Data':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.DataMenu)
            G2ddG.UpdateDData(G2frame,DData,data)
            wx.CallAfter(G2plt.PlotSizeStrainPO,G2frame,data,hist='',Start=True)            
        elif text == 'Atoms':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.AtomsMenu)
            FillAtomsGrid(Atoms)
        elif text == 'Layers':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.LayerData)
            UpdateLayerData()
        elif text == 'Wave Data' and data['General']['Modulated']:
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.WavesData)
            UpdateWavesData()
            wx.CallAfter(G2plt.PlotStructure,G2frame,data,firstCall=True)
        elif text == 'Draw Options':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.DataDrawOptions)
            UpdateDrawOptions()
            wx.CallAfter(G2plt.PlotStructure,G2frame,data,firstCall=True)
        elif text == 'Draw Atoms':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.DrawAtomsMenu)
            UpdateDrawAtoms()
            wx.CallAfter(G2plt.PlotStructure,G2frame,data,firstCall=True)
        elif text == 'RB Models':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.RigidBodiesMenu)
            FillRigidBodyGrid()
        elif text == 'Map peaks':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.MapPeaksMenu)
            FillMapPeaksGrid()
            wx.CallAfter(G2plt.PlotStructure,G2frame,data,firstCall=True)
        elif text == 'MC/SA':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.MCSAMenu)
            UpdateMCSA()                        
            wx.CallAfter(G2plt.PlotStructure,G2frame,data,firstCall=True)
        elif text == 'Texture':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.TextureMenu)
            UpdateTexture()                        
            wx.CallAfter(G2plt.PlotTexture,G2frame,data,Start=True)            
        elif text == 'Pawley reflections':
            G2gd.SetDataMenuBar(G2frame,G2frame.dataFrame.PawleyMenu)
            FillPawleyReflectionsGrid()
        else:
            G2gd.SetDataMenuBar(G2frame)
            
    def FillMenus():
        '''Create the Select tab menus and bind to all menu items
        '''
        # General
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.DataGeneral)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnFourierMaps, id=G2gd.wxID_FOURCALC)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnSearchMaps, id=G2gd.wxID_FOURSEARCH)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnChargeFlip, id=G2gd.wxID_CHARGEFLIP)
        G2frame.dataFrame.Bind(wx.EVT_MENU, On4DChargeFlip, id=G2gd.wxID_4DCHARGEFLIP)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnFourClear, id=G2gd.wxID_FOURCLEAR)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnRunSingleMCSA, id=G2gd.wxID_SINGLEMCSA)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnRunMultiMCSA, id=G2gd.wxID_MULTIMCSA)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnTransform, id=G2gd.wxID_TRANSFORMSTRUCTURE)
        # Data
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.DataMenu)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDataUse, id=G2gd.wxID_DATAUSE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDataCopy, id=G2gd.wxID_DATACOPY)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDataCopyFlags, id=G2gd.wxID_DATACOPYFLAGS)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnSelDataCopy, id=G2gd.wxID_DATASELCOPY)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPwdrAdd, id=G2gd.wxID_PWDRADD)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnHklfAdd, id=G2gd.wxID_HKLFADD)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDataDelete, id=G2gd.wxID_DATADELETE)
        # Atoms
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.AtomsMenu)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnSetAll, id=G2gd.wxID_ATOMSSETALL)
        G2frame.dataFrame.Bind(wx.EVT_MENU, AtomRefine, id=G2gd.wxID_ATOMSSETSEL)
        G2frame.dataFrame.Bind(wx.EVT_MENU, AtomModify, id=G2gd.wxID_ATOMSMODIFY)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnAtomInsert, id=G2gd.wxID_ATOMSEDITINSERT)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnHydAtomAdd, id=G2gd.wxID_ADDHATOM)
        G2frame.dataFrame.Bind(wx.EVT_MENU, AtomDelete, id=G2gd.wxID_ATOMSEDITDELETE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, AtomTransform, id=G2gd.wxID_ATOMSTRANSFORM)
#        G2frame.dataFrame.Bind(wx.EVT_MENU, AtomRotate, id=G2gd.wxID_ATOMSROTATE)
        
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnAtomAdd, id=G2gd.wxID_ATOMSEDITADD)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnAtomViewAdd, id=G2gd.wxID_ATOMSVIEWADD)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnAtomViewInsert, id=G2gd.wxID_ATOMVIEWINSERT)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnHydAtomUpdate, id=G2gd.wxID_UPDATEHATOM)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnAtomMove, id=G2gd.wxID_ATOMMOVE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, MakeMolecule, id=G2gd.wxID_MAKEMOLECULE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnReloadDrawAtoms, id=G2gd.wxID_RELOADDRAWATOMS)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDistAngle, id=G2gd.wxID_ATOMSDISAGL)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDistAnglePrt, id=G2gd.wxID_ATOMSPDISAGL)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnIsoDistortCalc, id=G2gd.wxID_ISODISP)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDensity, id=G2gd.wxID_ATOMSDENSITY)
        if 'HydIds' in data['General']:
            G2frame.dataFrame.AtomEdit.Enable(G2gd.wxID_UPDATEHATOM,True)
        else:
            G2frame.dataFrame.AtomEdit.Enable(G2gd.wxID_UPDATEHATOM,False)
        for id in G2frame.dataFrame.ReImportMenuId:     #loop over submenu items
            G2frame.dataFrame.Bind(wx.EVT_MENU, OnReImport, id=id)
        # Wave Data
        if data['General']['Modulated']:
            FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.WavesData)
            G2frame.dataFrame.Bind(wx.EVT_MENU, OnWaveVary, id=G2gd.wxID_WAVEVARY)
        # Stacking faults 
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.LayerData)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnCopyPhase, id=G2gd.wxID_COPYPHASE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnLoadDIFFaX, id=G2gd.wxID_LOADDIFFAX)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnSimulate, id=G2gd.wxID_LAYERSIMULATE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnSeqSimulate, id=G2gd.wxID_SEQUENCESIMULATE)
        # Draw Options
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.DataDrawOptions)
        # Draw Atoms
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.DrawAtomsMenu)
        G2frame.dataFrame.Bind(wx.EVT_MENU, DrawAtomStyle, id=G2gd.wxID_DRAWATOMSTYLE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, DrawAtomLabel, id=G2gd.wxID_DRAWATOMLABEL)
        G2frame.dataFrame.Bind(wx.EVT_MENU, DrawAtomColor, id=G2gd.wxID_DRAWATOMCOLOR)
        G2frame.dataFrame.Bind(wx.EVT_MENU, ResetAtomColors, id=G2gd.wxID_DRAWATOMRESETCOLOR)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnEditAtomRadii, id=G2gd.wxID_DRWAEDITRADII)   
        G2frame.dataFrame.Bind(wx.EVT_MENU, SetViewPoint, id=G2gd.wxID_DRAWVIEWPOINT)
        G2frame.dataFrame.Bind(wx.EVT_MENU, AddSymEquiv, id=G2gd.wxID_DRAWADDEQUIV)
        G2frame.dataFrame.Bind(wx.EVT_MENU, AddSphere, id=G2gd.wxID_DRAWADDSPHERE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, TransformSymEquiv, id=G2gd.wxID_DRAWTRANSFORM)
        G2frame.dataFrame.Bind(wx.EVT_MENU, FillCoordSphere, id=G2gd.wxID_DRAWFILLCOORD)            
        G2frame.dataFrame.Bind(wx.EVT_MENU, FillUnitCell, id=G2gd.wxID_DRAWFILLCELL)
        G2frame.dataFrame.Bind(wx.EVT_MENU, DrawAtomsDelete, id=G2gd.wxID_DRAWDELETE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDrawDistVP, id=G2gd.wxID_DRAWDISTVP)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDrawDAT, id=G2gd.wxID_DRAWDISAGLTOR)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDrawPlane, id=G2gd.wxID_DRAWPLANE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnRestraint, id=G2gd.wxID_DRAWRESTRBOND)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnRestraint, id=G2gd.wxID_DRAWRESTRANGLE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnRestraint, id=G2gd.wxID_DRAWRESTRPLANE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnRestraint, id=G2gd.wxID_DRAWRESTRCHIRAL)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnDefineRB, id=G2gd.wxID_DRAWDEFINERB)
        # RB Models
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.RigidBodiesMenu)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnAutoFindResRB, id=G2gd.wxID_AUTOFINDRESRB)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnRBAssign, id=G2gd.wxID_ASSIGNATMS2RB)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnRBCopyParms, id=G2gd.wxID_COPYRBPARMS)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnGlobalResRBTherm, id=G2gd.wxID_GLOBALTHERM)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnGlobalResRBRef, id=G2gd.wxID_GLOBALRESREFINE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnRBRemoveAll, id=G2gd.wxID_RBREMOVEALL)
        # Map peaks
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.MapPeaksMenu)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPeaksMove, id=G2gd.wxID_PEAKSMOVE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPeaksViewPoint, id=G2gd.wxID_PEAKSVIEWPT)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPeaksDistVP, id=G2gd.wxID_PEAKSDISTVP)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPeaksDA, id=G2gd.wxID_PEAKSDA)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnShowBonds, id=G2gd.wxID_SHOWBONDS)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPeaksEquiv, id=G2gd.wxID_FINDEQVPEAKS)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPeaksUnique, id=G2gd.wxID_PEAKSUNIQUE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPeaksDelete, id=G2gd.wxID_PEAKSDELETE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPeaksClear, id=G2gd.wxID_PEAKSCLEAR)
        # MC/SA
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.MCSAMenu)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnMCSAaddAtom, id=G2gd.wxID_ADDMCSAATOM)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnMCSAaddRB, id=G2gd.wxID_ADDMCSARB)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnMCSAclear, id=G2gd.wxID_CLEARMCSARB)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnMCSAmove, id=G2gd.wxID_MOVEMCSA)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnClearResults, id=G2gd.wxID_MCSACLEARRESULTS)
        # Texture
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.TextureMenu)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnTextureRefine, id=G2gd.wxID_REFINETEXTURE)
#        G2frame.dataFrame.Bind(wx.EVT_MENU, OnTextureClear, id=G2gd.wxID_CLEARTEXTURE)
        # Pawley reflections
        FillSelectPageMenu(TabSelectionIdDict, G2frame.dataFrame.PawleyMenu)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPawleySet, id=G2gd.wxID_PAWLEYSET)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPawleyLoad, id=G2gd.wxID_PAWLEYLOAD)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPawleyEstimate, id=G2gd.wxID_PAWLEYESTIMATE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPawleyUpdate, id=G2gd.wxID_PAWLEYUPDATE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPawleySelAll, id=G2gd.wxID_PAWLEYSELALL)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPawleySelNone, id=G2gd.wxID_PAWLEYSELNONE)
        G2frame.dataFrame.Bind(wx.EVT_MENU, OnPawleyToggle, id=G2gd.wxID_PAWLEYSELTOGGLE)
        
    # UpdatePhaseData execution starts here
#patch
    if 'RBModels' not in data:
        data['RBModels'] = {}
    if 'MCSA' not in data:
        data['MCSA'] = {'Models':[{'Type':'MD','Coef':[1.0,False,[.8,1.2],],'axis':[0,0,1]}],'Results':[],'AtInfo':{}}
    #if isinstance(data['MCSA']['Results'],dict):
    if 'dict' in str(type(data['MCSA']['Results'])):
        data['MCSA']['Results'] = []
    if 'Modulated' not in data['General']:
        data['General']['Modulated'] = False
    if 'modulated' in data['General']['Type']:
        data['General']['Modulated'] = True
        data['General']['Type'] = 'nuclear'
        
#end patch    

    global rbAtmDict   
    rbAtmDict = {}
    if G2frame.dataDisplay:
        G2frame.dataDisplay.Destroy()
    PhaseName = G2frame.PatternTree.GetItemText(Item)
    G2gd.SetDataMenuBar(G2frame)
    G2frame.dataFrame.SetLabel('Phase Data for '+PhaseName)
    G2frame.dataFrame.CreateStatusBar()
    G2frame.dataDisplay = G2G.GSNoteBook(parent=G2frame.dataFrame,size=G2frame.dataFrame.GetClientSize())
    G2frame.dataDisplay.gridList = [] # list of all grids in notebook
    Pages = []    
    wx.Frame.Unbind(G2frame.dataFrame,wx.EVT_SIZE) # ignore size events during this routine
    G2frame.dataDisplay.gridList = []
    General = wx.ScrolledWindow(G2frame.dataDisplay)
    G2frame.dataDisplay.AddPage(General,'General')
    Pages.append('General')
    DData = wx.ScrolledWindow(G2frame.dataDisplay)
    G2frame.dataDisplay.AddPage(DData,'Data')
    Pages.append('Data')
    Atoms = G2G.GSGrid(G2frame.dataDisplay)
    G2frame.dataDisplay.gridList.append(Atoms)
    G2frame.dataDisplay.AddPage(Atoms,'Atoms')
    Pages.append('Atoms')
    if data['General']['Modulated']:
        G2frame.waveData = wx.ScrolledWindow(G2frame.dataDisplay)
        G2frame.dataDisplay.AddPage(G2frame.waveData,'Wave Data')
        Pages.append('Wave Data') 
    if data['General']['Type'] == 'faulted':
        G2frame.layerData = wx.ScrolledWindow(G2frame.dataDisplay)
        G2frame.dataDisplay.AddPage(G2frame.layerData,'Layers')
        Pages.append('Layers')               
    drawOptions = wx.ScrolledWindow(G2frame.dataDisplay)
    G2frame.dataDisplay.AddPage(drawOptions,'Draw Options')
    Pages.append('Draw Options')
    drawAtoms = G2G.GSGrid(G2frame.dataDisplay)
    G2frame.dataDisplay.gridList.append(drawAtoms)
    G2frame.dataDisplay.AddPage(drawAtoms,'Draw Atoms')
    Pages.append('Draw Atoms')
    if data['General']['Type'] not in ['faulted',] and not data['General']['Modulated']:
        RigidBodies = wx.ScrolledWindow(G2frame.dataDisplay)
        G2frame.dataDisplay.AddPage(RigidBodies,'RB Models')
        Pages.append('RB Models')
    MapPeaks = G2G.GSGrid(G2frame.dataDisplay)
    G2frame.dataDisplay.gridList.append(MapPeaks)    
    G2frame.dataDisplay.AddPage(MapPeaks,'Map peaks')
    Pages.append('Map peaks')
    if data['General']['Type'] not in ['faulted',] and not data['General']['Modulated']:
        G2frame.MCSA = wx.ScrolledWindow(G2frame.dataDisplay)
        G2frame.dataDisplay.AddPage(G2frame.MCSA,'MC/SA')
        Pages.append('MC/SA')
    Texture = wx.ScrolledWindow(G2frame.dataDisplay)
    G2frame.dataDisplay.AddPage(Texture,'Texture')
    Pages.append('Texture')
    G2frame.PawleyRefl = G2G.GSGrid(G2frame.dataDisplay)
    G2frame.dataDisplay.gridList.append(G2frame.PawleyRefl)
    G2frame.dataDisplay.AddPage(G2frame.PawleyRefl,'Pawley reflections')
    Pages.append('Pawley reflections')
    G2frame.dataFrame.AtomCompute.ISOcalc.Enable('ISODISTORT' in data)
    G2frame.dataDisplay.Bind(wx.aui.EVT_AUINOTEBOOK_PAGE_CHANGED, OnPageChanged)
    FillMenus()
    if oldPage is None or oldPage == 0:
        ChangePage(0)
    elif oldPage:
        SetupGeneral()    # not sure why one might need this when moving from phase to phase; but does not hurt
        G2frame.dataDisplay.SetSelection(oldPage)
