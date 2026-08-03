from builder.device import Device
from builder.modules.ipac.Carrier import IpDevice

class DLS8515(IpDevice):
    '''Configure a Hy8515 ip module for RS232 serial communication'''
    DbdDir = 'DLS8515/0-11/'
    DbdFileList = ['DLS8515']

    def __init__(self, carrier, ipslot, prefix="ty"):
        self.prefix = prefix
        super().__init__(carrier, ipslot, None)

    def channel(self, *pargs, **kargs):
        return DLS8515channel(self, *pargs, **kargs)


class DLS8516(DLS8515):
    '''Configure a Hy8516 ip module for RS422/RS485 serial communication'''

    def channel(self, *pargs, **kargs):
        return DLS8516channel(self, *pargs, **kargs)


class DLS8515channel(Device):
    '''Setup a single channel on a DLS8515 for RS232 serial communication'''
    # TODO Are most of these parameters used anymore with the removal of initialisation functions?
    def __init__(self, card, channel,
                 baud = 9600,
                 data = 8,
                 parity = 'N',
                 stop = 1,
                 flow = 'N'):

        super().__init__()
        assert channel in range(8), 'Channel out of range'
        self.channel = channel
        self.baud = baud
        self.data = data
        self.parity = parity
        self.stop = stop
        self.flow = flow
        self.device = '/ty/%d/%d' % (card.cardid, channel)

    # Returns the associated device name.
    def DeviceName(self):
        return self.device

class DLS8516channel(DLS8515channel):
    '''Setup a single channel on a DLS8516 for RS422/RS485 serial
    communication'''
    def __init__(self, card, channel, delay = 0, fullduplex = False, **args):
        super().__init__(card, channel, **args)
        assert delay in range(16), 'Delay out of range'
        self.delay = delay
        self.fullduplex = fullduplex
