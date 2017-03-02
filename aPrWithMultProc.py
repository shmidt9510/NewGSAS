
"""
Example involving multiprocessing package.
"""

from multiprocessing import Pool
import os
import numpy as np
import aastatcr as StCr
#import time


#class Profiler(object):
#    def __enter__(self):
#        self._startTime = time.time()
#
#    def __exit__(self, type, value, traceback):
#        print "Elapsed time: {:.3f} sec".format(time.time() - self._startTime)

#9300000
def data_gen(k1,k2):
    for i in range(k1,k2,1):
        k = str(i)
        yield k

fre = open('SChemForm.txt', 'w')
fre.close()
Staticd = np.zeros((1000,10))
Staticd1 = np.zeros((1000,10))
StaticdO = np.zeros(1000)
arr = np.linspace(0.5,35,num=1000)

#for IntCond in [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
#    stre = str(IntCond * 10)
#    f = open('Static' + stre + '.txt', 'r')
#    i=0
#    for line in f:
#        Staticd[i, int(IntCond * 10 - 1)] = line
#        i = i +1
#    f.close()


if __name__ == '__main__':
    p = Pool(processes = 4)
    onenum=0
    twonum=0
    # true range 8301 7153000
    for l in range(0,8301,1):
        g = data_gen(1000001+l*1000,1000000+(l+1)*1000)
        results = p.map(StCr.GetSomeDSpace,g)
        print(1000000+l*1000)
        #len(results)
        for tt in range(len(results)):
            Massiv = results[tt][0]
            infq = results[tt][1]
            #ChemFormLast = 'First'
            if type(infq) == type('strinex'):
                yearq = infq[0:4:1]
                ChemForm = infq[4::1]
                fre = open('SChemForm.txt', 'a')
                fre.write(ChemForm + '  '+yearq +' '+ '\n')
                fre.close()
            if not(type(Massiv) == type(2)):
                twonum = twonum + 1 #and not (ChemForm == ChemFormLast)
                #ChemFormLast = ChemForm
                for i in range(len(Massiv)):
                    ind = np.searchsorted(arr, Massiv[i])
                    StaticdO[ind - 1] = StaticdO[ind - 1] + 1
                f = open('Static00.txt', 'w')
                for i in range(len(StaticdO)):
                    f.write(str(StaticdO[i]) + '\n')
                f.close()
                #for IntCond in [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
                #    for i in range(len(Massiv)):
                #        ind = np.searchsorted(arr, Massiv[i][0])
                 #       if Massiv[i][1] > float(IntCond):
                 #           Staticd[ind - 1, int(IntCond * 10 - 1)] = Staticd[ind - 1, int(IntCond * 10 - 1)] + Massiv[i][1]
                 #           Staticd1[ind - 1, int(IntCond * 10 - 1)] = Staticd1[ind - 1, int(IntCond * 10 - 1)]+1
                 #   stre = str(IntCond * 10)
                 #   f = open('Static' + stre + '.txt', 'w')
                 #   g = open('Static1' + stre + '.txt', 'w')
                 #   for i in range(len(Staticd)):
                  #      f.write(str(Staticd[i, int(IntCond * 10 - 1)]) + '\n')
                  #      g.write(str(Staticd1[i, int(IntCond * 10 - 1)]) + '\n')
                 #   f.close()
                 #   g.close()