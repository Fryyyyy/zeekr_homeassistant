# Zeekr EV Integration for Home Assistant

This is a custom integration for Zeekr Electric Vehicles for Home Assistant. It uses the [zeekr_ev_api](https://github.com/Fryyyyy/zeekr_ev_api) library.

## Features

- **Sensors**: Battery Level, Range, Odometer, Interior Temperature, Tire Pressures.
- **Binary Sensors**: Charging Status, Plugged In Status.
- **Locks**: Door Lock status (control planned for future).
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

## Issues

Please report issues on the [GitHub Issue Tracker](https://github.com/Fryyyyy/zeekr_homeassistant/issues).
