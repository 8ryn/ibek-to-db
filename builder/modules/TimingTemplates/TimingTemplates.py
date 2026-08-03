from builder.template import Substitution
from builder.device import Device


__all__ = ['MonitorEvent', 'EvrAlive']

class TimingTemplates(Substitution):
    TemplateDir = "TimingTemplates/6-11"


# Depends on EventReceiver (er, erevent)
class BL_EVR_PMC(TimingTemplates, Device):
    TemplateFile = 'BL-EVR-PMC.template'
    LibFileList = ['timingfuncs']
    DbdDir = 'TimingTemplates/6-11'
    DbdFileList = ['TimingTemplates']

class BL_EVR_PMC_disable_ch0(TimingTemplates, Device):
    TemplateFile = 'BL-EVR-PMC_disable_ch0.template'
    LibFileList = ['timingfuncs']
    DbdDir = 'TimingTemplates/6-11'
    DbdFileList = ['TimingTemplates']

# Depends on EventReceiver (erevent)
class decode(TimingTemplates):
    TemplateFile = 'decode.template'

class event_stats(TimingTemplates, Device):
    TemplateFile = 'event_stats.template'
    LibFileList = ['timingfuncs']
    DbdDir = 'TimingTemplates/6-11'
    DbdFileList = ['TimingTemplates']

class evr_alive(TimingTemplates):
    TemplateFile = 'evr_alive.template'

class defaultEVR(TimingTemplates):
    TemplateFile = 'defaultEVR.template'

class evr_usec_calc(TimingTemplates):
    TemplateFile = 'evr_usec_calc.template'

class offset(TimingTemplates):
    TemplateFile = 'offset.template'

class generalTimeTemplate(TimingTemplates):
    TemplateFile = 'generalTime.template'

# Templates for event statistics

def MonitorEvent(eventMap, **kargs):
    '''Monitors the event receiver event specified by eventMap.
    '''
    # "Official" event names as defined by Angelos
    EventNames = {
        0x20: 'TZERO',      0x21: 'LB0DITRG',
        0x24: 'LINACPRE',   0x25: 'LINACHBT',
        0x26: 'LBDITRG',    0x2A: 'BRHWTRG',
        0x2C: 'BRINJ',      0x30: 'BRPREXTR',
        0x31: 'BSDITRG',    0x32: 'SRPREINJ',
        0x33: 'SRINJSEP',   0x3C: 'SRINJ',
        0x40: 'SRDITRG',    0x53: 'TOPUPON',
        0x54: 'TOPUPOFF',   0x5D: 'BEAMLOSS',
        0x5E: 'MPSTRIP',    0x76: 'FPINPUT',
        0x7D: 'TSRESET'}

    evnum = eventMap.SoftEvent(**kargs).event
    return event_stats(
        SYSTEM = eventMap.er.GetDevice(),
        EVNAME = EventNames[evnum],
        EVNUM  = evnum)


class EvrAlive(evr_alive):
    def __init__(self, er, **kargs):
        # Ensure that we receive a Linac heartbeat soft event.
        self.softEvent = \
            er.EventMap('LINAC-HBT', er.LINAC_HBT).SoftEvent(**kargs)
        super().__init__(device = er.GetDevice())
