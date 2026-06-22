from epicsdbbuilder import records
from record_factory import RecordFactory

from builder.ipac import IpDevice


# Helper routine for consuming optional parameters.
def _ReadField(fields, key, param):
    result = ''
    if key in fields:
        result = ' %s=%d' % (param, fields[key])
        del fields[key]
    return result



class Hy8401(IpDevice):
    '''Hytec 8401 Analogue to Digital Converter (ADC).'''
    DbdDir = 'Hy8401ip/3-21/'
    DbdFileList = ['Hy8401ip']

    def __init__(self, carrier, ipslot, cardid=None):

        super().__init__(carrier, ipslot, cardid)

        address = '#C%d S0 @' % self.cardid
        self.bi = RecordFactory(records.bi, 'Hy8401ip', 'INP', address + 'MIS')
        self.bo = RecordFactory(
            records.bo, 'Hy8401ip', 'OUT', self.__bo_address)
        self.longin = RecordFactory(records.longin, 'Hy8401ip', 'INP', address)
        self.longout = RecordFactory(
            records.longout, 'Hy8401ip', 'OUT', address)

    def channel(self, channel):
        return _ADCchannel(self, channel)

    def __bo_address(self, fields):
        mode = fields.pop('mode', '')
        assert mode in ['', 'ST', 'XC', 'ET', 'EII'], 'Invalid control mode'
        return '#C%d S0 @%s' % (self.cardid, mode)


# A single ADC channel on an ADC.  This class remembers all the information
# required to create records to read from the adc
class _ADCchannel:
    def __init__(self, adc, channel):
        assert 0 <= channel  and  channel < 8, 'Channel out of range'
        self.adc = adc
        self.card = adc.cardid
        self.channel = channel

        self.ai = RecordFactory(
            records.ai, 'Hy8401ip', 'INP', self._ai_address)
        self.waveform = RecordFactory(
            records.waveform, 'Hy8401ip', 'INP', self._waveform_address)

    def _ai_address(self, fields):
        params = \
            _ReadField(fields, 'offset', 'OFFSET') + \
            _ReadField(fields, 'mean', 'MEAN')
        return '#C%d S%d @%s' % (self.adc.cardid, self.channel, params)

    def _waveform_address(self, fields):
        params = _ReadField(fields, 'offset', 'OFFSET')
        return '#C%d S%d @%s' % (self.adc.cardid, self.channel, params)
