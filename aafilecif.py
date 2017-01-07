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
s2 = ['00','01','02','03','04','05','06','07','08','09','10']
for i in range(11,99,1):
    s2.append(str(i))
#print(s2)
#print(os.path.exists('f:\\DBcif\\cif\\4\\08\\06\\4080617.cif'))
#print('f:\\DBcif\\cif\\4\\08\\06\\4080617.cif')
#cf = CifFile.ReadCif('file:\\f:\\DBcif\\cif\\4\\08\\06\\4080617.cif')
#print(cf)
sq2 = ['01']
sq1 = ['1']
sq3 = ['00']
sq4 = ['23','24','25','26','27']
falsenum = 0
truenum = 0
Staticd = np.zeros((1000,9))
arr = np.linspace(0.5,35,num=1000)
for st1 in s1:
    for st2 in s2:
        for st3 in s2:
            for st4 in s2:
                try:
                    path = 'f:\\DBcif\\cif\\'+st1+'\\'+st2+'\\'+st3+'\\'+st1+st2+st3+st4
                    ReDFile ='file:\\'+ path + '.cif'
                    #print(ReDFile)
                    #print(os.path.exists(path+'.cif'))
                    DataNum = st1+st2+st3+st4
                    if os.path.exists(path+'.cif'):
                        cf = CifFile.ReadCif(ReDFile)
                        volu = (cf[DataNum]['_cell_volume'])
                        #year = (cf[DataNum]['_journal_year'])
                        #except Exception:
                        #    cf = CifFile.ReadCif('file:\\f:\\DBcif\\cif\\1\\00\\00\\1000001.cif')
                         #   DataNum = '1000001'
                         #   volu = (cf['1000001']['_cell_volume'])
                        if volu == 'NONO':
                            volu = float(10)
                        else:
                            volu = (float(re.sub(r'\([^\)]+\)', '', volu)))
                        print(DataNum)
                        #print(StCr.FileCheck(DataNum,cf))
                        if StCr.FileCheck(DataNum,cf) and (volu < 2500):
                            truenum = truenum + 1
                            Massiv2 = StCr.StatisticCreate(DataNum,cf)
                            #print(Massiv2)
                            for IntCond in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
                                for i in range(len(Massiv2)):
                                    ind = np.searchsorted(arr, Massiv2[i][0])
                                    #print(ind)
                                    if Massiv2[i][1] > IntCond:
                                        Staticd[ind-1,int(IntCond*10-1)] = Staticd[ind-1,int(IntCond*10-1)] + Massiv2[i][1]
                                stre = str(IntCond*10)
                                #print(stre)
                                f = open('Static'+stre+'.txt', 'w')
                                for i in range(len(Staticd)):
                                    f.write(str(Staticd[i,int(IntCond*10-1)]) + '\n')
                except Exception:
                    falsenum = falsenum + 1
                    #print (Massiv2)
                    #print(Staticd)
                print('T',truenum)
                print('F',falsenum)

    #print(st2)
#ReFilee = '1000009'  # Номер считываемого файла
#ReDFile = ReFilee + '.cif'
#cf = CifFile.ReadCif(ReDFile)
#wav = cf[ReFilee]['_symmetry_space_group_name_H-M']  #
#a = ((cf[ReFilee]['_symmetry_space_group_name_H-M']))
