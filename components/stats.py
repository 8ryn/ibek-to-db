# Simple aggregation of devIocStats status PVs

import epicsdbbuilder
from builder.DLSRecordName import SetDevice, UnsetDevice
from epicsdbbuilder import ImportRecord, recordnames

status_pvs = [
    'CA_CLNT_CNT',
    'CA_CONN_CNT',
    'SUSP_TASK_CNT',
    'IOC_CPU_LOAD',
    'FD_FREE',
]

def status(ioc_name):
    domain, area, component, id = ioc_name.split('-')
    SetDevice(component, int(id), domain, area)

    # Aggregate severity from the important devIocStats pv into a single :STA
    status_recs = [ImportRecord(recordnames.RecordName(pv)) for pv in status_pvs]
    # It turns out that all id==1 IOCs take their time from the EVR, and all
    # id==2 IOCs take their time from vxWorks's feeble approach to NTP.
    # Unfortunately this means that we can't realistically monitor the timing
    # error count for NTP based IOCs as their error counts are pretty well
    # always in error state.  On the other hand, for EVR based IOCs we most
    # definitely *do* want this extra status.
    if int(id) == 1:
        status_recs.append(ImportRecord(recordnames.RecordName(('GTIM_ERR_CNT'))))

    epicsdbbuilder.records.calc('STA',
        CALC = 0, DESC = 'Aggregate IOC status', SCAN = '1 second',
        **dict([
            ('INP' + c, epicsdbbuilder.MS(r))
            for c, r in zip ('ABCDEFGHIJKL', status_recs)]))

    # Poke the general time error counter reset 5 seconds after booting so that
    # we can ignore the burst of errors that invariably occurs during startup.
    epicsdbbuilder.records.seq('RESET:STA',
        PINI = 'YES', SELM = 'All',
        LNK1 = epicsdbbuilder.PP(ImportRecord(recordnames.RecordName(('GTIM_RESET')))),
        DLY1 = 10)

    UnsetDevice()
