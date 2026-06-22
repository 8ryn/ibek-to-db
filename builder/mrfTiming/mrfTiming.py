# Timing system

from record_factory import RecordFactory
from builder.device import Device
from DLSRecordName import SetDevice, UnsetDevice, GetDevice
from epicsdbbuilder import records

__all__ = ['EventReceiverVME', 'EventReceiverPMC', 'EventReceiver']



# This lookup table converts convenient names into front panel selection
# identifiers.  See the Timing Event System documentation for details and
# the description of the External Event Code Register (0x051) for the VME
# Event Receiver (VME-EVR-RF).
FPSLookup = dict(
    # Programmable Delayed Pulse outputs
    PDP0  = 0x00,  PDP1  = 0x01,  PDP2  = 0x02,  PDP3  = 0x03,
    # Trigger Event outputs
    TEV0  = 0x04,  TEV1  = 0x05,  TEV2  = 0x06,  TEV3  = 0x07,
    TEV4  = 0x08,  TEV5  = 0x09,  TEV6  = 0x0A,
    # Programmable Width Pulse outputs
    OTP0  = 0x0B,  OTP1  = 0x0C,  OTP2  = 0x0D,  OTP3  = 0x0E,
    OTP4  = 0x0F,  OTP5  = 0x10,  OTP6  = 0x11,  OTP7  = 0x12,
    OTP8  = 0x13,  OTP9  = 0x14,  OTP10 = 0x15,  OTP11 = 0x16,
    OTP12 = 0x17,  OTP13 = 0x18,
    # Latched outputs
    OTL0  = 0x19,  OTL1  = 0x1A,  OTL2  = 0x1B,  OTL3  = 0x1C,
    OTL4  = 0x1D,  OTL5  = 0x1E,  OTL6  = 0x1F,
    # Distributed Bus outputs
    DBUS0 = 0x20,  DBUS1 = 0x21,  DBUS2 = 0x22,  DBUS3 = 0x23,
    DBUS4 = 0x24,  DBUS5 = 0x25,  DBUS6 = 0x26,  DBUS7 = 0x27,
    # Prescalers
    PRES0 = 0x28,  PRES1 = 0x29,  PRES2 = 0x2A)


class _EventRecords:
    '''This class provides a mechanism for binding any record to the given
    EPICS event.'''
    def __init__(self, event):
        self.event = event

    def Bind(self, record, set_tse = True):
        '''This binds record to this event so that the record will process
        when the associated event triggers.'''
        record.SCAN = 'Event'
        record.EVNT = self.event
        record.TSE = self.event


# Support for handling a single event number.
class _EventMap:
    def __init__(self, er, name, event):
        assert 0 <= event < 256, 'Invalid event number'
        self.er = er
        self.name = name
        self.event = event
        self.__SoftEvent = None

        # Create the bare record, with all events disabled
        self.er.SetDevice()
        self.record = self.er.erevent(name,
            PINI = 'YES',
            ENAB = 'Enabled',
            VME  = 'Disabled',
            ENM  = event)
        self.er.UnsetDevice()
        for i in range(14):
            setattr(self.record, 'OUT%X' % i, 'Disabled')


    def Append(self, *enables):
        '''Extend the set of internal events triggered by this external
        event.'''
        for i in enables:
            assert 0 <= i < 14, 'Invalid MAP signal enabled'
            setattr(self.record, 'OUT%X' % i, 'Enabled')

    def Enable_field(self, event):
        '''Returns field corresponding to enable for corresponding event in
        this event map.'''
        return getattr(self.record, 'OUT%X' % event)

    def SoftEvent(self, name=None, epics_event=None, PRIO='HIGH', **kargs):
        '''Enables delivery of EPICS events for this external event.  The
        returned class can be used to bind records to this event.'''

        if not self.__SoftEvent:
            # If soft events have already been configured then we'll return
            # the work already done, otherwise configure it now.

            if name is None:  name = self.name + 'S'
            if epics_event is None:  epics_event = self.event

            # Enable delivery to EPICS of the event managed by this event map
            self.record.VME = 'Enabled'
            # Convert this hardware event into the appropriate internal EPICS
            # event.  By default the EPICS event number is the same as the
            # global event number.
            self.er.SetDevice()
            self.er.event(name,
                event = self.event,
                VAL = epics_event, PRIO = PRIO, **kargs)
            self.er.UnsetDevice()

            self.__SoftEvent = _EventRecords(epics_event)

        return self.__SoftEvent

    def Bind(self, record, set_tse = True, **kargs):
        self.SoftEvent(**kargs).Bind(record, set_tse)


