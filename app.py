import json
import os
import requests
import time

from flask import render_template, Flask, make_response, Response

app = Flask(__name__)

# Load the configuration values from environment variables - HE_URI and HE_TOKEN
# are mandatory, however a default collection of metrics is provided if the
# HE_METRICS env is missing.
try:
    base_uri = os.environ["HE_URI"]
    access_token = os.environ["HE_TOKEN"]
    collected_metrics = os.getenv("HE_METRICS", " battery,contact,humidity,illuminance,level,switch,temperature,energy,heatingSetpoint,thermostatSetpoint,thermostatOperatingState,thermostatMode,water,contact").split(",")
except KeyError as e:
    print(f"Could not read the environment variable - {e}")

def get_devices():
    return requests.get(f"{base_uri}?access_token={access_token}")

@app.route("/info")
def info():
    res = {
        "status": {
            "CONNECTION": "ONLINE" if get_devices().status_code == 200 else "OFFLINE"
        },
        "config": {
            "HE_URI": base_uri,
            "HE_TOKEN": access_token,
            "HE_METRICS": collected_metrics
        }
    }
    response = app.response_class(
        response=json.dumps(res),
        status=200,
        mimetype='application/json'
    )
    return response

@app.route("/metrics")
def metrics():
    devices = get_devices()
    device_attributes = []

    for device in devices.json():
        device_details = requests.get(f"{base_uri}/{device['id']}?access_token={access_token}").json()
        for attrib  in device_details['attributes']:
            # Is this a metric we should be collecting?
            if attrib["name"] in collected_metrics:
                # Does it have a "proper" value?
                if attrib["currentValue"] is not None:
                    # If it's a switch, then change from text to binary values

                    match attrib["name"]:
                        case "switch":
                            attrib["currentValue"] = transform_binary_values(attrib["currentValue"])
                        case "power":
                            attrib["currentValue"] = transform_binary_values(attrib["currentValue"])
                        case "thermostatOperatingState":
                            if attrib["currentValue"] == "heating":
                                attrib["currentValue"] = 0
                            elif attrib["currentValue"] == "pending cool":
                                attrib["currentValue"] = 1
                            elif attrib["currentValue"] == "pending heat":
                                attrib["currentValue"] = 2
                            elif attrib["currentValue"] == "vent economizer":
                                attrib["currentValue"] = 3
                            elif attrib["currentValue"] == "idle":
                                attrib["currentValue"] = 4
                            elif attrib["currentValue"] == "cooling":
                                attrib["currentValue"] = 5
                            elif attrib["currentValue"] == "fan only":
                                attrib["currentValue"] = 6
                        case "thermostatMode":
                            if attrib["currentValue"] == "auto":
                                attrib["currentValue"] = 0
                            elif attrib["currentValue"] == "off":
                                attrib["currentValue"] = 1
                            elif attrib["currentValue"] == "heat":
                                attrib["currentValue"] = 2
                            elif attrib["currentValue"] == "emergency heat":
                                attrib["currentValue"] = 3
                            elif attrib["currentValue"] == "cool":
                                attrib["currentValue"] = 4
                        case "water":
                            attrib["currentValue"] = transform_binary_values(attrib["currentValue"])

                    # Sanitise the device name as it will appear in the label
                    device_name = sanitize_device_name(device['label'])
                    # Sanitise the metric name
                    metric_name = attrib['name'].lower().replace(' ','_').replace('-','_')
                    # Create the dict that holds the data
                    device_attributes.append({
                        "device_name": f"{device_name}",
                        "metric_name": f"{metric_name}",
                        "metric_value": f"{attrib['currentValue']}",
                        "metric_timestamp": time.time()})
    # Create the response
    response = make_response(render_template('base.txt',
            device_details=device_attributes
            ))
    # Make sure we return plain text otherwise Prometheus complains
    response.mimetype = "text/plain"
    return response

def sanitize_device_name(device_name):
    return device_name.lower().replace(' ','_').replace('-','_').strip('_')

def transform_binary_values(value):
    if value == "on" or value == "open" or value == "active" or value == "present" or value == "unlocked" or value == "wet":
        return 1
    elif value == "off" or value == "closed" or value == "inactive" or value == "not present" or value == "locked" or value == "dry":
        return 0
    else:
        return value

