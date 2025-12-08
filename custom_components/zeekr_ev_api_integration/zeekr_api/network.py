"""
Dummy Network Module.
"""
import json
from . import const

null = None

# Sample data provided by user
SAMPLE_VEHICLE_STATUS = {
  "code": "000000",
  "msg": "ok",
  "data": {
    "basicVehicleStatus": {
      "keyStatus": "",
      "position": {
        "latitude": "-37.8981817",
        "longitude": "145.0420683",
        "altitude": "56",
        "direction": null,
        "posCanBeTrusted": "1",
        "carLocatorStatUploadEn": "1",
        "marsCoordinates": "0"
      },
      "speed": 0,
      "speedUnit": "",
      "speedValidity": "",
      "engineStatus": "engine-off",
      "usageMode": "0",
      "carMode": "0",
      "engineBlockedStatus": "",
      "distanceToEmpty": "0",
      "combinedDistanceToEmpty": ""
    },
    "additionalVehicleStatus": {
      "electricVehicleStatus": {
        "isCharging": False,
        "isPluggedIn": False,
        "stateOfCharge": "",
        "chargeLevel": "86.0",
        "timeToFullyCharged": "2047",
        "statusOfChargerConnection": "0",
        "distanceToEmptyOnBatteryOnly": "470",
        "distanceToEmptyOnBattery20Soc": "367",
        "distanceToEmptyOnBattery100Soc": "84",
        "averPowerConsumption": "18.9",
        "chargeSts": "0",
        "bookChargeSts": "",
        "chargeLidAcStatus": "2",
        "chargeLidDcAcStatus": "2",
        "dcDcConnectStatus": "0",
        "dcChargeSts": "",
        "dcChargeIAct": "-1638.0",
        "chargerState": "0",
        "chargeIAct": "0.0",
        "chargeUAct": "0.0",
        "disChargeConnectStatus": "0",
        "disChargeSts": "",
        "disChargeIAct": "",
        "disChargeUAct": "",
        "timeToTargetDisCharged": "2047",
        "hvBatteryOptimizeFlag": "0",
        "hvTempLevel": "0",
        "pncStatus": null,
        "hvBatteryPreHeatingActive": null,
        "hvBatteryTempStatus": null,
        "hvBatteryHTMStatus": "",
        "chargeHeatingEgy": null,
        "chargeHeatingTime": "",
        "dcChargePowerLimitSts": null,
        "averTraPowerConsumption": null,
        "dcChargePileIAct": "0.0",
        "dcChargePileUAct": "0.0",
        "dcIAct800V": ""
      },
      "drivingSafetyStatus": {
        "srsStatus": null,
        "centralLockingStatus": "1",
        "doorOpenStatusDriver": "0",
        "doorOpenStatusPassenger": "0",
        "doorOpenStatusDriverRear": "0",
        "doorOpenStatusPassengerRear": "0",
        "doorPosDriver": "0",
        "doorPosPassenger": "0",
        "doorPosDriverRear": "0",
        "doorPosPassengerRear": "0",
        "doorGripStatusDriver": "",
        "doorGripStatusPassenger": "",
        "doorGripStatusDriverRear": "",
        "doorGripStatusPassengerRear": "",
        "doorLockStatusPassengerRear": "1",
        "doorLockStatusDriverRear": "1",
        "doorLockStatusDriver": "1",
        "doorLockStatusPassenger": "1",
        "trunkOpenStatus": "0",
        "trunkLockStatus": "1",
        "engineHoodOpenStatus": "0",
        "electricParkBrakeStatus": "1",
        "privateLockStatus": "",
        "tankFlapStatus": "0",
        "seatBeltStatusDriver": null,
        "seatBeltStatusPassenger": null,
        "seatBeltStatusDriverRear": null,
        "seatBeltStatusPassengerRear": null,
        "seatBeltStatusMidRear": null,
        "seatBeltStatusThDriverRear": null,
        "seatBeltStatusThMidRear": null,
        "seatBeltStatusThPassengerRear": null,
        "trunkUpperOpenStatus": "",
        "trunkLowerOpenStatus": "",
        "trunkUpperOpenMode": null,
        "trunkLowerOpenMode": null,
        "petModeStatus": null,
        "submersionAlrmActive": null,
        "vpdActive": null,
        "prkgCameraActive": null
      },
      "maintenanceStatus": {
        "mainBatteryStatus": null,
        "tyrePreWarningDriver": 0,
        "tyrePreWarningPassenger": 0,
        "tyrePreWarningDriverRear": 0,
        "tyrePreWarningPassengerRear": 0,
        "tyreStatusDriver": "299",
        "tyreStatusPassenger": "297",
        "tyreStatusDriverRear": "299",
        "tyreStatusPassengerRear": "295",
        "tyreTempDriver": 20,
        "tyreTempPassenger": 20,
        "tyreTempDriverRear": 20,
        "tyreTempPassengerRear": 20,
        "tyreTempWarningDriver": 0,
        "tyreTempWarningPassenger": 0,
        "tyreTempWarningDriverRear": 0,
        "tyreTempWarningPassengerRear": 0,
        "distanceToService": 32000,
        "daysToService": null,
        "engineHrsToService": null,
        "serviceWarningTrigger": "",
        "serviceWarningStatus": "",
        "washerFluidLevelStatus": "",
        "brakeFluidLevelStatus": "3",
        "odometer": 38,
        "repairModeActive": null
      },
      "runningStatus": {
        "bulbStatus": "",
        "engineOilPressureWarning": "",
        "engineOilTemperature": "",
        "engineOilLevelStatus": "",
        "engineCoolantTemperature": "",
        "engineCoolantLevelStatus": "3",
        "aveFuelConsumption": null,
        "aveFuelConsumptionInLatestDrivingCycle": null,
        "avgSpeed": "18",
        "fuelLevel": "",
        "fuelLevelPct": null,
        "fuelEnCnsFild": "",
        "fuelLevelStatus": null,
        "tripMeter1": "",
        "tripMeter2": "110",
        "fuelLow1WarningDriver": "",
        "fuelLow2WarningDriver": "",
        "engineEnableRunning": "false",
        "rmtEngStartFuncActive": null
      },
      "climateStatus": {
        "interiorTemp": "23.3",
        "interiorTempValidity": null,
        "interiorSecondTemp": "",
        "interiorSecondTempValidity": null,
        "exteriorTemp": "",
        "climateSts": "",
        "winStatusDriver": "2",
        "winStatusPassenger": "2",
        "winStatusDriverRear": "2",
        "winStatusPassengerRear": "2",
        "sunroofOpenStatus": "1",
        "winPosDriver": "0",
        "winPosPassenger": "0",
        "winPosDriverRear": "0",
        "winPosPassengerRear": "0",
        "sunroofPos": "101",
        "sunroofOpenStatusWarning": null,
        "winStatusDriverWarning": null,
        "winStatusPassengerWarning": null,
        "winStatusDriverRearWarning": null,
        "winStatusPassengerRearWarning": null,
        "ventilateStatus": "",
        "drvHeatDetail": 2,
        "passHeatingDetail": 2,
        "rlHeatingDetail": 2,
        "rrHeatingDetail": 2,
        "tlHeatingSts": null,
        "trHeatingSts": null,
        "drvHeatSts": 0,
        "passHeatingSts": 0,
        "rlHeatingSts": 0,
        "rrHeatingSts": 0,
        "tlHeatLv": null,
        "trHeatLv": null,
        "drvVentSts": 2,
        "passVentSts": 2,
        "rrVentSts": 0,
        "rlVentSts": 0,
        "drvVentDetail": 0,
        "passVentDetail": 0,
        "rlVentDetail": 0,
        "rrVentDetail": 0,
        "airCleanSts": null,
        "preClimateActive": False,
        "curtainOpenStatus": 1,
        "curtainPos": 0,
        "sunCurtainRearOpenStatus": 1,
        "sunCurtainRearPos": null,
        "curtainWarning": null,
        "winCurtainStatusDriver": null,
        "winCurtainStatusPassenger": null,
        "winCurtainStatus2ndLeft": null,
        "winCurtainStatus2ndRight": null,
        "winCurtainPosDriver": null,
        "winCurtainPosPassenger": null,
        "winCurtainPos2ndLeft": null,
        "winCurtainPos2ndRight": null,
        "airBlowerActive": "0",
        "climateOverHeatProActive": "false",
        "cabinTempReductionStatus": "0",
        "fragActive": False,
        "steerWhlHeatingSts": "2",
        "defrost": "0",
        "storageBoxStatus": "[{\"id\":\"3\",\"status\":\"1\"}]",
        "activeStatus": "2",
        "currentTemperature": "",
        "carFridgeModel": "",
        "carRefrigeratorStatus": "",
        "vtmTemperature": "0.0",
        "vtmTsActive": "false",
        "fragStrs": {
          "activated": 0,
          "number": 5,
          "items": {
            "elements": [
              {
                "id": 1,
                "activated": 0,
                "level": 0,
                "code": 0,
                "residueTime": null
              },
              {
                "id": 2,
                "activated": 0,
                "level": 0,
                "code": 0,
                "residueTime": null
              },
              {
                "id": 3,
                "activated": 0,
                "level": 0,
                "code": 0,
                "residueTime": null
              },
              {
                "id": 4,
                "activated": 0,
                "level": 0,
                "code": 0,
                "residueTime": null
              },
              {
                "id": 5,
                "activated": 0,
                "level": 0,
                "code": 0,
                "residueTime": null
              }
            ]
          }
        },
        "updateTime": 1763418526287,
        "htSerilizationSts": null,
        "rapidCoolingActive": null,
        "rapidWarmingActive": null,
        "oxyConcentration": null,
        "oxyGeneratorActive": null,
        "lrdVentDetail": null,
        "rrdVentDetail": null
      },
      "drivingBehaviourStatus": {
        "transimissionGearPostion": "",
        "cruiseControlStatus": null,
        "brakePedalDepressed": "",
        "engineSpeed": "",
        "gearAutoStatus": "0",
        "gearManualStatus": ""
      },
      "pollutionStatus": {
        "interiorPM25": null,
        "exteriorPM25": null,
        "interiorSecondPM25": null,
        "interiorPM25Level": null,
        "exteriorPM25Level": null,
        "interiorSecondPM25Level": null,
        "interCO2Warning": null,
        "airQualityIndex": null,
        "airParticleConcentration": null,
        "relHumSts": null,
        "airPurifierActive": null,
        "updateTime": 1763418487706,
        "pupdateTime": null
      }
    },
    "updateTime": 1763418526287
  },
  "debug": {
    "traceId": "024b8344-478a-4371-9d77-a8d0d7b7d6ad",
    "time": 1763424346704
  },
  "success": True
}


