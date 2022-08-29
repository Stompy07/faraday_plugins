"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
import re

from faraday_plugins.plugins.plugin import PluginBase


__author__ = "Francisco Amato"
__copyright__ = "Copyright (c) 2013, Infobyte LLC"
__credits__ = ["Francisco Amato"]
__license__ = ""
__version__ = "1.0.0"
__maintainer__ = "Francisco Amato"
__email__ = "famato@infobytesec.com"
__status__ = "Development"

valid_records = ["NS", "CNAME", "A"]


class FierceParser:
    """
    The objective of this class is to parse an shell output generated by
    the fierce tool.

    TODO: Handle errors.
    TODO: Test fierce output version. Handle what happens if the parser
    doesn't support it.
    TODO: Test cases.

    @param fierce_filepath A proper simple report generated by fierce
    """

    def __init__(self, output):
        self.target = None
        self.items = []

        regex = re.search(
            "DNS Servers for ([\\w\\.-]+):\n([^$]+)Trying zone transfer first...",
            output)

        if regex is not None:
            self.target = regex.group(1)
            mstr = re.sub("\t", "", regex.group(2))
            self.dns = list(filter(None, mstr.splitlines()))

        regex = re.search(
            "Now performing [\\d]+ test\\(s\\)...\n([^$]+)\nSubnets found ",
            output)
        if regex is not None:
            hosts_list = regex.group(1).splitlines()
            for i in hosts_list:
                if i != "":
                    mstr = i.split("\t")
                    host = mstr[1]
                    record = "A"
                    ip = mstr[0]
                    self.add_host_info_to_items(ip, host, record)

        self.isZoneVuln = False
        output = output.replace('\\$', '')
        regex = re.search(
            "Whoah, it worked - misconfigured DNS server found:([^$]+)\nThere isn't much point continuing, "
            "you have  everything.", output)

        if regex is not None:
            self.isZoneVuln = True
            dns_list = regex.group(1).splitlines()
            for i in dns_list:
                if i != "":
                    mstr = i.split()
                    if (mstr and mstr[0] != "" and len(mstr) > 3 and mstr[3] in valid_records):
                        host = mstr[0]
                        record = mstr[3]
                        ip = mstr[4]
                        self.add_host_info_to_items(ip, host, record)

    def add_host_info_to_items(self, ip_address, hostname, record):
        data = {}
        exists = False
        for item in self.items:
            if ip_address in item['ip']:
                item['hosts'].append(hostname)
                exists = True

        if not exists:
            data['ip'] = ip_address
            data['hosts'] = [hostname]
            data['record'] = record
            self.items.append(data)


class FiercePlugin(PluginBase):
    """
    Example plugin to parse fierce output.
    """

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.id = "Fierce"
        self.name = "Fierce Output Plugin"
        self.plugin_version = "0.0.1"
        self.version = "0.9.9"
        self.options = None
        self._current_output = None
        self._command_regex = re.compile(
            r'^(sudo fierce|fierce|sudo fierce\.pl|fierce\.pl|perl fierce\.pl|\.\/fierce\.pl)\s+.*?')


    def resolveCNAME(self, item, items):
        for i in items:
            if (item['ip'] in i['hosts']):
                item['ip'] = i['ip']
                return item
        try:
            item['ip'] = self.resolve_hostname(item['ip'])
        except:
            pass  # nosec
        return item

    def resolveNS(self, item, items):
        try:
            item['hosts'][0] = item['ip']
            item['ip'] = self.resolve_hostname(item['ip'])
        except:
            pass
        return item

    def parseOutputString(self, output):

        parser = FierceParser(output)
        for item in parser.items:

            item['isResolver'] = False
            item['isZoneVuln'] = False
            if item['record'] == "CNAME":
                self.resolveCNAME(item, parser.items)
            if item['record'] == "NS":
                self.resolveNS(item, parser.items)
                item['isResolver'] = True
                item['isZoneVuln'] = parser.isZoneVuln
                for item2 in parser.items:

                    if item['ip'] == item2['ip'] and item != item2:
                        item2['isResolver'] = item['isResolver']
                        item2['isZoneVuln'] = item['isZoneVuln']
                        item['ip'] = ''

        for item in parser.items:
            if item['ip'] == "127.0.0.1" or item['ip'] == '':
                continue
            h_id = self.createAndAddHost(
                item['ip'],
                hostnames=item['hosts'])

            if item['isResolver']:
                s_id = self.createAndAddServiceToHost(
                    h_id,
                    "domain",
                    "tcp",
                    ports=['53'])

                if item['isZoneVuln']:
                    self.createAndAddVulnToService(
                        h_id,
                        s_id,
                        "Zone transfer",
                        desc="A Dns server allows unrestricted zone transfers",
                        ref=["CVE-1999-0532"])


def createPlugin(*args, **kwargs):
    return FiercePlugin(*args, **kwargs)
