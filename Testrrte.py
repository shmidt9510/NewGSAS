
"""
Example involving multiprocessing package.
"""

from multiprocessing import Pool
import os
import numpy as np
import aastatcr as StCr
import time


class Profiler(object):
    def __enter__(self):
        self._startTime = time.time()

    def __exit__(self, type, value, traceback):
        print "Elapsed time: {:.3f} sec".format(time.time() - self._startTime)

#9300000
def data_gen(k1,k2):
    for i in range(k1,k2,1):
        k = str(i)
        yield k


fre = open('SChemForm.txt', 'w')
fre.close()
Staticd = np.zeros((1000,10))
arr = np.linspace(0.5,35,num=1000)
if __name__ == '__main__':
    p = Pool(processes=5)
    onenum=0
    twonum=0
    # true range 8301
    for l in range(1):
        g = data_gen(1000000+l*1000,1000000+(l+1)*1000)
        results = p.map(StCr.GetSomeDSpace,g)
        #print(1000000+l*1000)#len(results)
        for tt in range(len(results)):
            Massiv = results[tt][0]
            infq = results[tt][1]
            ChemFormLast = 'First'
            if type(infq) == type('strinex'):
                yearq = infq[0:4:1]
                ChemForm = infq[4::1]
                fre = open('SChemForm.txt', 'a')
                fre.write(ChemForm + '  '+yearq +' '+ '\n')
                fre.close()
            if not(type(Massiv) == type(2)) and not (ChemForm == ChemFormLast):
                twonum = twonum + 1
                ChemFormLast = ChemForm
                for IntCond in [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
                    for i in range(len(Massiv)):
                        ind = np.searchsorted(arr, Massiv[i][0])
                        if Massiv[i][1] > float(IntCond):
                            Staticd[ind - 1, int(IntCond * 10 - 1)] = Staticd[ind - 1, int(IntCond * 10 - 1)] + Massiv[i][1]
                    stre = str(IntCond * 10)
                    f = open('Static' + stre + '.txt', 'w')
                    for i in range(len(Staticd)):
                        f.write(str(Staticd[i, int(IntCond * 10 - 1)]) + '\n')
                    f.close()
