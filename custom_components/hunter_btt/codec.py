"""Byte layouts for the Hunter BTT (newer: service 0xFF80, older: 0xFCC0). Pure Python, no Home Assistant imports.

See PROTOCOL.md in the repo. Worked out from the official app, not yet confirmed on a real timer.
"""
from __future__ import annotations

from dataclasses import dataclass


def uuid16(short: int) -> str:
    return f"{short:08x}-0000-1000-8000-00805f9b34fb"


SERVICE = uuid16(0xFF80)
OLD_SERVICE = uuid16(0xFCC0)  # older one-outlet timers whose name starts with "BTT"
STATUS = uuid16(0xFF82)  # 14 bytes, read only here
CONTROL = uuid16(0xFF83)  # 12 bytes
CLOCK = uuid16(0xFF84)
OUTLET_SETTINGS = {1: uuid16(0xFF86), 2: uuid16(0xFF8B)}  # 17 bytes each
BATTERY = uuid16(0x2A19)
FIRMWARE = uuid16(0x2A26)

# Older timers: one outlet, two modes. Each value is framed as header, length, data;
# the header is the characteristic's low byte minus 0x70. Two-byte numbers are high byte first.
OLD_MODE = uuid16(0xFCC2)  # current mode: 1 timed, 2 cycle-and-soak
OLD_STATE = {1: uuid16(0xFCD1), 2: uuid16(0xFCE1)}  # per-mode detail state, read for diagnostics
OLD_MANUAL = {1: uuid16(0xFCD9), 2: uuid16(0xFCEB)}  # per-mode manual run: control (1 on / 0 off), minutes
OLD_MODE_TIMED, OLD_MODE_CYCLE = 1, 2
OLD_MAX_MINUTES = 360

# The only characteristics this integration ever touches. Everything else, above all the
# TI OAD firmware service (f000ffc0-0451-...), the debug char 0xFF9F and the passcodes
# 0xFF81 / 0xFCC1, is refused in protocol.py.
ALLOWED_READS = {
    STATUS, CONTROL, CLOCK, *OUTLET_SETTINGS.values(), BATTERY, FIRMWARE,
    OLD_MODE, *OLD_STATE.values(), *OLD_MANUAL.values(),
}
ALLOWED_WRITES = {CONTROL, *OUTLET_SETTINGS.values(), *OLD_MANUAL.values()}

STATUS_LEN = 14
CONTROL_LEN = 12
SETTINGS_LEN = 17

STATE_IDLE = 1
STATE_MANUAL = 17  # 0x11

# CONTROL byte positions
C_MANUAL = {1: 4, 2: 7}
C_SPECIAL = 11
# OUTLET_SETTINGS byte positions
S_WHICH = 0
S_WHICH_MANUAL = 4
S_HOURS, S_MINUTES, S_SECONDS = 11, 12, 13

MAX_RUN_MINUTES = 180


class CodecError(ValueError):
    """A value from the timer did not have the expected shape."""


@dataclass(frozen=True)
class Outlet:
    enabled: int
    mode: int  # 1 timed, 2 cycle-and-soak
    manual: bool
    state: int

    @property
    def running(self) -> bool:
        """Same rule as the Hunter app: 1 idle, 17 manual watering, otherwise trust the manual flag."""
        if self.state == STATE_IDLE:
            return False
        if self.state == STATE_MANUAL:
            return True
        return self.manual


@dataclass(frozen=True)
class Status:
    enabled: bool
    suspend: int
    outlets: dict[int, Outlet]
    raw: bytes


def parse_status(data: bytes) -> Status:
    if len(data) < STATUS_LEN:
        raise CodecError(f"status is {len(data)} bytes, expected {STATUS_LEN}: {data.hex(' ')}")
    d = data
    return Status(
        enabled=bool(d[0]),
        suspend=d[1],
        outlets={
            1: Outlet(enabled=d[2], mode=d[3], manual=bool(d[4]), state=d[10]),
            2: Outlet(enabled=d[6], mode=d[7], manual=bool(d[8]), state=d[11]),
        },
        raw=bytes(data),
    )


