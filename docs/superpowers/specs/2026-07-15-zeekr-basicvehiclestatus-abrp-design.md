# Zeekr `basicVehicleStatus` → ABRP-telemetrie — Ontwerp

**Datum:** 2026-07-15
**Component:** `custom_components/zeekr_ev` (Home Assistant) + HA-package `abrp_zeekr.yaml`
**Status:** Goedgekeurd ontwerp, klaar voor implementatieplan

---

## 1. Aanleiding & probleem

De `zeekr_ev`-integratie pollt `GET /ms-vehicle-status/api/v1.0/vehicle/status/latest`
(`vehicle.get_status`). Die respons bevat twee blokken:

- `additionalVehicleStatus` — **wordt uitgelezen** (SoC, range, banden, klimaat, odometer…).
- `basicVehicleStatus` — **grotendeels genegeerd**. Bevat o.a. `speed`, `position.direction`,
  `position.altitude`, `engineStatus`.

Gevolg: de bestaande, werkende ABRP-push (`abrp_zeekr.yaml`, geverifieerd 14–15/07/2026)
kan **geen live snelheid, heading of hoogte** meesturen. De package documenteert dit gat zelf
("Er is GEEN momentane snelheidssensor … in HA"). De data bestáát in de API; ze wordt alleen
niet ontsloten.

### Reverse-engineering-bevinding (14–15/07/2026)
Via Frida OkHttp-interceptor (`zeekr_http_interceptor.js`) op een Android-emulator is bevestigd:
- Alle app-verkeer loopt via één TSP-gateway (`eu-snc-tsp-api-gw.zeekrlife.com`, APISIX REST).
  **Geen verborgen realtime/push-kanaal** (geen websocket/MQTT). De app pollt dezelfde
  endpoints die de HA-integratie al kan aanroepen.
- `basicVehicleStatus` bevat `speed` / `speedUnit` / `speedValidity`,
  `position.{latitude,longitude,altitude,direction}`, `engineStatus`, `distanceToEmpty`.
- Captures zijn bij stilstand gemaakt (`engine-off`, `speed:0`, `direction:null`); dat live
  velden zich tijdens rijden vullen wordt als aangenomen waar behandeld (bevestiging vereist
  een rit-capture).
- Nieuw in de juli-API t.o.v. april: `vocLevel`/`vocConcentration` (binnenlucht),
  enkele warnings, `tracelessModeActive` — **niets nieuws in het snelheidsdomein**.

### Aanname (geverifieerd)
`basicVehicleStatus` zit gegarandeerd in `coordinator.data[vin]`: `device_tracker.py` leest
`data["basicVehicleStatus"]["position"]["latitude"]`. **Geen coordinator-wijziging nodig** —
puur nieuwe sensor-entities.

### Codestatus
- Repo `zeekr_homeassistant/custom_components/zeekr_ev/sensor.py` (651 regels) heeft al
  `ZeekrVehicleStatusSensor` (uit `usageMode`) en `ZeekrEngineStatusSensor`
  (`engine-off`→"Parked", `engine-running`→"Driving"). **Engine/parkeerstatus is dus al klaar.**
- De snapshot `05-Custom-Components/zeekr_ev/sensor.py` (586 regels) mist deze en loopt achter.
  **Beide kopieën moeten gesynchroniseerd worden** (gebruikerskeuze: "beide plaatsen").

---

## 2. Scope

**Deel A — component:** voeg sensor-entities toe die ontbrekende `basicVehicleStatus`- en
ontlaad-velden ontsluiten. Additief, geen wijziging aan coordinator/data-flow.

**Deel B — package:** stuur die nieuwe entities mee in de `abrp_send` payload, met per-veld
validiteits-guards zodat leeg/0 nu niets verkeerds pusht.

**Beide code-locaties bijwerken en in sync brengen:**
1. `…/2) Development D-Crypt/zeekr_homeassistant/custom_components/zeekr_ev/` (git, canoniek)
2. `…/1) Prive/HomeAssistant Fam-Deckers Mill/05-Custom-Components/zeekr_ev/` (snapshot)

---

## 3. ABRP-veld-mapping (volledig)

| ABRP-param | Bron in Zeekr-API | Status |
|---|---|---|
| `speed` | `basicVehicleStatus.speed` | 🆕 nieuwe sensor |
| `heading` | `basicVehicleStatus.position.direction` | 🆕 nieuwe sensor |
| `elevation` | `basicVehicleStatus.position.altitude` | 🆕 nieuwe sensor |
| `is_parked` | `basicVehicleStatus.engineStatus` (via bestaande `engine_status`-sensor = "Parked") | ✅ sensor bestaat; package omschakelen |
| `power`/`current`/`voltage` (rijden) | `electricVehicleStatus.disChargeIAct` / `disChargeUAct` | 🆕 nieuwe sensoren (rij-experiment) |
| `soc`, `lat`, `lon`, `is_charging`, `is_dcfc`, `odometer`, `est_battery_range`, `cabin_temp`, `hvac_setpoint`, `tire_pressure_*` | bestaande sensoren | ✅ al in package |
| `power`/`voltage`/`current` (laden) | `chargingStatus`-endpoint | ✅ al in package |

