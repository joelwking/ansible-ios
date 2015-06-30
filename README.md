# ansible-ios
Ansible modules for managing Cisco IOS devices.

## Summary
This module was writtent to address a use case of a Consulting SE of WWT who is working on a Cisco ISE (Identity Services Engine) deployment for a customer. To implement ISE, each switch port in the network must have configuration statements added as well as global configuration statements added to the switch configuration.

The configuration file is stored on an FTP server. The file may be the same configuration for all devices or unique configuration files could be templated with Ansible, and stored on the server.

The module initiates an SSH session to the target device, optionally issues the command and password to enter enable mode (priviledge level 15), saves a copy of the running configuration to a file on NVRAM, configures the device from the URL specified (FTP, TFTP, etc.) and then saves a copy of the updated running config to the startup configuration.

## Alternate Use Cases
This module could also be used as a mechanism to update configurations for iWAN or Cisco Virtual Office router deployments.
