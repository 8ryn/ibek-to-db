# Implementation of BR and SR DCCT.

# Parametric Current Transformers (PCT or DCCT)
#   Two types of readout: booster ring has filtering and noise baseline
#   subtraction; storage ring has averaging and derivative calculation.


from epicsdbbuilder import records, ImportRecord, create_fanout, PP, LookupRecord

from builder.DLSRecordName import SetDevice, UnsetDevice

from builder.modules.diagTools import resample
from builder.autosave_helper import add_autosave


# Nominal RF frequency: 60 cm per bucket.  We actually operate at a slightly
# different frequency, of course, which can be read from LI-RF-MOSC-01:FREQ,
# but the difference is no more than a few parts per million.
F_RF = 499654097        # 60 cm

BR_BUNCHES = 264        # 158.4 m
SR_BUNCHES = 936        # 561.6 m

# Conversion factors to convert stored mA in booster and storage rings into
# stored nC.  The revolution time is basically _BUNCHES / F_RF, and we have to
# scale mA to nC, hence the factor 1e6.
SR_MA_TO_NC = 1e6 * SR_BUNCHES / F_RF       # 1.87 us (534 kHz)
BR_MA_TO_NC = 1e6 * BR_BUNCHES / F_RF       #  523 ns (1.89 MHz)