def customGet(session, url, headers=None) -> dict:
    """Mock customGet."""
    if const.URL_URL in url:
        return {
            "success": True,
            "data": [
                {
                    "countryCode": "AU",
                    "url": {
                        "appServerUrl": const.APP_SERVER_HOST,
                        "userCenterUrl": const.USERCENTER_HOST,
                        "messageCoreUrl": const.MESSAGE_HOST,
                    },
                    "regionCode": "SEA"
                }
            ]
        }
    if const.INBOX_URL in url:
        return {"success": True}
    if const.TSPCODE_URL in url:
        return {"success": True, "data": {"code": "dummy_tsp_code", "loginId": "dummy_login_id"}}
    if const.UPDATELANGUAGE_URL in url:
        return {"success": True}
    return {"success": False, "msg": "Mock unhandled URL"}

def customPost(session, url, data=None, headers=None) -> dict:
    """Mock customPost."""
    if const.CHECKUSER_URL in url:
        return {"success": True}
    if const.USERINFO_URL in url:
        return {"success": True, "data": {"nickname": "Zeekr User"}}
    if const.PROTOCOL_URL in url:
        return {"success": True}
    return {"success": False, "msg": "Mock unhandled URL"}

def appSignedGet(session, url, headers=None) -> dict:
    """Mock appSignedGet."""
    if const.VEHLIST_URL in url:
        return {
            "success": True,
            "data": [{"vin": "ZEEKR123456789", "model": "001"}]
        }
    if const.VEHICLESTATUS_URL in url:
        return SAMPLE_VEHICLE_STATUS
    return {"success": False, "msg": "Mock unhandled URL"}

def appSignedPost(session, url, data=None, headers=None) -> dict:
    """Mock appSignedPost."""
    if const.BEARERLOGIN_URL in url:
        return {
            "success": True,
            "data": {"accessToken": "dummy_bearer_token"}
        }
    return {"success": False, "msg": "Mock unhandled URL"}
