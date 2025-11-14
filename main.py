from pypresence.presence import Presence
from pypresence import InvalidPipe
from datetime import datetime, UTC
from time import sleep
from pathlib import Path
from sys import platform
import json

from vmware import vmware
from hyperv import hyperv
from virtualbox import virtualbox

def clear() -> None:
    global epoch_time, STATUS, LASTSTATUS, running
    epoch_time = 0
    RPC.clear()
    STATUS = None
    LASTSTATUS = None
    if running:
        print("Stopped running VMs.")
        running = False

running = False

# Load JSON settings file
settings_path = Path("settings.json")
if settings_path.is_file() and settings_path.stat().st_size != 0:
    with open(settings_path, encoding="utf-8") as f:
        settings = json.load(f)
else:
    settings_path.touch()
    settings = {}

# Get client ID
if settings.get("clientID"):
    client_id = settings.get("clientID")
elif Path("clientID.txt").is_file():
    client_id = Path("clientID.txt").read_text(encoding="utf-8")
else:
    client_id = input("Enter client ID: ")
    settings["clientID"] = client_id

# get hypervisors
hypervisors = []
if "vmware" in settings and settings["vmware"].get("enabled", True):
    hypervisors.append("vmware")
    settings["vmware"]["enabled"] = True
if "hyper-v" in settings and settings["hyper-v"].get("enabled", True):
    hypervisors.append("hyper-v")
    settings["hyper-v"]["enabled"] = True
if "virtualbox" in settings and settings["virtualbox"].get("enabled", True):
    hypervisors.append("virtualbox")
    settings["virtualbox"]["enabled"] = True
if not hypervisors:
    if Path("hypervisors.txt").is_file():
        # Client ID found in legacy file
        hypervisors = Path("hypervisors.txt").read_text(encoding="utf-8")
        hypervisors = hypervisors.casefold().split("\n")
    else:
        hypervisors = ["vmware", "hyper-v", "virtualbox"]
        settings.update({'vmware': {'enabled': True}, 'hyper-v': {'enabled': True}, 'virtualbox': {'enabled': True}})

if "vmware" in hypervisors:
    # Get path to VMware
    if platform.lower() == "win32":
        if "vmware" in settings and settings["vmware"].get("path"):
            # VMware path found in settings.json and it's not blank (NoneType/blank strings == False)
            vmwarepath = settings["vmware"].get("path")
        elif Path("vmwarePath.txt").is_file():
            # VMware path found in legacy file
            vmwarepath = Path("vmwarePath.txt").read_text(encoding="utf-8")
            settings["vmware"]["path"] = vmwarepath
        elif Path("C:/Program Files (x86)/VMware/VMware Workstation/vmrun.exe").is_file():
            print("Using C:/Program Files (x86)/VMware/VMware Workstation as path.")
            vmwarepath = Path("C:/Program Files (x86)/VMware/VMware Workstation")
            settings["vmware"]["path"] = vmwarepath.as_posix()
        elif Path("C:/Program Files/VMware/VMware Workstation/vmrun.exe").is_file():
            print("Using C:/Program Files/VMware/VMware Workstation as path.")
            vmwarepath = Path("C:/Program Files/VMware/VMware Workstation")
            settings["vmware"]["path"] = vmwarepath.as_posix()
        else:
            # Prompt for path
            vmwarepath = input("Enter path to VMware Workstation folder: ")
            settings["vmware"]["path"] = vmwarepath
    else:
        vmwarepath = Path("vmrun")

if "virtualbox" in hypervisors:
    # Get path to VirtualBox
    if platform.lower() == "win32":
        if "virtualbox" in settings and settings["virtualbox"].get("path"):
            # VirtualBox path found in settings.json and it's not blank (NoneType/blank strings == False)
            virtualboxpath = settings["virtualbox"].get("path")
        elif Path("C:/Program Files (x86)/Oracle/VirtualBox/VBoxManage.exe").is_file():
            print("Using C:/Program Files (x86)/Oracle/VirtualBox/ as path.")
            virtualboxpath = Path("C:/Program Files (x86)/Oracle/VirtualBox/")
            settings["virtualbox"]["path"] = virtualboxpath.as_posix()
        elif Path("C:/Program Files/Oracle/VirtualBox/VBoxManage.exe").is_file():
            print("Using C:/Program Files/Oracle/VirtualBox/ as path.")
            virtualboxpath = Path("C:/Program Files/Oracle/VirtualBox")
            settings["virtualbox"]["path"] = virtualboxpath.as_posix()
        else:
            # Prompt for path
            virtualboxpath = input("Enter path to VirtualBox folder: ")
            settings["virtualbox"]["path"] = virtualboxpath
    else:
        virtualboxpath = Path("vboxmanage")

# Get large image key
if settings.get("largeImage"):
    largeimage = settings.get("largeImage")
