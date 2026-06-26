# ---------------------------------------------------------------------------
#     IOC hardware resources
# ---------------------------------------------------------------------------
# See drawing number 1007175, issue B for the underlying hardware

import epicsdbbuilder

from builder.DLSRecordName import SetDLSRecordNames, SetDomain

from builder.Hy8402 import Hy8402
from builder.ipac import Hy8001, Hy8002, DIRECTION_INPUT, DIRECTION_OUTPUT
from builder.Hy8401 import Hy8401

from components import fanMonitor, timing, signals, actuator, camera, beamControl, stats
'''Linac Hardware Layout

VME   IP
Slot  Slot  Description          Transition    Interface
  3         Event Receiver       EVR TTB-200
  4         8002 IP carrier           8304
      A      8516  RS-485 controller           8904  (PIM1)
  5         8002                      8202
      A,B    8401  ADC                         8901T x2  (PIM3,4)
  6         8002                      8202
      A,B    8402  DAC                         PMT crate
  7         8002                      8202
      A-D    8401  ADC                         PMT crate
  8   C     8001  Digital I/O         8213     Actuator crate +
      D                                        8901 (PIM5)
  9   A,B   8001  Digital I/O         8301     Actuator crate
      C                                        8901-CC (PIM2)

Hardware connections:
  4.A   <- Radiation safety readback
  5.A  Untriggered (free running)
      0,1 <- Collimator blade positions
      2   <- OYAG1 zoom readback
      3   <- OYAG1 focus readback
      4   <- OYAG2 zoom readback
      5   <- OYAG2 focus readback
      6,7 <- (spare)
  5.B  Triggered at start of booster cycle
      6   <- ICT1
      7   <- ICT2
  6.A,B -> PMT gain control
  7.A-D <- PMT
  8.C   -> Actuator control crate
  8.D   -> ICT calibration control
  9.A,B <- Actuator control crate
  9.C   <- Fan status monitor
'''

epicsdbbuilder.InitialiseDbd('/dls_sw/epics/R3.14.12.7/base/')
SetDLSRecordNames()

stats.status('LI-DI-IOC-01')

# Card 4: Radiation Safety monitor and crate fan temperature monitor.
# ======
# Left commented for now as I don't believe any db files are generated TODO: Review

#card4 = Hy8002(4)    # Sheet 5
#cmsIonSerialCard = card4.DLS8516(0)  # CMS ION monitor channels in IP slot A

# Card 5: Analogue inputs from FC/ICT/COL/cameras and spare inputs
# ======


card5 = Hy8002(5)    # Sheet 6

monitor_adc = Hy8401(card5, 0) # Monitor signals (untriggered)

# LI-DI-COL-01 - two channels to read collimator blade position
#collimator_readbacks = [monitor_adc.channel(i) for i in range(2)]
# Camera position readbacks from channels 2 to 5
zoomFocusReadbacks = [monitor_adc.channel(i) for i in range(2, 6)]

# Miscellaneous signals (on booster trigger)
gen_adc = Hy8401(card5, 1)
# LI,LB-DI-WCM-01 - Wall Current Monitor
li_wcm = gen_adc.channel(0)
lb_wcm = gen_adc.channel(3)
# LI,LB-DI-FC-01,02 - Faraday Cup charge readouts
li_fc1 = gen_adc.channel(1)
li_fc2 = gen_adc.channel(2)
lb_fc1 = gen_adc.channel(4)
lb_fc2 = gen_adc.channel(5)
# LB-DI-ICT-01,02 - Integrating Current Transformer
ict_channels = (gen_adc.channel(6), gen_adc.channel(7))

# The remaining ADC module manages 8 unassigned input channels
#spare_adc = card5.Hy8401(2)

card6 = Hy8002(6)    # Sheet 8
card7 = Hy8002(7)    # Sheet 8
pmt_dacs = [Hy8402(card6, i) for i in range(2)]  # Two DAC IPs on card 6
pmt_dac_channels = [          # Each DAC IP has 16 DAC channels
    pmt_dacs[i].channel(j) for i in range(2) for j in range(16)]
# Four ADC IPs on card 7
pmt_adcs = [Hy8401(card7, i) for i in range(4)]
pmt_adc_channels = [          # Each ADC IP has 8 ADC channels
    pmt_adcs[i].channel(j) for i in range(4) for j in range(8)]