# This routine builds the core records used to compute the DCCT reading.
# This calculation proceeds as follows:
#
#   1. The raw waveform is captured at 100kHz sample rate into the WAVEFORM
#      ai record.  This is either triggered on interrupt (for BR) or polled
#      (on SR), as controlled by the scan parameter.  A small sub-waveform
#      (small enough for EPICS13 transport) is also captured and set aside
#      into FULLRES.
#
#   2. The raw waveform is resampled (by a factor of 50:1) down to a sample
#      rate of 2kHz.  This also has the useful side effect of filtering out
#      unwanted high frequency components present in the outputs of both
#      DCCTs.  The output is in the record RSAMPLE.
#
#   3. The resampled waveform is scaled to convert volts read into mA of beam
#      current, and a baseline correction is made.  For historical reasons
#      the output at this stage (which is shown on various displays) is
#      called SMOOTH.
#
#   4. The waveform is averaged.  For BR only the first 100ms is averaged
#      (normally the beam is extracted after this point), while for SR the
#      entire waveform is averaged.  This is output as both AVERAGE and
#      SIGNAL.
#
#   5. A lifetime accumulated current is recorded in TOTAL.  This record is
#      both autosaved and archived.
#
# This routine returns a list of all records which need to be scanned, in
# sequence.
def _DCCT_core(
        adc,                    # Source of sampled waveform
        event,                  # Event source for timestamping result
        scan,                   # Scan mode: passive or I/O
        ScalingFactor,          # Conversion factor volts to mA
        MaxCurrent,             # Maximum expected current (for HOPR field)
        CaptureTime,            # Time in seconds to capture

        # The raw 100kHz sampled waveform is decimated down by a factor of 50
        # or 25:1.  This both removes undesirable high frequency components
        # from the DCCT output and reduces the volume of data to a manageable
        # amount.
        ResampleFilter,         # Filter to be used
        FilterLength,           # Length of filter
        DecimationFactor,       # Decimation factor to use when reducing data
        BunchCount,             # RF bunches per revolution
        zeroPointHook,          # Hook routine for zero point calculation

        AverageTime = None      # By default average entire captured length
    ):

    # We run the ADC at 100kHz to reduce noise by avoiding aliasing of high
    # frequency noise.
    SampleFrequency = 100000
    SamplesPerSecond = SampleFrequency / DecimationFactor

    # Compute the resampled filter length from the requested ScanPeriod, and
    # compute the raw waveform capture length taking the filter length into
    # account.
    ResampledLength = int(SamplesPerSecond * CaptureTime)
    # The raw capture length needs to take account of ResampledLength samples
    # taken at DecimationFactor intervals (thus (RL-1)*DF+1 points) plus
    # enough points either end for the filter.  So long as the filter is
    # accurate, the following number is correct.
    RawLength = DecimationFactor * (ResampledLength - 1) + FilterLength
    if AverageTime is None:
        AverageTime = CaptureTime
        AverageLength = ResampledLength
    else:
        AverageLength = int(SamplesPerSecond * AverageTime)

    # Initialise the resampling filter.
    filter = resample.ReadFile().ReadFileWaveform(
        'FILTER', ResampleFilter, FilterLength)

    # First capture the raw waveform.
    waveform = adc.waveform('WAVEFORM',
        SCAN = scan, FTVL = 'FLOAT', NELM = RawLength, offset = 0)

    # Reduce the sampled data by the given decimation factor and high pass
    # filter it, reducing the long waveform to a manageable size
    reduce = resample.ResampleWaveform(
        'RESAMPLE', waveform, filter, DecimationFactor, ResampledLength)


    # On demand capture a zero point baseline by taking an average of the
    # entire waveform.  This will only be captured when deliberately
    # triggered, and is used to compensate for zero point drift of the DCCT.
    zeroPoint = resample.AverageWaveform('ZERO', reduce.VALA, ResampledLength)
    add_autosave(zeroPoint, 'VALA')

    zeroReference, zeroRecords = zeroPointHook(
        zeroPoint, reduce.VALA, ResampledLength)
    baseline = resample.FoldWaveform('BASELINE',
        zeroReference, 1, 0, 1, 0, ResampledLength, PINI = 'YES')
    zeroRecords.append(baseline)

    # Subtract the baseline to produce a zero corrected signal
    zeroCorrected = resample.SubtractWaveform(
        'CORRECTED', reduce.VALA, baseline.VALA, ResampledLength)

    # Scale the resampled and zero corrected waveform to convert volts into mA
    # with the appropriate scaling factor.
    scale = records.ai('SCALE', VAL = ScalingFactor, PREC = 1, EGU = 'mA/V')
    rescale = resample.ScaleWaveform('SMOOTH',
        zeroCorrected.VALA, scale, ResampledLength)

    # Compute the average current over the selected averaging period and
    # accumulate an integrated total current
    average = resample.AverageWaveform('AVERAGE', rescale.VALA, AverageLength)
    # The SIGNAL record is really just the same data as AVERAGE.VALA, but
    # with a more convenient name and with proper range settings and units.
    signal = records.ai('SIGNAL',
        DTYP = 'Soft Channel',
        INP  = average.VALA,
        TSE  = event.event,
        MDEL = -1,  ADEL = 0.001,       # Update on 1uA change
        LOPR = 0,   HOPR = MaxCurrent,
        PREC = 3,   EGU  = 'mA')

    # From the signal compute the associated stored charge in nC: simply
    # divide by revolution frequency.  The signal is in mA and the charge in
    # nC, so we need to scale the result accordingly: the revolution
    # frequency is in MHz!
    RevolutionFrequency = 1e-6 * F_RF / BunchCount
    charge = records.calc('CHARGE',
        CALC = 'A/B',
        INPA = average.VALA,
        INPB = RevolutionFrequency,
        TSE  = event.event,
        MDEL = -1,
        LOPR = 0,   HOPR = MaxCurrent / RevolutionFrequency,
        PREC = 3,   EGU  = 'nC')

    # Only accumulate current if current reading is greater than a given
    # threshold.
    total = records.calc('TOTAL',
        CALC = 'B>C?A+B*D:A',
        INPB = average.VALA,
        INPC = 0.05,                    # Threshold of 50 uA
        INPD = AverageTime * 1e-3 / 3600,    # Convert mA to Ah
        TSE  = event.event,
        ADEL = 1e-4,                    # Update on 0.36As change
        PREC = 4,  EGU  = 'Ah')
    total.INPA = total
    add_autosave(total, 'VAL')

    # Finally generate a time base waveform in milliseconds.  This is used to
    # label the graph of SMOOTH.VALA against time.
    resample.RampWaveform('TIMEBASE',
        ResampledLength, 0.0, 1000 * CaptureTime, PINI = 'YES')


    # Return a list of all the records that need to be scanned, in sequence.
    # Return the waveform record separately, as it may need special treatment
    # as the source of events.  Also return a copy of the signal in case it
    # is wanted for separate processing.
    return waveform, signal, \
        [reduce] + zeroRecords + [zeroCorrected, rescale,
         average, signal, charge, total]



