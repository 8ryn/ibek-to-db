# Database generator for BR01

import epicsdbbuilder
from epicsdbbuilder import ImportRecord, records

from builder.DLSRecordName import SetDLSRecordNames, SetDomain, SetDevice, UnsetDevice
from builder.modules.ipac import Hy8001, Hy8002
from builder.modules.DLS8512 import DLS8512
from builder.modules.Hy8401 import Hy8401
from builder.modules.Hy8402 import Hy8402

from builder.modules.ipac import DIRECTION_INPUT, DIRECTION_OUTPUT
import components.timing as timing
import components.fanMonitor as fanMonitor
import components.stats as stats
import components.camera as camera
import components.actuator as actuator
import components.signals as signals
import components.beamControl as beamControl
import components.DCCT as DCCT
import components.pin as pin



# ---------------------------------------------------------------------------
#     IOC hardware resources
# ---------------------------------------------------------------------------

# See drawing number 1007176, issue B for the underlying hardware associated
# with these definitions.

'''Booster Ring 1 (BR01C) Hardware Layout

VME   IP
Slot  Slot  Description          Transition    Interface
  3         Event Receiver       EVR TTB-200
  4         8001 Digital I/O & IP     8301
      A      8512 Scaler                       PIN crate
      C                                        8901-CC  (PIM1)
      D                                        Actuator crate in
  5   C     8001 Digital I/O          8213     Actuator crate out
      D                                        8901  (PIM3)
  6         8002 IP carrier           8202
      A      8401  ADC                         8901T  (PIM2)
      B      8401  ADC                         RIM
      C      8401  ADC                         PMT crate
      D      8402  DAC                         PMT crate
  8         IOC (for camera)

Hardware connections:
  4.A   <- PIN diode radiation detector
  4.C   <- Fan status monitor
  4.D   <- Actuator crate status inputs
  5.C   -> Actuator crate control outputs
  5.D   -> ICT calibration control
  6.A  Triggered at start of booster cycle
      0,1 <- ICT inputs
      2   <- DCCT inputs
      3-7 <- (spare)
  6.B  Trigger from RIM
      0-7 <- RIM
  6.C   <- PMT
  6.D   -> PMT gain control
'''
IocLocation = 'BR01C'
IocArea = 'DI'
IocNumber = 1
IocName = '%s-%s-IOC-%02d' % (IocLocation, IocArea, IocNumber)

epicsdbbuilder.InitialiseDbd('/dls_sw/epics/R3.14.12.3/base/')
SetDLSRecordNames()

stats.status(IocName)

# Card 4: PIN radiation detectors, fan monitor, crate status inputs
# ======
card4 = Hy8001(4, DIRECTION_INPUT, invertin=1, ip_support=True)    # Sheet 10

pin_scaler = DLS8512(card4, 0)
pin_counters = [pin_scaler.channel(i) for i in range(16)]

fan_monitor = card4.register(32, 16)    # Port C
screen_inputs = card4.register(48, 16)  # Port D


# Card 5: Digital outputs for screens control
# ======
card5 = Hy8001(5, DIRECTION_OUTPUT, invertout=1)   # Sheet 8
screen_outputs = card5.register(32, 16)
lb_ict_controls, br_ict_controls = (card5.register(48, 8), card5.register(56, 8))


# Card 6: Analogue inputs from ICT and DCCT, spare inputs, and PMT control
# ======
card6 = Hy8002(6)    # Sheet 5 and 7

# Triggered ADC
gen_adc = Hy8401(card6, 0)
lb_ict_channel = gen_adc.channel(0)
br_ict_channel = gen_adc.channel(1)
dcct_channel   = gen_adc.channel(2)

spare_adc = Hy8401(card6,1)   # Miscellaneous signals (on booster trigger)

# PMT input and gain control
pmt_adc = Hy8401(card6, 2)
pmt_dac = Hy8402(card6, 3)     # PMT gain control
pmt_adc_channels = [pmt_adc.channel(i) for i in range(8)]
pmt_dac_channels = [pmt_dac.channel(i) for i in range(8)]

# ---------------------------------------------------------------------------
#     General stuff
# ---------------------------------------------------------------------------

SetDomain('BR01C', 'DI')

er = timing.BoosterEvents(1)

# Fan monitor records.  We monitor two adjacent racks
fanMonitor.FanMonitor(1, fan_monitor.register(0,4))
fanMonitor.FanMonitor(2, fan_monitor.register(4,4))

# Screen controls go through interface records generated here: these are
# shared between the BR01C screen and the LB screens.
(pim1,), (pim2,) = actuator.InterfaceRecords(
    1, (screen_inputs,), (screen_outputs,))
camera.CameraPower(1, pim2.register(6, 1))

# ---------------------------------------------------------------------------
#     Linac to Booster transfer devices (devices in Booster vault)
# ---------------------------------------------------------------------------

SetDomain('LB', 'DI')

# Actuators for screens in booster vault of LtB.
lb_oyag3 = actuator.OYAG(3, pim1.register(0, 4), pim2.register(0, 2))
lb_oyag4 = actuator.OYAG(4, pim1.register(4, 4), pim2.register(2, 2))

# LB-DI-ICT-03
lb_ict = signals.ICT(
    3, er.TickEvent, lb_ict_channel, lb_ict_controls, offset=647)

# The remaining 8 of 16 LtB PMT devices are here.
for i in range(8):
    signals.PMT(i + 9, pmt_dac_channels[i], pmt_adc_channels[i])

# Create the beam control records for LB.  This uses actuator records created
# by the linac together with two dipole status records.
lb1_beam = ImportRecord('LI-DI-CTRL-01:BEAM1.BF')
beamControl.BeamControlBits(1, lb1_beam, (4, lb_oyag3), (7, lb_oyag4))


# ---------------------------------------------------------------------------
#     Booster ring devices
# ---------------------------------------------------------------------------

SetDomain('BR01C', 'DI')

br_oyag1 = actuator.OTR(1, pim1.register( 8, 3), pim2.register(4, 1))
br_oyag4 = actuator.OTR(4, pim1.register(11, 3), pim2.register(5, 1))

# The booster ICT behaves for all the world like a DCCT.
ICT_CALIBRATION = 0.4 / 7.572   # 0.4 nC for 7.572V output
ICT_SCALE = ICT_CALIBRATION / DCCT.BR_MA_TO_NC
DCCT.BR('ICT', 1, er.TickEvent, br_ict_channel,
    filter = 'flattop25-1', scaling = ICT_SCALE)

# The normal booster DCCT.  The scaling on this device is 2mA per Volt.
DCCT.BR('DCCT', 1, er.TickEvent, dcct_channel,
    filter = 'br-filter-25-1', scaling = 2.0)

pins = pin.PINs(pin_counters)

SetDevice('CTRL', 1)
records.seq('INIT_CPU',
    DO1  = 65,   PINI = 'YES',  SELM = 'All',
    LNK1 = ImportRecord('%s:CPU:LOAD' % IocName).HIGH)
UnsetDevice()

epicsdbbuilder.WriteRecords('br01.db')
print("Wrote br01.db")
