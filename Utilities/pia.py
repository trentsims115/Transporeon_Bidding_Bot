import subprocess
import random

# Full path to the piactl executable
piactl_path = r"C:\Program Files\Private Internet Access\piactl.exe"

# Regions to choose from
regions = ["us-houston", "us-texas", "us-missouri"]

# Function to get the current region
def get_current_region():
    process = subprocess.run([piactl_path, "get", "region"], capture_output=True, text=True)
    return process.stdout.strip()

# Function to set the region
def set_region(region):
    subprocess.run([piactl_path, "set", "region", region], capture_output=True, text=True)

def switch_region():
    # Create a copy of the regions list to work with
    available_regions = regions.copy()

    # Main logic to switch regions randomly
    current_region = get_current_region()

    # Remove the current region from the copy of the list to ensure we pick a different one
    if current_region in available_regions:
        available_regions.remove(current_region)

    # Randomly select a new region from the remaining list
    new_region = random.choice(available_regions)

    # Set the new region
    set_region(new_region)
    print(f"Switched to {new_region}")
