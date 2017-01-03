########### SVN repository information ###################
# $Date: 2013-10-03 22:11:47 +0400 (Чт, 03 окт 2013) $
# $Author: toby $
# $Revision: 1077 $
# $URL: https://subversion.xray.aps.anl.gov/pyGSAS/trunk/unit_tests.py $
# $Id: unit_tests.py 1077 2013-10-03 18:11:47Z toby $
########### SVN repository information ###################
'''
*unit_tests: Self-test Module*
------------------------------

A script that can be run to test a series of self-tests in GSAS-II. At present,
only modules ``GSASIIspc`` and ``GSASIIlattice`` have self-tests. 

'''

import GSASIIspc
import GSASIIlattice
def test_GSASIIspc():
    '''Test registered self-tests in ``GSASIIspc``.
    Takes no input and returns nothing. Throws an Exception if a test fails.
    '''
    #GSASIIspc.selftestquiet = False
    for test in GSASIIspc.selftestlist:
        test()
def test_GSASIIlattice():
    '''Test registered self-tests in ``GSASIIlattice``.
    Takes no input and returns nothing. Throws an Exception if a test fails.
    '''
    #GSASIIlattice.selftestquiet = False
    for test in GSASIIlattice.selftestlist:
        test()

if __name__ == '__main__':
    test_GSASIIspc()
    test_GSASIIlattice()
    print "OK"
