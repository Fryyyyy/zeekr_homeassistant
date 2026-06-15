# Zeekr Home Assistant — Functional Entity Reference

> **What this is:** a plain-language guide to what the Zeekr HA integration's entities *do* and *how they behave in Home Assistant* — written for people who use the integration, not for people building it. It describes observable behaviour and the quirks you'll actually hit, not how the integration talks to the car.
>
> Entities are created per vehicle on your account (entity IDs look like `<domain>.<car-name>_<entity>`). A few entities are global (one per account connection) rather than per-car.

---

## How to read the tables

Each table lists the entities for one HA domain. Columns:

- **Entity** — what you'll see in HA (repetitive groups like the four tyres are listed as one row).
- **What it does** — what it controls or reports.
- **How it behaves in HA** — the practical quirks.
- **Known issues** — anything that's outright broken or surprising.

A recurring quirk worth knowing up front: **most writable entities are optimistic.** When you flip a switch or change a value, HA shows the new state immediately, but if the car hasn't actually applied it yet the next status poll can overwrite your change — so the entity appears to "revert" about 10 seconds later. Manual control inside the car always sticks; the revert is purely an HA display effect. See [Known issues](#known-issues).

---

## Switches

| Entity | What it does | How it behaves in HA | Known issues |
|---|---|---|---|
| **Defroster** | Turns the windscreen defroster on/off. | Optimistic. Climate-related. | Can revert ~10s after toggling. |
| **Charging** | Starts/stops charging on demand (separate from any schedule). | Unlike most switches, this one waits up to ~30s for the car to confirm before settling its state — so it's more reliable than a typical optimistic toggle. | — |
| **Steering Wheel Heat** | Turns the heated steering wheel on/off. | Run time comes from the *Steering Wheel Heat Operation Duration* number. | Can revert ~10s after toggling. |
| **Sentry Mode** | Single on/off toggle for the car's guard/sentry mode. | Arms when the car is locked. State settles after a short delay rather than instantly. | See [Sentry Mode notes](#sentry-mode). |
| **Charge Plan** | Enables/disables the scheduled-charging window. | Part of the **charge-schedule trio** (with Charge Start/End Time). Toggling it reuses the currently-set start/end times. | — |
| **Travel Plan** | Master on/off for the departure (pre-conditioning) plan. | Part of the **departure-plan trio** (with Departure AC and Departure Time). Treat this as the master switch when building automations. | Can revert ~10s after toggling. |
| **Departure AC** | Turns the AC pre-conditioning part of the departure plan on/off. | **Not** a standalone climate toggle — it's one setting *inside* the departure plan. Set it together with Travel Plan and Departure Time. | Easy to mis-model as standalone; see [Relationships](#relationships). |

---

## Climate

| Entity | What it does | How it behaves in HA | Known issues |
|---|---|---|---|
| **Climate** | Off / on (heat-cool). Sets cabin pre-conditioning and a single target temperature. Reports the current interior temperature. | Run time comes from the *AC Operation Duration* number. Single target temp; no fan or preset modes. | **Target temperature only reaches the car while climate is ON.** Changing it while climate is off just stores the value in HA and does nothing until you turn climate on. Set the temperature, *then* turn climate on (or turn climate on first). |

---

## Selects (seat comfort)

| Entity | What it does | How it behaves in HA | Known issues |
|---|---|---|---|
| **Seat Heat — Driver / Passenger / Rear Left / Rear Right** | Off / Level 1-3 heated-seat control for each of the 4 seats. | Run time comes from the *Seat Operation Duration* number. These are real and functional. | Can revert ~10s after changing. |
| **Seat Ventilation — Driver / Passenger** | Off / Level 1-3 ventilated-seat control. | **Phantom on trims without ventilated seats.** The selects exist and accept values, but on a 7X without cooled seats they do nothing. Only the front two exist. | Don't rely on these unless your car actually has ventilated seats. |

---

## Covers

| Entity | What it does | How it behaves in HA | Known issues |
|---|---|---|---|
| **Sunshade** | Opens/closes the sunroof sunshade. | Optimistic. | Can revert after operating. |
| **All Windows** | Opens/closes all four windows together; reports an aggregate open/closed + average position. | This is the only window control. Use it for any automation that opens/closes windows. | — |
| **Window — Driver / Passenger / Rear Driver-side / Rear Passenger-side** | **Read-only** per-window state and position. | Open/close do nothing here — control windows via *All Windows*. | Read-only by design. |

---

## Locks

