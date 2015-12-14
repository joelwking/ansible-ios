#!/usr/bin/env python
#
#
"""
     Copyright (c) 2015 World Wide Technology, Inc.
     All rights reserved.

     Revision history:
     10 December 2015  |  1.0 - initial release
     12 December 2015  |  1.1 - PEP 8 updates
     13 December 2015  |  1.2 - Enable password logic enhancements

"""

DOCUMENTATION = """
---
module: cisco_ios_show
author: Joel W. King, World Wide Technology
version_added: "1.2"
short_description: Issues show commands to IOS devices
description:
    - This module issues a list of show commands to Cisco IOS based network devices, captures the results of the commands in a file.

requirements:
    - paramiko can be a little hacky to install, some notes to install:
        sudo apt-get install python-dev
        sudo pip install pycrypto
        sudo pip install ecdsa

options:
    host:
        description:
            - The IP address or hostname of router or switch.
        required: true

    username:
        description:
            - Login username.
        required: true

    password:
        description:
            - Login password.
        required: true

    enablepw:
        description:
            - The enable password of the router or switch. If present, will attempt to authenticate into enable mode
        required: false

    dest:
        description:
            - The destination directory to write the output file.
        required: true
    
    debug:
        description:
            - A switch to enable debug logging to a file. Use a value of 'on' to enable.
         required: false

"""
EXAMPLES = """

  vars:
   runcmd:
     - show running-config
     - show version
     - show license
     - show inventory
     - show module
     - show cdp neighbor detail

  tasks:
  - name: Issue the commands specified in the list runcmd and output to a file
    cisco_ios_show:
      host: "{{inventory_hostname}}"
      username: admin
      password: redacted
      enablepw: redacted
      commands: "{{runcmd}}"
      dest: /tmp
      debug: on

"""

import paramiko
import time

# ---------------------------------------------------------------------------
# IOS
# ---------------------------------------------------------------------------

