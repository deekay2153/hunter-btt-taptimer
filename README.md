# Hunter BTT Tap Timer for Home Assistant

Control a **Hunter BTT Bluetooth tap timer** from Home Assistant over Bluetooth. No cloud, no Hunter account, and no extra hub beyond the Bluetooth you already use with Home Assistant.

[![hacs][hacs-badge]][hacs]
<a href="https://www.buymeacoffee.com/deekay2153"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-ffdd00?logo=buymeacoffee&logoColor=000" alt="Buy me a coffee"></a>

> Not affiliated with or endorsed by Hunter Industries. "Hunter" and "BTT" are their trademarks. Use at your own risk.

> ⚠️ **Early version, not yet tested on a real timer.** It was built from how the official Hunter BTT app talks to the timer. If you own a BTT, please try it and [open an issue](https://github.com/deekay2153/hunter-btt-taptimer/issues) with what happened (see [Help confirm it works](#help-confirm-it-works)).

## What you get

For each timer:

| Entity | What it does |
|---|---|
| `switch` Outlet *N* | On = water from that outlet for its run time. Off = stop that outlet. |
| `number` Outlet *N* run time | Minutes the switch waters for (1–180, default 10). Stored in Home Assistant and kept across restarts. |
| `sensor` Outlet *N* time remaining | Seconds left, for runs started from Home Assistant. The timer itself doesn't report time left. |
| `sensor` Battery | Battery % (diagnostic). |
| `sensor` Raw status | The timer's status bytes in hex (diagnostic, off by default). Handy for bug reports. |

The run time is sent to the timer with each start, so the **timer turns the water off by itself** when the time is up, even if Home Assistant or Bluetooth drops out.

On two-outlet timers, starting one outlet turns off a manual run on the other, the same as the Hunter app does.

## Which timers

Both kinds of BTT are supported, and the integration works out which one it's talking to:

- **Newer timers** (Bluetooth service `FF80`): one or two outlets.
- **Older timers** (Bluetooth service `FCC0`, name usually starts with `BTT`): one outlet. A manual run uses whichever mode the timer is set to in the Hunter app (timed or cycle-and-soak), up to 3 hours here.

## Requirements

- Home Assistant 2024.12 or newer with the **Bluetooth** integration working, through either:
  - a Bluetooth adapter on the Home Assistant machine, or
  - an **ESPHome Bluetooth proxy** (recommended; place it near the tap).
- The proxy or adapter must make *active connections*. For ESPHome that's `bluetooth_proxy: active: true`.

## Install

**HACS (recommended)**
1. HACS → three-dot menu → *Custom repositories* → add `https://github.com/deekay2153/hunter-btt-taptimer`, type *Integration*.
2. Install **Hunter BTT Tap Timer**, then restart Home Assistant.

**Manual:** copy `custom_components/hunter_btt` into your `config/custom_components/` folder and restart.

## Set up

*Settings → Devices & services → Add integration → Hunter BTT Tap Timer.*

| Field | What to enter |
|---|---|
| Timer | Pick it from the list. If it isn't listed, type its Bluetooth address (find it in *Settings → Bluetooth → Advertisement monitor*). |
| Name | What to call it, e.g. *Veggie patch*. |
| Outlets | Two only if your timer has two hose outputs. You can change this later with **Configure**. |

There's no passcode to enter. The timer doesn't check one over Bluetooth (the Hunter app does that on the phone).

**Close the Hunter app first.** The timer takes one Bluetooth connection at a time.

## How it talks to the timer

Every action is one short session: connect, read or write a few values, disconnect. The timer runs on batteries, so connections are kept rare:

- **Idle:** one check every **30 minutes** (status, battery and firmware).
- **While watering:** a check every **60 seconds**.

A run started by the timer's own schedule or button shows up at the next idle check, so up to 30 minutes late. Runs started from Home Assistant show at once.

## Safety

The integration touches only a short list of Bluetooth values. Anything else is refused in code before it reaches Bluetooth:

- **reads:** status, control, clock, outlet settings, battery, firmware version,
- **writes:** the manual run time of an outlet, and the manual on/off flags. Each write starts from the timer's current value and changes only those bytes.

It **never** writes firmware updates, the passcode, schedules, outlet names, photos or debug settings, and it never reads the passcode.

## Help confirm it works

1. Turn on the **Raw status** sensor (it's disabled by default) and note its value while idle.
2. Start a short run from Home Assistant (set the run time to 1 minute first). Does water flow? Does the switch stay on? Does the raw status change?
3. Turn the switch off. Does the water stop?
4. Download diagnostics: *Settings → Devices & services → Hunter BTT Tap Timer → ⋮ → Download diagnostics*. It reads every value the integration knows, as hex. The passcode is never included.
5. Open an issue with your timer model, the results, and the diagnostics file.

For details, add this to `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.hunter_btt: debug
```

## Troubleshooting

| You see | Try |
|---|---|
| Timer missing from the list | Close the Hunter app, check the proxy hears it in the advertisement monitor, or type the address. |
| "not in range of a Bluetooth adapter or proxy" | Move a proxy closer. It must be able to connect, not just hear the timer. |
| "no Hunter BTT service found" | The address isn't a BTT, or the wrong device was picked. |
| Switch turns back off right after starting | Please report it with the raw status and diagnostics. The byte layout may need a fix. |

## Protocol

See [PROTOCOL.md](PROTOCOL.md) for how the timer talks over Bluetooth.

## Support

If this saves you a trip to the tap, you can [buy me a coffee](https://www.buymeacoffee.com/deekay2153). ☕

[hacs]: https://hacs.xyz
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
