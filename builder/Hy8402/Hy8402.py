from epicsdbbuilder import records
from builder.record_factory import RecordFactory
from builder.ipac import IpDevice
from builder.asyn import Asyn

# Digital to Analogue convert (DAC)
class Hy8402(IpDevice, Asyn):
    DbdDir = 'Hy8402ip/4-13/'
    DbdFileList = ['Hy8402ip', 'funcgenRecord']

    def __init__(self, carrier, ipslot):
        super().__init__(carrier, ipslot, None)

    def channel(self, channel):
        return _DACchannel(self, channel)

# A single DAC channel on a DAC.  This class remembers all the information
# required to create records to read from the adc
class _DACchannel:
    def __init__(self, dac, channel):
        assert 0 <= channel  and  channel < 16, 'Channel out of range'
        address = '#C%d S%d @' % (dac.cardid, channel)
        self.ao = RecordFactory(records.ao, 'Hy8402ip', 'OUT', address)
