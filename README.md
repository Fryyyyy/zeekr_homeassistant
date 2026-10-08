# Zeekr EV Integration for Home Assistant

This is a custom integration for Zeekr Electric Vehicles for Home Assistant. It uses the [zeekr_ev_api](https://github.com/Fryyyyy/zeekr_ev_api) library.

## Features

- **Climate**: Control Heating / Cooling Vents & Seats and Steering Wheel.
- **Sensors**: Battery Level, Range, Odometer, Interior Temperature, Tire Pressures, Charging Power, Voltage, Speed.
- **Binary Sensors**: Charging Status, Plugged In Status, Doors, Tyre Warnings.
- **Covers**: Open the Front Hood and control the Sunshade and All Windows.
- **Buttons**: Flash blinkers, ventilate windows, enable/disable Sentry Mode.
- **Locks**: Door and Trunk Lock.
- **Device Tracker**: Location tracking.

## Installation

### HACS

1. Open HACS.
2. Add this repository as a custom repository (Integration).
3. Search for "Zeekr EV Integration" and install.
4. Restart Home Assistant.

### Manual

1. Copy the `custom_components/zeekr_ev` folder to your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Go to Settings -> Devices & Services.
2. Click "Add Integration".
3. Search for "Zeekr EV".
4. Enter your Zeekr account email and password.

### Smart polling

While the car is in deep sleep and not plugged in, charging details, plans, the journey log and VTM status cannot change. With **Smart polling** enabled (default), only the main status is fetched on those polls, which cuts API requests by about 85% for a parked car. A full poll still happens when the car wakes, is plugged in or charging, after a command or a manual poll, and at least every **Deep sleep full refresh interval** (default 60 minutes).

The **Deep sleep polling interval** (default 5 minutes) sets how often the car is checked while asleep. A longer interval saves more requests but delays noticing that the car has woken up. All options can be changed under Settings -> Devices & Services -> Zeekr EV -> Configure.

### Operation durations

AC, seat heating and ventilation, and steering wheel heating durations are stored locally in Home Assistant. They are not synchronized with the mobile app because the car does not report these settings. Each command uses the duration configured in the client that starts it.

New entities default to 15 minutes for AC and seats, and 8 minutes for steering wheel heating. Existing Home Assistant values are carried over to every car during migration (a previous value of 0 becomes 1 minute, the new minimum) and may therefore differ from the mobile app defaults.

## Tips & Tricks

- **Account**: Create a new account and share your car with the new account to avoid "The account is currently logged in elsewhere"
- **Secrets**: Get the secrets by decompiling the Android app.
- **Display**: Use vehicle-status-card for a good quality dashboard.

## Issues

Please report issues on the [GitHub Issue Tracker](https://github.com/Fryyyyy/zeekr_homeassistant/issues).
