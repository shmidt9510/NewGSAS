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
#fre = open('SChemForm1.txt', 'w')
#fre.close()
s1 = ['1','2','3','4','5','6','7','8','9']
s2 = ['00','01','02','03','04','05','06','07','08','09','10']
for i in range(11,99,1):
    s2.append(str(i))
astat = np.zeros(300);
bstat = np.zeros(300);
cstat = np.zeros(300);
sq1 = ['1','2','3','4','5','6','7','8','9']
sq2 = s2
sq3 = s2
sq4 = s2
amas = np.linspace(4,25,num=300)
bmas = np.linspace(4,25,num=300)
cmas = np.linspace(4,25,num=300)
falsenum = 0
truenum = 0
Staticd = np.zeros((1000,9))
#Massiv2 = 1
arr = np.linspace(0.5,35,num=1000)
for st1 in sq1:
    for st2 in sq2:
        for st3 in sq3:
            for st4 in sq4:
                try:
                    path = 'd:\\DB1\\cif\\'+st1+'\\'+st2+'\\'+st3+'\\'+st1+st2+st3+st4
                    ReDFile ='file:\\'+ path + '.cif'
                    #print(os.path.exists(path+'.cif'))
                    DataNum = st1+st2+st3+st4
                    print(DataNum)
                    if os.path.exists(path+'.cif'):
                        cf = CifFile.ReadCif(ReDFile)
                        #volu = (cf[DataNum]['_cell_volume'])
                        #year = (cf[DataNum]['_journal_year'])
                        ChemForm = (cf[DataNum]['_chemical_formula_sum'])
                        if not(StCr.isitorganic(ChemForm)):
                            a = cf[DataNum]['_cell_length_a']
                            a = (float(re.sub(r'\([^\)]+\)', '', a)))
                            b = cf[DataNum]['_cell_length_b']
                            b = (float(re.sub(r'\([^\)]+\)', '', b)))
                            c = cf[DataNum]['_cell_length_c']
                            c = (float(re.sub(r'\([^\)]+\)', '', c)))
                            ind = np.searchsorted(amas, a)
                            astat[ind - 1] = astat[ind - 1] + 1
                            ind = np.searchsorted(bmas, b)
                            bstat[ind - 1] = bstat[ind - 1] + 1
                            ind = np.searchsorted(cmas, c)
                            cstat[ind - 1] = cstat[ind - 1] + 1
                            truenum = truenum + 1
                            #print('gotya')
                except Exception:
                    #print('dosentgotya')
                    falsenum = falsenum + 1
        print(st2)
    print('Were up all night for good fun' , truenum)
print('Were up all night to get lucky')
print('T', truenum)
print('F', falsenum)
f = open('qstata.txt', 'w')
for i in range(len(astat)):
    f.write(astat[i])
f.close()
f = open('qstatb.txt', 'w')
for i in range(len(bstat)):
    f.write(bstat[i])
f.close()
f = open('qstatc.txt', 'w')
for i in range(len(cstat)):
    f.write(cstat[i])
f.close()