def outlets_from_firmware(text: str | None) -> int | None:
    """'Version 4.2 2C' -> 2, 'Version 4.2' -> 1, unreadable -> None."""
    if not text:
        return None
    parts = text.replace("Version", "").split()
    if not parts:
        return None
    try:
        major = int(parts[0].split(".")[0])
    except ValueError:
        return None
    if major <= 3:
        return 1
    return 2 if len(parts) > 1 and parts[1].upper() == "2C" else 1


def _check(data: bytes, size: int, what: str) -> bytearray:
    if len(data) != size:
        raise CodecError(f"{what} is {len(data)} bytes, expected {size}: {data.hex(' ')}")
    return bytearray(data)


def _check_outlet(outlet: int) -> None:
    if outlet not in (1, 2):
        raise CodecError(f"no outlet {outlet}")


def set_manual_time(settings: bytes, minutes: int) -> bytes:
    """Outlet settings as read, with the manual run time set. Other bytes untouched."""
    if not 1 <= minutes <= MAX_RUN_MINUTES:
        raise CodecError(f"run time {minutes} min is outside 1-{MAX_RUN_MINUTES}")
    b = _check(settings, SETTINGS_LEN, "outlet settings")
    b[S_WHICH] = S_WHICH_MANUAL
    b[S_HOURS], b[S_MINUTES], b[S_SECONDS] = minutes // 60, minutes % 60, 0
    return bytes(b)


def control_start(control: bytes, outlet: int) -> bytes:
    """Control as read, with this outlet's manual run on. Like the app, the other outlet's is turned off."""
    _check_outlet(outlet)
    b = _check(control, CONTROL_LEN, "control")
    for n, pos in C_MANUAL.items():
        b[pos] = 1 if n == outlet else 0
    b[C_SPECIAL] = 0
    return bytes(b)


def control_stop(control: bytes, outlet: int) -> bytes:
    """Control as read, with this outlet's manual run off."""
    _check_outlet(outlet)
    b = _check(control, CONTROL_LEN, "control")
    b[C_MANUAL[outlet]] = 0
    b[C_SPECIAL] = 0
    return bytes(b)


# ---- older timers (service 0xFCC0) ----


def old_header(uuid: str) -> int:
    return int(uuid[4:8], 16) - 0xFC70


def unframe(uuid: str, data: bytes) -> bytes:
    """Data part of an older timer's value: header, length, data."""
    if len(data) < 2 or data[0] != old_header(uuid):
        raise CodecError(f"{uuid[4:8]}: unexpected frame {data.hex(' ')}")
    return bytes(data[2 : 2 + data[1]])


def frame(uuid: str, payload: bytes) -> bytes:
    return bytes([old_header(uuid), len(payload)]) + payload


def parse_old_mode(data: bytes) -> int:
    """1 timed or 2 cycle-and-soak. Anything else is treated as timed, like the app."""
    p = unframe(OLD_MODE, data)
    return OLD_MODE_CYCLE if p and p[0] == OLD_MODE_CYCLE else OLD_MODE_TIMED


def parse_old_manual(uuid: str, data: bytes) -> tuple[bool, int]:
    """(running, minutes) from a manual-run characteristic."""
    p = unframe(uuid, data)
    if len(p) < 3:
        raise CodecError(f"{uuid[4:8]}: manual run is {len(p)} bytes, expected 3: {data.hex(' ')}")
    return p[0] == 1, int.from_bytes(p[1:3], "big")


def old_manual(uuid: str, run: bool, minutes: int) -> bytes:
    if uuid not in OLD_MANUAL.values():
        raise CodecError(f"{uuid} is not a manual-run characteristic")
    if run and not 1 <= minutes <= OLD_MAX_MINUTES:
        raise CodecError(f"run time {minutes} min is outside 1-{OLD_MAX_MINUTES}")
    return frame(uuid, bytes([1 if run else 0]) + max(0, minutes).to_bytes(2, "big"))


def old_status(mode: int, manual: dict[int, tuple[bool, int]], raw: bytes) -> Status:
    """One outlet. It's watering if either mode's manual run is on."""
    running = any(on for on, _ in manual.values())
    return Status(
        enabled=True,
        suspend=0,
        outlets={1: Outlet(enabled=1, mode=mode, manual=running, state=0)},
        raw=raw,
    )
