# Hunter BTT tap timer Bluetooth protocol

Worked out from the official **Hunter BTT** Android app (`com.hunter.hunterbtt`, version 6.1.7) in November 2026, for interoperability. **Not yet confirmed on a real timer.**

This is a summary. No code from the app is copied here.

## Compared with the Hunter NODE-BT

The BTT talks a **completely different protocol** from the NODE-BT.

| | NODE-BT | BTT |
|---|---|---|
| App built with | .NET MAUI | Ionic/Cordova (web code) plus a small Java Bluetooth plugin, made by an outside developer |
| How commands travel | JSON text over Nordic UART (one pipe for everything) | Raw bytes. **Each setting is its own Bluetooth characteristic** that you read or write directly |
| Login | PIN challenge/response that the controller checks | No real login. The timer hands its 4-character passcode to anyone who reads it, and the **app** compares it |
| Status updates | Indications on the UART pipe | Notifications on the status characteristic |
| Firmware update | Hunter's own OTA services | TI's standard "OAD" service |

That's why this is a separate integration from [hunter-node-bt](https://github.com/deekay2153/hunter-node-bt).

## Two generations

The app chooses by the name the timer advertises:

- **Name starts with `BTT`** → older timers ("First"), service `0000fcc0-…`.
- **Any other name** → newer timers ("Second"), service `0000ff80-…`. Devices with `Spray` in the name are skipped (the first-ever generation).

On newer timers the app reads the standard Firmware Revision string (`0x2A26`). It looks like `Version 4.x` or `Version 4.x 2C`: major version above 3 means "new", and `2C` means the two-outlet model, otherwise it's one outlet ("1C").

All UUIDs below are 16-bit short forms of `0000XXXX-0000-1000-8000-00805f9b34fb`.

## Newer timers (service `0xFF80`)

Each characteristic is `0xFF00 + command`. Values are plain bytes; true/false is one byte (0 or 1). The app uses ordinary GATT read and write-with-response, with no pairing or bonding. It turns on notifications for `0xFF82`, `0xFF8A`, `0xFF8F`, `0xFF99`, `0xFF9B`, `0xFF9E`, `0xFFA2` and `0xFFA3`.

| Char | What it is | Safe to read? | Writes |
|---|---|---|---|
| `FF81` | Passcode, 4 ASCII bytes, zero-padded. All zeros = no passcode | Yes | **Don't**: writing sets or clears the passcode |
| `FF82` | **Live status** (14 bytes, notifies): enabled, suspend, then per outlet: enabled, mode (1 timed / 2 cycle), manual flag, ext-manual flag; then outlet 1 state, outlet 2 state, outlet 1 conflict, outlet 2 conflict | Yes | Not used |
| `FF83` | **Control** (12 bytes): enabled, suspend, outlet 1 enabled / mode / manual-on, outlet 2 enabled / mode / manual-on, run-all hours / minutes / seconds, "special" byte (0 normal, 1 a settings action, 2 run all) | Yes | Start / stop (below). Always write back the whole 12 bytes as read, changing only what you mean to |
| `FF84` | Clock: year (2 bytes, high byte first), month, day, hour, minute, second, weekday | Yes | Sets the clock |
| `FF85` | Schedule header for both outlets | Yes | Schedule (leave alone) |
| `FF86` / `FF8B` | Outlet 1 / outlet 2 run settings (17 bytes). Byte 0 = which setting, `4` = manual. Bytes 11–13 = manual run time hours, minutes, seconds | Yes | Used to set the manual run time before a start |
| `FF87`, `FF88` / `FF8C`, `FF8D` | Outlet 1 / 2 timed and cycle-and-soak start times | Yes | Schedule (leave alone) |
| `FF8A` / `FF8F` | Outlet 1 / 2 run times (manual, timed, cycle, soak). Notifies | Yes | Not needed |
| `FF90` / `FF91` | Outlet 1 / 2 names | Yes | Renames |
| `FF92`–`FF9B` | Upload and download of the **zone photos** the app shows. Not firmware | Not needed | Don't |
| `FF9C` | Seasonal adjust | Yes | Don't |
| `FF9D`, `FF9E`, `FFA2`, `FFA3` | Watering log (time range, records, record count, one record: zone, timestamp, run, soak) | Yes | `FF9D` sets the time range to fetch |
| `FF9F` | Debug | No | **Never** |
| `FFA0` / `FFA1` | Extra start times 5–8 for outlet 1 / 2 | Yes | Schedule (leave alone) |

Outlet state in `FF82`: **`1` = idle**, **`17` (0x11) = manual watering**. Other values weren't labelled in the app.

### Start, stop, status (newer timers)