# Card 8: Digital outputs for screens control
# Card 9: Digital inputs for screens control
# ======
card8 = Hy8001(8, DIRECTION_OUTPUT, invertout=1)  # Sheet 9
card9 = Hy8001(9, DIRECTION_INPUT,  invertin=1)   # Sheet 9

screen_outputs = card8.register(32, 16)
screen_inputs = (card9.register( 0, 16), card9.register(16, 16))
ict_controls  = (card8.register(48,  8), card8.register(56,  8))

fan_monitor = card9.register(32, 16)  # Fan crate monitor digital input

# ---------------------------------------------------------------------------
#     General stuff
# ---------------------------------------------------------------------------

SetDomain('LI', 'DI')

# IOC timing system
er = timing.LinacEvents()

# Add support for the CMS ION radiation safety monitor and fan monitoring
#cmsIon.createCmsIon(er, cmsIonSerialCard, 'LI', 1, 1)
#cmsIon.createCmsIon(er, cmsIonSerialCard, 'LI', 2, 2)

fanMonitor.FanMonitor(1, fan_monitor.register(0,4))
fanMonitor.FanMonitor(2, fan_monitor.register(4,4))

# ---------------------------------------------------------------------------
#     Linac devices
# ---------------------------------------------------------------------------

# 24 Linac PMT devices
for i in range(24):
    signals.PMT(i + 1, pmt_dac_channels[i], pmt_adc_channels[i])

# Build the crate interface records here.
(pim1, pim2), (pim3,) = actuator.InterfaceRecords(
    1, screen_inputs, (screen_outputs,))
# The camera power switch is part of this register set.
camera.CameraPower(1, pim3.register(15,1))

# Actuators and cameras.  There are four actuators carrying between them four
# YAG screens, 2 Faraday cups and an OTR screen.

# LI-DI-YAG-01 + LI-DI-FC-01 = LI-DI-YAGFC-01
li_yagfc1 = actuator.YAGFC(1, 1, 1, pim1.register(0, 5), pim3.register(0, 2))
# LI-DI-YAG-02
li_yag2 = actuator.YAG(2, pim1.register(5, 3), pim3.register(2, 1))
# LI-DI-YAG-03 + LI-DI-FC-02 = LI-DI-YAGFC-02
li_yagfc2 = actuator.YAGFC(2, 3, 2, pim1.register(8, 5), pim3.register(3, 2))
# LI-DI-OYAG-01
li_oyag1 = actuator.OYAG(1, pim2.register(0, 4), pim3.register(5, 2))

# ---------------------------------------------------------------------------
#     Linac to Booster transfer devices (devices in Linac vault)
# ---------------------------------------------------------------------------

SetDomain('LB', 'DI')

# The first 8 LtB PMT devices are in the Linac vault.
for i in range(8):
    signals.PMT(i + 1, pmt_dac_channels[i + 24], pmt_adc_channels[i + 24])

# Two further OYAG actuators
# LB-DI-OYAG-01,02
lb_oyag1 = actuator.OYAG(1, pim2.register(4, 4), pim3.register(7, 2))
lb_oyag2 = actuator.OYAG(2, pim2.register(8, 4), pim3.register(9, 2))
# The two cameras associated with these actuators have zoom and focus.
camera.DoubleZoomAndFocus(1, pim3.register(11, 4), zoomFocusReadbacks)

# Two Integrating Current Transformers
signals.ICT(1, er.TickEvent, ict_channels[0], ict_controls[0])
signals.ICT(2, er.TickEvent, ict_channels[1], ict_controls[1])


SetDomain('LI', 'DI')
# Beam control display information: we do this in the LI domain.
dipole1 = beamControl.DipoleStatus(1, 1, epicsdbbuilder.ImportRecord('LB-PC-DIPOL-01:I'))
dipole2 = beamControl.DipoleStatus(1, 2, epicsdbbuilder.ImportRecord('LB-PC-DIPOL-02:I'))
lb1_beam = beamControl.BeamControlBits(1, None,
    (1, li_yagfc1), (2, li_yag2), (3, li_yagfc2), (4, li_oyag1),
    (10, lb_oyag1), (11, dipole1), (14, lb_oyag2), (15, dipole2))


epicsdbbuilder.WriteRecords('linac.db')
print("Wrote linac.db")
