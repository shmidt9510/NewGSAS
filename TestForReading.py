# coding=utf-8
import CifFile
import GSASIIlattice
import GSASIIspc
import GSASIIElem
import numpy as np

ReFilee='1000009'
ReDFile=ReFilee+'.cif'
cf = CifFile.ReadCif(ReDFile)
wav = cf[ReFilee]['_symmetry_space_group_name_H-M'] #
a = int(float(cf[ReFilee]['_cell_length_a']))
b = int(float(cf[ReFilee]['_cell_length_b']))
c = int(float(cf[ReFilee]['_cell_length_c']))
alpha = int(float(cf[ReFilee]['_cell_angle_alpha']))
beta = int(float(cf[ReFilee]['_cell_angle_beta']))
gamma = int(float(cf[ReFilee]['_cell_angle_gamma']))
cell = (a, b, c, alpha, beta, gamma)
#print(cell)
Amat= GSASIIlattice.cell2A(cell)
#print(A)
err,SGData=GSASIIspc.SpcGroup(wav)
#Gmat, g = GSASIIlattice.cell2Gmat(cell)
#print(G)
#system = SGData['SGSys']
#center = SGData['SGLatt']
#BravNum = GSASIIlattice.GetBraviasNum(center, system)
HKL = GSASIIlattice.GenHLaue(1, SGData, Amat)
#Получили матрицу с hkl и d
dspace = []
for i in range(len(HKL)):
    dspace.append(HKL[i][3])
# Добавить, что если совпадают d, то это учитывается
#print(dspace)
Element = (cf[ReFilee]['_atom_site_label'])
Xpos = cf[ReFilee]['_atom_site_fract_x']
Ypos = cf[ReFilee]['_atom_site_fract_y']
Zpos = cf[ReFilee]['_atom_site_fract_z']
#Intens = np.zeros(len(HKL))
Intens = []
print(HKL[5][0],HKL[43][0],HKL[56][0])
for k in range(len(HKL)):
    Intensity = 0
    for i in range(len(Element)):
        Elem = []
        Elem = Element[i][0]
        if Element[i][1].islower():
            Elem = Elem + Element[i][1]
        #print(Elem)
        orb = GSASIIElem.GetXsectionCoeff(Elem)
        #print(orb)
        FRe, fIm, ss = GSASIIElem.FPcalc(orb, 12)
        #print(FRe)
        Int = (abs(FRe*np.exp(2*np.pi*1j*(float(Xpos[i])*HKL[k][0]+float(Ypos[i])*HKL[k][1]+float(Zpos[i])*HKL[k][2]))))**2
        #print(Int)
        Intensity = Intensity + Int
    Intens.append(Intensity)
    print(Intensity)
print(Intens)