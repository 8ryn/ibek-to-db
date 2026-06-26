# Generic signal handling activities covering FC, PMT, ICT and DCCT.

from epicsdbbuilder import records, create_fanout, MS, PP
from builder.diagTools import resample
from builder.DLSRecordName import SetDevice, UnsetDevice



# ----------------------------------------------------------------------------
# Device support required for signal handling
# ----------------------------------------------------------------------------


# This routine creates the records required to extract an average from a
# waveform.  This is done as a cascade of three records, one to capture the
# raw waveform, one to compute the average, and one to do any post processing
# required for user presentation.  This last record is the one returned.
def MonitorSignal(adc,
    captureLength=None, captureOffset=0,
    averageLength=None, averageOffset=0, **args):

    # Assign default arguments and check for validity
    if captureLength is None:
        captureLength = adc.SampleSize()
    if averageLength is None:
        averageLength = captureLength
    assert 0 < captureLength and 0 <= captureOffset and \
           captureLength + captureOffset <= adc.SampleSize(), \
           'Invalid captured waveform length'
    assert 0 < averageLength and 0 <= averageOffset and \
           averageLength + averageOffset <= captureLength, \
           'Invalid averaged waveform length'

    # Capture the raw ADC signal into a waveform record.
    waveform = adc.waveform(
        'WAVEFORM',
        SCAN = 'I/O Intr',
        FTVL = 'FLOAT',
        NELM = captureLength,
        offset = captureOffset)

    # Compute the desired signal as the average of a sequence of interest.
    average = resample.AverageWaveform(
        'AVERAGE', waveform, averageLength, averageOffset)
    waveform.FLNK = average

    # Finally use an ai record to deliver the final result and allow any
    # desired scaling to be performed.
    result = records.ai('SIGNAL', INP = average.VALA, **args)
    average.FLNK = result

    return result





# ----------------------------------------------------------------------------
# Wall Current Monitor (WCM)
#   Simple signal readout of a pulse
# ----------------------------------------------------------------------------


def WCM(id, adc):
    SetDevice('WCM', id)

#    average = MonitorSignal(adc, EGU = 'nC', PREC = 4)
    records.stringin('SIGNAL', VAL = 'Disconnected', SEVR = 'INVALID')

    UnsetDevice()



# ----------------------------------------------------------------------------
# Faraday cups (FC)
#   Simple signal readout of a pulse
# ----------------------------------------------------------------------------


def FaradayCup(id, adc):
    SetDevice('FC', id)

    # The Faraday cup signal is in nano-columbs, though calibrating this is
    # going to be tricky.
#    average = MonitorSignal(adc, EGU = 'nC', PREC = 4)
    records.stringin('SIGNAL', VAL = 'Disconnected', SEVR = 'INVALID')

    UnsetDevice()



# ----------------------------------------------------------------------------
# Photomultiplier tubes (PMT)
#   Simple signal readout plus gain control with persistent settings
# ----------------------------------------------------------------------------

PMTsampleSize = 22
PMTmax = 1600               # 1.6 kV is the maximum safe PMT gain setting
PMT_initial_gain = 700      # 700 Volts is sufficient to see activity


