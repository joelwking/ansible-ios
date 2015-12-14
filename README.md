# ansible-ios
Ansible modules for managing Cisco IOS devices.

## Summary
These modules were written to address specific use cases of Ansible managing Cisco IOS routers and switches.

## Module: cisco_ios_show.py
This module was written to address a customer need for capturing the output of a series of show commands (including the running configuration) for the purposes of auditing a network of 300-500 devices. A sample playbook is shown in the file ios_show.yml. While it assumes the devices are specified in an inventory file, the playbook could be modified to use APIC-EM as the source of the inventory by way of the module apic_em_gather_facts.py in https://github.com/joelwking/ansible-apic-em

## Module: cisco_ios_install_config.py
This module was written to address a use case of a Consulting SE of WWT who is working on a Cisco ISE (Identity Services Engine) deployment for a customer. To implement ISE, each switch port in the network must have configuration statements added as well as global configuration statements added to the switch configuration.

The configuration file is stored on an FTP server. The file may be the same configuration for all devices or unique configuration files could be templated with Ansible, and stored on the server.

The module initiates an SSH session to the target device, optionally issues the command and password to enter enable mode (priviledge level 15), saves a copy of the running configuration to a file on NVRAM, configures the device from the URL specified (FTP, TFTP, etc.) and then saves a copy of the updated running config to the startup configuration.

### Alternate Use Cases
This module could also be used as a mechanism to update configurations for iWAN or Cisco Virtual Office router deployments.
