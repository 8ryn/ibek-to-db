import itertools

from epicsdbbuilder import records, CP, PP, create_fanout

from builder.diagTools import supportLib
from .beamControl import ActuatorSet
from builder.DLSRecordName import SetDevice, UnsetDevice
from builder.autosave import add_autosave



# Allow five seconds for movement timeout
MovementTimeout = 5.0



# ----------------------------------------------------------------------
#
#   Support for interface registers.


# Some of the complexity here is a relic of simulation support code, now
# stripped out.
class _InputRegister:
    def __init__(self, name, register, **fields):
        self.input = register.mbbiDirect(name, **fields)

    def register(self, start, length):
        return _SubRegister(self, start, length)


class _SubRegister:
    def __init__(self, inReg, start, length):
        self.input = inReg.input.register(start, length)

    def register(self, start, length):
        return _SubRegister(self, start, length)

    def bit(self, start):
        return _SubRegister(self, start, 1)

    def bi(self, name, **fields):
        return self.input.bi(name, **fields)

    def bo(self, name, **fields):
        return self.output.bo(name, **fields)




# This builds the array of mbbi interface registers to the underlying
# hardware.
def InterfaceRecords(id, inputs, outputs):
    SetDevice('CTRL', id)

    # Generate the input and output registers.
    count = itertools.count(1)
    inregs = [
        _InputRegister('PIM%d' % next(count), reg,
             SCAN = '.1 second') for reg in inputs]

    outregs = [
        reg.mbboDirect('PIM%d' % next(count),
            OMSL = 'supervisory',
            PINI = 'YES',
            VAL = 0) for reg in outputs]

    UnsetDevice()
    return inregs, outregs



# ----------------------------------------------------------------------
#
# Support routines for the three actuator types below.


# Pressure sensor bit
def _Pressure(bit):
    return bit.bi('PRESSURE',
        ZNAM = 'Pressure low',
        ONAM = 'Ok',
        ZSV  = 'MAJOR')

# Switch sensor bit
def _Switch(bit, name, entity, state):
    return bit.bi(name,
        ZNAM = '%s not %s' % (entity, state),
        ONAM = '%s %s' % (entity, state))

def _Control(bit, name, zero='Off', one='On', omsl='supervisory'):
    return bit.bo(name,
        OMSL = omsl,
        ZNAM = zero,  ONAM = one, VAL  = 0,
        PINI = 'YES')

def _ShowIn(name, act_in, set):
    return records.calc(name,
        CALC = 'A + 2 * B',
        INPA = CP(act_in),
        INPB = CP(set))

def _ShowOut(name, act_out, set):
    return records.calc(name,
        CALC = 'A + 2 * (1 - B)',
        INPA = CP(act_out),
        INPB = CP(set))

def _CalcSelect(name, value, set, flnk):
    return records.calc(name,
        CALC = 'A = %d' % value,
        INPA = CP(set),
        FLNK = flnk)

# Every time this record is processed it increments.
def _Counter(state):
    last_state = records.longin('LASTSET', INP = state, PINI = 'YES')
    counter = records.calc('COUNT',
        CALC = 'A+(B#C)',
        INPB = state,
        INPC = last_state,
        FLNK = last_state)
    counter.INPA = counter

    add_autosave(counter, 'VAL')
    return counter

# Builds the reason translation code
def _Reason(stateMachine):
    return records.mbbi(
        'REASON',
        INP  = stateMachine.H,
        ZRVL = 0,  ZRST = '',
        ONVL = 1,  ONST = 'Not initialised',
        TWVL = 2,  TWST = 'Pressure low',
        THVL = 3,  THST = 'Move timed out',
        FRVL = 4,  FRST = 'No switches set',
        FVVL = 5,  FVST = 'Not in position',
        SXVL = 6,  SXST = 'Many switches')


# ----------------------------------------------------------------------
#
#  Simple two position actuators


# Single two position actuator: YAG or OTR screen
def _Single(name, BIT_IN, BIT_OUT, BIT_SET, pressure):
    # Input sensor bits
    act_in  = _Switch(BIT_IN,  'IN',  name, 'in')
    act_out = _Switch(BIT_OUT, 'OUT', name, 'out')
    # Output control bit: we count every state change.
    set = _Control(BIT_SET, 'SET', 'Out', name)
    set.FLNK = _Counter(set)
    # Status monitoring bit: this is managed by the single actuator
    # state machine which sets one of the four states we see here.  This is
    # then converted into a displayable status value.
    stateMachine = supportLib.ActuatorState(
        'STATE', MovementTimeout, act_out, act_in, 0, set, 0, pressure)
    status = records.mbbi('STATUS',
        INP = stateMachine,
        ZRVL = 0, ZRST = 'Fault', ZRSV = 'MAJOR',
        ONVL = 1, ONST = 'Out',
        TWVL = 2, TWST = 'Moving',
        THVL = 3, THST = '%s in' % name)
    stateMachine.FLNK = create_fanout('FAN', status, _Reason(stateMachine))

    # Encoding of switch monitors
    _ShowIn ('SWITCH:IN',  act_in,  set)
    _ShowOut('SWITCH:OUT', act_out, set)

    # The output control bit is needed for interlock control
    return (set, status)


