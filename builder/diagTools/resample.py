# Interface to resample gensub library.  This includes a variety of general
# purpose signal processing tools as well as the core resample waveform
# function.

import os, os.path

from epicsdbbuilder import records
from builder.device import Device, autodepends


class resampleLib(Device):
    '''Base library implements all other functions defined in the resample
    module.'''
    DbdBaseDir = '/home/brw82791/epics/Diagnostics/'
    DbdDir = 'diagTools/'
    DbdFileList = ['diagToolsResample']



class ReadFile(resampleLib):
    '''Waveform records read from a file.'''

    def __init__(self, path='filters'):
        super().__init__()
        self.path = '/path/to/filters/in/genericIoc/'

    def ReadFileWaveform(self, name, filename, length):
        #This relies on filters being present in a defined directory in the generic IOC
        return records.waveform(name,
            DTYP = 'ReadFileWaveform',
            INP  = '@' + os.path.join(self.path, filename),
            FTVL = 'FLOAT',
            NELM = length)


@autodepends(resampleLib)
def History(name, length, input):
    '''Waveform which continously accumulates a memory of all updates of its
    input.  Index 0 is the oldest point, index length-1 the most recently
    read.'''
    return records.waveform(name,
        DTYP = 'History',
        INP  = input,
        FTVL = 'FLOAT',
        NELM = length)




# Factories for the various resample entities.  These all rely on the fact
# that creating a resampleLib instance will automatically ensure that genSub
# records become available!


@autodepends(resampleLib)
def ResampleWaveform(
    name, waveform, filter, interval, outputLength, offset=0):

    '''Using the given filter the input waveform is resampled at the specified
    interval to yield a waveform of the specified outputLength.'''
    return records.aSub(name,
        EFLG = 'ALWAYS',
        INAM = 'initResampleWaveform',
        SNAM = 'ResampleWaveform',
        INPA = waveform,
        INPB = filter,
        INPC = interval,    FTC  = 'LONG',
        INPD = offset,      FTD  = 'LONG',
        FTVA = 'FLOAT',
        NOVA = outputLength)



@autodepends(resampleLib)
def FoldWaveform(
        name, waveform, period, start, cycles, phase, outputLength, **fields):
    '''Computes the average of a periodic waveform.'''
    return records.aSub(name,
        EFLG = 'ALWAYS',
        INAM = 'initFoldWaveform',
        SNAM = 'FoldWaveform',
        INPA = waveform,
        INPB = period,  FTB  = 'LONG',
        INPC = start,   FTC  = 'LONG',
        INPD = cycles,  FTD  = 'LONG',
        INPE = phase,   FTE  = 'LONG',
        FTVA = 'FLOAT',
        NOVA = outputLength,
        **fields)



@autodepends(resampleLib)
def SubtractWaveform(name, waveformA, waveformB, outputLength):
    '''Computes the difference of two waveforms.'''
    return records.aSub(name,
        EFLG = 'ALWAYS',
        INAM = 'initSubtractWaveform',
        SNAM = 'SubtractWaveform',
        INPA = waveformA,
        INPB = waveformB,
        FTVA = 'FLOAT',
        NOVA = outputLength)


@autodepends(resampleLib)
def AverageWaveform(name, waveform, length, offset=0):
    '''Computes the average of a segment of a waveform record.  The arguments
    are:
        waveform  The waveform record to be averaged
        length    The length of segment over which to compute an average
        offset    The starting point of the segment to average (default =0).

    Some auxiliary statistics are also calculated at the same time:
        VALA      Average
        VALB      Minimum value
        VALC      Maximum value
    '''
    return records.aSub(name,
        EFLG = 'ALWAYS',
        INAM = 'initAverageWaveform',
        SNAM = 'AverageWaveform',
        INPA = waveform,
        INPB = offset,  FTB = 'LONG',
        INPC = length,  FTC = 'LONG',
        FTVA = 'FLOAT',
        FTVB = 'FLOAT',
        FTVC = 'FLOAT')

@autodepends(resampleLib)
def WaveformSlope(name, waveform, length, offset=0):
    '''Computes the slope of a segment of a waveform record.  The arguments
    are:
        waveform  The waveform record to be averaged
        length    The length of segment over which to compute an average
        offset    The starting point of the segment to compute the slope
    '''
    return records.aSub(name,
        EFLG = 'ALWAYS',
        INAM = 'initSlopeWaveform',
        SNAM = 'SlopeWaveform',
        INPA = waveform,
        INPB = offset,  FTB = 'LONG',
        INPC = length,  FTC = 'LONG',
        FTVA = 'FLOAT',
        FTVB = 'FLOAT')

@autodepends(resampleLib)
def ScaleWaveform(name, waveform, scale, outputLength):
    '''Rescales the waveform by the given scale factor.'''
    return records.aSub(name,
        EFLG = 'ALWAYS',
        INAM = 'initScaleWaveform',
        SNAM = 'ScaleWaveform',
        INPA = waveform,
        INPB = scale,   FTB  = 'DOUBLE',
        FTVA = 'FLOAT', NOVA = outputLength)

@autodepends(resampleLib)
def RampWaveform(name, length, start, finish, **fields):
    return records.aSub(name,
        EFLG = 'ALWAYS',
        INAM = 'initRampWaveform',
        SNAM = 'RampWaveform',
        INPA = start,   FTA  = 'DOUBLE',
        INPB = finish,  FTB  = 'DOUBLE',
        FTVA = 'FLOAT', NOVA = length,
        **fields)

@autodepends(resampleLib)
def DiffWaveform(name, waveform, inputLength, offset=0):
    '''Computes derivative of waveform.'''
    return records.aSub(name,
        EFLG = 'ALWAYS',
        INAM = 'initDiffWaveform',
        SNAM = 'DiffWaveform',
        INPA = waveform,
        INPB = offset,  FTB  = 'LONG',
        FTVA = 'FLOAT', NOVA = inputLength - 1)
