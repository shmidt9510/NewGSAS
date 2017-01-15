import numpy as np
Staticd = np.zeros((1000,10))
for IntCond in [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
    stre = str(IntCond * 10)
    f = open('Static' + stre + '.txt', 'r')
    i=0
    for line in f:
        Staticd[i, int(IntCond * 10 - 1)] = line
        i = i +1
    f.close()