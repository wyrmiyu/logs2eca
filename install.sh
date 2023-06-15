#!/bin/bash

# Define default values
SCRIPTS_LOCATION=$(pwd)
INSTALL_PREFIX=/usr/local
SYSTEMD_LOCATION=/etc/systemd/system
ENV_LOCATION=/etc/logs2eca
RPM_DEPS=python3-inotify

# Process command line options
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -s|--src) SCRIPTS_LOCATION="$2"; shift;;
        -d|--dst) INSTALL_PREFIX="$2"; shift;;
        *) echo "Unknown parameter: $1"; exit 1;;
    esac
    shift
done

# Check if python3-inotify is installed, if not, install it
if ! rpm -q python3-inotify > /dev/null 2>&1; then
    echo "python3-inotify is not installed. Installing it now..."
    yum install -y $RPM_DEPS
fi

# Install the logs2eca script
install -m 755 -o root -g root ${SCRIPTS_LOCATION}/logs2eca ${INSTALL_PREFIX}/bin/logs2eca

# Install the systemd service, replacing the ExecStart path with the install location
sed "s|/usr/bin/logs2eca|${INSTALL_PREFIX}/bin/logs2eca|g" ${SCRIPTS_LOCATION}/logs2eca@.service > ${SYSTEMD_LOCATION}/logs2eca@.service

# Create the environment file directory if it doesn't exist
if [ ! -d "$ENV_LOCATION" ]; then
    mkdir -p $ENV_LOCATION
    echo "Created directory ${ENV_LOCATION}..."
fi

# Install the environment file template
install -m 644 -o root -g root ${SCRIPTS_LOCATION}/logs2eca_env_template ${ENV_LOCATION}/logs2eca_env_template

# Reload systemd daemon to reflect changes
systemctl daemon-reload

echo "Installation complete!"
msg="
Systemd service template: ${SYSTEMD_LOCATION}/logs2eca@.service
Environment file template: ${ENV_LOCATION}/logs2eca_env_template

When creating an instance of the logs2eca service, follow these steps:

1. Choose a name for your instance that reflects its purpose.
    - The name must be unique.
    - Both the service and environment file must use the same name.
    - Replace <instance_name> with the name in the following steps.

2. Copy the environment template to: ${ENV_LOCATION}/<instance_name>.monitor
    - Note that the file name must end with a '.monitor' extension.
    - E.g. 'sssd.monitor' or 'httpd_access_log.monitor'
    - Edit the file and fill in values for the following constants:
        LOGS2ECA_LOG_FILE
        LOGS2ECA_EVENT_PATTERN
        LOGS2ECA_COMMAND

3. Apply by enabling and starting the service with:

    # systemctl enable --now logs2eca@<instance_name>.service

"
printf "$msg"