def _MakeSingle(id, name, reg_in, reg_out):
    SetDevice(name, id)
    pressure = _Pressure(reg_in.bit(2))
    single = _Single(name,
        reg_in.bit(0), reg_in.bit(1), reg_out.bit(0), pressure)
    UnsetDevice()
    return ActuatorSet(single)

def OTR(id, reg_in, reg_out):
    return _MakeSingle(id, 'OTR', reg_in, reg_out)

def YAG(id, reg_in, reg_out):
    return _MakeSingle(id, 'YAG', reg_in, reg_out)


# This interlock record ensures that whenever from is set then to is cleared.
def _Interlock(name, input, output):
    records.calcout(name,
        INPA = CP(input),
        OOPT = 'When Non-zero',
        OUT  = PP(output),
        DOPT = 'Use OCAL',
        CALC = 'A',
        OCAL = 0)


# The YAGFC actuator is a rather odd special case design: there are actually
# two actuators, YAG and FC, but setting one in automatically forces the
# other one out.
def YAGFC(yagfcid, yagid, fcid, reg_in, reg_out):
    SetDevice('YAGFC', yagfcid)
    pressure = _Pressure(reg_in.bit(2))

    SetDevice('YAG', yagid)
    yag = setyag, yagStatus = _Single('YAG',
        reg_in.bit(0), reg_in.bit(1), reg_out.bit(0), pressure)
    SetDevice('FC', fcid)
    fc = setfc, fcStatus = _Single('FC',
        reg_in.bit(3), reg_in.bit(4),
        reg_out.bit(1), pressure)

    # Now compute the interlocks: these ensure that we don't bring the FC
    # and the YAG in at the same time.
    SetDevice('YAGFC', yagfcid)
    _Interlock('IL:FCYAG', setfc, setyag)
    _Interlock('IL:YAGFC', setyag, setfc)
    UnsetDevice()

    # This actuator set has two components, YAG and FC.
    return ActuatorSet(yag, fc)



# Three position actuator carrying YAG and OTR screens
def OYAG(id, reg_in, reg_out):
    SetDevice('OYAG', id)

    BIT_A_IN     = reg_in.bit(0)             # Select OTR
    BIT_B_IN     = reg_in.bit(1)             # Select YAG
    BIT_OUT      = reg_in.bit(2)
    BIT_PRESSURE = reg_in.bit(3)
    BIT_SET_A    = reg_out.bit(0)            # Sense OTR in
    BIT_SET_B    = reg_out.bit(1)            # Sense YAG in

    # Input sensor bits
    out    = _Switch(BIT_OUT,  'OUT', 'OYAG', 'out')
    otr_in = _Switch(BIT_A_IN, 'OTR', 'OTR', 'in')
    yag_in = _Switch(BIT_B_IN, 'YAG', 'YAG', 'in')
    pressure = _Pressure(BIT_PRESSURE)
    # The two output control bits
    set_otr = _Control(BIT_SET_A, 'SETOTR', omsl='closed_loop')
    set_yag = _Control(BIT_SET_B, 'SETYAG', omsl='closed_loop')

    # Selector and output to control bits
    select = records.mbbo('SET',
        ZRVL = 0, ZRST = 'Out',
        ONVL = 1, ONST = 'YAG',
        TWVL = 2, TWST = 'OTR')
    select.FLNK = _Counter(select)
    calc_yag = _CalcSelect('CALC_YAG', 1, select, set_yag)
    calc_otr = _CalcSelect('CALC_OTR', 2, select, set_otr)
    set_otr.DOL = calc_otr
    set_yag.DOL = calc_yag

    # Compute the status by monitoring the status bits.
    stateMachine = supportLib.ActuatorState(
        'STATE', MovementTimeout,
        out, yag_in, otr_in, set_yag, set_otr, pressure)
    status = records.mbbi('STATUS',
        INP  = stateMachine,
        ZRVL = 0, ZRST = 'Fault', ZRSV = 'MAJOR',
        ONVL = 1, ONST = 'Out',
        TWVL = 2, TWST = 'Moving',
        THVL = 3, THST = 'YAG in',
        FRVL = 4, FRST = 'OTR in')
    stateMachine.FLNK = create_fanout('FAN', status, _Reason(stateMachine))

    UnsetDevice()

    # The associated actuator set is just the single actuator.
    return ActuatorSet((select, status))
