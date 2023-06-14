# Design Document for logs2eca

## Overview
This Python script, named `logs2eca`, monitors a log file for specific error patterns and executes a given command when the error pattern is detected.

## Inputs
The script takes in four arguments that can also be provided as environment variables:
1. **Log file to monitor** (`--logfile`, `-l`): The file path of the log file to monitor. Can be provided via the environment variable `LOGS2ECA_LOG_FILE`.
2. **Error pattern to look for** (`--pattern`, `-p`): The error pattern to search for in the log file. If the pattern is surrounded by `/`, `|`, or `%`, it's treated as a regular expression. This can be provided via the environment variable `LOGS2ECA_EVENT_PATTERN`.
3. **Command to execute** (`--command`, `-c`): The command to run when the error pattern is detected. This can be provided via the environment variable `LOGS2ECA_COMMAND`.
4. **Wait time** (`--wait`, `-w`): The optional time in seconds to wait after executing the command before resuming the monitoring. Defaults to 3 seconds if not provided. This can be provided via the environment variable `LOGS2ECA_WAIT`.

## Operation
The script uses the inotify API of the Linux kernel, interfacing through the pyinotify Python module, to monitor changes in the log file. This allows for efficient file change detection without continuous polling.

When the script starts, it parses the command-line arguments with the `parse_args` function. It uses the argparse module for parsing command-line arguments and generating help text.

The script uses the `pyinotify.ProcessEvent` class to handle filesystem events. This class provides methods to handle different types of filesystem events, including file modification, creation, deletion, and move events.

The `EventHandler` class is a subclass of `pyinotify.ProcessEvent`. It adds custom behavior to the event handling methods of the parent class, such as looking for the error pattern in modified lines and executing the command when the pattern is found.

## Handling Filesystem Events
The `EventHandler` class implements the following methods to handle filesystem events:

1. `process_IN_MODIFY`: This method reads the log file from the last known position to the end of the file whenever a file modification event is detected. If the error pattern is found in any line, it calls the `run_command` method.

2. `process_IN_CREATE`: This method reopens the log file and resets the current position to 0 when a file creation event is detected.

3. `process_IN_DELETE`: This method closes the log file handle and sets it to None when a file deletion event is detected. It also resets the current position to 0.

4. `process_IN_MOVED_FROM`: This method behaves similar to the `process_IN_DELETE` method. It closes the log file handle and sets it to None when a file move event is detected.

The script also listens to the SIGHUP signal to handle log rotation. When it receives a SIGHUP signal, it closes the current file handle, opens a new one, and resets the current position to 0 using the `handle_sighup` function.

When an error pattern is detected in the log file, the `run_command` method of the `EventHandler` class executes the provided command using the `subprocess.call` method. After running the command, the script waits for the specified wait time before resuming the monitoring of the log file.

## Finalization
When the `EventHandler` object is destroyed, the `__del__` method is called. This method closes the log file handle if it is open.

## Main Function

The script execution starts from the main function, which does the following tasks:

1. Parses the command-line arguments.
2. Validates the inputs, opens the log file and gets ready to monitor it.
3. Sets up the pyinotify instance and the event handler.
4. Enters the main loop to monitor the log file.

The main loop runs until it's interrupted by a signal like SIGINT or SIGTERM. When it receives an interrupt signal, it cleans up and exits gracefully.

### Signal Handling

The script sets signal handlers for SIGINT, SIGTERM, and SIGHUP. When it receives a SIGINT or SIGTERM signal, it exits the main loop and cleans up. When it receives a SIGHUP signal, it handles log rotation by reopening the log file.
