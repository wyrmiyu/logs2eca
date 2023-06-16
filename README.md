# logs2eca

## Table of Contents

- [logs2eca](#logs2eca)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Requirements](#requirements)
  - [Usage](#usage)
  - [Additional Information](#additional-information)

## Introduction

`logs2eca` is a Python-based script designed to actively monitor specified log files for a given error pattern. When the error pattern is identified, the script executes a predefined command and waits for a specified time period before resuming its monitoring activity. This tool is currently developed for RHEL 8 environments with the shipped Python 3.6. Due to this, the script relies on a deprecated version of pyinotify. In future, the plan is to create a more generic version with a modern inotify implementation, but this is not the primary focus at the moment.

## Requirements

- RHEL 8 environment
- Python 3.6 (default with RHEL 8)
- python3-inotify package

`logs2eca` relies on the pyinotify module to interface with the inotify API of the Linux kernel. This functionality is provided by the `python3-inotify` package in RHEL 8. Install it using the following command:

```bash
sudo yum install python3-inotify
```

## Usage

The script accepts the following four arguments which can be provided either as command-line arguments or as environment variables:

- Log file to monitor (`--logfile`)
- Error pattern to look for (`--pattern`)
- Command to execute when the error pattern is found (`--command`)
- Optional wait time (in seconds) after executing the command to allow for the process to restart before resuming the file monitoring (`--wait`)

Here's an example of how to run `logs2eca` via command line:

```bash
logs2eca --logfile /var/log/sssd/sssd_implicit_files.log --pattern "timed out before identification" --command "systemctl restart sssd.service" --wait 5
```

If the error pattern is surrounded by `/`, `|`, or `%`, it will be interpreted as a regex pattern. However, one does not have to escape those characters, even if they are used in the actual regex pattern.

When the pattern is a string, the pattern will be matched using Python's substring matching with the 'in' operator. By default, logs2eca adds a space at the start and end of both the line and the pattern to ensure that only whole words are matched. 

However, if you want to match the pattern as a pure substring, you can use the `--arbitrary-substring-match` option. Do note that this option will also match the pattern as a substring of other words. For example, the pattern 'foo' will match all of the following strings: 'foobar', 'foofoobar', 'bazbarfoobar', etc.

## Additional Information

Upon start, `logs2eca` begins to monitor new log entries from the specified log file. If a line matches the provided error pattern, the script executes the provided command, waits for the optional wait time, and then continues to monitor the log file.

When the script detects a log rotation (listening to the SIGHUP signal), it continues the loop, reopening the file in the next loop iteration.

For deployment as a systemd service and environment-specific configuration, see the detailed instructions in [SETUP.md](./SETUP.md). The systemd service is designed to ensure `logs2eca` is always running and can be reused for similar monitoring tasks with different instances using different environment files.

For a thorough understanding of the design and implementation of `logs2eca`, refer to [DESIGN.md](./DESIGN.md).