def PMT(id, dac, adc):
    SetDevice('PMT', id)

    waveform = adc.waveform('WAVEFORM',
        SCAN = 'I/O Intr',
        FTVL = 'FLOAT',
        NELM = PMTsampleSize)

    # We look at two parts of the waveform: the first 10 points are the
    # baseline, and the last 10 points are the desired value.
    average  = resample.AverageWaveform('AVERAGE',  waveform, 10, 12)
    baseline = resample.AverageWaveform('BASELINE', waveform, 10, 0)
    signal = records.calc('SIGNAL',
        CALC = 'A-B',
        INPA = average.VALA,
        INPB = baseline.VALA,
        EGU  = 'AU',
        PREC = 3)

    # The 0dB point for the PMT signal is really very arbitrary.  The signal
    # from a PMT with no signal is very low, something in the region of
    # 0.3mV!  So we set this as our zero point.
    log = records.calc('LOG',
        CALC = '35+10*LOG(ABS(A)+1e-4)',
        LOPR = 0,    HOPR = 45,         # 0.3 mV to 10V
        HIGH = 15,   HSV  = 'MINOR',    # 10 mV
        HIHI = 30,   HHSV = 'MAJOR',    # 300 mV
        EGU  = 'dB', PREC = 0,
        INPA = signal)

    waveform.FLNK = create_fanout('FANOUT', average, baseline, signal, log)

    # Gain control for PMT.  Full scale on the DAC (10V) corresponds to
    # 1,600V inside the PMT itself.
    gain = dac.ao('GAIN',
        OMSL = 'supervisory',
        LINR = 'LINEAR',
        VAL  = PMT_initial_gain, PINI = 'YES',
        DRVL = 0,       DRVH = PMTmax,
        LOPR = 0,       HOPR = PMTmax,
        EGUL = -PMTmax, EGUF = PMTmax,
        EGU  = 'V',     PREC = 0)
    #gain.Autosave('VAL')

    # An editable description field for convenience
    records.stringin('LOCATION')
    #records.stringin('LOCATION').Autosave('VAL')

    UnsetDevice()


# ----------------------------------------------------------------------------
# Integrating Current Transformers (ICT)
#   Simple signal readout plus some calibration control records.
# ----------------------------------------------------------------------------


def ICT(id, event, adc, control, offset=0):
    SetDevice('ICT', id)

    # The ICT hardware integrates the beam current pulse and holds the
    # integrated value for 400 us.  Because of jitter between the 100kHz
    # ADC sampling clock and the master trigger (running at 5Hz) the two
    # ends of the hold time are a little unreliable, so we sample only 34
    # points.  The raw waveform is made available so that it can be examined
    # by the operator if required.
    waveform = adc.waveform('WAVEFORM',
        SCAN = 'I/O Intr', FTVL = 'FLOAT',  NELM = 80,  offset = offset)
    # Average the held value to get the basic reading, and also average the
    # baseline (after the held value returns to zero) to get the zero voltage
    # reading.
    average  = resample.AverageWaveform('AVERAGE',  waveform, 34, 5)
    baseline = resample.AverageWaveform('BASELINE', waveform, 34, 45)
    # If the input value is out of range then treat it as an error.  This
    # will be propagated to the calculated signal value.  Similarly we check
    # the baseline, which we treat as somewhat more serious: if this isn't
    # very close to zero then something is badly wrong!
    average_alarm = records.ai('AVG_ALARM',
        INP  = average.VALA,
        LOW  = -0.1,     HIGH = 8.1,     HYST = 0.1,
        HSV  = 'MINOR',  LSV  = 'MINOR')
    baseline_alarm = records.ai('BASE_ALARM',
        INP  = baseline.VALA,
        LOW  = -0.1,     HIGH = 0.1,     HYST = 0.05,
        HSV  = 'MAJOR',  LSV  = 'MAJOR')

    # The calibration control bits allow the ICT to be put into calibration
    # mode and some operational and calibration parameters to be set.  The
    # following bits can be controlled:
    #   0-2  Gain, from 6dB to 40dB
    #   3    Optionally invert output signal
    #   4    Optionally invert calibration signal
    #   5-6  Calibration charge, from 1nC to 1pC
    #   7    Enable calibration
    # The inversion bits are not used.

    # Gain control register.  We need to also feed this forward to the
    # readback register.  Note that the rather strange output values for
    # gains of 20 and 26 dB do indeed correspond to the hardware, and that
    # output value 3 is indeed missing (it is another way of generating a
    # gain of 26dB)!
    gain = control.register(0, 3).mbbo('SET_RANGE',
        PINI = 'YES',
        ZRVL = 0,  ZRST = '40 nC',      #  +6 dB
        ONVL = 1,  ONST = '20 nC',      # +12 dB
        TWVL = 2,  TWST = '10 nC',      # +18 dB
        THVL = 4,  THST = '8 nC',       # +20 dB
        FRVL = 5,  FRST = '4 nC',       # +26 dB
        FVVL = 6,  FVST = '2 nC',       # +32 dB
        SXVL = 7,  SXST = '0.8 nC')     # +40 dB
    #gain.Autosave1('VAL')
    # Calibration charge selection
    control.register(5, 2).mbbo('SET_CHARGE',
        VAL  = 0,  PINI = 'YES',
        ZRVL = 0,  ZRST = '10 nC',
        ONVL = 1,  ONST = '1 nC',
        TWVL = 2,  TWST = '100 pC',
        THVL = 3,  THST = '10 pC')
    # Calibration enable.  When calibration is set force an alarm on this bit:
    # this will be used to ensure that the operator doesn't accidentially use
    # calibration values!
    set_calibrate = control.bit(7).bo('CALIBRATE',
        VAL  = 0, PINI = 'YES',
        ZNAM = 'Normal',     ZSV  = 'NO_ALARM',
        ONAM = 'Calibrate',  OSV  = 'MAJOR')

    # Now convert the averaged signal into a properly calibrated beam charge.
    # Calibration values are determined by the selected gain and entries
    # must correspond with values in the gain record.
    calibration = records.sel('CONVERT',
        INPA = 5,    INPB = 2.5,   INPC = 1.25,  INPD = 1,
        INPE = 0.5,  INPF = 0.25,  INPG = 0.1,
        SELM = 'Specified',   NVL  = gain,
        EGU  = 'nC/V',        PREC = 2)
    gain.FLNK = calibration

    # The final signal picks up any alarm state on the underlying reading
    # and combines it with the calibration setting to produce an output in
    # nano-Coulombs.
    zero_offset = records.ao('OFFSET', PINI = 'YES', PREC = 3, VAL = 0)
    #zero_offset.Autosave('VAL')
    scaling = records.ao('SCALING', PINI = 'YES', PREC = 3, VAL = 1)
    #scaling.Autosave('VAL')

    signal = records.calc('SIGNAL',
        CALC = '(A-C-E)*B*F',
        INPA = MS(average_alarm),
        INPB = calibration,
        INPC = MS(baseline_alarm),
        INPD = MS(set_calibrate),
        INPE = zero_offset,
        INPF = scaling,
        TSE  = event.event,
        LOPR = 0,  HOPR = 40,  EGU  = 'nC',  PREC = 3)
    calibration.FLNK = signal

    # Tie everything together from the initial waveform: updates to the
    # waveform trigger everything else in turn.
    waveform.FLNK = create_fanout('FANOUT',
        average, average_alarm, baseline, baseline_alarm, signal)

    UnsetDevice()



