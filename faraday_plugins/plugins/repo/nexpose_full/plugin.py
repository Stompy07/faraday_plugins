"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
import re
import xml.etree.ElementTree as ET

from faraday_plugins.plugins.plugin import PluginXMLFormat
from faraday_plugins.plugins.plugins_utils import CVE_regex

__author__ = "Micaela Ranea Sanchez"
__copyright__ = "Copyright (c) 2013, Infobyte LLC"
__credits__ = ["Francisco Amato", "Federico Kirschbaum",
               "Micaela Ranea Sanchez", "German Riera"]
__license__ = ""
__version__ = "1.0.0"
__maintainer__ = "Micaela Ranea Sanchez"
__email__ = "mranea@infobytesec.com"
__status__ = "Development"


class NexposeFullXmlParser:
    """
    The objective of this class is to parse Nexpose's XML 2.0 Report.

    TODO: Handle errors.
    TODO: Test nexpose output version. Handle what happens if the parser doesn't support it.
    TODO: Test cases.

    @param xml_filepath A proper xml generated by nexpose
    """

    def __init__(self, xml_output):
        tree = self.parse_xml(xml_output)
        self.vulns = self.get_vuln_definitions(tree)

        if tree:
            self.items = self.get_items(tree, self.vulns)
        else:
            self.items = []

    @staticmethod
    def get_severity_from_report(score):
        try:
            if not isinstance(score, float):
                score = float(score)

            cvss_ranges = [(0.0, 3.4, 'med'),
                           (3.5, 7.4, 'high'),
                           (7.5, 10.1, 'critical')]
            for (lower, upper, severity) in cvss_ranges:
                if lower <= score < upper:
                    return severity
        except ValueError:
            return 'unclassified'

    @staticmethod
    def parse_xml(xml_output):
        """
        Open and parse an xml file.

        TODO: Write custom parser to just read the nodes that we need instead of
        reading the whole file.

        @return xml_tree An xml tree instance. None if error.
        """
        try:
            tree = ET.fromstring(xml_output)
        except SyntaxError as err:
            return None

        return tree

    def parse_html_type(self, node: ET.Element) -> str:
        """
        Parse XML element of type HtmlType

        @return ret A string containing the parsed element
        """
        ret = ""
        tag: str = node.tag.lower()
        if tag == 'containerblockelement':
            if len(list(node)) > 0:
                for child in list(node):
                    ret += self.parse_html_type(child)
            else:
                ret += node.text.strip() if node.text else ""
        if tag == 'listitem':
            if len(list(node)) > 0:
                for child in list(node):
                    ret += self.parse_html_type(child)
            else:
                ret = node.text.strip() if node.text else ""
        if tag == 'orderedlist':
            i = 1
            for item in list(node):
                ret += "\t" + str(i) + " " + self.parse_html_type(item) + "\n"
                i += 1
        if tag == 'paragraph':
            if len(list(node)) > 0:
                for child in list(node):
                    ret += self.parse_html_type(child)
            else:
                ret += node.text.strip() if node.text else ""
        if tag == 'unorderedlist':
            for item in list(node):
                ret += "\t" + "* " + self.parse_html_type(item) + "\n"
        if tag == 'urllink':
            if node.get('text'):
                ret += node.text.strip() + " "
            last = ""
            for attr in node.attrib:
                if node.get(attr) and node.get(attr) != node.get(last):
                    ret += node.get(attr) + " "
                last = attr

        return ret

    def parse_tests_type(self, node, vulnsDefinitions):
        """
        Parse XML element of type TestsType

        @return vulns A list of vulnerabilities according to vulnsDefinitions
        """
        vulns = list()

        for tests in node.findall('tests'):
            for test in tests.iter('test'):
                if test.get('id').lower() in vulnsDefinitions:
                    vuln = vulnsDefinitions[test.get('id').lower()].copy()
                    key = test.get('key', '')
                    vuln['pci'] = test.get('pci-compliance-status')
                    vuln['vulnerable_since'] = test.get('vulnerable-since')
                    vuln['scan_id'] = test.get('scan-id')
                    if key.startswith('/'):
                        # It has the path where the vuln was found
                        # Example key: "/comments.asp||content"
                        vuln['path'] = key[:key.find('|')]
                    for desc in list(test):
                        vuln['desc'] += self.parse_html_type(desc)
                    vulns.append(vuln)
        return vulns

    def get_vuln_definitions(self, tree):
        """
        @returns vulns A dict of Vulnerability Definitions
        """
        vulns = dict()

        for vulnsDef in tree.iter('VulnerabilityDefinitions'):
            for vulnDef in vulnsDef.iter('vulnerability'):
                vid = vulnDef.get('id').lower()
                vector = vulnDef.get('cvssVector')
                vuln = {
                    'desc': "",
                    'name': vulnDef.get('title'),
                    'refs': [],
                    'resolution': "",
                    'severity': self.get_severity_from_report(vulnDef.get('severity')),
                    'tags': list(),
                    'is_web': vid.startswith('http-'),
                    'risk': vulnDef.get('riskScore'),
                    'CVE': [],
                    'cvss2': {
                        "vector_string": vector.replace("(", "").replace(")", "") if vector else None
                    }
                }

                for item in list(vulnDef):
                    if item.tag == 'description':
                        for htmlType in list(item):
                            vuln['desc'] += self.parse_html_type(htmlType)
                    if item.tag == 'exploits':
                        for exploit in list(item):
                            if exploit.get('title') and exploit.get('link') and exploit.get('type') \
                                    and exploit.get('skillLevel'):
                                title = exploit.get('title').strip()
                                link = exploit.get('link').strip()
                                type = exploit.get('type').strip()
                                skillLevel = exploit.get('skillLevel').strip()
                                vuln['refs'].append(" ".join([title, link, type, skillLevel]))
                    if item.tag == 'malware':
                        for names in item.findall("name"):
                            nameMalware = names.text
                            vuln['refs'].append(nameMalware)
                    if item.tag == 'references':
                        for ref in list(item):
                            if not ref.text:
                                continue
                            source = ""
                            if "source" in ref.attrib:
                                source = ref.attrib['source'] + ": "
                            rf = ref.text.strip()
                            check = CVE_regex.search(rf.upper())
                            if check:
                                vuln["CVE"].append(check.group())
                            else:
                                if rf.isnumeric():
                                    rf = source + rf
                                vuln['refs'].append(rf)
                    if item.tag == 'solution':
                        for htmlType in list(item):
                            vuln['resolution'] += self.parse_html_type(htmlType)

                """
                # there is currently no method to register tags in vulns
                if item.tag == 'tags':
                    for tag in list(item):
                        vuln['tags'].append(tag.text.lower())
                """
                vulns[vid] = vuln
        return vulns

    def get_items(self, tree, vulns):
        """
        @return hosts A list of Host instances
        """

        hosts = list()

        for nodes in tree.iter('nodes'):
            for node in nodes.iter('node'):
                host = dict()
                host['name'] = node.get('address')
                host['mac'] = node.get('hardware-address')
                host['hostnames'] = list()
                host['os'] = ""
                host['services'] = list()
                host['vulns'] = self.parse_tests_type(node, vulns)

                for names in node.iter('names'):
                    for name in list(names):
                        host['hostnames'].append(name.text)

                for fingerprints in node.iter('fingerprints'):
                    for os_data in fingerprints.iter('os'):
                        os_name = os_data.get('product')
                        if os_name:
                            host['os'] = os_name
                for endpoints in node.iter('endpoints'):
                    for endpoint in list(endpoints):
                        svc = {
                            'protocol': endpoint.get('protocol'),
                            'port': endpoint.get('port'),
                            'status': endpoint.get('status'),
                        }
                        for services in endpoint.iter('services'):
                            for service in list(services):
                                svc['name'] = service.get('name')
                                svc['vulns'] = self.parse_tests_type(
                                    service, vulns)
                                for configs in service.iter('configurations'):
                                    for config in list(configs):
                                        if "banner" in config.get('name'):
                                            svc['version'] = config.get('name')
                        host['services'].append(svc)
                hosts.append(host)

        return hosts