### Niet leverbaar door de API (voor deze 7X) — non-goals
| ABRP-param | Reden |
|---|---|
| `ext_temp` | `exteriorTemp` is altijd leeg (706× ""). |
| `batt_temp` (°C) | Alleen `hvTempLevel` (niveau, geen °C). |
| `soh` | Alleen 12V-SoH ("0"); geen HV-SoH. |
| `hvac_power` | Niet in API. |
| `capacity` / `soe` | Niet in API. **Uitgesteld** (YAGNI). Voor later vastgelegd: usable **96,4 kWh**, geen degradatie (SoH 100%). SoC-resolutie blijft 1%. |

---

## 4. Deel A — nieuwe component-sensoren

Nieuwe entities per voertuig, gelezen uit `coordinator.data[vin]`. Voor de eenvoudige numerieke
velden het bestaande `ZeekrSensor`-factory-patroon gebruiken (met float/empty-guard zoals
`trip_2_distance` al doet: lege string / `None` → `None`).

| Entity (`_attr_unique_id`) | Waarde-pad | Unit | device_class |
|---|---|---|---|
| `{vin}_vehicle_speed` | `basicVehicleStatus.speed` | km/h | `SPEED` |
| `{vin}_heading` | `basicVehicleStatus.position.direction` | ° | — |
| `{vin}_elevation` | `basicVehicleStatus.position.altitude` | m | — |
| `{vin}_discharge_current` | `additionalVehicleStatus.electricVehicleStatus.disChargeIAct` | A | `CURRENT` |
| `{vin}_discharge_voltage` | `additionalVehicleStatus.electricVehicleStatus.disChargeUAct` | V | `VOLTAGE` |

Naamgeving volgt bestaand patroon → entity-ids als `sensor.zeekr_2055_vehicle_speed` (consistent
met de `sensor.zeekr_2055_*` die de package verwacht).

**Guards:** waarden kunnen `""`, `null` of `0` zijn bij stilstand. De sensor geeft dan `None`
(of 0 waar zinvol) terug; nooit crashen op een lege string.

**Implementatie-stap 1 (verificatie):** bevestig in de geïnstalleerde build dat
`get_status` het `basicVehicleStatus`-blok teruggeeft (al aangetoond via `device_tracker.py`).

**Engine/parkeerstatus:** `ZeekrEngineStatusSensor` bestaat al in de repo — alleen naar de
snapshot syncen. Geen nieuwe code.

---

## 5. Deel B — package `abrp_zeekr.yaml`

In `rest_command.abrp_send` het `tlm`-object uitbreiden, elk veld met guard:

- `speed` ← `sensor.zeekr_2055_vehicle_speed`, alleen als numeriek en ≥ 0.
- `heading` ← `sensor.zeekr_2055_heading`, alleen als numeriek (Iternio: niet sturen bij
  null/onnauwkeurig → bij stilstand weglaten).
- `elevation` ← `sensor.zeekr_2055_elevation`, alleen als numeriek.
- `is_parked` → omschakelen naar `is_state('sensor.zeekr_2055_engine_status','Parked')`,
  parkeerrem (`lock.…_electric_park_brake`) als fallback.
- **Rij-vermogen** (naast de bestaande laad-tak), tekens conform Iternio (output +, input −):
  ```
  laden (cp > 0.1):                    power = -cp,           voltage = laadV, current = -laadA
  anders, ontlaad geldig (I>0, V>0):   power = +(I·V/1000),   voltage = V,     current = +I
  ```
  waarbij `I = sensor.zeekr_2055_discharge_current`, `V = sensor.zeekr_2055_discharge_voltage`.
- Push-automation `abrp_zeekr_push`: extra state-trigger op
  `sensor.zeekr_2055_vehicle_speed`, zodat rij-updates vaker vuren.

Bestaande velden (soc, lat/lon, is_charging, is_dcfc, odometer, est_battery_range, cabin_temp,
hvac_setpoint, tire_pressure_*) blijven ongewijzigd.

---

## 6. Verificatie

**Bij stilstand (nu):**
- Nieuwe entities bestaan en tonen `None`/0 zonder fouten.
- `abrp_send` bevat géén `speed`/`heading`/`elevation`/rij-`power` (guards laten ze weg) →
  geen regressie in de bestaande, werkende push.
- ABRP blijft SoC/positie/laden correct ontvangen.

**Tijdens rijden (uitgesteld tot een rit):**
- `vehicle_speed` > 0, `heading` gevuld, `engine_status` = "Driving".
- Controleren of `disChargeIAct`/`disChargeUAct` vollopen → dan komt rij-`power` mee; zo niet,
  dan blijft rij-vermogen onbeschikbaar (guard laat het weg, geen schade).

---

## 7. Risico's & kanttekeningen

- **Cadans/rate-limit:** ongewijzigd. De cloud-poll (min-interval, `request_stats`) levert geen
  10 s-telemetrie; ABRP's individuele verbruikskalibratie blijft daarom handmatig. Het
  referentieverbruik blijft in ABRP ingesteld. Dit ontwerp verbetert positie/snelheid-liveness,
  niet de kalibratie.
- **Rij-vermogen onzeker:** `disChargeIAct/UAct` staan bij stilstand leeg; of ze tijdens rijden
  vollopen is niet bevestigd. Leidingen worden gebouwd; guard voorkomt onzin bij leeg.
- **Twee kopieën:** repo en snapshot moeten identiek blijven; risico op drift. Implementatieplan
  past beide aan in dezelfde stap.
- **Emulator/omgeving (terzijde):** Frida ↔ ART-GC crasht op Android 16 (API 36); een
  betrouwbare rit-capture vraagt API 34. Niet nodig voor dit ontwerp, wel voor het rij-experiment.
