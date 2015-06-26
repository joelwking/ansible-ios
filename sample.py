#!/usr/bin/env python
#
#
#==============================================================================
# author: Joel W. King, World Wide Technology
#==============================================================================

REFERENCES = """

   https://github.com/npug/network-scripts/blob/master/router-login/router-login.py
   https://pynet.twb-tech.com/blog/python/paramiko-ssh-part1.html

"""

DOCUMENTATION = """


  Sample IOS code to put the user into Priviledge Level 15 (enable) mode

        aaa new-model
        aaa authentication login default local
        aaa authorization exec default local
        aaa session-id common
        username foo privilege 15 secret XXXpasswordXXX
        line vty 0 5
          transport input ssh

"""

import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

ip = "10.255.138.121"
ssh.connect(ip, username="foo", password="XXXpasswordXXX")

print "### %s" % time.asctime()
stdin, stdout, stderr = ssh.exec_command('copy running-config startup-config')
stdin.write("\n")                          # hit a return for the command

for line in stdout.readlines():
    print line,

ssh.close()
print "\n### %s" % time.asctime()


OUTPUT = """
### Fri Jun 26 09:43:18 2015
C
 UNAUTHORIZED ACCESS TO THIS NETWORK DEVICE IS PROHIBITED.
 You must have explicit permission to access or configure this
 device. All activities performed on this device are logged and
 violations of this policy may result in disciplinary action.

 onePK Development Router


Destination filename [startup-config]? 
Building configuration...
[OK] 
### Fri Jun 26 09:43:21 2015
"""
