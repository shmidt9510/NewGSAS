# coding=utf-8
import CifFile
import GSASIIlattice
import GSASIIspc
import os.path
import GSASIIElem
import numpy as np
import re
import atmdata
#import matplotlib.pyplot as plt

def StatisticCreate(ReFilee,cf):
    #wavelength = wavel
    #ReFilee='1000009'  # Номер считываемого файла
    #ReDFile=ReFilee+'.cif'
    #cf = CifFile.ReadCif(ReDFile)
    wav = cf[ReFilee]['_symmetry_space_group_name_H-M'] #
    if wav == 'NONO':
        wav = cf[ReFilee]['_symmetry_space_group_name_H-M_alt']
    a = cf[ReFilee]['_cell_length_a']
    a = (float(re.sub(r'\([^\)]+\)', '', a)))
    b = cf[ReFilee]['_cell_length_b']
    b = (float(re.sub(r'\([^\)]+\)', '', b)))
    c = cf[ReFilee]['_cell_length_c']
    c = (float(re.sub(r'\([^\)]+\)', '', c)))
    alpha = cf[ReFilee]['_cell_angle_alpha']
    alpha = (float(re.sub(r'\([^\)]+\)', '', alpha)))
    beta = cf[ReFilee]['_cell_angle_beta']
    beta = (float(re.sub(r'\([^\)]+\)', '', beta)))
    gamma = cf[ReFilee]['_cell_angle_gamma']
    gamma = (float(re.sub(r'\([^\)]+\)', '', gamma)))
    cell = (a, b, c, alpha, beta, gamma)
    Amat= GSASIIlattice.cell2A(cell)
    err,SGData=GSASIIspc.SpcGroup(wav)
    HKL = GSASIIlattice.GenHLaue(1, SGData, Amat)
    #print(HKL)
    HKL = HKL[:151:]
    #print(HKL)
    #Получили матрицу с hkl и d
    dspace = []
    for i in range(len(HKL)):
        dspace.append(HKL[i][3])
    # Добавить, что если совпадают d, то это учитывается
    Element = (cf[ReFilee]['_atom_site_label'])
    Xpos = cf[ReFilee]['_atom_site_fract_x']
    Ypos = cf[ReFilee]['_atom_site_fract_y']
    Zpos = cf[ReFilee]['_atom_site_fract_z']
    #print(Xpos)
    for i in range(len(Element)):
        Xpos[i] = float((re.sub(r'\([^\)]+\)', '', Xpos[i])))
        Ypos[i] = float((re.sub(r'\([^\)]+\)', '', Ypos[i])))
        Zpos[i] = float((re.sub(r'\([^\)]+\)', '', Zpos[i])))
    #Intens = np.zeros(len(HKL))
    Intens = []
    OverInt = []

    for k in range(len(HKL)):
        Intensity = 0
        for i in range(len(Element)):
            Elem = Element[i]
            while (len(Elem)) > 2:
                Elem = Elem[0:-1]
            if not(GSASIIElem.CheckElement(Elem)):
                Elem = Elem[0:-1]
            SSQ = 1/(2*float(dspace[k]))**2
            #XRAY
            #Elet = GSASIIElem.GetFormFactorCoeff(Elem)
            #FRe = GSASIIElem.ScatFac(Elet[0],SSQ)
            #Int = ((FRe*np.exp(2*np.pi*1j*((Xpos[i])*HKL[k][0]+(Ypos[i])*HKL[k][1]+(Zpos[i])*HKL[k][2]))))
            #Neutron
            #Elet = GSASIIElem.GetAtomInfo(Elem,False)
            #print(Elet)
            FRe = atmdata.AtmBlens[Elem+'_']['SL'][0]
            #print(FRe) * SSQ
            Int = ((FRe * np.exp(2  * np.pi * 1j * ((Xpos[i]) * HKL[k][0] + (Ypos[i]) * HKL[k][1] + (Zpos[i]) * HKL[k][2]))))
            Intensity = Intensity + Int
        Intens = (abs(Intensity)) ** 2
        #print(Intens)
        OverInt.append(Intens)
    #print(OverInt)
    #OverInt это интенсивность

    OverIntMax = np.max(OverInt)
    OverIntNew = OverInt/OverIntMax

    DspaceIntensity = np.zeros((len(HKL),2))
    for i in range(len(HKL)):
        DspaceIntensity[i, 0] = dspace[i]
        DspaceIntensity[i, 1] = (OverIntNew[i])
    # Интенсивность и d-space
    return DspaceIntensity

def is_number(str):
    try:
        float(str)
        return True
    except ValueError:
        return False

def FileCheck(ReFilee,cf):
    check = 'NONO'
    wav = cf[ReFilee]['_symmetry_space_group_name_H-M']
    if wav == check:
        wav = cf[ReFilee]['_symmetry_space_group_name_H-M_alt']
    Element = (cf[ReFilee]['_atom_site_label'])
    che = True
    for i in range(len(Element)):
        Elem = Element[i]
        while (len(Elem)) > 2:
            Elem = Elem[0:-1]
        if not(GSASIIElem.CheckElement(Elem)):
            Elem = Elem[0:-1]
            if not(GSASIIElem.CheckElement(Elem)):
                che = False
    Xpos = cf[ReFilee]['_atom_site_fract_x']
    Ypos = cf[ReFilee]['_atom_site_fract_y']
    Zpos = cf[ReFilee]['_atom_site_fract_z']
    newcond = True
    for i in range(len(Xpos)):
        Xpos[i] = ((re.sub(r'\([^\)]+\)', '', Xpos[i])))
        Ypos[i] = ((re.sub(r'\([^\)]+\)', '', Ypos[i])))
        Zpos[i] = ((re.sub(r'\([^\)]+\)', '', Zpos[i])))
        newcond = newcond and is_number(Xpos[i]) and is_number(Ypos[i]) and is_number(Zpos[i])
    checking = False
    if (not ((check == wav) or (check == Xpos) or (check == Ypos) or (check == Zpos) or (check == Element))) and che and newcond:
        checking = True
    return checking

def GetSomeDSpace(st):
    global Massiv
    #global truenum
    #global falsenum
    chel = [0, 0]
    try:
        path = 'f:\\DBcif\\cif\\' + st[0] + '\\' + st[1]+st[2] + '\\' + st[3]+st[4] + '\\' + st
        ReDFile = 'file:\\' + path + '.cif'
        DataNum = st
        if os.path.exists(path + '.cif'):
            cf = CifFile.ReadCif(ReDFile)
            #volu = (cf[DataNum]['_cell_volume'])
            year = (cf[DataNum]['_journal_year'])
            ChemForm = (cf[DataNum]['_chemical_formula_sum'])
            organickcheck = False
            #if ChemForm[0]='C' and int(ChemForm[1]+ChemForm[2])>8:
            #    organickcheck = True
            inform = year + ChemForm
            #if volu == 'NONO':
            #    volu = float(10)
            #else:  and organickcheck == False
            #    volu = (float(re.sub(r'\([^\)]+\)', '', volu))) and (volu < 2500):
            print(DataNum)
            if FileCheck(DataNum, cf):
                Massiv = StatisticCreate(DataNum, cf)
                chel = [Massiv, inform]
    except Exception:
        print('I FOUND ERROR ON ',st)
    return chel
#Theta = []
#for i in range(len(HKL)):
#    Theta.append(np.arcsin(wavelength/(2*dspace[i])))
#
#plt.plot(Theta, OverIntNew)
#plt.show()