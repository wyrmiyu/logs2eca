#!/bin/bash
set -eo pipefail
# Define default values
script_path="$(readlink -f -- $BASH_SOURCE)"
script_dir="$(dirname $script_path)"

SYSTEMD_DIR=/etc/systemd/system
RPM_DEPS=python3-inotify

src_dir="${LOGS2ECA_SRC_DIR:=$script_dir}"
install_bin_dir="${LOGS2ECA_INSTALL_BIN_DIR:=/usr/local/bin}"
logs2eca_conf_dir="${LOGS2ECA_CONF_DIR:=/etc/logs2eca}"


usage="Usage: $0 [-s|--src <src_dir>] [-d|--dst <install_bin_dir>]

Optional parameters:
-s, --src                   Define the source directory
-d, --dst                   Define the installation directory for the script
-c, --conf                  Define the directory for the configuration files

Environment Variables:
LOGS2ECA_SRC_DIR            Define the source directory
LOGS2ECA_INSTALL_BIN_DIR    Define the installation directory for the script
LOGS2ECA_CONF_DIR           Define the directory for the configuration files

Defaults:
- Source directory: The directory of the installation script
- Installation directory: /usr/local/bin
- Configuration directory: /etc/logs2eca

"

function usage {
    echo "$usage"
    exit 1
}

# Process command line options
while (( "$#" )); do
    case $1 in
        -s|--src)
            if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
                src_dir="$2"
                shift 2
            else
                echo "Error: Argument for $1 is missing" >&2
                usage
            fi
            ;;
        -d|--dst)
            if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
                install_bin_dir="$2"
                shift 2
            else
                echo "Error: Argument for $1 is missing" >&2
                usage
            fi
            ;;
        -c|--conf)
            if [ -n "$2" ] && [ ${2:0:1} != "-" ]; then
                logs2eca_conf_dir="$2"
                shift 2
            else
                echo "Error: Argument for $1 is missing" >&2
                usage
            fi
            ;;
        -*|--*=) # unsupported flags
            echo "Error: Unsupported flag $1" >&2
            usage
            ;;
        *) # preserve positional arguments
            PARAMS="$PARAMS $1"
            shift
            ;;
    esac
done


# Check if python3-inotify is installed, if not, install it
if ! rpm -q python3-inotify > /dev/null 2>&1; then
    echo "python3-inotify is not installed. Installing it now..."
    yum install -y $RPM_DEPS
fi

# Install the logs2eca.py script to the install directory and make it
# executable
install -m 755 -o root -g root \
    "${src_dir}/logs2eca.py" \
    "${install_bin_dir}/logs2eca

# Install the systemd service, replacing the ExecStart path with the install location
sed "s|/usr/bin/logs2eca|${install_bin_dir/bin}/logs2eca|g" \
    "${src_dir}/logs2eca@.service" > "${SYSTEMD_DIR}/logs2eca@.service"

# Create the environment file directory if it doesn't exist
if [ ! -d "$logs2eca_conf_dir" ]; then
    mkdir -p "$logs2eca_conf_dir"
    echo "Created directory ${logs2eca_conf_dir}..."
fi

# Install the environment file template
install -m 644 -o root -g root \
    "${src_dir}/logs2eca_env_template" \
    "${logs2eca_conf_dir}/logs2eca_env_template"

# Reload systemd daemon to reflect changes
systemctl daemon-reload

echo "Installation complete!"
msg="
Systemd service template: ${SYSTEMD_DIR}/logs2eca@.service
Environment file template: ${logs2eca_conf_dir}/logs2eca_env_template

When creating an instance of the logs2eca service, follow these steps:

1. Choose a name for your instance that reflects its purpose.
    - The name must be unique.
    - Both the service and environment file must use the same name.
    - Replace <instance_name> with the name in the following steps.

2. Copy the environment template to: ${logs2eca_conf_dir}/<instance_name>.monitor
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