# The Booster DCCT is designed to run with a 5Hz cycle with 100ms of booster
# ramp and 100ms of recovery time.  As this particular DCCT is rather noisy,
# and in particular has quite a lot of hum, we do quite a lot of signal
# processing:  a low pass filter removes 7kHz noise from the electronics,
# and we use baseline subtraction to remove the hum.  The booster recovery
# time provides a nice source of baseline.
def BR(device, id, event, adc, filter, scaling):
    DecimationFactor = 25       # Reduce 100kHz samples to 4kHz rate

    # Use sophisticated zero point.  If the extractor is enabled then use the
    # latter part of the booster ramp as the zero reference, otherwise use
    # the stored zero point.
    def zeroPointHook(zeroPoint, waveform, length):
        extractor = ImportRecord('LI-TI-MTGEN-01:BRPREX-MODE')

        # Average the record starting from 105ms to get the post extract zero
        # point.
        offset = int(105 * 100 / DecimationFactor)
        extractedZeroPoint = resample.AverageWaveform('ZERO-EXTR',
            waveform, offset = offset, length = length - offset)

        # Multiplex between the fixed zero point and the post extract zero
        # depending on the value of the extractor.
        #     If the extractor is zero then extraction is disabled and we
        # should return the static stored zero point; otherwise return the
        # dynamic extracted zero point.
        zeroMux = records.calc('ZERO-MUX',
            CALC = 'A=0?B:C',
            INPA = extractor,
            INPB = zeroPoint.VALA,
            INPC = extractedZeroPoint.VALA)

        # We want to always process the zero point and MUX records
        return zeroMux, [extractedZeroPoint, zeroMux]

    SetDevice(device, id)

    # The ScanPeriod here determines the waveform length.  We want in fact
    # the waveform length to cover strictly less than the scan period: this
    # is necessary to allow time for the waveform capture ADC to rearm.
    waveform, current, core_records = _DCCT_core(adc, event,
        scan = 'I/O Intr',      # Triggered from timing system at 5Hz
        ScalingFactor = scaling,
        MaxCurrent = 10,        # 10 mA full scale
        CaptureTime = 0.18,     # Nearly but not quite 200ms
        ResampleFilter = filter,  FilterLength = 1001,
        DecimationFactor = DecimationFactor,    # 25:1 filter
        BunchCount = BR_BUNCHES, # 264 bunches per booster revolution
        zeroPointHook = zeroPointHook,
        AverageTime = 0.1)      # Average over the boost time, only

    waveform.FLNK = create_fanout('FANOUT', *core_records)

    UnsetDevice()


# Computes the age of the current waveform since a significant up-tick in
# current was seen.
def _Age(recordset, signal, threshold, max_age):
    # The logic here is reasonably straightforward.  LAST records the previous
    # signal (which we ensure by processing it *after* age).  The logic is
    # then: if signal-LAST>threshold reset the age (the signal is growing
    # fast enough to represent injection), otherwise allow age to grow (up to
    # max_age).
    last_signal = records.ai('LAST',
        INP  = signal,
        VAL  = 0,   PINI = 'YES')
    age = records.calc('AGE',
        CALC = 'A-B>C?0:E>=D?D:E+1',
        INPA = signal,
        INPB = last_signal,
        INPC = threshold,
        INPD = max_age)
    age.INPE = age

    recordset.extend([age, last_signal])
    return age