# ----------------------------------------------------------------------------
# Simple RIM waveform support
# ----------------------------------------------------------------------------

def RIM_waveforms(adc, sample_count, scan):
    SetDevice('RIM', 1)

    # One waveform for each channel, each will be processed when ready
    waveforms = [
        adc.channel(i).waveform('CHAN%d' % (i + 1),
            FTVL = 'FLOAT', NELM = sample_count)
        for i in range(8)]
    wf_fan = create_fanout('FAN', *waveforms)

    # We use INPTR to monitor data capture into the 8401 waveform memory and set
    # OUTPTR to read out captured data when ready.
    inptr = adc.longin('INPTR', SCAN = scan)
    outptr = adc.longout('OUTPTR', VAL = 0, FLNK = wf_fan)

    # Only want to process records when inptr has advanced far enough, naively
    # we simply need to wait until
    #   inptr > outptr + sample_count
    # Alas in modulo arithmetic this is not so easy.
    check = records.calcout('CHECKPTR',
        INPA = inptr,
        INPB = outptr,
        INPC = sample_count,
        INPD = 65536,
        CALC = '(B+C-A+D)%D>D/2',   # Want A > B+C modulo D here
        OOPT = 'When Non-zero',
        DOPT = 'Use OCAL',
        OCAL = '(B+C)%D',
        OUT  = PP(outptr))
    inptr.FLNK = check

    UnsetDevice()