class _EventReceiverCore(Device):
    DbdDir = 'mrfTiming/2-4-1dls10/'
    DbdFileList = ['mrfCommon', 'mrfEr', 'dlsTime']

    def __init__(self, cardid, priority):
        super().__init__()
        self.cardid = cardid
        self.priority = priority

        # Bind event receiver records to card.
        address = '#C%d S0 @' % cardid
        self.er = RecordFactory(
            records.er, 'MRF Event Receiver', 'OUT', address)
        self.erevent = RecordFactory(
            records.erevent, 'MRF Event Receiver', 'OUT', address)
        self.event = RecordFactory(
            records.event, 'MRF Event Receiver', 'INP', self.__event_address)

    # Helper routine for computing the address of an event record.  This
    # requires that an event field be included in the arguments.  We output
    # the event number in hex to be friendly to anyone reading the database.
    def __event_address(self, fields):
        event = fields.pop('event')
        address = '#C%d S%d @' % (self.cardid, event)
        fields['SCAN'] = 'I/O Intr'
        fields['TSE'] = event
        return address

class EventReceiverVME(_EventReceiverCore):
    def __init__(self,
            slot = 3, address = 0, intLevel = 5, priority = 10, cardid = None):
        if cardid is None:
            cardid = slot
        super().__init__(cardid, priority)


class EventReceiverPMC(_EventReceiverCore):
    def __init__(self, card_index = 0, priority = 10, cardid = None):
        if cardid is None:
            cardid = card_index
        super().__init__(cardid, priority)


