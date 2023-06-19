# How to install and configure logs2eca

This guide explains the manual installation and configuration process for logs2eca, a Python script devised for monitoring specific log files for predetermined error patterns. Alternatively, there's also an `install.sh` script available for automatic deployment. Detailed instructions for both processes are provided below.

## Manual Installation

### 1. Install the Dependencies

Logs2eca utilizes the `pyinotify` module to interface with the inotify API of the Linux kernel. This module is provided by the `python3-inotify` package in RHEL 8. To install it, use the following command:

```bash
yum install -y python3-inotify
```

>Note: Logs2eca is designed to work with the `python3-inotify` module from [this repository](https://github.com/seb-m/pyinotify), which aligns with the version included with RHEL 8.

### 2. Deploy the Script

Deploy the `logs2eca` script to a suitable directory, such as `/usr/local/bin`. See the following example below. In this example, the `install` command is used to deploy the file `logs2eca.py` to `/usr/local/bin/logs2eca`.

**NOTE: Remember to adjust paths below to match your environment.**

```bash
install -m 755 -o root -g root /path/to/source_directory/logs2eca.py /usr/local/bin/logs2eca
```

Make sure to replace `/path/to/source_directory` with the actual path to the directory with the sources files, i.e.contents of this git repository.

### 3. Systemd Service Template Setup

The systemd service template facilitates the script's execution as a persistent service. Modify the `ExecStart` path in the template to match the actual path of the `logs2eca` script, then place the service template in the systemd system directory (`/etc/systemd/system/`):

```bash
sed "s|/usr/bin/logs2eca|/usr/local/bin/logs2eca|g" /path/to/logs2eca@.service > /etc/systemd/system/logs2eca@.service
```

Be sure to replace `/path/to/logs2eca@.service` with the correct path to the service template file.

### 4. Environment File Setup

Construct the `/etc/logs2eca/` directory for storing environment files:

```bash
mkdir -p /etc/logs2eca
```

Transfer the environment file template into this directory:

```bash
install -m 644 -o root -g root /path/to/logs2eca_env_template /etc/logs2eca/logs2eca_env_template
```

As before, replace `/path/to/logs2eca_env_template` with the actual path to the file.

Each instance of the service relies on an environment file for its configuration. The file should be named after the service instance with a `.monitor` extension (for example, `sssd.monitor` for the `sssd` service instance). Create an instance of the service by copying the template file and customizing it with the correct environment variables:

```bash
cp /etc/logs2eca/logs2eca_env_template /etc/logs2eca/my_instance.monitor
vi /etc/logs2eca/my_instance.monitor
```

Replace `my_instance` with the desired service instance name.

In the environment file, you are required to specify the following variables:

- `LOGS2ECA_LOG_FILE`: The full path of the log file to monitor.
- `LOGS2ECA_EVENT_PATTERN`: The pattern to match. It can be a string or a regular expression.
- `LOGS2ECA_COMMAND`: The command to execute when the pattern is matched.

Optionally, you can specify `LOGS2ECA_WAIT`, the number of seconds to wait before resuming monitoring the log file after an event has been detected. The default is 3 seconds.

### 5. Applying the Configuration

After you've tailored the environment file, enable

 and start the service using:

```bash
systemctl enable --now logs2eca@my_instance.service
```

Replace `my_instance` with the desired service instance name.

## Automatic Installation

If you'd like to streamline the installation process, you can utilize the `install.sh` script included in the package. It automatically performs the tasks outlined in the manual installation guide.

Note that the `install.sh` script does not create or configure the environment file for service instances. You'll still need to manually configure the environment files as outlined in the section 4 of the manual installation guide.

When the script is ready, it will display a summary message providing instructions for creating an instance of the logs2eca service, along with the paths to the systemd service template and the environment file template.

### Deployment and usage of `install.sh`

To deploy the script:

1. Provide executable permissions to the script:

   ```bash
   chmod +x /path/to/source_directory/install.sh
   ```

2. Run the script:

   ```bash
   /path/to/source_directory/install.sh  # see below for optional parameters
   ```

Remember to replace `/path/to/source_directory/install.sh` with the actual path to the script.

You may customize the installation process through optional command-line parameters and environment variables. Here are the details:

| Optional CLI Parameter | Description |
| ------------------ | ----------- |
| `-s, --src` | Specifies the source directory. |
| `-d, --dst` | Specifies the installation directory for the script. |
| `-c, --conf` | Specifies the directory for the configuration files. |

| Environment Variable | Descriptions |
| -------------------- | ----------- |
| `LOGS2ECA_SRC_DIR` | Sets the source directory. |
| `LOGS2ECA_INSTALL_BIN_DIR` | Sets the installation directory for the script. |
| `LOGS2ECA_CONF_DIR` | Sets the directory for the configuration files. |

|  Default values  ||
|-------------------------|-------------------------------------------|
| Source directory        | The directory of the installation script. |
| Installation directory  | `/usr/local/bin`                          |
| Configuration directory | `/etc/logs2eca`                           |

For instance, to specify a different installation directory, you could run:

```bash
/path/to/install.sh -d /my/installation/directory
```

Or, alternatively, you could set an environment variable:

```bash
export LOGS2ECA_INSTALL_BIN_DIR=/my/installation/directory
/path/to/install.sh
```

The installation script also checks for the necessary dependency `python3-inotify`, and will attempt to install it if it's not already present on your system.
