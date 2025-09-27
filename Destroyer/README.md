Destroyer
Destroyer is a powerful and secure cross-platform data destruction tool designed for permanently erasing data from storage devices. It provides cryptographic proof of erasure through professional certificates, and can be controlled both locally and remotely, making it a flexible solution for data sanitization.

Key Features
Multiple Wipe Modes: Choose the level of security you need, from a quick single-pass wipe to a forensic-level hardware erase.

Quick: A 1-pass software wipe.

Paranoid: A 3-pass software wipe based on the DoD 5220.22-M standard.

Crypto: A hardware-based secure erase command.

Forensic: The most secure hardware erase, which also removes hidden data areas like HPA/DCO.

Cross-Platform: The wiping engine and device detection work on both Windows and Linux systems.

Professional Certification: After every successful wipe, Destroyer generates a certificate of data destruction in three formats:

A detailed JSON file for machine parsing.

A professional PDF document for auditing and record-keeping.

A scannable QR Code for quick verification.

Remote Wipe Capability: Run a secure agent on a target machine and trigger the wipe from a controller anywhere on your network using a secure API.

Interactive Controller: A user-friendly Command-Line Interface (CLI) that guides you through local wipes, remote wipes, and safe simulations.

Safe Demo Mode: Run a full simulation of any wipe process on any drive. This generates a sample watermarked certificate without destroying any actual data, perfect for testing and demonstrations.

Installation
Prerequisites:

Python 3.8+

pip for installing packages

Clone the Repository:

Bash

git clone <your-github-repository-url>
cd DESTROYER
Set up a Virtual Environment (Recommended):

Bash

python3 -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
Install Dependencies:
Install all the required libraries from the requirements.txt file.

Bash

pip install -r requirements.txt
Usage
Destroyer is controlled via the main interactive CLI. All commands should be run from within the backend directory.

Bash

cd backend
python3 wiple_cli.py
This will launch a menu with three primary modes of operation.

1. Local Wipe
Select "Wipe Current System" from the menu. The tool will guide you through:

Listing all drives connected to the local machine.

Selecting a drive to wipe.

Choosing a wipe mode.

A final confirmation before data is permanently destroyed.

2. Remote Wipe
This process involves two machines: a Target (to be wiped) and a Controller (your machine).

On the Target Machine:

Ensure the project is set up and dependencies are installed.

Make sure the firewall allows incoming connections on port 5000.

Start the secure agent by running:

Bash

python3 api.py
The agent will now listen for commands.

On the Controller Machine:

Launch the main CLI (python3 wiple_cli.py) and select "Wipe Remote System".

Enter the IP address of the Target Machine when prompted.

Enter the API Key when prompted. The default key is destroyer-secret-key-12345.

The tool will then securely list the drives from the target machine, and you can proceed with the wipe just like a local session.

3. Demo / Simulation Mode
Select "Run Demo / Simulation" from the menu. This mode is completely safe and will not destroy any data. It allows you to:

Walk through the entire process of selecting a drive and wipe mode.

See the simulated commands that would have been run.

Receive a complete set of certificates, which are clearly watermarked as "SIMULATION".

⚠️ Disclaimer ⚠️
This is a powerful tool designed for the PERMANENT DESTRUCTION OF DATA. Once a drive is wiped, the data cannot be recovered. Use with extreme caution. The author is not responsible for any data loss that occurs from the use of this software. Always double-check the selected drive before confirming the wipe operation.
