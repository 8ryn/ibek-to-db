# PIN diode radiation detector support

from epicsdbbuilder import records, create_fanout
from builder.DLSRecordName import SetDevice, UnsetDevice
from builder.diagTools import resample

HISTORY_LENGTH = 60


def Log(step, name = 'LOG', prec = 0):
    return records.calc(name,
        CALC = 'A>0?10*LOG(A):0',   # Map invalid log values to 0dB
        MDEL = -1,
        LOPR = 0,    HOPR = 60,
        HIGH = 20,   HSV  = 'MINOR',
        HIHI = 40,   HHSV = 'MAJOR',
        EGU  = 'dB', PREC = prec,
        INPA = step)

# Creates one minute moving average of rate.
def MovingAverage(step):
    history = resample.History('HISTORY', HISTORY_LENGTH, step)
    average = resample.AverageWaveform('AVERAGE', history, HISTORY_LENGTH)
    step60 = records.calc('RATE60',
        CALC = 'A',
        INPA = average.VALA,
        PREC = 2)
    log60  = Log(step60, 'LOG60', 1)
    max60  = records.calc('MAX60',
        CALC = 'A',
        INPA = average.VALC)

    return [history, average, step60, log60, max60]


def PIN(id, counter):
    SetDevice('PIN', id)

    count = counter.ai('COUNT', SCAN = '1 second', PHAS = 0)
    last = records.ai('LAST', INP = count)
    step = records.calc('RATE',
        CALC = '((A&C)-(B&C))&C',
        INPA = count,
        INPB = last,
        INPC = 0x7FFFFFFF)
    log = Log(step)

    averages = MovingAverage(step)

    count.FLNK = create_fanout('FANOUT', step, last, log, *averages)

    counter.bo('ENABLE', PINI = 'YES')

    # An editable description field for convenience
    # TODO: Handle autosave
    #records.stringin('LOCATION').Autosave('VAL')
    records.stringin('LOCATION')

    UnsetDevice()
    return step


# Record to calculate the maximum of an array of four values.
def Max4(name, values):
    return records.calc(name,
        CALC = 'MAX(MAX(A,B),MAX(C,D))',
        INPA = values[0],     INPB = values[1],
        INPC = values[2],     INPD = values[3])


def PINs(counters):
    '''Constructs an array of 16 PIN devices together with an extra device
    (number 17) which summarises the maximum count.'''

    assert len(counters) == 16, 'Expecting 16 counters'

    pins = [PIN(i + 1, counter) for i, counter in enumerate(counters)]

    # Now compute the maximum count.  We put this onto PIN-17 for lack of a
    # better name.
    SetDevice('PIN', 17)

    # The maximum of 16 pins is caclulated as a cascade of four input MAX
    # calculation: this is to work around tedious constraints in the
    # functionality of the CALC record.
    maxes = [Max4('MAX%d' % i, pins[4*i:4*(i+1)]) for i in range(4)]
    max = Max4('RATE', maxes)
    log = Log(max)
    averages = MovingAverage(max)
    create_fanout('FANOUT', SCAN = '1 second', PHAS = 1,
        *maxes + [max, log] + averages)

    # We also put the reset function on this device, though in fact we use
    # one of the counters: any counter will do!
    counters[0].bo('RESET')

    UnsetDevice()