elif Path("largeImage.txt").is_file():
    # Large image key found in legacy file
    largeimage = Path("largeImage.txt").read_text(encoding="utf-8")
    settings["largeImage"] = largeimage
else:
    largeimage = None

# Get small image key
smallimage = settings.get("smallImage")

# Save settings to file
with open("settings.json", "w", encoding="utf-8") as f:
    json.dump(settings, f, indent="\t")

if "vmware" in hypervisors:
    # Initialize VMware
    vmware_instance = vmware(str(vmwarepath))

if "hyper-v" in hypervisors:
    # Initialize Hyper-V
    hyperv_instance = hyperv()

if "virtualbox" in hypervisors:
    # Initialize VirtualBox
    virtualbox_instance = virtualbox(str(virtualboxpath))

# Set up RPC
RPC = Presence(client_id)
try:
    RPC.connect()
except InvalidPipe:
    print("Waiting for Discord...")
    while True:
        try:
            RPC.connect()
            print("Connected to RPC.")
            break
        except InvalidPipe:
            pass
        sleep(5)
else:
    print("Connected to RPC.")
# Create last sent status so we don't spam Discord
LASTSTATUS = None
STATUS = None
# Set time to 0 to update on next change
epoch_time = 0

# Warning
print("Please note that Discord has a 15 second ratelimit in sending Rich Presence updates.")

# Run on a loop
while True:
    # Run vmrun list, capture output, and split it up
    STATUS = None
    if "vmware" in hypervisors:
        vmware_instance.updateOutput()
        if not vmware_instance.isRunning():
            # No VMs running, clear rich presence and set time to update on next change
            clear()
        elif vmware_instance.runCount() > 1:
            running = True
            # Too many VMs to fit in field
            STATUS = "Running VMs"
            # Get VM count so we can show how many are running
            vmcount = [vmware_instance.runCount(), vmware_instance.runCount()]
            HYPERVISOR = "VMware"
        else:
            running = True
            # Init variable
            displayName = vmware_instance.getRunningGuestName(0)
            STATUS = f"Virtualizing {displayName}"
            vmcount = None
            HYPERVISOR = "VMware"
    if "hyper-v" in hypervisors:
        if not hyperv_instance.isFound():
            print("Hyper-V either not supported, enabled, or found on this machine. Disabling Hyper-V for this session.")
            while "hyper-v" in hypervisors:
                hypervisors.remove("hyper-v")
            continue
        hyperv_instance.updateRunningVMs()
        if not hyperv_instance.isRunning():
            # No VMs running, clear rich presence and set time to update on next change
            clear()
        elif hyperv_instance.runCount() > 1:
            running = True
            # Too many VMs to fit in field
            STATUS = "Running VMs"
            # Get VM count so we can show how many are running
            vmcount = [hyperv_instance.runCount(), hyperv_instance.runCount()]
            HYPERVISOR = "Hyper-V"
        else:
            running = True
            # Init variable
            displayName = hyperv_instance.getRunningGuestName(0)
            STATUS = f"Virtualizing {displayName}"
            vmcount = None
            HYPERVISOR = "Hyper-V"
    if "virtualbox" in hypervisors:
        virtualbox_instance.updateOutput()
        if not virtualbox_instance.isRunning():
            # No VMs running, clear rich presence and set time to update on next change
            clear()
        elif virtualbox_instance.runCount() > 1:
            running = True
            # Too many VMs to fit in field
            STATUS = "Running VMs"
            # Get VM count so we can show how many are running
            vmcount = [virtualbox_instance.runCount(), virtualbox_instance.runCount()]
            HYPERVISOR = "VirtualBox"
        else:
            running = True
            # Init variable
            displayName = virtualbox_instance.getRunningGuestName(0)
            STATUS = f"Virtualizing {displayName}"
            vmcount = None
            HYPERVISOR = "VirtualBox"
    if STATUS != LASTSTATUS and STATUS is not None:
        print(f"Rich presence updated locally; new rich presence is: {STATUS} (using {HYPERVISOR})")
        if "virtualbox" in hypervisors and virtualbox_instance.isRunning() and virtualbox_instance.runCount() == 1:
            epoch_time = virtualbox_instance.getVMuptime(0)
        elif epoch_time == 0: # Only change the time if we stopped running VMs before
            # Get epoch time
            now = datetime.now(UTC)
            epoch_time = int((now - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds())
        if largeimage is None:
            largetext = None
        else:
            largetext = "Check out vm-rpc by DhinakG on GitHub!"
        # Update Rich Presence
        RPC.update(
            state=STATUS,
            details=f"Running {HYPERVISOR}",
            small_image=smallimage,
            large_image=largeimage,
            small_text=HYPERVISOR,
            large_text=largetext,
            start=epoch_time,
            party_size=vmcount
        )
        LASTSTATUS = STATUS # Update last status to last status sent
    sleep(1)
