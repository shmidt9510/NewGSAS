# coding=utf-8
import CifFile
import os.path
import aastatcr as StCr
import numpy as np
#import GSASIIlattice
#import GSASIIspc
#import GSASIIElem
#import matplotlib.pyplot as plt
#F:\DBcif\cif\1
s1 = ['1','2','3','4','5','6','7','8','9']
s2 = ['00','01','02','03','04','05','06','07','08','09']
print(os.path.exists('D:\\DB1\\cif\\4\\08\\06\\4080617.cif'))
print('D:\\DB1\\cif\\4\\08\\06\\4080617.cif')
cf = CifFile.ReadCif('D:\\DB1\\cif\\4\\08\\06\\4080617.cif')
for i in range(11,99,1):
    s2.append(str(i))
stest = ['1']
Staticd = np.zeros(1000)
arr = np.linspace(1,12,num=1000)

for st1 in stest:
    for st2 in s2:
        for st3 in s2:
            for st4 in s2:
                path = 'D:\\DB1\\cif\\'+st1+'\\'+st2+'\\'+st3+'\\'+st1+st2+st3+st4
                ReDFile = path + '.cif'
                print(ReDFile)
                print(os.path.exists(ReDFile))
                if os.path.exists(ReDFile):
                    cf = CifFile.ReadCif(ReDFile)
                    if StCr.FileCheck(cf):
                        Massiv2 = StCr.StatisticCreate(path,cf,0.1)
                        for i in range(len(ar32)):
                            ind = np.searchsorted(arr, ar32[i][0])
                            Staticd[ind] = Staticd[ind] + ar32[i][1]
print(Staticd)


#ReFilee = '1000009'  # Номер считываемого файла
#ReDFile = ReFilee + '.cif'
#cf = CifFile.ReadCif(ReDFile)
#wav = cf[ReFilee]['_symmetry_space_group_name_H-M']  #
#a = ((cf[ReFilee]['_symmetry_space_group_name_H-M']))
