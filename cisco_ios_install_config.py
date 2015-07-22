#!/usr/bin/env python
#
#
"""
     Copyright (c) 2014 World Wide Technology, Inc. 
     All rights reserved. 

     Revision history:
     26 June 2015  |  1.0 - initial release
     22 July 2015  |  1.1 - handle exceptions if SSH is refused by host

"""

DOCUMENTATION = """
---
module: cisco_ios_install_config
author: Joel W. King, World Wide Technology
version_added: "1.1"
short_description: Updates the configuration of an IOS router or switch over the network.
description:
    - This module saves the existing running configuration, updates the configuration over the network, and
      saves the updated running configuration to the startup-configuration.

 
requirements:
    - paramiko can be a little hacky to install, some notes to install:
        sudo apt-get install python-dev
        sudo pip install pycrypto
        sudo pip install ecdsa

options:
    host:
        description:
            - The IP address or hostname of router or switch, the node we are configuring.
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
            - The enable password of the router or switch, only needed of the user account is not priviledge 15 at login.
        required: false

    URI:
        description:
            - The URL where the configuration commands are stored.
        required: true
    
    debug:
        description:
            - A switch to enable debug logging to a file. Use a value of 'on' to enable. Enabling this option will
              create a log file in /tmp, be careful as the passwords are printed in the log output!
         required: false

"""
EXAMPLES = """

    Using the test module:

   ./hacking/test-module -m /home/administrator/ansible/lib/ansible/modules/extras/network/cisco_ios_install_config.py 
                         -a "URI=ftp://sandbox:XXpasswdXX@10.255.40.101/sdn/lab_config_files/ios_config.cfg 
                             username=admin password=foo enablepw=foo debug=on host=10.255.138.120"


    Using a roles based playbook:


    ~/ansible$ cat /etc/ansible/hosts

    [IOS_routers]
    isr-2911-a.example.net
    isr-2911-b.example.net


    ~/ansible$ cat Fred_W_ISE_deployment.yml
    ---
    - name:  Ansible module to facilitate an ISE Deployment
      hosts:  IOS_routers
      connection: local
      gather_facts: no

      roles:
       - ios

    ~/ansible$ cat ./roles/ios/tasks/main.yml
    ---
     - name:  Update IOS to use google's nameserver
       cisco_ios_install_config:
           URI: ftp://foo:bar@10.255.40.101/sdn/lab_config_files/ios_config.cfg
           host: "{{ inventory_hostname }}"
           username: admin
           password: XXXpasswordXXX
           enablepw: XXXpasswordXXX
           debug: on


    ~/ansible$ curl ftp://foo:bar@10.255.40.101/sdn/lab_config_files/ios_config.cfg
    #
    #
    ip name-server vrf management 8.8.8.8
    #


    ~/ansible$ ./bin/ansible-playbook Fred_W_ISE_deployment.yml

"""

import paramiko
import hashlib
import json
import time
import datetime
import logging
import sys

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logfilename = "cisco_ios_install_config"
logger = logging.getLogger(logfilename)
hdlrObj = logging.FileHandler("/tmp/%s_%s.log" % (logfilename, time.strftime("%j")))
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlrObj.setFormatter(formatter)
logger.addHandler(hdlrObj)
logger.setLevel(logging.INFO)

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
    BUFFER_LEN = 4098                                      # length of buffer to receive in bytes

    def __init__(self, ssh_conn = None):

        self.enable = None
        self.debug = False
        self.URL = "ftp://foo:bar@ftpserver/sdn/lab_config_files/ios_config.cfg"
        self.hostname = "router"
        self.error_msg = None
        self.privilege = IOS.USER                          # <0-15>  User privilege level, default is 1
        self.ssh_conn = ssh_conn                           # paramiko has two objects, a connect object
        self.ssh = None                                    # and an the exec object
                                                           # override default policy to reject all unknown servers
        self.ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())



    def __terminal(self, width=512, length=0):
        "Set terminal line parameters"

        self.__send_command("terminal width %s\n" % width)
        output = self.__get_output()
        self.__send_command("terminal length %s\n" % length)
        output = self.__get_output()
        return



    def __send_command(self, command, timer=TIMER):
        """  Send data to the channel.
             Commands need to be paced due to the RTT,
             allow time for the remote host to respond.
        """

        time.sleep((timer / 2))                            # Short nap before we get started
        if self.debug:
            logger.info('%s SENT:%s' % (self.hostname, command.translate(None, "\n\r")))
        self.ssh.send(command)
        time.sleep(timer)                                  # Allow time for the command output to return
        return



    def __get_output(self):
        "  Receive data from the channel."

        output = ""
        while self.ssh.recv_ready():
            output = output + self.ssh.recv(IOS.BUFFER_LEN)
        
        if self.debug:
            logger.info('%s RECV:%s' % (self.hostname, output.translate(None, "\n\r")))
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
        output = self.__get_output()
        return



    def login(self, ip, user, pw):
        " Logon the node, clear MOTD banners and set the terminal width and length"
      

        try:
            self.ssh_conn.connect(ip, timeout=3.9, username=user, password=pw)
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
        self.ssh.close()
        return self.ssh.closed



    def get_hashed_filename(self):
        "  "
        return "%s_%s.cfg" % (self.hostname, hashlib.md5(time.asctime()).hexdigest())
        


    def get_error_msg(self):
        " return error messages saved from exceptions when attempting to login the host"
        return self.error_msg



    def set_debug(self, value):
        "set the debug value, the variable value, could be a NoneType"
        if str(value) in "true True on On":
            self.debug = True
            logger.setLevel(logging.DEBUG)
            logger.debug("exiting set_debug with debug=%s" % self.debug)



    def enable_mode(self, enable):
        """ Enter enable mode if required. """
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



    def save_config(self, filename="startup-config"):
        " By default, save to startup, otherwise, use the filename provided."
        self.__send_command("copy running-config %s \n" % filename)
        self.__send_command("\n")
        output = self.__get_output()
        for keyword in IOS.COPY:
            if keyword in output:
                return True

        return False



    def update_config(self, URL):
        "  Updates the running configuration from a remote file."

        self.URL = URL
        self.__send_command("copy %s running-config\n" % URL)
        self.__send_command("\n")                          # enter return to acknowledge.
        output = self.__get_output()
        for error in IOS.ERROR:
            if error in output:
                self.error_msg = output

        if self.error_msg:
            return False

        return True



# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    " "

    module = AnsibleModule(
        argument_spec = dict(
            URI = dict(required=True),
            host = dict(required=True),
            username = dict(required=True),
            password  = dict(required=True),
            enablepw = dict(required=False),
            debug = dict(required=False)
         ),
        check_invalid_arguments=False,
        add_file_common_args=True
    )

    node = IOS(paramiko.SSHClient())
    node.set_debug(module.params["debug"])

    if node.login(module.params["host"], module.params["username"], module.params["password"]):  
        node.enable_mode((module.params["enablepw"]))
        if node.save_config(filename=node.get_hashed_filename()):
            if node.update_config(module.params["URI"]):
                if node.save_config():
                    node.logoff
                    module.exit_json(changed=True, content="Success")
                else:
                    node.logoff
                    module.fail_json(changed=True, msg="Configuration updated, failure on save to NVRAM.")
            else:
                node.logoff
                module.fail_json(msg="Failed to update configuration.")
        else:
            node.logoff
            module.fail_json(msg="Save config failure.")
    else:
        module.fail_json(msg= node.get_error_msg())


                                  
from ansible.module_utils.basic import *
main()
