from itertools import count

from epicsdbbuilder import records, CP
from DLSRecordName import SetDevice, UnsetDevice


# The beam control function exported by this module takes as argument a list
# of two kinds of object: actuators and dipoles.  To complicate things, an
# actuator may consist of two actuators working together: thus an actuator is
# in fact represented by an "actuator set".
#
# The two classes below provide a uniform interface.
#
# For each actuator in an actuator set we have a pair of records, one to
# control the record, and one to read its status.  The status is interpreted
# thus:
#       status = 1  => beam is clear at this point
#       status != 1 => beam is obstructed at this point.
# A single beam display status record is generated for an actuator.
#
# A dipole represents a point where the beam branches and contains a single
# status record thus:
#       status = 1  => dipole on, beam is bent
#       status != 1 => dipole off, beam goes straight.
# Two beam status records are generated for a dipole.

class ActuatorSet:
    def __init__(self, *actuators):
        self.actuators = actuators
    def Status(self):   return [status  for _, status  in self.actuators]
    def Controls(self): return [control for control, _ in self.actuators]
    def Dipole(self):   return None

class Dipole:
    def __init__(self, dipole):
        self.dipole = dipole
    def Status(self):   return [self.dipole]
    def Controls(self): return []
    def Dipole(self):   return self.dipole



# A dipole status record picks up an external record from the magnet controller
# and returns a single status thus:
#       status = 0  => dipole current is off
#       status = 1  => dipole current is on
# This control assumes that the dipole is simply either on or off.
def DipoleStatus(id, statusid, dipole):
    SetDevice('CTRL', id)

    # Calculate whether the current is above some fairly arbitrary threshold.
    status = records.calc(
        'DIPOLE%d' % statusid,
        INPA = CP(dipole),
#        INPA = dipole + ' CP',   # Need to pass dipole in as a real record!!!
        INPB = 10.0,    # Random "on" threshold
        CALC = '(A > B)?1:0')

    UnsetDevice()

    return Dipole(status)



# Computes the status of the beam (indicating which parts of the beam are
# clear from diagnostics obstructions) from a list of locations and bit
# positions.
def BeamControlBits(id, prior, *locations):

    # This supporting class builds calculation records as necessary to
    # compute the required bit mask.  The CALC field can, alas, contain at
    # most 40 characters, which is a major restriction, so this class
    # encapsulates code to daisy-chain calculations as necessary.
    class Calc:
        def __init__(self):
            self.calc = None
            self.calc_n = count(1)
            self.Reset()
        def Reset(self):
            self.prior = self.calc
            self.calc = records.calc('CALCBEAM%d' % next(self.calc_n))
            self.calcString = ''
            self.c = iter(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L'])
        def Entry(self, input, index):
            # Work out whether there is enough room to complete this entry.
            # If not, close this record and start a new one.  The calculation
            # string at this stage may look like
            #   (%sX#1?%d:65536):Y
            # or
            #   %sX#1?%d:65536
            # depending on whether prior is set, where %s is the current
            # calcString, %d is the mask value at this point.  That is, we
            # need room for an extra 14+len(mask) characters
            bits = str((1 << index) - 1)
            if len(self.calcString) + len(bits) + 14 > 40:
                self.Close()
                self.Reset()

            # Ok, add the calculated string.
            ch = next(self.c)
            self.calcString += '%c#1?%s:' % (ch, bits)
            setattr(self.calc, 'INP' + ch, CP(input))

        def Close(self):
            # Complete the calculation by setting all bits if all stations
            # have status=1 and then taking any earlier chained record into
            # account.
            self.calcString += '65535'
            if self.prior:
                ch = next(self.c)
                setattr(self.calc, 'INP' + ch, CP(self.prior))
                self.calc.CALC = '(%s)&%c' % (self.calcString, ch)
            else:
                self.calc.CALC = self.calcString
            return self.calc


    SetDevice('CTRL', id)

    calc = Calc()
    beam_n = count(1)
    beam1 = records.mbbiDirect('BEAM%d' % next(beam_n), NOBT = 16)

    if prior:
        calc.Entry(prior, 0)
    for index, location in locations:
        dipole = location.Dipole()
        if dipole:
            # The dipole 'straight through' record is generated here.  This
            # needs to pick up the current position, so we close the
            # calculation record and pick up the result now.
            status = calc.Close()
            calc.Reset()
            records.calc('BEAM%d' % next(beam_n),
                CALC = '(A&32768)#0 && B=0',
                INPA = CP(status),
                INPB = CP(dipole))
        for status in location.Status():
            calc.Entry(status, index)

    beam1.INP = CP(calc.Close())

    UnsetDevice()
    return beam1.BF
