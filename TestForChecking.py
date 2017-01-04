#coding=utf-8
import CifFile as cifq
import numpy as np
import aastatcr
#import GSASIIlattice
#import GSASIIspc
#import GSASIIElem
#import matplotlib.pyplot as plt
#ReFilee='1000009'
#  Номер считываемого файла
#ReDFile=ReFilee+'.cif'
#cf = CifFile.ReadCif(ReDFile)
#print(cf[ReFilee]['_symmetry_space_group_name_H-M3'])
#Element = (cf[ReFilee]['_atom_site_label'])
#Xpos = cf[ReFilee]['_atom_site_fract_x']
#Ypos = cf[ReFilee]['_atom_site_fract_y']
#Zpos = cf[ReFilee]['_atom_site_fract_z']
Staticd = np.zeros(1000)
arr = np.linspace(1,20,num=1000)
#np.searchsorted(, MassFromStat[0])
#print(arr)
ReFilee = '1000009'  # Номер считываемого файла
ReDFile = ReFilee+'.cif'
cf = cifq.ReadCif(ReDFile)
ar32 = aastatcr.StatisticCreate(ReFilee,cf,0.1)
print(ar32)
#Theta = []
#for i in range(len(ar32)):
#    Theta.append(np.arcsin(1.5/(2*ar32[i][0])))
#print(ar32[1].n)
#plt.plot(Theta, ar32[1].n)
#plt.show()