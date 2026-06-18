# Hardware definitions for 8002 and IP cards

from .Carrier import IpCarrier

__all__ = ['Hy8002']


# ----------------------------------------------------------------------
#   Hytec 8002 IP carrier card


# General purpose carrier card
class Hy8002(IpCarrier):
    # This device supports up to 4 IP cards.
    MaxIpSlots = 4

    def __init__(self, slot, intLevel=2):
        super().__init__(slot)
        self.intLevel = intLevel
