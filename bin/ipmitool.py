#!/usr/bin/env python

from collections import namedtuple
import sys
import getopt
import logging

import pyipmi
import pyipmi.interfaces

IPMITOOL_VERSION = 0.1

Command = namedtuple('Command', 'name fn')
CommandHelp = namedtuple('CommandHelp', 'name arguments help')

# print helper
def _print(s):
    print s

def _get_command_function(name):
    for cmd in COMMANDS:
        if cmd.name == name:
            return cmd.fn
    else:
        return None

def cmd_bmc_info(ipmi, args):
    id = ipmi.get_device_id()
    print '''
Device ID:          %(id)s
Device Revision:    %(revision)s
Firmware Revision:  %(major_fw_revision)d.%(minor_fw_revision)d
IPMI Version:       %(major_ipmi_version)d.%(minor_ipmi_version)d
Manufacturer ID:    %(manufacturer_id)d (0x%(manufacturer_id)04x)
Product ID:         %(product_id)d (0x%(product_id)04x)
Device Available:   %(available)d
Provides SDRs:      %(provides_sdrs)d
Additional Device Support:
'''[1:-1] % id.__dict__

    functions = (
            ('SENSOR', 'Sensor Device'),
            ('SDR_REPOSITORY', 'SDR Repository Device'),
            ('SEL', 'SEL Device'),
            ('FRU_INVENTORY', 'FRU Inventory Device'),
            ('IPMB_EVENT_RECEIVER', 'IPMB Event Receiver'),
            ('IPMB_EVENT_GENERATOR', 'IPMB Event Generator'),
            ('BRIDGE', 'Bridge'),
            ('CHASSIS', 'Chassis Device')
    )
    for n, s in functions:
        if id.supports_function(n):
            print '  %s' % s

    if id.aux is not None:
        print 'Aux Firmware Rev Info:  [%02x %02x %02x %02x]' % (
                id.aux[0], id.aux[1], id.aux[2], id.aux[3])

def cmd_sdr_show(ipmi, args):
    if len(args) != 1:
        usage()
        return

    try:
        s = ipmi.get_sdr(int(args[0], 0))
        if s.type is pyipmi.sensor.SDR_TYPE_FULL_SENSOR_RECORD:
            raw = ipmi.get_sensor_reading(s.number)
            value = s.convert_sensor_reading(raw)
            print "SDR record ID:    0x%04x" % s.id
            print "Device Id string: %s" % s.device_id_string
            print "reading:          %s" % value
        else:
            print "SDR record ID:    0x%04x" % s.id
            print "Device Id string: %s" % s.device_id_string
    except ValueError:
        print ''

def cmd_sdr_list(ipmi, args):
    print "SDR-ID | Device String    |"
    print "=======|==================|===================="

    for s in ipmi.sdr_entries():
        if s.type is pyipmi.sensor.SDR_TYPE_FULL_SENSOR_RECORD:
            raw = ipmi.get_sensor_reading(s.number)
            value = s.convert_sensor_reading(raw)

            print "0x%04x | %-16s | %s" % (s.id, s.device_id_string, value)

        else:
            print "0x%04x | %-16s |" % (s.id, s.device_id_string)

def usage(toplevel=False):
    commands = []
    maxlen = 0

    if toplevel:
        argv = []
    else:
        argv = sys.argv[1:]

    # (1) try to find help for commands on exactly one level above
    for cmd in COMMAND_HELP:
        subcommands = cmd.name.split(' ')
        if (len(subcommands) == len(argv) + 1
                and subcommands[:len(argv)] == argv):
            commands.append(cmd)
            if cmd.arguments:
                maxlen = max(maxlen, len(cmd.name)+len(cmd.arguments)+1)
            else:
                maxlen = max(maxlen, len(cmd.name))

    # (2) if nothing found, try to find help on any level above
    if maxlen == 0:
        for cmd in COMMAND_HELP:
            subcommands = cmd.name.split(' ')
            if (len(subcommands) > len(argv) + 1 
                    and subcommands[:len(argv)] == argv):
                commands.append(cmd)
                if cmd.arguments:
                    maxlen = max(maxlen, len(cmd.name)+len(cmd.arguments)+1)
                else:
                    maxlen = max(maxlen, len(cmd.name))

    # (3) find help on same level
    if maxlen == 0:
        for cmd in COMMAND_HELP:
            subcommands = cmd.name.split(' ')
            if (len(subcommands) == len(argv)
                    and subcommands[:len(argv)] == argv):
                commands.append(cmd)
                if cmd.arguments:
                    maxlen = max(maxlen, len(cmd.name)+len(cmd.arguments)+1)
                else:
                    maxlen = max(maxlen, len(cmd.name))

    # if still nothing found, print toplevel usage
    if maxlen == 0:
        usage(toplevel=True)
        return

    if len(argv) == 0:
        version()
        print 'usage: ipmitool [options...] <command>'
        print 'Commands:'

    for cmd in commands:
        name = cmd.name
        if cmd.arguments:
            name = '%s %s' % (name, cmd.arguments)
        print '  %-*s   %s' % (maxlen, name, cmd.help)

