# Fan monitoring template
from epicsdbbuilder import records, MS, CP

from DLSRecordName import SetDevice, UnsetDevice

def FanMonitor(id, register):
    SetDevice('FANC', id)
    # There are four bits being monitored:
    #   Thermistor fail
    #   Temperature fail
    #   Fan fail
    #   Supply fail
    # Each bit is 1 in the normal operation state, 0 in the fail state.
    monitoredBits = [
        ('THERM',  'Thermistor status'),
        ('TEMP',   'Temperature status'),
        ('FAN',    'Fan status'),
        ('SUPPLY', 'Power supply status')]
    bits = []
    for i, (name, description) in enumerate(monitoredBits):
        bits.append(register.bit(i).bi(name,
            SCAN = '1 second',
            DESC = description,
            ZNAM = 'Fault',
            ONAM = 'Ok',
            ZSV  = 'MAJOR',
            OSV  = 'NO_ALARM'))

    # Accumulate all the fan status bits into a single master bit.
    calc_sta = records.calc('CALC-STA',
        CALC = 'A&B&C&D',
        INPA = MS(bits[0]),     INPB = MS(bits[1]),
        INPC = MS(bits[2]),     INPD = MS(bits[3]))
    for bit in bits:
        bit.FLNK = calc_sta
    records.bi('STA',
        DESC = 'Fan rack status',
        INP  = CP(MS(calc_sta)),
        ZNAM = 'Fault',
        ONAM = 'Ok')

    UnsetDevice()