# Computes the derivative with the given number of points of the history
def _Derivative(recordset, ScanPeriod, Duration, History, HistoryLength, Age):
    points = int(Duration / ScanPeriod)
    # Compute the raw slope of the history display.  The units here are mA
    # per ScanPeriod.
    rawslope = resample.WaveformSlope(
        'RAW%d' % Duration, History, points, HistoryLength - points)
    # Now convert mA per ScanPeriod into mA/s, with the appropriate sign.
    slope = records.calc('SLOPE%d' % Duration,
        CALC = 'A/B',
        INPA = rawslope.VALA,
        INPB = ScanPeriod,
        PREC = 3,  EGU = 'mA/s')
    average = resample.AverageWaveform(
        'AVG%d' % Duration, History, points, HistoryLength - points)

    # Estimate the lifetime as SIGNAL/SLOPE.  The signal is in units of mA
    # and the slope in mA/s.  We scale the output lifetime to hours.
    # The lifetime is only calculated if all of the following three
    # conditions are satisfied:
    #   (B<-C)  The current slope is negative with magnitude at least 1nA/s
    #   (G>D)   The current throughout the window is at least 0.1mA
    #   (E>=F)  No injection has been observed in the current window.
    lifetime = records.calc('LIFE%d' % Duration,
        CALC = '(B<-C&&G>D&&E>=F)?-A/(B*3600):0',
        INPA = average.VALA,    # Current current
        INPB = slope,           # Computed derivative
        INPC = 1e-6,            # Slope threshold
        INPD = 0.1,             # Current threshold
        INPE = Age,             # Age of current waveform
        INPF = points,          # Age threshold
        INPG = average.VALB,    # Minimum current in current window
        ADEL = 0.01,    MDEL = -1,
        LOPR = 0,       HOPR = 20,
        PREC = 2,       EGU = 'h')
    condition = records.calc('COND%d' % Duration,
        CALC = 'A*B',
        INPA = lifetime,
        INPB = average.VALA,
        ADEL = 1,       MDEL = -1,
        PREC = 0,       EGU  = 'mAh')

    recordset.extend(
        [rawslope, slope, average, lifetime, condition])
    return slope, lifetime, condition



# The long history requires special treatment.  We're pushing the waveform
# length limits of EPICS 3.13 at this point.
def _LongHistory(recordset, signal, ScanPeriod, age):
    # Compute an ultra-long history with 20 minutes worth of points.  We'll
    # use this for the published lifetime, at least for now.
    longDuration = 60 * 20      # 20 minutes(!)
    longHistoryLength = int(longDuration / ScanPeriod)
    longHistory = resample.History('HIST1200', longHistoryLength, signal)

    # Unfortunately the long history buffer is too long for users to display:
    # this is an EPICS 3.13 channel access limit.  So resample the waveform
    # down to one that's manageable.
    filter_2_1 = resample.ReadFile().ReadFileWaveform(
        'FILTER2_1', 'sr-filter-2-1', 2)
    longHistoryResampled = resample.ResampleWaveform(
        'LONGHIST', longHistory, filter_2_1, 2, int(longHistoryLength/2))
    resample.RampWaveform('LONGTIME',
        int(longHistoryLength/2), 0.0, longDuration / 60, PINI = 'YES')

    recordset.extend([longHistory, longHistoryResampled])
    return _Derivative(recordset,
        ScanPeriod, longDuration, longHistory, longHistoryLength, age)