class NexposeFullPlugin(PluginXMLFormat):
    """
    Example plugin to parse nexpose output.
    """

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.identifier_tag = "NexposeReport"
        self.id = "NexposeFull"
        self.name = "Nexpose XML 2.0 Report Plugin"
        self.plugin_version = "0.0.1"
        self.version = "Nexpose Enterprise 5.7.19"
        self.framework_version = "1.0.0"
        self.options = None

    def parseOutputString(self, output):

        parser = NexposeFullXmlParser(output)

        for item in parser.items:
            pattern = '([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
            if not item['mac']:
                item['mac'] = '0000000000000000'
            match = re.search(pattern, item['mac'])
            if match:
                mac = item['mac']
            else:
                mac = ':'.join(item['mac'][i:i + 2] for i in range(0, 12, 2))
            h_id = self.createAndAddHost(item['name'], item['os'], hostnames=item['hostnames'], mac=mac)
            for v in item['vulns']:
                v['data'] = {"vulnerable_since": v['vulnerable_since'], "scan_id": v['scan_id'], "PCI": v['pci']}
                self.createAndAddVulnToHost(
                    h_id,
                    v['name'],
                    v['desc'],
                    v['refs'],
                    v['severity'],
                    v['resolution'],
                    cve=v.get('CVE'),
                    cvss2=v.get('cvss2')
                )

            for s in item['services']:
                version = s.get("version", "")
                s_id = self.createAndAddServiceToHost(
                    h_id,
                    s['name'],
                    s['protocol'],
                    ports=[str(s['port'])],
                    status=s['status'],
                    version=version)

                for v in s['vulns']:

                    if v['is_web']:
                        self.createAndAddVulnWebToService(
                            h_id,
                            s_id,
                            v['name'],
                            v['desc'],
                            v['refs'],
                            v['severity'],
                            v['resolution'],
                            cve=v.get('CVE'),
                            path=v.get('path', ''),
                            cvss2=v.get('cvss2')
                        )
                    else:
                        self.createAndAddVulnToService(
                            h_id,
                            s_id,
                            v['name'],
                            v['desc'],
                            v['refs'],
                            v['severity'],
                            v['resolution'],
                            cve=v.get('CVE'),
                            cvss2=v.get('cvss2')
                        )

        del parser


def createPlugin(*args, **kwargs):
    return NexposeFullPlugin(*args, **kwargs)