# Timing system event receiver
class EventReceiver:
    def __init__(self, device, name = 'SET_HW', component = 'EVR', id = 1):
        super().__init__()

        # Pick up the record factories from the device.  That's all we
        # actually need from it.
        self.er      = device.er
        self.erevent = device.erevent
        self.event   = device.event

        self.__component = component
        self.__id = id
        self.__EventMap = {}

        # Create basic event receiver record with all fields initialised to
        # sensible disabled defaults.
        self.SetDevice()
        self.record = self.er(name, PINI = 'YES', ENAB = 'YES')
        self.UnsetDevice()

        # Disable all fields by default
        self.__Disabled('OT%XB', 8)     # Disable DBUS fields
        self.__Disabled('TRG%X', 7)     # Disable trigger events
        self.__Disabled('OTL%X', 7)     # Disable latched outputs
        self.__Disabled('OTP%X', 14)    # Disable programmable outputs
        self.__Disabled('DG%XE', 4)     # Disable basic programmable pulses
        self.__Disabled('FPS%X', 7, 0)  # Disable front panel outputs


    # The following methods are used to add event receiver definitions to the
    # event receiver.

    def EventMap(self, name, event, *enables):
        '''Add an event map to the table.  This maps a global event number
        into a list of MAP signals that will be pulsed when this event
        occurs.'''
        if event in self.__EventMap:
            # If this event has already been configured return the existing
            # event map.
            map = self.__EventMap[event]
        else:
            # For new events create a new event map
            map = _EventMap(self, name, event)
            self.__EventMap[event] = map

        map.Append(*enables)
        return map


    # Sets all fields matching pattern to given initial default value.
    def __Disabled(self, pattern, count, value='Disabled'):
        for i in range(count):
            setattr(self.record, pattern % i, value)

    def DBUS(self, *enables):
        '''Enables the selected DBUS signals to appear on the EVR-TTB
        transition card.'''
        for i in enables:
            setattr(self.record, 'OT%XB' % i, 'Enabled')

    def OTL(self, *enables):
        '''Enables the selected OTL (latched outputs) to operate.'''
        for i in enables:
            setattr(self.record, 'OTL%X' % i, 'Enabled')

    def TEV(self, *enables):
        '''Enables the selected TEV (Trigger Event) to operate.'''
        for i in enables:
            setattr(self.record, 'TRG%X' % i, 'Enabled')

    def PDP(self, signal, name, delay, width, prescaler, inverted=False):
        '''Enable and configure one of the four basic programmable pulses.'''
        assert 0 <= signal < 4, 'Invalid PDP signal'
        setattr(self.record, 'DG%XE' % signal, 'Enabled')
        setattr(self.record, 'DG%XC' % signal, prescaler)
        setattr(self.record, 'DG%XD' % signal, delay)
        setattr(self.record, 'DG%XW' % signal, width)
        if inverted:
            setattr(self.record, 'DG%XP' % signal, 'Inverted')

    def OTP(self, signal, name, delay, width, inverted=False, enabled=True):
        '''Enable an OTP signal and program the delay and pulse width.  If
        desired the output polarity of the signal can be inverted.'''
        assert 0 <= signal < 14, 'Invalid OTP signal'
        if enabled:
            setattr(self.record, 'OTP%X' % signal, 'Enabled')
        setattr(self.record, 'OT%XD' % signal, delay)
        setattr(self.record, 'OT%XW' % signal, width)
        if inverted:
            setattr(self.record, 'OT%XP' % signal, 'Inverted')

    def PRES(self, prescaler, divider):
        '''Configure one of the three prescalers.'''
        assert 0 <= prescaler < 3, 'Invalid prescaler'
        setattr(self.record, 'PRES%d' % prescaler, divider)

    def EXTE(self, event):
        '''Configure alternative event code for external input.'''
        self.record.EXTE = event

    def FPS_TTL(self, output, signal):
        '''Route an internal signal to one of the front panel TTL outputs.'''
        assert 0 <= output < 5, 'Invalid front panel TTL selection'
        self.FPS(output, signal)

    def FPS_ECL(self, output, signal):
        '''Route an internal signal to one of the front panel ECL outputs.'''
        assert 0 <= output < 2, 'Invalid front panel ECL selection'
        self.FPS(output + 5, signal)

    def FPS(self, output, signal):
        '''Route an internal signal to one of the front panel outputs.
        Outputs 0-4 are TTL, outputs 5,6 are ECL.'''
        assert 0 <= output < 7, 'Invalid front panel selection'
        try:
            fps = int(signal)
            assert 0 <= fps <= 0x2A, 'Invalid front panel output value'
        except ValueError:
            fps = FPSLookup[signal]
        setattr(self.record, 'FPS%X' % output, fps)


    def SetDevice(self):
        SetDevice(self.__component, self.__id)

    def UnsetDevice(self):
        UnsetDevice()

    def GetDevice(self):
        # Quick and dirty hack (with side effects) to retrieve device name.
        # We should do this in a completely different way...
        self.SetDevice()
        result = GetDevice()
        self.UnsetDevice()
        return result


    # Control access to er fields.

    def __get_field(self, lookup, limit, signal, parameter):
        assert 0 <= signal < limit, 'Invalid signal'
        field = lookup[parameter]
        return getattr(self.record, field % signal)

    def get_OTP_field(self, signal, parameter):
        '''Returns record field corresponding to the specified OTP control
        parameter, which can be one of:
            enable, inverted, delay, width.'''
        lookup = dict(
            enable = 'OTP%X', inverted = 'OT%XP',
            delay  = 'OT%XD', width    = 'OT%XW')
        return self.__get_field(lookup, 14, signal, parameter)

    def get_PDP_field(self, signal, parameter):
        '''Returns record field corresponding to the specified PDP control
        parameter, which can be one of:
            enable, inverted, delay, width, prescale.'''
        lookup = dict(
            enable = 'DG%XE', inverted = 'DG%XP',
            delay  = 'DG%XD', width    = 'DG%XW', prescale = 'DG%XC')
        return self.__get_field(lookup, 4, signal, parameter)

    def OTP_Delay_field(self, signal):
        '''Returns field corresponding to delay of corresponding output.  This
        method now only exists for backwards compatibility, use get_field()
        instead.'''
        return self.get_OTP_field(signal, 'delay')


    # Standard timing system names
    T_ZERO      = 0x20  # Start of booster cycle sequence.
    LB0_DI_TRG  = 0x21  # Early trigger, tied to LB_DI_TRG
    LINAC_PRE   = 0x24  # Linac pre-trigger, c. 150us before linac fires.
    LINAC_HBT   = 0x25  # Linac heartbeat, same as LINAC_PRE, but continuous.
    LB_DI_TRG   = 0x26  # Diagnostics LB & BR trigger for Libera.
    BR_HW_TRG   = 0x2A  # Trigger for booster magnets.
    BR_INJ      = 0x2C  # Booster injection
    BR_PRE_EXTR = 0x30  # Booster pre-extract, c. 1ms before extract kick.
    BS_DI_TRG   = 0x31  # Diagnostics BS & SR trigger for Libera.
    SR_PRE_INJ  = 0x32  # Storage ring pre-injection
    SR_INJ_SEPT = 0x33  #
    SR_INJ      = 0x3C  # Storage ring injection.
    SR_DI_TRG   = 0x40  # Single shot trigger for SR diagnostics.
    SR_BP_SYNK1 = 0x46  #
    SEQ_RUN     = 0x50  #
    SEQ_STOP    = 0x51  #
    TOPUP_ON    = 0x53  # Start of topup/injection cycle
    TOPUP_OFF   = 0x54  # Start of non-injection cycle
    FOFB_READ   = 0x57  #
    BEAM_DUMP   = 0x5B  #
    BEAM_LOSS   = 0x5D  # Diagnostics beam loss event for Libera PM event.
    MPS_TRIP    = 0x5E  # Machine Protection System trip.
    I10_FASTCH  = 0x5F  # I10 Fast Chicaine
    SHIFT_0_TS  = 0x70  # Shift 0 into timestamp register.
    SHIFT_1_TS  = 0x71  # Shift 1 into timestamp register.
    FP_INPUT    = 0x76  # Event generated by front panel input
    HEART_BEAT  = 0x7A  #
    EVRS_SYNK   = 0x7B  # Reset EVR prescalsers.
    TS_INCR     = 0x7C  # Increment timestamp counters
    TS_RESET    = 0x7D  # Reset timestamp counters: 1Hz synchronous clock.
    SEQ_FREEZE  = 0x7E  # Freeze event sequence
    SEQ_END     = 0x7F  # End event sequence


    # Names for signals that can be routed to the front panel.
    MHzClock         = 'DBUS4'
    BoosterClock     = 'DBUS5'
    StorageClock     = 'DBUS6'
    CoincidenceClock = 'DBUS7'
