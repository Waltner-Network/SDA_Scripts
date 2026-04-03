import csv, os

SITE_DIR = "MOT East"
SWITCH = "CIE0510W"
SWITCH_DIR = os.path.join(SITE_DIR, "Edge Switches", SWITCH)
CLOSED_DIR = os.path.join(SWITCH_DIR, "Closed Mode")

switches = [
    "C93MOTE01SDAE-01.csmc.edu",
    "C93MOTE02SDAE-01.csmc.edu",
    "C93MOTE02SDAE-02.csmc.edu", 
    "C93MOTE03SDAE-01.csmc.edu",
    "C93MOTE04SDAE-01.csmc.edu", 
    "C93MOTE05SDAE-01.csmc.edu"
    ]

endpoints = []
with open(os.path.join(CLOSED_DIR, "export.csv"), "r") as f:
    reader = csv.DictReader(f)
    for line in reader:
        if line["Network Device"] in switches:
            endpoints.append({
                "MACAddress" : line["Identity"],
                "EndPointPolicy" : "",
                "IdentityGroup" : "CS_Approved_MAC",
                "Description" : "",
                "DeviceRegistrationStatus" : "NotRegistered",
                "BYODRegistration" : "Unknown",
                "Device Type" : "Device Type#All Device Types",
                "EmailAddress" : "",
                "ip" : "",
                "FirstName" : "",
                "host-name" : "",
                "LastName" : "",
                "MDMServerID" : "",
                "MDMServerName" : "",
                "MDMEnrolled" : "",
                "Location" : line["Location"],
                "PortalUser" : "",
                "User-Name" : line["Identity"].replace(":","-"),
                "StaticAssignment": "FALSE",
                "StaticGroupAssignment": "TRUE",
                "MDMOSVersion": "",
                "PortalUser.FirstName": "",
                "PortalUser.LastName": "",
                "PortalUser.EmailAddress": "",
                "PortalUser.PhoneNumber": "",
                "PortalUser.GuestType": "",
                "PortalUser.GuestStatus": "",
                "PortalUser.Location": "",
                "PortalUser.GuestSponsor": "",
                "PortalUser.CreationType": "",
                "AUPAccepted": ""									
                })


#remove duplicate macs
dedup_endpoints = []
seen_macs = []
for endpoint in endpoints:
    if endpoint["MACAddress"] not in seen_macs:
        seen_macs.append(endpoint["MACAddress"])
        dedup_endpoints.append(endpoint)


with open(os.path.join(CLOSED_DIR, "import.csv"), "w") as f:
    writer = csv.DictWriter(f,endpoints[0].keys())
    writer.writeheader()
    for endpoint in dedup_endpoints:
        writer.writerow(endpoint)