| Entity | What it does | How it behaves in HA | Known issues |
|---|---|---|---|
| **Central Locking** | Locks/unlocks the whole car. | The only fully read-and-write door lock. State settles after a short delay. | — |
| **Charge Lid** | Opens/closes the charge-port lid (lock = closed, unlock = open). | Writable. | — |
| **Trunk Lock** | Reports trunk lock state; unlock opens the trunk. | Locking the trunk uses the central "lock all" (the trunk re-locks with the car). | — |
| **Door Locks — Driver / Passenger / Rear Driver-side / Rear Passenger-side** | **Read-only** per-door lock state. | Lock/unlock do nothing on these — use *Central Locking*. | Read-only by design. |
| **Hood** | **Read-only** bonnet latch state (closed = "locked"). | State only. | Read-only by design. |
| **Electric Park Brake** | **Read-only** park-brake state (engaged = "locked"). | State only. | Read-only by design. |

---

## Binary sensors

| Entity | What it does | How it behaves in HA | Known issues |
|---|---|---|---|
| **Charging Status** | On while the car is charging. | — | — |
| **Plugged In** | On while a charge cable is connected (independent of whether charging is active). | — | Can read `unknown` if the car isn't reporting plug state. |
| **Doors Open ×4** (per door) | On when that door is open. | — | — |
| **Trunk Open / Hood Open** | On when the trunk / bonnet is open. | — | — |
| **Tyre Pre-Warning ×4** | Problem indicator per tyre. | Tyre positions follow the car's drive side. | — |
| **Tyre Temperature Warning ×4** | Problem indicator per tyre. | — | — |

---

## Sensors

| Entity | What it does | How it behaves in HA | Known issues |
|---|---|---|---|
| **Battery Level** | Battery state of charge, %. | — | — |
| **Range** | Estimated remaining range, km. | — | — |
| **Range at 20% SoC / Range at 100% SoC** | Projected range at those charge levels. | — | **The two are swapped** (known upstream bug). |
| **Odometer** | Total distance, km. | — | — |
| **Interior Temperature** | Cabin temperature, °C. | Same reading the Climate entity uses. | — |
| **Trip 2 — Distance / Avg Speed / Avg Consumption** | The car's trip-meter-2 figures. | — | — |
| **Tyre Pressure ×4** | Pressure per tyre, kPa. | Positions follow the car's drive side. | — |
| **Tyre Temperature ×4** | Temperature per tyre, °C. | — | — |
| **Charge Voltage / Current / Power / Speed** | Live charging metrics. | **Only appear when the car is charging at the moment the integration loads.** They come and go across reloads — if the car wasn't charging when HA started, they won't exist until you reload while charging. | — |
| **Charging Time Remaining** | Time to full as `Xh Ym`; shows "Not charging" when idle. | — | — |
| **Vehicle Status** | Usage mode (e.g. Parked, Unlocked, Ready to Go, Active). | — | Some less-common modes may show a raw value. |
| **Engine Status** | Drive state (Parked / Driving / Ready / Charging). | — | — |
| **Journey Log — Last Distance / Avg Speed / Consumption / Regeneration / Duration** | Details of the most recent logged trip. | Depend on the journey-log being fetched. | — |
| **Journey Log Total Trips** | Count of trips on record. | — | — |
| **Journey Log** | Number of loaded trips; the full trip list (with IDs and timestamps) is in its attributes. | Provides the trip IDs used by the *Get Trip Trackpoints* action. | Large attribute payload. |
| **API Status** *(global)* | "Connected" / "Disconnected" for the account connection. | One per account, on the "Zeekr API" device. | **Security: its attributes contain the account's API tokens.** Don't share screenshots or diagnostics of this entity — the tokens grant full account access. A fix is being proposed upstream. |
| **API Requests / Invokes — Today / Total** *(global)* | Counters for API usage; the "today" counters reset at local midnight. | Useful for health/quota monitoring. | — |

---

## Numbers

| Entity | What it does | How it behaves in HA | Known issues |
|---|---|---|---|
| **Seat / AC / Steering Wheel Heat Operation Duration** *(global)* | How long (0-15 min) the matching comfort feature runs when you turn it on. | Pure HA-side settings, remembered across restarts. They feed the seat-heat selects, Climate, and the steering-wheel-heat switch. | — |
| **Charging Limit** *(per car)* | Target charge level (50-100%, in 5% steps). | The car stops charging itself when it reaches this level — set it and forget it. | — |

---

## Date / time

| Entity | What it does | How it behaves in HA | Known issues |
|---|---|---|---|
| **Departure Time** | The departure time for the pre-conditioning plan. | Part of the **departure-plan trio**. This is the write that sticks most reliably. | — |
| **Charge Start Time / Charge End Time** | The scheduled-charging window. | Part of the **charge-schedule trio** with the Charge Plan switch. | — |

---

## Buttons

| Entity | What it does | Known issues |
|---|---|---|
| **Flash Blinkers** | Flashes the hazards once. | — |
| **Honk Horn and Flash Blinkers** | Sounds the horn and flashes the hazards (find-my-car). | — |
| **Disable Parking Comfort** | Turns off parking-comfort mode. | Disable only — there's no matching enable button. |
| **Poll Vehicle Data** | Forces an immediate refresh from the car; also the timestamp source for "last poll". | — |

