# Design of logs2eca

## Overview

The `logs2eca` script operates based on an event-condition-action (ECA) model to a limited extent, where the event is a modification in a log file, the condition is a match with a user-specified pattern (either a string or a regular expression), and the action is the execution of a user-defined command.

This script monitors a specified log file for the occurrence of a defined pattern. Upon detecting the pattern, it executes a given command and waits for a defined interval before resuming the monitoring process. The pattern can be specified as a regex pattern if it is enclosed by "/", "|", or "%". The script only considers log lines that are written after it starts execution and does not parse pre-existing lines.

## Components

The script consists of multiple components that work together to enable the desired functionality:

### The main function

The main function parses the command-line arguments, sets up the signal handler for SIGHUP, and starts the pyinotify.WatchManager and the pyinotify.Notifier. The WatchManager watches the directory containing the log file for changes, and the Notifier calls the EventHandler methods when changes are detected.

### Command-line Argument Parsing

The script uses the argparse module to parse command-line arguments. These arguments specify the log file to monitor, the error pattern to search for, the command to execute when the pattern is found, and an optional wait time (in seconds) to pause execution after running the command.

### Log File Monitoring

The script utilizes the pyinotify module to interface with the inotify API of the Linux kernel. This allows the script to efficiently monitor the log file for changes without the need for polling.

The event handler (an instance of the `EventHandler` class) processes changes in the log file and responds appropriately. The handler includes methods to manage various events such as log file modification, creation, deletion, and relocation.

### Pattern Detection and Command Execution

When a modification event occurs, the script reads the new data, and if it matches the error pattern, the script triggers the user-defined command using the subprocess module. It then waits for a specified duration before resuming monitoring. This allows the invoked process time to execute and potentially fix the issue that caused the error before monitoring is resumed.

### Signal Handling and Log Rotation

The script also responds to SIGHUP signals. This is particularly important to handle log rotation scenarios. When a SIGHUP signal is received, the script closes and reopens the log file to ensure it can continue monitoring the new log file post-rotation.

The design of `logs2eca` leverages the event-condition-action principle to provide a robust and efficient mechanism for real-time log file monitoring and error handling.

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

The script also listens to the SIGHUP signals, that are typically sent during log rotation processes in Unix systems. When it receives a SIGHUP signal, it closes the current file handle, reopens the file, and resets the current position to 0 using the `handle_sighup` function.

When an error pattern is detected in the log file, the `run_command` method of the `EventHandler` class executes the provided command using the `subprocess.call` method. After running the command, the script waits for the specified wait time before resuming the monitoring of the log file.

When the `EventHandler` object is destroyed, the `__del__` method is called. This method closes the log file handle if it is open.