import GSASIIElem as GE
import atmdata
import CifFile
import GSASIIlattice
import GSASIIspc
import os.path
import GSASIIElem
import numpy as np
import re
import atmdata
import aastatcr as stcr

#mmm = GE.GetAtomInfo('H',False)
#print(type(mmm))
#print(mmm)
#data = atmdata.AtmBlens['H_']['SL'][0]
#print(data)
#print(type(data))
#print(data)
#print(mmm['Isotopes']['1']['SL'][0])
sq1 = '1'
sq2 = '00'
sq3 = '41'
sq4 = '13'
path = 'f:\\DBcif\\cif\\'+sq1+'\\'+sq2+'\\'+sq3+'\\'+sq1+sq2+sq3+sq4
ReDFilee ='file:\\'+ path + '.cif'
cf = CifFile.ReadCif(ReDFilee)
ReFilee = sq1+sq2+sq3+sq4
#EquivPos = cf[ReFilee]['_symmetry_equiv_pos_as_xyz']
#Xpos = cf[ReFilee]['_atom_site_fract_x']
#Ypos = cf[ReFilee]['_atom_site_fract_y']
#Zpos = cf[ReFilee]['_atom_site_fract_z']
#for i in range(len(Xpos)):
#    Xpos[i] = float((re.sub(r'\([^\)]+\)', '', Xpos[i])))
#    Ypos[i] = float((re.sub(r'\([^\)]+\)', '', Ypos[i])))
#    Zpos[i] = float((re.sub(r'\([^\)]+\)', '', Zpos[i])))
#print(stcr.equivpositions(EquivPos, Xpos, Ypos, Zpos))
stcr.StatisticCreate(ReFilee,cf)