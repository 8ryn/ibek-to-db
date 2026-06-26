# This file creates helper records for managing the cameras.

from epicsdbbuilder import records, CP, PP, ImportRecord, RecordName, create_fanout
from builder.DLSRecordName import SetDevice, UnsetDevice


# Imports a record by name
def ImportName(record):
    return ImportRecord(RecordName(record))


# The camera switches are done in a rather roundabout way.  Each camera has
# its own camera power control switch, but in fact they are grouped together
# into groups which are switched together.  For example, all the Linac
# cameras plus the first four LtB cameras are switched together.
#
# To enable each camera display to have its own power switch, eg
#   LI-DI-DCAM-01:POWER
# it is necessary to gang them together so that each switch updates all the
# other switches.  This is implemented via an intermediate dfanout record
# (which is written to by each power switch) which both operates the real
# power switch and writes the current state of the power switch back to each
# display switch.
#
# This routine should be passed the control register for the hardware switch
# together with the array of camera switch controls.
def CameraPower(id, powerRegister):
    SetDevice('CTRL', id)
    powerRegister.bo('CAM_POWER',
        ZNAM = 'On',   ONAM = 'Off',
        PINI = 'YES',  VAL  = 0)
    UnsetDevice()


# ----------------------------------------------------------------------



# This class is just a fancy wrapped up subroutine!  This routine creates
# the zoom and focus controls for the LB-DI-DCAM-01 and -02 cameras: these
# are attached to the LB-DI-OYAG-01 and -02 actuators.
class DoubleZoomAndFocus:
    # The table of calibration factors is recorded here.  These are
    # coefficients for a model
    #     V = (a + b*F) * (c + d*Z) / (1 + e*Z)
    # where F and Z are the voltage readbacks (driven by a 9V supply) for the
    # focus and zoom positions (respectively) and V is the extent in pixels on
    # the screen of a 30mm target.  This model is solved for coefficients
    # a,b,c,d,e by the matlab function lsqcurvefit against values measured
    # from the real cameras.
    #     Note that this model is only really dependent on 4 coefficents, but
    # for example fixing c=1 causes lsqcurvefit to fail to find a good
    # solution!  Similarly fitting to 1/V directly also fails.

    # The following coefficients were calculated by fitting the model for V
    # against measurements of the installed optics.
    ZFmodel01 = [16.0, 0.43,  16.7, 1.97, -0.14]
    ZFmodel02 = [17.7, 0.435, 14.6, 2.47, -0.124]


    def _Readback(self, channel, name):
        return channel.ai(name,
            mean = 20,
            LINR = 'LINEAR',  MDEL = -1,
            EGUL = -10.0,     EGUF = 10.0,
            EGU  = "V",       PREC = 3,
            SCAN = '.1 second')

    def _ControlBit(self, bit, name, zero, one, dol, sdis=None):
        controlBit = self.bits[bit].bo(name,
            OMSL = 'closed_loop',  DOL = dol,
            ZNAM = zero,  ONAM = one)
        if sdis:
            controlBit.SDIS = sdis
            controlBit.DISV = 0
        return controlBit


    def _ControlRecords(self, id, register):
        # The global control bits go into the catch-all CTRL device.
        SetDevice('CTRL', id)

        # The four control bits are selected from the control register thus:
        #  bit(0) - camera select,    0=>OYAG-02,  1=>OYAG-01
        #  bit(1) - motor select,     0=>Focus,    1=>Zoom
        #  bit(2) - direction select, 0=>In,       1=>Out
        #  bit(3) - motor enable,     0=>Disabled, 1=>Enabled
        self.bits = [register.bit(i) for i in range(4)]

        # User interface to the multiplexed zoom and focus.  The controlling
        # bits correspond to camera, action, direction and enable selection.
        self.mux = records.mbbiDirect('ZF:MUX', VAL = 0, PINI = 'YES')

        # The three multiplex bits are read directly from the corresponding
        # multiplexed bit.  Furthermore, we disable changes to the multiplex
        # bits when the enable bit is disabled.
        self.select    = self._ControlBit(
            0, 'ZF:CAMERA', 'OYAG-02', 'OYAG-01', self.mux.B0, self.mux.B3)
        self.action    = self._ControlBit(
            1, 'ZF:ACTION', 'Focus',   'Zoom',    self.mux.B1, self.mux.B3)
        self.direction = self._ControlBit(
            2, 'ZF:DIR',    'In',      'Out',     self.mux.B2, self.mux.B3)

        # The control chain is moderately complicated: we use a delay record
        # to give the multiplexor control bits time to settle before we
        # enable the output control bit.
        delay = records.bo(
            'ZF:DELAY',
            ZNAM = 'No delay', ONAM = 'Delay', HIGH = 0.05,
            OMSL = 'supervisory')
        enable_in = records.bo(
            'ZF:EN_IN',
            OUT = PP(delay),
            ZNAM = 'Disable', ONAM = 'Enable',
            OMSL = 'closed_loop', DOL = self.mux.B3)
        calc_enable = records.calc(
            'ZF:CALCEN',
            CALC = 'A&&!B',
            INPA = self.mux.B3,
            INPB = delay)
        self.enable    = self._ControlBit(
            3, 'ZF:ENABLE', 'Off', 'On', calc_enable)
        delay.FLNK = calc_enable
        calc_enable.FLNK = self.enable

        # Explicit fanout to control ZF propogation.  Any write to ZF:MUX is
        # propogated to the three select control bits and then to the enable
        # delay chain.
        self.mux.FLNK = create_fanout(
            'ZF:FAN', self.select, self.action, self.direction,
                      enable_in, calc_enable)

        UnsetDevice()


    def _ZoomAndFocus(self, id, readZoom, readFocus, model):
        SetDevice('DCAM', id)

        # Readbacks
        zoom  = self._Readback(readZoom,  'READZOOM')
        focus = self._Readback(readFocus, 'READFOCUS')

        # Control.  This controls a value written into the ZF:MUX control
        # record.  The bottom bit selects the id, but with sel=0 selecting
        # for id=2 and sel=1 selecting id=1.
        sel = 2 - id
        control = records.mbbo(
            'ZF:CONTROL',
            DTYP = 'Raw Soft Channel',
            ZRVL = 0,         ZRST = 'Disabled',
            ONVL = sel + 8,   ONST = 'Focus In',
            TWVL = sel + 12,  TWST = 'Focus Out',
            THVL = sel + 10,  THST = 'Zoom In',
            FRVL = sel + 14,  FRST = 'Zoom Out',
            VAL  = 0,
            OUT  = PP(self.mux))

        # Compute the image scale from the zoom readback
        computeScale = records.calcout(
            'CALC_MMPIX',
            INPA = model[0],
            INPB = model[1],
            INPC = model[2],
            INPD = model[3],
            INPE = model[4],
            INPF = CP(focus),
            INPG = CP(zoom),
            CALC = '30/((A+B*F)*(C+D*G)/(1+E*G))',
            OOPT = 'Every Time',    OUT  = PP(ImportName('MM_PIXEL')))

        UnsetDevice()
        return (zoom, focus)


    def __init__(self, id, register, readbacks):
        # First generate the common controls: this is where the multiplexing
        # onto the control bits above is performed.
        self._ControlRecords(id, register)

        # Position readbacks and camera specific controls for the two DCAMs
        self.zoom1, self.focus1 = self._ZoomAndFocus(
            1, readbacks[0], readbacks[1], self.ZFmodel01)
        self.zoom2, self.focus2 = self._ZoomAndFocus(
            2, readbacks[2], readbacks[3], self.ZFmodel02)