# Storage ring DCCT
#
# Here are the requirements for integrated current:
#   1 - Total charge circulated in the last ramp (5Hz updated)
#   2 - Accumulate over 10 seconds
#   3 - Long term accumulation of lifetime integrated charge in Ah.
# (3) needs to be preserved over reboots
# Publish lifetime integrated charge as:
#   - Two integer PVs (?) or maybe a 2 point waveform in, eg, mC
#   - An floating point value for convenience in Ah.
# Requirements:
#   1. Resolution at least 1e-6 Ampere Hours (Ah)
#   2. Total more that 200,000 Ah.
def SR(id, adc, event):
    # Use simple zero point behaviour
    def zeroPointHook(zeroPoint, *_): return zeroPoint.VALA, []

    SetDevice('DCCT', id)

    # Some basic defining constants
    ScanPeriod = 0.2                # Derived scan frequency
    HistoryPeriod = 2               # Length of history in minutes

    # Create the SIGNAL and TOTAL records.
    # The resampling filter used for the SR DCCT is a 501 point flattop
    # filter.  This provides low pass filtering suitable for 50:1 decimation
    # without too much ringing in the impulse response.  For historical
    # reasons the filter is padded out to 1001 points.
    waveform, signal, core_records = _DCCT_core(adc, event,
        scan = 'Passive',           # Triggered from soft event TICK record.
        ScalingFactor = 200.0,      # 200 mA per Volt
        MaxCurrent = 500,           # 0.5A full scale
        CaptureTime = ScanPeriod,   # Scan every 400ms, 2.5Hz.
        ResampleFilter = 'sr-filter-50-1',  FilterLength = 1001,
        DecimationFactor = 50,      # 50:1 filter
        BunchCount = SR_BUNCHES,    # 936 bunches per storage ring revolution
        zeroPointHook = zeroPointHook)

    # Record a history of the last HistoryPeriod minutes of reading
    HistoryLength = int(HistoryPeriod * 60 / ScanPeriod)
    history = resample.History('HISTORY', HistoryLength, signal)
    # Plus a baseline in seconds for the history plot
    resample.RampWaveform('HISTTIME',
        HistoryLength, 0.0, 60 * HistoryPeriod, PINI = 'YES')

    lifetime_records = []
    age = _Age(lifetime_records, signal, 0.1, 10000000)

    for duration in (2, 10, 30, 60, 120):
        _Derivative(lifetime_records,
            ScanPeriod, duration, history, HistoryLength, age)

    # Compute an ultra-long history with 20 minutes worth of points.  We'll
    # use this for the published lifetime.
    slopeN, lifetimeN, condition = \
        _LongHistory(lifetime_records, signal, ScanPeriod, age)

    # Finally publish the 20min slope, lifetime and condition values with
    # their canonical names
    slope = records.ai('SLOPE',
        INP  = slopeN,
        PREC = 3,       EGU = 'mA/s')
    lifetime = records.ai('LIFETIME',
        INP  = lifetimeN,
        ADEL = 0.01,    MDEL = -1,
        LOPR = 0,       HOPR = 20,
        PREC = 2,       EGU  = 'h')
    condition = records.ai('CONDITION',
        INP  = condition,
        ADEL = 1,   MDEL = -1,
        PREC = 0,   EGU  = 'mAh')


    # Propogate updates through all the records as required from the
    # pre-extract soft event.  Program this to be triggered on every
    # injection event.
    record_list = \
        [waveform] + core_records + \
        [history] + lifetime_records + \
        [slope, lifetime, condition]
    # DCCT processing is triggered on the LINAC_HBT trigger, as this is one
    # of the few events that is *always* active, but we delay the processing
    # by 100ms so that we capture the signal level between injections.
    event.Bind(records.seq('TICK',
        SELM = 'All',
        DLY1 = 0.1,
        LNK1 = PP(create_fanout('FANOUT', *record_list))))

    # Create compatibility aliases so that PVs pointing to SR21 don't break.
    LookupRecord('TOTAL'   ).add_alias('SR21C-DI-DCCT-01:TOTAL')
    LookupRecord('SIGNAL'  ).add_alias('SR21C-DI-DCCT-01:SIGNAL')
    LookupRecord('LIFETIME').add_alias('SR21C-DI-DCCT-01:LIFETIME')

    UnsetDevice()
