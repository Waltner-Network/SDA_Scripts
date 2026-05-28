import time
import csv
from catalystcentersdk import CatalystCenterAPI
from catalystcentersdk.exceptions import ApiError

#initiate connection to catalyst center API
api = CatalystCenterAPI(verify=False)

def check_call_status(api, response, success_message, in_progress_message, failure_message):
    while True:
        time.sleep(2)  # Wait for a moment before checking status
        if response.executionStatusUrl:
            status = api.custom_caller.call_api('GET', response.executionStatusUrl)
            if status.status == 'SUCCESS':
                print(success_message)
                break
            elif status.status == 'IN_PROGRESS':
                print(in_progress_message)
                continue
            else:
                print(failure_message)
                print(status)
                break
        elif response.response.url:
            status = api.custom_caller.call_api('GET', response.response.url)
            if status.response.isError == True:
                print(failure_message)
                print(status)
                break
            elif status.response.isError == False & bool(status.response.endTime):
                print(success_message)
                break
            else:
                print(in_progress_message)
                continue

def update_to_closed_mode(api, device_ip):

    networkDevice = api.devices.get_network_device_by_ip(ip_address=device_ip).response
    networkDeviceId = networkDevice.id
    networkDeviceName = networkDevice.hostname

    port_assignments = api.sda.get_port_assignments(network_device_id=networkDeviceId).response
    
    payload = []
    interfaceNames = []
    with open(f"port_assignments_backup_{networkDeviceName}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(['interfaceName', "dataVlanName", "voiceVlanName", "description"])
        for port in port_assignments:
            if port.authenticateTemplateName == "Open Authentication":
                port.authenticateTemplateName = "Closed Authentication"
                payload.append(port)
                interfaceNames.append(port.interfaceName)
                writer.writerow([
                            port.interfaceName,
                            port.dataVlanName,
                            port.voiceVlanName,
                            port.description
                        ])

    

    print(f"Confirm the following details")
    print(f"Device Name: {networkDeviceName}")
    print(f"Device IP: {device_ip}")
    print(f"Interfaces to be updated to Closed Authentication: {interfaceNames}")
    while True:
        user_hostname = input("Enter device hostname to confirm: ")
        if user_hostname.lower() == "q":
            print("exiting closed mode function")
            return
        elif user_hostname.lower() != networkDeviceName.lower():
            print("Hostnames do not match. Try again or enter \"q\" to exit.")
        else:
            break
        
    confirmation = input("Do you want to proceed with updating the above interfaces to Closed Authentication? (yes/no): ")
    if confirmation.lower() == "yes":
        print("Proceeding with the update...")
        try:
            response = api.sda.update_port_assignments(payload=payload)
            check_call_status(
                api,
                response,
                f"Ports updated to Closed Authentication successfully.",
                f"Updating ports to Closed Authentication is in progress...",
                f"Failed to update ports to Closed Authentication."
            )
        except ApiError as e:
            print(f"API error occurred while updating ports: {e}")

update_to_closed_mode(api, "10.189.0.20")