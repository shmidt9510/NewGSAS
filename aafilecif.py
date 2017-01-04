# coding=utf-8
import CifFile
import os.path
import aastatcr as StCr
import numpy as np
import re
import csv
#import GSASIIlattice
#import GSASIIspc
#import GSASIIElem
#import matplotlib.pyplot as plt
#F:\DBcif\cif\1
s1 = ['1','2','3','4','5','6','7','8','9']
s2 = ['00','01','02','03','04','05','06','07','08','09']
for i in range(11,99,1):
    s2.append(str(i))
#print(s2)
#print(os.path.exists('f:\\DBcif\\cif\\4\\08\\06\\4080617.cif'))
#print('f:\\DBcif\\cif\\4\\08\\06\\4080617.cif')
cf = CifFile.ReadCif('file:\\f:\\DBcif\\cif\\4\\08\\06\\4080617.cif')
#print(cf)
stest1 = ['00']
stest = ['1']
Staticd = np.zeros(1000)
arr = np.linspace(0.5,35,num=1000)
for st1 in stest:
    for st2 in stest1:
        for st3 in s2:
            for st4 in s2:
                path = 'f:\\DBcif\\cif\\'+st1+'\\'+st2+'\\'+st3+'\\'+st1+st2+st3+st4
                ReDFile ='file:\\'+ path + '.cif'
                #print(ReDFile)
                #print(os.path.exists(path+'.cif'))
                DataNum = st1+st2+st3+st4
                print(DataNum)
                if os.path.exists(path+'.cif'):
                    cf = CifFile.ReadCif(ReDFile)
                    volu = (cf[DataNum]['_cell_volume'])
                    if volu == 'NONO':
                        volu = float(10)
                    else:
                        volu = (float(re.sub(r'\([^\)]+\)', '', volu)))
                    if StCr.FileCheck(DataNum,cf) and (volu < 2500):
                        Massiv2 = StCr.StatisticCreate(DataNum,cf,0.2)
                        #print(Massiv2)
                        for i in range(len(Massiv2)):
                            ind = np.searchsorted(arr, Massiv2[i][0])
                            #print(ind)
                            Staticd[ind-1] = Staticd[ind-1] + Massiv2[i][1]
    #print(st2)
print(Staticd)
f = open('Static.txt', 'w')
for i in range(len(Staticd)):
    f.write(str(Staticd[i])+'\n')
#ReFilee = '1000009'  # Номер считываемого файла
#ReDFile = ReFilee + '.cif'
#cf = CifFile.ReadCif(ReDFile)
#wav = cf[ReFilee]['_symmetry_space_group_name_H-M']  #
#a = ((cf[ReFilee]['_symmetry_space_group_name_H-M']))
