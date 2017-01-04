      REAL*4  FUNCTION  ACOSD(ARG)

!PURPOSE:

      INCLUDE       '../INCLDS/COPYRIGT.FOR' 

!CALLING ARGUMENTS:

      REAL*4        ARG                 

!INCLUDE STATEMENTS:

!LOCAL VARIABLES:

!FUNCTION DEFINITIONS:

!DATA STATEMENTS:

      DATA  RPD/0.017453292519943/

!CODE:

      ARG1 = MIN(1.0,MAX(-1.0,ARG))
      ACOSD = ACOS(ARG1)/RPD
      RETURN
      END