---

## Device tracker

| Entity | What it does | Known issues |
|---|---|---|
| **Location** | The car's GPS position. | For "is the car home?" automations, charger plug state is faster and more reliable than GPS, which lags by a minute or more. |

---

## Actions (services)

| Action | What it does | Notes |
|---|---|---|
| **Get Trip Trackpoints** | Fetches the GPS track for a specific trip and returns the points. | Pass the trip ID and report time from the *Journey Log* sensor's attributes. |

---

## Relationships

A few entities only make sense as groups. Model your automations around these clusters, not the individual pieces.

**The departure-plan trio — one plan, three entities.**
*Travel Plan* (switch), *Departure AC* (switch), and *Departure Time* (datetime) are three faces of a **single** departure/pre-conditioning plan:
- **Travel Plan** = the plan on/off.
- **Departure AC** = whether the plan pre-conditions the cabin.
- **Departure Time** = when the plan fires.

Set them together, and treat **Travel Plan** as the master in automations — don't drive *Departure AC* as if it were a standalone climate switch. Of the three, the **Departure Time** write is the one that sticks most reliably.

**The charge-schedule trio.**
*Charge Plan* (switch) plus *Charge Start Time* and *Charge End Time* are one scheduled-charging window. These are separate from the **Charging Limit** number (the target % the car charges to) and from the **Charging** switch (start/stop charging right now).

**Charging entities at a glance.**
- **Charging** switch = start/stop charging now.
- **Charging Status** binary sensor = is it charging.
- **Plugged In** binary sensor = is a cable connected (true even when not charging).
- **Charge Voltage / Current / Power / Speed** sensors = live metrics, present only while charging at load time.

**Climate temperature depends on climate being on.**
Setting the target temperature only reaches the car while Climate is on. With Climate off, a temperature change just sits in HA until you turn Climate on.

**Duration numbers feed the comfort features.**
The three *Operation Duration* numbers (seat / AC / steering wheel) aren't car readings — they decide how long the seat-heat selects, Climate, and steering-wheel-heat switch run.

---

## Known issues

| Issue | What you'll see | Status / workaround |
|---|---|---|
| **Optimistic writes revert** | A switch/select/climate change shows immediately, then flips back ~10s later. | Known upstream; a proposed retry/debounce fix did **not** fully resolve it. Practical mitigation: in automations, sequence the writes with small delays and a retry rather than firing them all at once. Manual control inside the car always sticks. |
| **Target temp ignored while climate is off** | Changing target temperature does nothing until climate is on. | Turn climate on first, or set temp then turn climate on. Consider hiding/locking the temp control in your dashboard while climate is off. |
| **Phantom seat-ventilation selects** | The two seat-vent selects accept Off/Level 1-3 but do nothing. | Only relevant on trims with ventilated seats. Don't present them as working otherwise. |
| **Entities go `unknown` on a sleeping car** | When the car is asleep, its entities can drop to `unknown` instead of holding their last value. | Known behaviour; they recover on the next successful poll. |
| **Range-at-SoC sensors swapped** | *Range at 20% SoC* and *Range at 100% SoC* show each other's value. | Known upstream bug. |
| **Single-session conflict** | Repeated connection errors when the same account is logged in on the app and HA at the same time. | Use a **dedicated account** for HA so the app and HA don't fight over the session. |
| **Charge metrics come and go** | Charge Voltage/Current/Power/Speed are missing unless the car was charging when the integration loaded. | Reload the integration while charging to get them; expect them to disappear when charging ends and HA reloads. |
| **A fully-closed window can read as "open"** | Occasionally the All Windows cover (and a per-window state) shows "open" when the windows are actually shut. | A status-detection edge case; the position reading (0–100%) is the reliable signal. |
| **API Status exposes tokens** | The *API Status* sensor's attributes contain the account's API tokens. | Don't share screenshots or diagnostics of that entity — the tokens grant full account access. A fix is being proposed upstream. |

### Sentry Mode

- **Sentry Mode** is a single on/off toggle. It **arms when the car is locked** — flip the switch on and lock the car.
- There's **no storage requirement to arm**. Plugging in a USB drive adds local recording, but it's optional.
- On the **EU/export 7X**, USB recording was confirmed working in our own test (plugging in a USB drive created the sentry recordings folder, with playback available in the car's app). The earlier worry that export models couldn't record to USB is resolved.

---

## Open questions

Things still not fully pinned down — phrased for users, not internals:

1. **Sentry toggle edge cases** — on and off behave as a single toggle; whether a rapid double-toggle could leave it in the wrong state is untested.
2. **Departure / charge plan extras** — the plans carry a couple of conditioning flags whose exact effect on the car isn't documented; they're preserved as-is when you change the parts you control.
