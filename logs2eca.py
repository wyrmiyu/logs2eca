#!/usr/bin/env python3
"""
This script monitors a log file for events and runs a command when an event
is detected. It uses pyinotify to monitor the log file, and the subprocess
module to run the command.
"""

from pathlib import Path
from typing import Pattern

import argparse
import logging
import os
import re
import signal
import subprocess
import sys
import time
import uuid

import pyinotify


logging.basicConfig(level=logging.ERROR)

# Constants
RE_INDICATORS = ('/', '|', '%')
DEFAULT_LOGS2ECA_WAIT = 3
DEFAULT_ARBITRARY_MATCH = False


class ArgumentParsingError(Exception):
    pass


class MainExecutionError(Exception):
    pass


class MissingRequiredArgumentError(Exception):
    pass


class PatternMatchError(Exception):
    pass


class SIGHUPHandlingError(Exception):
    pass


def parse_args():
    """
    This function parses the command line arguments. It will return a
    argparse.Namespace object, which has attributes that correspond to
    the command line arguments. The function uses a dictionary with
    the following data structure to define the command line arguments:
    dict = {
        'arg_name': {
            'opts': ['--arg_name', '-a'],
            'required': True,  # or False
            'type': str,  # or int, float, bool, etc.
            'metavar': 'arg_value', # e.g. file, string, int, etc.
            'env': 'ENV_VAR_NAME', # e.g. LOGS2ECA_LOG_FILE
            'default': const, # e.g. DEFAULT_LOGS2ECA_LOG_FILE or None
            'help': 'help message',
            },
        ...
    }
    returns: Namespace[
        logfile,
        pattern,command,
        wait,
        arbitrary_substring_match
    ]
    """

    try:
        desc = ('Monitor a log file for events and run a command when '
                'an event is detected.')
        re_chars = ", ".join(list(RE_INDICATORS))
        epilogue = (
            "When the pattern is a string, the pattern will be matched "
            "using Python's substring matching with the 'in' operator. "
            "By default, logs2eca adds a space at the start and end of both "
            "the line and the pattern to ensure that only whole words are "
            "matched. However, if you want to match the pattern as "
            "a pure substring, you can use the `--arbitrary-substring-match` "
            "option. Do note that this option will also match the pattern "
            "as a substring of other words. For example, the pattern 'foo' "
            "will match all of the following strings: 'foobar', 'foofoobar', "
            "'bazbarfoobar', etc. "
            "Regular expressions must be enclosed in any of the following "
            f"characters: {re_chars}. However, you don't need to escape those "
            "characters, even if you use them in the actual regex pattern.")
        arg_parser = argparse.ArgumentParser(
            description=desc,
            epilog=epilogue,
            add_help=False,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        required = arg_parser.add_argument_group('Required arguments')
        optional = arg_parser.add_argument_group('Optional arguments')

        arg_dict = {
            'logfile': {
                "opts": ["--logfile", "-l"],
                "required": True,
                "type": str,
                "metavar": "FILE",
                "env": "LOGS2ECA_LOG_FILE",
                "default": "",
                "help": "The log file to monitor for events.",
            },
            "pattern": {
                "opts": ["--pattern", "-p"],
                "required": True,
                "type": str,
                "metavar": "STRING|REGEX",
                "env": "LOGS2ECA_EVENT_PATTERN",
                "default": "",
                "help": (
                    "The pattern to match in the log file, which can be "
                    "either a string or a regular expression."
                    ),
            },
            "command": {
                "opts": ["--command", "-c"],
                "required": True,
                "type": str,
                "metavar": "CMD",
                "env": "LOGS2ECA_COMMAND",
                "default": "",
                "help": "The command to run when an event is detected.",
            },
            "wait": {
                "opts": ["--wait", "-w"],
                "required": False,
                "type": int,
                "metavar": "int",
                "env": "LOGS2ECA_WAIT",
                "default": DEFAULT_LOGS2ECA_WAIT,
                "help": (
                    "The number of seconds to wait before resuming monitoring "
                    "the log file after an event has been detected."
                ),
            },
            "arbitrary_substring_match": {
                "opts": ["--arbitrary-substring-match", "-a"],
                "required": False,
                "type": bool,
                "metavar": None,
                "env": "LOGS2ECA_ARBITRARY_MATCH",
                "default": DEFAULT_ARBITRARY_MATCH,
                "help": (
                    "If the pattern is a string, this flag will make logs2eca "
                    "match the pattern as *any* substring of a line instead "
                    "of a word in a line."
                ),
            },
        }

        for arg, params in arg_dict.items():
            env = params.get("env")
            arg_default = params.get("default")
            if (env and os.environ.get(env)):
                arg_default = os.environ.get(env)

            arg_help = params.get("help")
            if (env):
                if (params.get("required")):
                    arg_help = (f'{arg_help} Can only be omitted if provided '
                                f'with the environment variable: {env}')
                else:
                    arg_help = (f'{arg_help} Can optionally be provided with '
                                f'the environment variable: {env}')

            arg_group = optional
            if (params.get("required")):
                arg_group = required
            # Since both commandline arguments and environment variables are
            # used to set the arguments, and argparse only considers
            # command-line arguments when checking for required arguments,
            # we set required=False and check for missing arguments manually.
            if (params.get("type") == bool):
                arg_group.add_argument(
                    *params.get("opts"),
                    required=False,
                    action="store_true",
                    dest=arg,
                    help=arg_help)
            else:
                arg_group.add_argument(
                    *params.get("opts"),
                    required=False,
                    type=params.get("type"),
                    dest=arg,
                    metavar=params.get("metavar"),
                    default=arg_default,
                    help=arg_help)

        optional.add_argument(
            '--help', '-h',
            help='Show this help message and exit',
            action='help',
            default=argparse.SUPPRESS)

        args = arg_parser.parse_args()

        # Verify all required arguments are provided
        missing_args = []
        for arg, params in arg_dict.items():
            if (params.get("required") and getattr(args, arg) is None):
                missing_args.append(arg)
        if missing_args:
            raise MissingRequiredArgumentError(
                f'Missing required argument: {arg}'
            )

    except argparse.ArgumentError as e:
        raise ArgumentParsingError(f'Error parsing arguments: {str(e)}')

    except Exception as e:
        raise ArgumentParsingError(
            f'Unexpected error during argument parsing: {str(e)}'
        )

    return args


class EventHandler(pyinotify.ProcessEvent):
    """
    pyinoify.ProcessEvent is a class that handles events triggered by the
    pyinotify.WatchManager. It has methods for handling different types
    of events. We will be using the following methods:
        process_IN_MODIFY  - triggered when the log file is modified
        process_IN_CREATE  - triggered when the log file is created
        process_IN_DELETE  - triggered when the log file is deleted
        process_IN_MOVED_FROM - triggered when the log file is moved
    """

    def my_init(self,
                logfile,
                pattern,
                command,
                wait,
                arbitrary_substring_match):
        """
        This method is called by __init__ and is meant for user-defined
        initialization. It performs the following:

        1. Sets up:
            - The logfile, pattern, command, wait and arbitrary_substring_match
            attributes.
            - The file attribute, which is a file handle to the logfile.
            - The current_position attribute, which is the current position of
            the file handle.

        2. If the logfile does not exist, the file attribute is set to None,
        and the current position to 0.

        3. Creates an unique id for the logs2eca instance to distinct it from
        other instances, the format is: <UUID>, where UUID is a 8 letter
        hexadecimal string generated by uuid.uuid4().

        4. Sets up the pattern_match attribute, which is a function that
        returns True if the pattern is found in the line passed to it, and
        False otherwise.
            - If the pattern is a string, it will check if the pattern is
            found either as a substring or as a word in the line depending on
            the arbitrary_substring_match attribute.
            - If the pattern is a regular expression, it will check if
            the pattern matches
        """

        self.logfile = Path(logfile).absolute()
        self.pattern = pattern
        self.command = command
        self.wait = wait
        self.arbitrary_substring_match = arbitrary_substring_match
        # Create an unique id for the logs2eca instance to distinct it from
        # other instances, the format is: <UUID>, where UUID is
        # a 8 letter hexadecimal string generated by uuid.uuid4()
        self.id = f"<{uuid.uuid4().hex[:8]}>"

        if (self.logfile.exists()):
            try:
                print(f"{self.id} Logfile '{self.logfile}' exists")
                self.current_position = self.logfile.stat().st_size
                self.file = open(self.logfile, 'a+')
                self.file.seek(self.current_position)
            except PermissionError:
                raise MainExecutionError(
                    f"Permission denied to open file '{self.logfile}'"
                )
            except FileNotFoundError:
                raise MainExecutionError(
                    f"File '{self.logfile}' does not exist"
                )
        else:
            warn = (f"[warn] Logfile '{self.logfile}' does not exist, "
                    "will wait for it to be created.")
            print(warn)
            self.file = None
            self.current_position = 0

        try:
            # Check if the pattern is a string or a regex pattern
            if (isinstance(self.pattern, str)):
                if (self.arbitrary_substring_match):
                    # If arbitrary string match is allowed, simply check if
                    # pattern is a substring of the line
                    self.pattern_match = lambda line: self.pattern in line
                else:
                    # If arbitrary string match is not allowed, use a method
                    # that ensures word match only
                    self.pattern_match = self.match_words
            else:
                # Assuming Pattern is a regex pattern
                self.pattern_match = lambda line: self.pattern.search(line)

        except (TypeError, AttributeError):
            raise PatternMatchError(f"Invalid pattern '{self.pattern}'")

    def match_words(self, line):
        # Add space at start and end of line to allow matching pattern
        # at the start and end of the line
        line = f" {line} "
        # Add space at start and end of pattern to ensure only whole words
        # are matched
        pattern = f" {self.pattern} "
        return pattern in line

    def process_IN_MODIFY(self, event):
        """
        This method will read the log file from the lastknown position to the
        end of the file, and if the pattern is found in any of the lines, it
        will call the run_command method.
        """

        if (Path(event.pathname) == self.logfile):
            if (self.file):
                self.file.seek(self.current_position)
                for line in self.file:
                    line = line.strip()
                    if (self.id in line):
                        continue
                    if (self.pattern_match(line)):
                        print(f"{self.id} Event: {line.strip()}")
                        if isinstance(self.pattern, Pattern):
                            info = (f"{self.id} Matching the regex pattern: "
                                    f"{self.pattern.pattern}")
                            print(info)
                        else:
                            info = (f"{self.id} Matching the pattern: "
                                    f"{self.pattern}")
                            print(info)
                        self.run_command()
                self.current_position = self.file.tell()

    def process_IN_CREATE(self, event):
        """
        This method will close the current file handle (if any), open a new
        one, and reset the current position to 0.
        """

        if (Path(event.pathname) == self.logfile):
            print(f"{self.id} Logfile '{self.logfile}' created")
            self.file = open(self.logfile, 'a+')
            self.current_position = 0

    def process_IN_DELETE(self, event):
        """
        Handles IN_DELETE events, which are triggered when the log file is
        deleted. This method will close the current file handle, and set it to
        None, and reset the current position to 0.
        """

        if (Path(event.pathname) == self.logfile):
            info = (f"{self.id} Logfile '{self.logfile}' deleted, "
                    "closing and waiting for it to be re-created.")
            print(info)
            if (self.file):
                self.file.close()
            self.file = None

    def process_IN_MOVED_FROM(self, event):
        """
        This method will run the command specified by the user. It will print
        the command to stdout, and then run it using the subprocess module.
        It will then sleep for the number of seconds specified by the user.
        """

        if (Path(event.pathname) == self.logfile):
            info = (f"{self.id} Logfile '{self.logfile}' moved, "
                    "closing and waiting for it to be re-created.")
            print(info)
            if (self.file):
                self.file.close()
            self.file = None

    def run_command(self):
        """
        This method will run the command specified by the user. It will print
        the command to stdout, and then run it using the subprocess module.
        It will then sleep for the number of seconds specified by the user.
        """

        try:
            print(f"{self.id} Running command: '{self.command}'")
            result = subprocess.run(self.command,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            # Print the output of the command
            if result.stdout:
                print(f"Command stdout: {result.stdout.decode('utf-8')}")
            if result.stderr:
                result_error = ("Command stderr: "
                                f"{result.stderr.decode('utf-8')}")
                print(result_error, file=sys.stderr)

        except FileNotFoundError:
            raise MainExecutionError(f"Command '{self.command}' not found")
        except subprocess.CalledProcessError as e:
            subprocess_error = (f"Command '{self.command}' "
                                f"failed with error:  {str(e)}")
            raise MainExecutionError(subprocess_error)

        time.sleep(self.wait)

    def __del__(self):
        """
        Handles SIGHUP signals. This method will close the current file handle
        (if any), open a new one, and reset the current position to 0.
        """
        if (self.file):
            self.file.close()


class LogFileMonitor:
    """
    This class is the main class of the program. It will parse the command
    line arguments, and then create an instance of the EventHandler class,
    and then start the pyinotify.Notifier.
    """
    def __init__(self):
        """
        This method will declare the handler attribute, which is an instance
        of the EventHandler class.
        """
        self.handler = None

    def handle_sighup(self, signal, frame):
        """
        Handles SIGHUP signals. This method will close the current file handle
        (if any), open a new one, and reset the current position to 0.
        """
        try:
            print("[info] Received SIGHUP")
            if self.handler and self.handler.file:
                self.handler.file.close()
                self.handler.file = open(self.handler.logfile, 'r')
                self.handler.current_position = 0
        except IOError as e:
            logging.error(f'Error handling SIGHUP signal: {str(e)}')
        except Exception as e:
            logging.error(f'Unexpected error during SIGHUP handling: {str(e)}')

    def run(self):
        try:
            args = parse_args()
            signal.signal(signal.SIGHUP, self.handle_sighup)
            pattern = args.pattern.strip()
            for indicator in RE_INDICATORS:
                if (
                    pattern.startswith(indicator) and
                    pattern.endswith(indicator)
                ):
                    try:
                        pattern = re.compile(pattern[1:-1])
                        break
                    except re.error:
                        raise ArgumentParsingError(
                            f"Invalid regular expression pattern '{pattern}'"
                        )

            wm = pyinotify.WatchManager()
            self.handler = EventHandler(
                logfile=args.logfile.strip(),
                pattern=pattern,
                command=args.command.strip(),
                wait=args.wait,
                arbitrary_substring_match=args.arbitrary_substring_match)
            notifier = pyinotify.Notifier(wm, self.handler)
            wm.add_watch(str(Path(args.logfile).parent), pyinotify.ALL_EVENTS)
            notifier.loop()
        except Exception as e:
            raise MainExecutionError(
                f'Unexpected error during the main execution: {str(e)}')


if (__name__ == "__main__"):
    try:
        monitor = LogFileMonitor()
        monitor.run()
    except MissingRequiredArgumentError as e:
        print(str(e), file=sys.stderr)
    except KeyboardInterrupt:
        print('Interrupted by user', file=sys.stderr)
    except (ArgumentParsingError,
            MainExecutionError,
            PatternMatchError,
            SIGHUPHandlingError) as e:
        print(str(e), file=sys.stderr)
        raise
