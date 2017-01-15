import GSASIIElem as GE
import atmdata

mmm = GE.GetAtomInfo('H',False)
#print(type(mmm))
#print(mmm)
data = atmdata.AtmBlens['H_']['SL'][0]
#print(data)
print(type(data))
print(data)
#print(mmm['Isotopes']['1']['SL'][0])