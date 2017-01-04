# coding=utf-8
import CifFile
import GSASIIlattice
import GSASIIspc
import GSASIIElem
import numpy as np
#import matplotlib.pyplot as plt

def StatisticCreate(ReFilee,cf,IntCond):
    #wavelength = wavel
    #ReFilee='1000009'  # Номер считываемого файла
    #ReDFile=ReFilee+'.cif'
    #cf = CifFile.ReadCif(ReDFile)
    wav = cf[ReFilee]['_symmetry_space_group_name_H-M'] #
    if wav == 'NONO':
        wav = cf[ReFilee]['_symmetry_space_group_name_H-M_alt']
    a = int(float(cf[ReFilee]['_cell_length_a']))
    b = int(float(cf[ReFilee]['_cell_length_b']))
    c = int(float(cf[ReFilee]['_cell_length_c']))
    alpha = int(float(cf[ReFilee]['_cell_angle_alpha']))
    beta = int(float(cf[ReFilee]['_cell_angle_beta']))
    gamma = int(float(cf[ReFilee]['_cell_angle_gamma']))
    cell = (a, b, c, alpha, beta, gamma)
    Amat= GSASIIlattice.cell2A(cell)
    err,SGData=GSASIIspc.SpcGroup(wav)
    HKL = GSASIIlattice.GenHLaue(1.2, SGData, Amat)
    #Получили матрицу с hkl и d
    dspace = []
    for i in range(len(HKL)):
        dspace.append(HKL[i][3])
    # Добавить, что если совпадают d, то это учитывается
    Element = (cf[ReFilee]['_atom_site_label'])
    Xpos = cf[ReFilee]['_atom_site_fract_x']
    Ypos = cf[ReFilee]['_atom_site_fract_y']
    Zpos = cf[ReFilee]['_atom_site_fract_z']
    #Intens = np.zeros(len(HKL))
    Intens = []
    OverInt = []

    for k in range(len(HKL)):
        Intensity = 0
        Intens = 0
        for i in range(len(Element)):
            Elem = []
            Elem = Element[i][0]
            if Element[i][1].islower():
                Elem = Elem + Element[i][1]
            SSQ = 1/(2*float(dspace[k]))**2
            Elet = GSASIIElem.GetFormFactorCoeff(Elem)
            FRe = GSASIIElem.ScatFac(Elet[0],SSQ)
            Int = ((FRe*np.exp(2*np.pi*1j*(float(Xpos[i])*HKL[k][0]+float(Ypos[i])*HKL[k][1]+float(Zpos[i])*HKL[k][2]))))
            Intensity = Intensity + Int
        Intens = (abs(Intensity)) ** 2
        OverInt.append(Intens[0])
    #print(OverInt)
    #OverInt это интенсивность

    OverIntMax = np.max(OverInt)
    OverIntNew = OverInt/OverIntMax

    DspaceIntensity = np.zeros((len(HKL),2))
    for i in range(len(HKL)):
        DspaceIntensity[i, 0]=dspace[i]
        if OverIntNew[i]>IntCond:
            DspaceIntensity[i, 1] = OverIntNew[i]
        else:
            DspaceIntensity[i, 1] = 0
    # Интенсивность и d-space
    return DspaceIntensity

def FileCheck(ReFilee,cf):
    check = 'NONO'
    wav = cf[ReFilee]['_symmetry_space_group_name_H-M']
    if wav == check:
        wav = cf[ReFilee]['_symmetry_space_group_name_H-M_alt']
    Element = (cf[ReFilee]['_atom_site_label'])
    Xpos = cf[ReFilee]['_atom_site_fract_x']
    Ypos = cf[ReFilee]['_atom_site_fract_y']
    Zpos = cf[ReFilee]['_atom_site_fract_z']
    #checking = bool()
    if not ((check == wav) or (check == Xpos) or (check == Ypos) or (check == Zpos) or (check == Element)):
        checking = True
    return checking



#Theta = []
#for i in range(len(HKL)):
#    Theta.append(np.arcsin(wavelength/(2*dspace[i])))
#
#plt.plot(Theta, OverIntNew)
#plt.show()