# Copyright (C) 2015 Junzi Sun (TU Delft)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
The wrapper for decoding ADS-B messages
"""

from __future__ import absolute_import, print_function, division
from pyModeS.decoder import common
# from pyModeS.decoder.bds import bds05, bds06, bds09

from pyModeS.decoder.bds.bds05 import airborne_position, airborne_position_with_ref, altitude
from pyModeS.decoder.bds.bds06 import surface_position, surface_position_with_ref, surface_velocity
from pyModeS.decoder.bds.bds08 import category, callsign
from pyModeS.decoder.bds.bds09 import airborne_velocity, altitude_diff

def df(msg):
    return common.df(msg)

def icao(msg):
    return common.icao(msg)

def typecode(msg):
    return common.typecode(msg)

def position(msg0, msg1, t0, t1, lat_ref=None, lon_ref=None):
    """Decode position from a pair of even and odd position message
    (works with both airborne and surface position messages)

    Args:
        msg0 (string): even message (28 bytes hexadecimal string)
        msg1 (string): odd message (28 bytes hexadecimal string)
        t0 (int): timestamps for the even message
        t1 (int): timestamps for the odd message

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """
    tc0 = typecode(msg0)
    tc1 = typecode(msg1)

    if (5<=tc0<=8 and 5<=tc1<=8):
        if (not lat_ref) or (not lon_ref):
            raise RuntimeError("Surface position encountered, a reference \
                               position lat/lon required. Location of \
                               receiver can be used.")
        else:
            return surface_position(msg0, msg1, t0, t1, lat_ref, lon_ref)

    elif (9<=tc0<=18 and 9<=tc1<=18):
        # Airborne position with barometric height
        return airborne_position(msg0, msg1, t0, t1)

    elif (20<=tc0<=22 and 20<=tc1<=22):
        # Airborne position with GNSS height
        return airborne_position(msg0, msg1, t0, t1)

    else:
        raise RuntimeError("incorrect or inconsistant message types")


def position_with_ref(msg, lat_ref, lon_ref):
    """Decode position with only one message,
    knowing reference nearby location, such as previously
    calculated location, ground station, or airport location, etc.
    Works with both airborne and surface position messages.
    The reference position shall be with in 180NM (airborne) or 45NM (surface)
    of the true position.

    Args:
        msg (string): even message (28 bytes hexadecimal string)
        lat_ref: previous known latitude
        lon_ref: previous known longitude

    Returns:
        (float, float): (latitude, longitude) of the aircraft
    """

    tc = typecode(msg)

    if 5<=tc<=8:
        return surface_position_with_ref(msg, lat_ref, lon_ref)

    elif 9<=tc<=18 or 20<=tc<=22:
        return airborne_position_with_ref(msg, lat_ref, lon_ref)

    else:
        raise RuntimeError("incorrect or inconsistant message types")


def altitude(msg):
    """Decode aircraft altitude

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: altitude in feet
    """

    tc = typecode(msg)

    if tc<5 or tc==19 or tc>22:
        raise RuntimeError("%s: Not a position message" % msg)

    if tc>=5 and tc<=8:
        # surface position, altitude 0
        return 0

    msgbin = common.hex2bin(msg)
    q = msgbin[47]
    if q:
        n = common.bin2int(msgbin[40:47]+msgbin[48:52])
        alt = n * 25 - 1000
        return alt
    else:
        return None


def velocity(msg):
    """Calculate the speed, heading, and vertical rate
    (handles both airborne or surface message)

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        (int, float, int, string): speed (kt), ground track or heading (degree),
            rate of climb/descend (ft/min), and speed type
            ('GS' for ground speed, 'AS' for airspeed)
    """

    if 5 <= typecode(msg) <= 8:
        return surface_velocity(msg)

    elif typecode(msg) == 19:
        return airborne_velocity(msg)

    else:
        raise RuntimeError("incorrect or inconsistant message types, expecting 4<TC<9 or TC=19")


def speed_heading(msg):
    """Get speed and ground track (or heading) from the velocity message
    (handles both airborne or surface message)

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        (int, float): speed (kt), ground track or heading (degree)
    """
    spd, trk_or_hdg, rocd, tag = velocity(msg)
    return spd, trk_or_hdg


def nic(msg):
    """Calculate NIC, navigation integrity category

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: NIC number (from 0 to 11), -1 if not applicable
    """
    if typecode(msg) < 9 or typecode(msg) > 18:
        raise RuntimeError("%s: Not a airborne position message, expecting 8<TC<19" % msg)

    msgbin = common.hex2bin(msg)
    tc = typecode(msg)
    nic_sup_b = common.bin2int(msgbin[39])

    if tc in [0, 18, 22]:
        nic = 0
    elif tc == 17:
        nic = 1
    elif tc == 16:
        if nic_sup_b:
            nic = 3
        else:
            nic = 2
    elif tc == 15:
        nic = 4
    elif tc == 14:
        nic = 5
    elif tc == 13:
        nic = 6
    elif tc == 12:
        nic = 7
    elif tc == 11:
        if nic_sup_b:
            nic = 9
        else:
            nic = 8
    elif tc in [10, 21]:
        nic = 10
    elif tc in [9, 20]:
        nic = 11
    else:
        nic = -1
    return nic


def oe_flag(msg):
    """Check the odd/even flag. Bit 54, 0 for even, 1 for odd.
    Args:
        msg (string): 28 bytes hexadecimal message string
    Returns:
        int: 0 or 1, for even or odd frame
    """
    msgbin = common.hex2bin(msg)
    return int(msgbin[53])

# Uncertainty & accuracy

def nic_v1(msg,nic_sup_b):
    """Calculate NIC, navigation integrity category

    Args:
        msg (string): 28 bytes hexadecimal message string, nic_sup_b (int): NIC supplement

    Returns:
        int: NIC number (from 0 to 11), -1 if not applicable
    """
    if typecode(msg) < 5 or typecode(msg) > 22:
        raise RuntimeError("%s: Not a surface position message (5<TC<8, )airborne position message (8<TC<19), airborne position with GNSS height (20<TC<22)" % msg)

    tc = typecode(msg)

    if tc in [0, 8, 18, 22]:
        nic = 0
    elif tc == 17:
        nic = 1
    elif tc == 16:
        if nic_sup_b:
            nic = 3
        else:
            nic = 2
    elif tc == 15:
        nic = 4
    elif tc == 14:
        nic = 5
    elif tc == 13:
        if nic_sup_b:
            nic = 6
        else:
            nic = 6
    elif tc == 12:
        nic = 7
    elif tc == 11:
        if nic_sup_b:
            nic = 9
        else:
            nic = 8
    elif tc in [6, 10, 21]:
        nic = 10
    elif tc in [5, 9, 20]:
        nic = 11
    elif tc == 7:
        if nic_sup_b:
            nic = 9
        else:
            nic = 8
    else:
        nic = -1
    return nic

def nic_v2(msg,nic_a,nic_b,nic_c):
    """Calculate NIC, navigation integrity category

    Args:
        msg (string): 28 bytes hexadecimal message string, nic_a (int): NIC supplement, nic_b (int): NIC supplement, nic_c (int): NIC supplement
    Returns:
        int: NIC number (from 0 to 11), -1 if not applicable
    """
    if typecode(msg) < 5 or typecode(msg) > 22:
        raise RuntimeError("%s: Not a surface position message (5<TC<8, )airborne position message (8<TC<19), airborne position with GNSS height (20<TC<22)" % msg)

    tc = typecode(msg)

    if tc in [0, 18, 22]:
        nic = 0
    elif tc == 17:
        nic = 1
    elif tc == 16:
        if nic_a:
            nic = 3
        else:
            nic = 2
    elif tc == 15:
        nic = 4
    elif tc == 14:
        nic = 5
    elif tc == 13:
        if nic_a:
            nic = 6
        else:
            if nic_b:
                nic = 6
            else:
                nic = 6
    elif tc == 12:
        nic = 7
    elif tc == 11:
        if nic_a:
            nic = 9
        else:
            nic = 8
    elif tc in [6, 10, 21]:
        nic = 10
    elif tc in [5, 9, 20]:
        nic = 11
    elif tc == 8:
        if nic_a:
            if nic_c:
                nic = 7
            else:
                nic = 6
        else:
            if nic_c:
                nic = 6
            else:
                nic = 0
    elif tc == 7:
        if nic_a:
            nic = 9
        else:
            nic = 8
    else:
        nic = -1
    return nic



def nic_s(msg):
    """Calculate NICs, navigation integrity category supplement

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: NIC number (from 0 to 11), -1 if not applicable
    """
    if typecode(msg) != 31:
        raise RuntimeError("%s: Not a status operation message, expecting TC = 31" % msg)

    msgbin = common.hex2bin(msg)
    nic_s = common.bin2int(msgbin[75])

    return nic_s

def nic_a_and_c(msg):
    """Calculate NICa and NICc, navigation integrity category supplements

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: NIC number (from 0 to 11), -1 if not applicable
    """
    if typecode(msg) != 31:
        raise RuntimeError("%s: Not a status operation message, expecting TC = 31" % msg)

    msgbin = common.hex2bin(msg)
    nic_a = common.bin2int(msgbin[75])
    nic_c = common.bin2int(msgbin[51])

    return nic_a, nic_c

def nic_b(msg):
    """Calculate NICb, navigation integrity category supplement

    Args:
        msg (string): 28 bytes hexadecimal message string

    Returns:
        int: NIC number (from 0 to 11), -1 if not applicable
    """
    if typecode(msg) < 9 or typecode(msg) > 18:
        raise RuntimeError("%s: Not a airborne position message, expecting 8<TC<19" % msg) 

    msgbin = common.hex2bin(msg)
    nic_b = common.bin2int(msgbin[39])

    return nic_b

def nac_p(msg):
    """Calculate NACp, Navigation Accuracy Category - Position

    Args:
        msg (string): 28 bytes hexadecimal message string, TC = 29 or 31

    Returns:
        int: NACp number (from 0 to 11), -1 if not applicable
    """
    if typecode(msg) not in [29,31]:
        raise RuntimeError("%s: Not a target state and status message neither operation status message, expecting TC = 29 or 31" % msg)

    msgbin = common.hex2bin(msg)
    tc = typecode(msg)
    if tc == 29:
        nac_p = common.bin2int(msgbin[71:75])
    elif tc == 31:
        nac_p = common.bin2int(msgbin[76:80])
    else:
        nac_p = -1
    return nac_p


def nac_v(msg):
    """Calculate NACv, Navigation Accuracy Category - Velocity

    Args:
        msg (string): 28 bytes hexadecimal message string, TC = 19

    Returns:
        int: NACv number (from 0 to 4), -1 if not applicable
    """
    if typecode(msg) != 19:
        raise RuntimeError("%s: Not an airborne velocity message, expecting TC = 19" % msg)

    msgbin = common.hex2bin(msg)
    tc = typecode(msg)
    if tc == 19:
        nac_v = common.bin2int(msgbin[42:45])
    else:
        nac_v = -1
    return nac_v

def sil(msg,version):
    """Calculate SIL, Surveillance Integrity Level 

    Args:
        msg (string): 28 bytes hexadecimal message string with TC = 29, 31

    Returns:
        int: sil number, -1 if not applicable
    """
    if typecode(msg) not in [29,31]:
        raise RuntimeError("%s: Not a target state and status message neither operation status message, expecting TC = 29 or 31" % msg)

    msgbin = common.hex2bin(msg)
    tc = typecode(msg)
    if tc == 29:
        sil = common.bin2int(msgbin[76:78])
    elif tc == 31:
        sil = common.bin2int(msg[82:84])
    else:
        sil = -1

    if version == 2:
        if typecode(msg) == 29:
            sils = common.bin2int(msgbin[39])
        elif typecode(msg) == 31:
            sils = common.bin2int(msgbin[86])
    else:
        sils = -1

    return sil, sils

def version(msg):
    """ADS-B Version

    Args:
        msg (string): 28 bytes hexadecimal message string, TC = 31

    Returns:
        int: version number
    """
    msgbin = common.hex2bin(msg)
    if typecode(msg) not in [29,31]:
        raise RuntimeError("%s: Not a target state and status message neither operation status message, expecting TC = 29 or 31" % msg)

    if typecode(msg) in [29,31]:
        version = common.bin2int(msgbin[72:75])
    else:
        version = -1
    return version