- **Status:** read `FF82` (or subscribe to it). Outlet state 17 = watering.
- **Start outlet 1 for N minutes:** read `FF86`, set byte 0 to `4` and bytes 11–13 to the run time, write it back. Then read `FF83`, set "outlet 1 manual-on" to 1 (outlet 2's to 0) and "special" to 0, write it back. Outlet 2 is the same using `FF8B`.
- **Run both outlets:** in `FF83` set both manual-on flags to 1, the run-all time, and "special" to 2.
- **Stop:** read `FF83`, set the manual-on flag(s) to 0 and "special" to 0, write it back.
- The app also writes a matching log entry, but that's kept on the phone, not on the timer.

## Older timers (service `0xFCC0`, name starts with `BTT`)

One outlet, with two watering modes: **timed** (characteristics `FCD*`) and **cycle-and-soak** (`FCE*`). Characteristics run from `FCC1` to `FCF2`.

Each value is wrapped as `header byte, length byte, data`, both when read and when written. The header is the characteristic's low byte minus `0x70`, so `FCD9` → `0x69` and `FCEB` → `0x7B`. Two-byte numbers are high byte first.

| Char | What it is |
|---|---|
| `FCC1` | Passcode, 4 ASCII bytes (same idea as `FF81`). **Don't write.** |
| `FCC2` | Current mode: `1` timed, `2` cycle-and-soak |
| `FCC3` | Selected mode (`0` timed, `1` cycle). The app writes it on connect to match `FCC2` |
| `FCC4` | Clock: hour, minute, second, weekday |
| `FCD1` / `FCE1` | Detail state for timed / cycle mode |
| `FCD9` / `FCEB` | **Manual run** for timed / cycle mode: control (`1` on, `0` off), then minutes (2 bytes, up to 360). Notifies control `0` when the run ends |
| `FCD8` / `FCEA` | Off switch for each mode. **Don't write** |
| `FCD2`–`FCD7`, `FCE2`–`FCE9`, `FCD6` | Schedule, start times, rain delay days. **Don't write** |

### Start, stop, status (older timers)

- **Status:** read `FCD9` and `FCEB`. Control `1` on either = watering.
- **Start for N minutes:** read `FCC2` for the mode, then write `[header, 3, 1, minutes high, minutes low]` to that mode's manual characteristic (`FCD9` for timed, `FCEB` for cycle).
- **Stop:** write the same with control `0`, keeping the minutes.

## Standard services the app also reads

- Battery `0x180F` / level `0x2A19` (0–100).
- Device Information `0x180A`: firmware `0x2A26`, maker `0x2A29`.
- Generic Access `0x1800` / name `0x2A00`.

## Never write to these

- **TI OAD firmware update**, service `f000ffc0-0451-4000-b000-000000000000`, characteristics `f000ffc1`–`f000ffc5`. Writing here can brick the timer.
- `FF9F` debug.
- `FF81` / `FCC1` passcode (it would change or clear the owner's passcode).
- Older timers: everything except `FCD9` / `FCEB`.
- Schedule, name and photo characteristics (`FF85`–`FF8D`, `FF90`–`FF9C`, `FFA0`/`FFA1`). Not needed for watering on demand, and a bad write would scramble the owner's program.

## Gaps only a real timer can fill

- Whether the timer refuses writes until the passcode has been read or written in that session. The app never "sends" a passcode before control, so probably not.
- The other outlet state values (auto watering, rain delay, low battery).
- How long the timer stays connectable, and whether it sleeps between advertisements (battery device).
- Whether a one-outlet timer ignores the outlet 2 fields.
- The exact meaning of each mode and "special" value beyond what's listed.
- Whether reading `FCD9` / `FCEB` reliably shows control `1` for the whole run on older timers.

## Read-only checks a BTT owner can run

With **nRF Connect** (phone app) or an **ESPHome Bluetooth proxy**. Close the Hunter app first: the timer probably only allows one connection.

1. Scan and note the advertised **name** (starts with `BTT`, or something else?) and which service is listed: `FF80` or `FCC0`.
2. Connect and list the services. Confirm `FF80` (or `FCC0`), `180F` battery, `180A` device info, and the TI OAD service `F000FFC0-…`. **Don't touch the OAD service.**
3. Read `2A26` (firmware revision). Is it like `Version 4.x 2C`?
4. Read `2A19` (battery percent).
5. Read `FF82` with the timer idle. Expect 14 bytes, with outlet state `01`.
6. Turn on notifications for `FF82`, then start a short manual run **from the timer's own button or the Hunter app**. Does outlet state change to `11` (17)? Does a notification arrive? Stop it the same way and watch it return to `01`.
7. Read `FF83` (12 bytes), `FF84` (clock: does it match the real time?), and `FF86` (17 bytes).
8. Read `FF81`. All zeros means no passcode. Don't share the value if one is set.

Sharing the hex values from steps 1–7 (passcode left out) would be enough to confirm or correct these notes. **Read only: no writes at all until the layouts are confirmed.**