class IOS(object):
    """ Class for managing the SSH connection and updating a router or switch
        configuration from a remote host
    """
    ENABLE = 15                                            # Privilege EXEC mode
    USER = 1                                               # User EXEC mode
    ERROR = ["Error opening", "Invalid input"]             # Possible error messages from IOS
    COPY = ["[OK]", "bytes copied"]                        # Possible success criteria for copy command
    TIMER = 3.0                                            # Paces the command and response from node, seconds
    BUFFER_LEN = 4096                                      # length of buffer to receive in bytes

    def __init__(self, ssh_conn=None):

        self.enable = None                                 # Enable mode is an optional parameter
        self.debug = False
        self.hostname = "router"
        self.output_file = "cis"                           # prefix for the output file(s)
        self.file_obj = None
        self.error_msg = None
        self.privilege = IOS.USER                          # <0-15>  User privilege level, default is 1
        self.ssh_conn = ssh_conn                           # paramiko has two objects, a connect object
        self.ssh = None                                    # and an the exec object
                                                           # override default policy to reject all unknown servers
        self.ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())



    def __terminal(self, width=512, length=0):
        "Set terminal line parameters"

        self.__send_command("terminal width %s\n" % width)
        self.__get_output()
        self.__send_command("terminal length %s\n" % length)
        self.__get_output()
        return



    def __send_command(self, command, timer=TIMER):
        """  Send data to the channel.
             Commands need to be paced due to the RTT,
             allow time for the remote host to respond.
        """

        time.sleep((timer / 2))                            # Short nap before we get started
        self.ssh.send(command)
        time.sleep(timer)                                  # Allow time for the command output to return
        return



    def __get_output(self):
        "  Receive data from the channel."

        output = ""
        while self.ssh.recv_ready():
            output = output + self.ssh.recv(IOS.BUFFER_LEN)

        return output



    def __determine_privilege_level(self):
        """ determine the hostname and privilege level
           '\r\nisr-2911-a#' would be a privilege level of 15
           if there is a ">" at the end of the output string, we need to go into enable mode
           if there is a "#" at the end, we are already in enable mode
        """

        self.__send_command("\n")                          # send a return to get back a prompt
        output = self.__get_output()
        if output[-1] == "#":
            self.privilege = 15

        self.hostname = output[2:-1]                       # glean the hostname from '\r\nisr-2911-a#'
        return self.privilege



    def __clear_banners(self):
        """
           after logon, the buffer will contain the banner exec and MOTD text, clear it!
           you might have both a banners, hit return once.
        """

        self.__send_command("\n")
        self.__get_output()
        return



    def login(self, hostname, user, password):
        " Logon the node, clear MOTD banners and set the terminal width and length"

        self.hostname = hostname
        try:
            self.ssh_conn.connect(hostname, timeout=3.9, username=user, password=password)
        except paramiko.ssh_exception.AuthenticationException as msg:
            self.error_msg = str(msg)
            return False
        except paramiko.ssh_exception.SSHException as msg:
            self.error_msg = str(msg)
            return False
        except:
            self.error_msg = "No connection could be made to target machine"
            return False

        self.ssh = self.ssh_conn.invoke_shell()
        self.__clear_banners()
        self.__terminal()
        return True



    def logoff(self):
        "  Returns True or False"
        self.close_output_file()
        self.ssh.close()
        return self.ssh.closed



    def get_error_msg(self):
        " return error messages saved from exceptions when attempting to login the host."
        return self.error_msg



    def set_debug(self, value):
        "set the debug value, the variable value, could be a NoneType if not specified."
        if str(value) in "true True on On":
            self.debug = True


    def enable_mode(self, enable):
        """ Enter enable mode if required. As it is optional, Ansible will pass the value as None (type 'NoneType') 
            test if not provided and exit true, assuming that there are no commands which require enable mode to issue.
            Test if we are already in enable mode and also return True, otherwise, provide the enable password.
        """ 
        if enable is None:
            return True

        self.enable = enable
        if self.__determine_privilege_level() == IOS.ENABLE:
            return True

        self.__send_command("enable\n")                    # send command
        self.__send_command("%s\n" % self.enable)          # send enable password
        self.__send_command("\n")                          # send return
        output = self.__get_output()
        if "Access denied" in output:
            return False

        return True



    def close_output_file(self):
        " Close the output file."
        self.file_obj.close()
        return



    def open_output_file(self, destination_directory, hostname):
        " Create a unique output filename and open it for writing, check if user included trailing slash "
        if destination_directory[-1] == "/":
            destination_directory = destination_directory[:-1]
        self.output_file = "%s/%s_%s_%s.log" % (destination_directory, self.output_file, hostname, time.strftime("%j"))
        try:
            self.file_obj = open(self.output_file, "a")
        except:
            return False
        return True



    def issue_commands(self, commands):
        "the playbook as provided us a list of commands to issue against the device."
        self.file_obj.write(" ### %s %s ###\r\n" % (time.asctime(), self.hostname))
        for item in commands:
            self.__send_command("%s\n" % item)
            output = self.__get_output()
            self.file_obj.write(output)
        return True



# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    "main"

    module = AnsibleModule(
        argument_spec=dict(
            host=dict(required=True),
            username=dict(required=True),
            password=dict(required=True),
            enablepw=dict(required=False),
            commands=dict(required=True),
            dest=dict(required=True),
            debug=dict(required=False)
        ),
        check_invalid_arguments=False,
        add_file_common_args=True
    )

    node = IOS(paramiko.SSHClient())
    node.set_debug(module.params["debug"])

    if node.open_output_file(module.params["dest"], module.params["host"]):
        pass
    else:
        module.fail_json(msg="Error opening output file.")

                                                           # LOGIN
    if node.login(module.params["host"], module.params["username"], module.params["password"]):
        if node.enable_mode((module.params["enablepw"])):  # ENABLE MODE
            pass
        else:
            node.logoff()
            module.fail_json(msg="Enable password specified and an error occured entering enable mode.")

        if node.issue_commands(module.params["commands"]): # ISSUE COMMANDS
            node.logoff()
            module.exit_json(changed=False, content="Success.")
        else:
            node.logoff()
            module.fail_json(msg="Error issuing commands.")
    else:
        module.fail_json(msg=node.get_error_msg())



from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
