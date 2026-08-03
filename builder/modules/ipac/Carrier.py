from builder.device import Device

# Base class for IP carrier card: both the 8001 and 8002 can act as IP
# carrier cards (though the 8001 only supports slots A and B).
class IpCarrier(Device):
    '''Support for IP carrier cards.'''

    DbdDir = 'ipac/2-8dls4-8-1/'
    DbdFileList = ['drvIpac']

    def __init__(self, slot, ip_support=True):
        super().__init__()

        self.slot = slot
        self.IPACid = 'IPAC%d' % slot
        # Record whether this instance actually supports IP cards
        self.ip_support = ip_support

class IpDevice(Device): #Have kept this for now, have not yet worked out if necessary for only producing db files.
    '''All the IP cards installed in a carrier card should be declared as
    sub-classes of this class.'''

    DbdBaseDir = '/dls_sw/prod/R3.14.12.7/support/'
    DbdDir = 'ipac/2-8dls4-8-1/'
    DbdFileList = ['drvIpac']

    def __init__(self, carrier: IpCarrier, ipslot, cardid=None):
        '''Every IP device is attached to a specific carrier card in a
        specified ipslot.  By default an EPICS card id and one interrupt
        are allocated.'''

        super().__init__()

        assert 0 <= ipslot < carrier.MaxIpSlots, 'Invalid IP slot: %d' % ipslot
        assert carrier.ip_support, 'Carrier card not configured for IP cards'

        # The standard algorithm for assigning card identifers is used.  This
        # can be overridden by the caller, but shouldn't normally be.
        if cardid is None:
            cardid = 10 * carrier.slot + ipslot
        self.IPACid = carrier.IPACid
        self.ipslot = ipslot
        self.cardid = cardid
        self.carrier = carrier
