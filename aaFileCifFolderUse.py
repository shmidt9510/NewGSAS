# coding=utf-8
import CifFile
import os.path
import aaStatisticsCreate as StCr
#import GSASIIlattice
#import GSASIIspc
#import GSASIIElem
#import numpy as np
#import matplotlib.pyplot as plt
#F:\DBcif\cif\1
s1 = ['1','2','3','4','5','6','7','8','9']
s2 = ['00','01','02','03','04','05','06','07','08','09']
print(os.path.exists('F:\\DBcif\\cif\\4\\08\\06\\4080617.cif'))
for i in range(11,99,1):
    s2.append(str(i))


for st1 in s1:
    for st2 in s2:
        for st3 in s2:
            for st4 in s2:
                path = 'F:\\DBcif\\cif\\'+st1+'\\'+st2+'\\'+st3+'\\'+st1+st2+st3+st4
                ReDFile = path + '.cif'
                if os.path.exists(ReDFile):
                    cf = cf = CifFile.ReadCif(ReDFile)
                    if StCr.FileCheck(cf):
                        Mass = StCr.StatisticCreate(path,cf,0.1)



#ReFilee = '1000009'  # Номер считываемого файла
#ReDFile = ReFilee + '.cif'
#cf = CifFile.ReadCif(ReDFile)
#wav = cf[ReFilee]['_symmetry_space_group_name_H-M']  #
#a = ((cf[ReFilee]['_symmetry_space_group_name_H-M']))
