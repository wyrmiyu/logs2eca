#!/bin/bash

# Define default values
SCRIPTS_LOCATION=$(pwd)
INSTALL_LOCATION=/usr/local
SYSTEMD_LOCATION=/etc/systemd/system
ENV_LOCATION=/etc/logs2eca
RPM_DEPS=python3-inotify

# Process command line options
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -s|--src) SCRIPTS_LOCATION="$2"; shift;;
        -d|--dst) INSTALL_LOCATION="$2"; shift;;
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
install -m 755 -o root -g root ${SCRIPTS_LOCATION}/logs2eca ${INSTALL_LOCATION}/logs2eca

# Install the systemd service, replacing the ExecStart path with the install location
sed "s|/usr/bin/logs2eca|${INSTALL_LOCATION}/logs2eca|g" ${SCRIPTS_LOCATION}/logs2eca@.service > ${SYSTEMD_LOCATION}/logs2eca@.service

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
echo "The environment file template for the systemd service template logs2eca@.service is located at ${ENV_LOCATION}/logs2eca_env_template. When creating an instance of the service, copy this file to ${ENV_LOCATION}/instance_name.monitor, edit it for your use casa and apply by enabling starting the service with: systemctl enable --now logs2eca@instance_name.service"
