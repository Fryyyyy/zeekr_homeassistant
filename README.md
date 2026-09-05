# Zeekr EV Integration for Home Assistant

This is a custom integration for Zeekr Electric Vehicles for Home Assistant. It uses the [zeekr_ev_api](https://github.com/Fryyyyy/zeekr_ev_api) library.

## Features

- **Climate**: Control Heating / Cooling Vents & Seats and Steering Wheel.
- **Sensors**: Battery Level, Range, Odometer, Interior Temperature, Tire Pressures, Charging Power, Voltage, Speed.
- **Binary Sensors**: Charging Status, Plugged In Status, Doors, Tyre Warnings.
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

## Tips & Tricks

- **Account**: Create a new account and share your car with the new account to avoid "The account is currently logged in elsewhere"
- **Secrets**: Get the secrets by decompiling the Android app.
- **Display**: Use vehicle-status-card for a good quality dashboard.

## Model-specific diagnostics

To inspect which API fields are actually returned for your vehicle model:

1. Go to Settings -> Devices & Services -> Zeekr EV.
2. Open the integration menu and select **Download diagnostics**.

The diagnostics contain a redacted snapshot of the fields returned for each
vehicle, plus a flattened field inventory. Account credentials, VINs, plates,
device identifiers, and precise location data are removed.

## Issues

Please report issues on the [GitHub Issue Tracker](https://github.com/Fryyyyy/zeekr_homeassistant/issues).
