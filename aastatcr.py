# coding=utf-8
import CifFile
import GSASIIlattice
import GSASIIspc
import os.path
import GSASIIElem
import numpy as np
import re
import atmdata
# import matplotlib.pyplot as plt

def StatisticCreate(ReFilee,cf):
    # ReFilee='1000009'  # Номер считываемого файла
    EquivPos = cf[ReFilee]['_symmetry_equiv_pos_as_xyz']
    wav = cf[ReFilee]['_symmetry_space_group_name_H-M']
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
    # HKL = HKL[:151:]
    # print(HKL)
    # Получили матрицу с hkl и d
    dspace = []
    for i in range(len(HKL)):
        dspace.append(HKL[i][3])
    # Добавить, что если совпадают d, то это учитывается
    Element = (cf[ReFilee]['_atom_site_label'])
    Xpos = cf[ReFilee]['_atom_site_fract_x']
    Ypos = cf[ReFilee]['_atom_site_fract_y']
    Zpos = cf[ReFilee]['_atom_site_fract_z']
    MultFact = cf[ReFilee]['_atom_site_symmetry_multiplicity']
    if MultFact == 'NONO':
        MultFact = np.ones(len(Elements))
    # print(Xpos)
    for i in range(len(Element)):
        Xpos[i] = float((re.sub(r'\([^\)]+\)', '', Xpos[i])))
        Ypos[i] = float((re.sub(r'\([^\)]+\)', '', Ypos[i])))
        Zpos[i] = float((re.sub(r'\([^\)]+\)', '', Zpos[i])))
    # Intens = np.zeros(len(HKL))
    Positions = equivpositions(EquivPos,Xpos,Ypos,Zpos)
    print(Positions)
    Intens = []
    OverInt = []
    ForModInt = np.zeros(len(HKL))
    for k in range(len(HKL)):
        Intensity = 0
        for i in range(len(Element)):
            Elem = Element[i]
            Int = 0
            while (len(Elem)) > 2:
                Elem = Elem[0:-1]
            if not(GSASIIElem.CheckElement(Elem)):
                Elem = Elem[0:-1]
            # XRAY
            SSQ = 1 / (2 * float(dspace[k])) ** 2
            Elet = GSASIIElem.GetFormFactorCoeff(Elem)
            FRe = GSASIIElem.ScatFac(Elet[0],SSQ)
            for l in range(len(EquivPos)):
                Xpos = Positions[l][i][0]
                Ypos = Positions[l][i][1]
                Zpos = Positions[l][i][2]
                if Xpos<1.01 and Ypos<1.01 and Zpos<1.01:
                    Int = Int + (FRe * np.exp(2 * np.pi * 1j * ( Xpos * HKL[k][0] + Ypos * HKL[k][1] + Zpos * HKL[k][2])))
            # Neutron
            #Elet = GSASIIElem.GetAtomInfo(Elem,False)
             #print(Elet)
            #FRe = atmdata.AtmBlens[Elem+'_']['SL'][0]
            #xj = Xpos[i]*a
            #yj = Ypos[i]*b
            #zj = Zpos[i]*c
            #Int = ((FRe * np.exp(2  * np.pi * 1j * (xj * HKL[k][0]  + yj *HKL[k][1]  + zj *HKL[k][2]))))
            #for l in range(len(EquivPos)):
            #    Xpos = Positions[l][i][0]
            #    Ypos = Positions[l][i][1]
            #    Zpos = Positions[l][i][2]
            #    if Xpos<1.01 and Ypos<1.01 and Zpos<1.01:
            #        Int =Int + (FRe * np.exp(2 * np.pi * 1j * ( Xpos * HKL[k][0] + Ypos * HKL[k][1] + Zpos * HKL[k][2])))*np.exp(-1/(4*(HKL[k][3])**2))
            Intensity = Intensity + Int
        Intens = (abs(np.real(Intensity))) ** 2
        print(str((Intensity)))
        #ForModInt[i] = str(Intensity)
        OverInt.append(Intens)
    # print(OverInt)
    # OverInt это интенсивность

    OverIntMax = np.max(OverInt)
    OverIntNew = OverInt/OverIntMax*100

    DspaceIntensity = np.zeros((len(HKL),6))
    for i in range(len(HKL)):
        DspaceIntensity[i, 0] = dspace[i]
        DspaceIntensity[i, 1] = (OverIntNew[i])
        DspaceIntensity[i, 2] = HKL[i][0]
        DspaceIntensity[i, 3] = HKL[i][1]
        DspaceIntensity[i, 4] = HKL[i][2]
        DspaceIntensity[i, 5] = ForModInt[i]
    # Интенсивность и d-space
    return DspaceIntensity
#def butisitorganic(Elem):
#    if Elem[0] == 'C' and Elem[1].isdigit:



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
            inform = year + ChemForm
            #if volu == 'NONO':
            #    volu = float(10)
            #else:
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

def equivpositions(equiv,Xpos,Ypos,Zpos):
    a = []
    b = []
    c = []
    equivpos = []
    for i in range(len(equiv)):
        equiv[i] = equiv[i].replace('1/2','0.5')
        l1 = equiv[i].find(',')
        l2 = equiv[i].rfind(',')
        a.append(equiv[i][:l1:])
        b.append(equiv[i][l1+1:l2:])
        c.append(equiv[i][l2+1::])
        equivp = []
        for k in range(len(Xpos)):
            x = float(Xpos[k])
            y = float(Ypos[k])
            z = float(Zpos[k])
            equivp.append([round(eval(a[i]),5),round(eval(b[i]),5),round(eval(c[i]),5)])
        equivpos.append(equivp)
    for i in range(len(Xpos)):
        for k in range(len(equiv)-1):
            for l in range(k+1,len(equiv)):
                if equivpos[l][i] == equivpos[k][i]:
                    equivpos[l][i]=[10,10,10]
    return equivpos