def version():
    print 'ipmitool v%s' % IPMITOOL_VERSION
    
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 't:hvVI:H:U:P:')
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    verbose = False
    interface = 'aardvark'
    target_address = 0x20
    rmcp_host = None
    rmcp_user = ''
    rmcp_password = ''
    for o, a in opts:
        if o == '-v':
            verbose = True
        elif o == '-h':
            usage()
            sys.exit()
        elif o == '-V':
            version()
            sys.exit()
        elif o == '-t':
            target_address = int(a, 0)
        elif o == '-H':
            rmcp_host = a
        elif o == '-U':
            rmcp_user = a
        elif o == '-P':
            rmcp_password = a
        elif o == '-I':
            interface = a
        else:
            assert False, 'unhandled option'

    # fake sys.argv
    sys.argv = [sys.argv[0]] + args

    if len(args) == 0:
        usage()
        sys.exit(1)

    handler = logging.StreamHandler()
    if verbose:
        handler.setLevel(logging.DEBUG)
    else:
        handler.setLevel(logging.INFO)
    pyipmi.logger.add_log_handler(handler)
    pyipmi.logger.set_log_level(logging.DEBUG)

    for i in xrange(len(args)):
        cmd = _get_command_function(' '.join(args[0:i+1]))
        if cmd is not None:
            args = args[i+1:]
            break
    else:
        usage()
        sys.exit(1)

    interface = pyipmi.interfaces.create_interface(interface)
    ipmi = pyipmi.create_connection(interface)
    ipmi.target = pyipmi.Target(target_address)

    if rmcp_host is not None:
        ipmi.session.set_session_type_rmcp(rmcp_host)
        ipmi.session.set_auth_type_user(rmcp_user, rmcp_password)
        ipmi.session.establish()

    try:
        cmd(ipmi, args)
    except pyipmi.errors.CompletionCodeError, e:
        print 'Command returned with completion code 0x%02x' % e.cc
    except pyipmi.errors.TimeoutError, e:
        print 'Command timed out'

    if rmcp_host is not None:
        ipmi.session.close()

COMMANDS = (
        Command('bmc info', cmd_bmc_info),
        Command('bmc reset cold', lambda i, a: i.cold_reset()),
        Command('bmc reset warm', lambda i, a: i.warm_reset()),
        Command('sel list', lambda i, a: map(_print, i.sel_entries())),
        Command('sdr list', cmd_sdr_list),
        Command('sdr show', cmd_sdr_show),
)

COMMAND_HELP = (
#        CommandHelp('raw', None, 'Send a RAW IPMI request and print response'),
#        CommandHelp('fru', None,
#                'Print built-in FRU and scan SDR for FRU locators'),
#        CommandHelp('sensor', None, 'Print detailed sensor information'),
#        CommandHelp('sdr', None,
#                'Print Sensor Data Repository entries and readings'),
#        CommandHelp('chassis', None, 'Get chassis status and set power state'),

        CommandHelp('sel', None, 'Print System Event Log (SEL)'),
        CommandHelp('sel list', None, 'List all SEL entries'),

        CommandHelp('sdr', None, 'Print SDRs '),
        CommandHelp('sdr list', None, 'List all SDRs'),
        CommandHelp('sdr show', '<sdr-id>', 'List all SDRs'),

        CommandHelp('bmc', None,
                'Management Controller status and global enables'),
        CommandHelp('bmc info', None, 'BMC Device ID inforamtion'),
        CommandHelp('bmc reset', '<cold|warm>', 'BMC reset control'),
)

if __name__ == '__main__':
    main()
