"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from faraday_plugins.plugins.plugin import PluginXMLFormat
from faraday_plugins.plugins.plugins_utils import resolve_hostname

__author__ = "Francisco Amato"
__copyright__ = "Copyright (c) 2013, Infobyte LLC"
__credits__ = ["Francisco Amato"]
__license__ = ""
__version__ = "1.0.0"
__maintainer__ = "Francisco Amato"
__email__ = "famato@infobytesec.com"
__status__ = "Development"


class WapitiXmlParser:
    """
    The objective of this class is to parse an xml file generated by the wapiti tool.

    TODO: Handle errors.
    TODO: Test wapiti output version. Handle what happens if the parser doesn't support it.
    TODO: Test cases.

    @param wapiti_xml_filepath A proper xml generated by wapiti
    """

    def __init__(self, xml_output):
        tree = self.parse_xml(xml_output)
        if tree:
            self.items = [data for data in self.get_items(tree)]
        else:
            self.items = []

    def parse_xml(self, xml_output):
        """
        Open and parse an xml file.

        TODO: Write custom parser to just read the nodes that we need instead of
        reading the whole file.

        @return xml_tree An xml tree instance. None if error.
        """
        try:
            tree = ET.fromstring(xml_output)
        except SyntaxError as err:
            print("SyntaxError: %s. %s" % (err, xml_output))
            return None

        return tree

    def get_items(self, tree):
        """
        @return items A list of Host instances
        """

        yield Item(tree)


def get_attrib_from_subnode(xml_node, subnode_xpath_expr, attrib_name):
    """
    Finds a subnode in the item node and the retrieves a value from it

    @return An attribute value
    """

    node = xml_node.find(subnode_xpath_expr)
    if node is not None:
        return node.get(attrib_name)
    return None


class Item:
    """
    An abstract representation of a Item

    TODO: Consider evaluating the attributes lazily
    TODO: Write what's expected to be present in the nodes
    TODO: Refactor both Host and the Port clases?

    @param item_node A item_node taken from an wapiti xml tree
    """

    def __init__(self, item_node):
        self.node = item_node
        self.url = self.get_url(item_node)
        if self.url.hostname is not None:
            self.ip = resolve_hostname(self.url.hostname)
        else:
            self.ip = '0.0.0.0'
        self.hostname = self.url.hostname
        self.port = self.get_port(self.url)
        self.scheme = self.url.scheme
        self.vulns = self.get_vulns(item_node)

    def do_clean(self, value):
        myreturn = ""
        if value is not None:
            myreturn = re.sub("\n", "", value)
        return myreturn

    def get_text_from_subnode(self, node, subnode_xpath_expr):
        """
        Finds a subnode in the host node and the retrieves a value from it.

        @return An attribute value
        """
        sub_node = node.find(subnode_xpath_expr)
        if sub_node is not None:
            return sub_node.text.strip()

        return None

    def get_url(self, item_node):
        target = self.get_info(item_node, 'target')
        return urlparse(target)

    def get_info(self, item_node, name):
        path = item_node.findall('report_infos/info')

        for item in path:
            if item.attrib['name'] == name:
                return item.text

    def get_port(self, url):
        if url.port:
            return url.port
        else:
            if url.scheme == "http":
                return "80"
            elif url.scheme == "https":
                return "443"

    def get_vulns(self, item_node):
        vulns_node = item_node.findall('vulnerabilities/vulnerability')
        vulns_list = []

        for vuln in vulns_node:
            vulns_dict = {}
            vulns_dict['id'] = vuln.attrib['name']
            vulns_dict['description'] = self.get_text_from_subnode(vuln, 'description')
            vulns_dict['solution'] = self.get_text_from_subnode(vuln, 'solution')
            vulns_dict['references'] = self.get_references(vuln)
            vulns_dict['entries'] = self.get_entries(vuln)
            vulns_list.append(vulns_dict)

        return vulns_list

    def get_references(self, node):
        refs = node.findall('references/reference')
        references_list = []
        for ref in refs:
            references_list.append('Title: ' + self.get_text_from_subnode(ref, 'title'))
            references_list.append('URL: ' + self.get_text_from_subnode(ref, 'url'))

        return references_list

    def get_entries(self, node):
        entries = node.findall('entries/entry')
        entries_list = []
        for entry in entries:
            entries_dict = {}
            entries_dict['method'] = self.get_text_from_subnode(entry, 'method')
            entries_dict['path'] = self.get_text_from_subnode(entry, 'path')
            entries_dict['level'] = self.severity_format(entry)
            entries_dict['parameter'] = self.get_text_from_subnode(entry, 'parameter')
            entries_dict['http_request'] = self.get_text_from_subnode(entry, 'http_request')
            entries_dict['curl_command'] = self.get_text_from_subnode(entry, 'curl_command')
            entries_list.append(entries_dict)

        return entries_list

    def severity_format(self, node):
        """
        Convert Nexpose severity format into Faraday API severity format

        @return a severity
        """
        severity = self.get_text_from_subnode(node, 'level')

        if severity == '1':
            return 'high'
        elif severity == '2':
            return 'medium'
        elif severity == '3':
            return 'low'


class WapitiPlugin(PluginXMLFormat):
    """
    Example plugin to parse wapiti output.
    """

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.identifier_tag = "report"
        self.id = "Wapiti"
        self.name = "Wapiti XML Output Plugin"
        self.plugin_version = "0.0.1"
        self.version = "2.2.1"
        self.options = None
        self.protocol = None
        self.host = None
        self.port = "80"
        self._use_temp_file = True
        self._temp_file_extension = "xml"
        self.xml_arg_re = re.compile(r"^.*(-oX\s*[^\s]+).*$")
        self._command_regex = re.compile(
            r'^(python wapiti|wapiti|sudo wapiti|sudo wapiti\.py|wapiti\.py|python wapiti\.py|\.\/wapiti\.py|wapiti |\.'
            r'\.\/wapiti|python wapiti|python \.\/wapiti)\s+.*?')
        self._completition = {
            "": "python wapiti.py http://server.com/base/url/ [options]",
            "-s": "&lt;url&gt; ",
            "--start": "&lt;url&gt; ",
            "-x": "&lt;url&gt; ",
            "--exclude": "&lt;url&gt; ",
            "-p": "&lt;url_proxy&gt; ",
            "--proxy": "&lt;url_proxy&gt; ",
            "-c": " -c &lt;cookie_file&gt; ",
            "--cookie": "&lt;cookie_file&gt; ",
            "-t": "&lt;timeout&gt; ",
            "--timeout": "&lt;timeout&gt; ",
            "-a": "&lt;login%password&gt; ",
            "--auth": "&lt;login%password&gt; ",
            "-r": "&lt;parameter_name&gt; ",
            "--remove": "&lt;parameter_name&gt; ",
            "-n": "&lt;limit&gt; ",
            "--nice": "&lt;limit&gt; ",
            "-m": "&lt;module_options&gt; Set the modules and HTTP methods to use for attacks. Example: -m \"-all,"
                  "xss:get,exec:post\"",
            "--module": "&lt;module_options&gt; Set the modules and HTTP methods to use for attacks. Example: -m \"-"
                        "all,xss:get,exec:post\"",
            "-u": "Use color to highlight vulnerables parameters in output",
            "--underline": "Use color to highlight vulnerables parameters in output",
            "-v": "&lt;level&gt; ",
            "--verbose": "&lt;level&gt; ",
            "-b": "&lt;scope&gt;",
            "--scope": "&lt;scope&gt;",
            "-f": "&lt;type_file&gt; ",
            "--reportType": "&lt;type_file&gt; ",
            "-o": "&lt;output_file&gt; ",
            "--output": "&lt;output_file&gt; ",
            "-i": "&lt;file&gt;",
            "--continue": "&lt;file&gt;",
            "-k": "&lt;file&gt;",
            "--attack": "&lt;file&gt;",
            "-h": "To print this usage message",
            "--help": "To print this usage message",
        }

    def report_belongs_to(self, **kwargs):
        if super().report_belongs_to(**kwargs):
            report_path = kwargs.get("report_path", "")
            with open(report_path) as f:
                output = f.read()
            return re.search("Wapiti", output) is not None
        return False

    def parseOutputString(self, output):
        """
        This method will discard the output the shell sends, it will read it from
        the xml where it expects it to be present.
        """

        parser = WapitiXmlParser(output)
        for item in parser.items:
            host_id = self.createAndAddHost(item.ip, hostnames=[item.hostname])
            if item.port is None:
                port = 0
            else:
                port = item.port
            service_id = self.createAndAddServiceToHost(host_id, item.scheme, protocol='tcp', ports=[port])
            for vuln in item.vulns:
                for entry in vuln['entries']:
                    vuln_id = self.createAndAddVulnWebToService(host_id,
                                                                service_id,
                                                                vuln['id'],
                                                                desc=vuln['description'],
                                                                ref=vuln['references'],
                                                                resolution=vuln['solution'],
                                                                severity=entry['level'],
                                                                website=entry['curl_command'],
                                                                path=entry['path'],
                                                                request=entry['http_request'],
                                                                method=entry['method'],
                                                                params=entry['parameter'])

    def processCommandString(self, username, current_path, command_string):
        """
        Adds the -oX parameter to get xml output to the command string that the
        user has set.
        """
        super().processCommandString(username, current_path, command_string)
        host = re.search(
            "(http|https|ftp)\://([a-zA-Z0-9\.\-]+(\:[a-zA-Z0-9\.&amp;%\$\-]+)*@)*((25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]"
            "{2}|[1-9]{1}[0-9]{1}|[1-9])\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2"
            "[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]{1}|[1-9]|0)\.(25[0-5]|2[0-4][0-9]|[0-1]{1}[0-9]{2}|[1-9]{1}[0-9]"
            "{1}|[0-9])|localhost|([a-zA-Z0-9\-]+\.)*[a-zA-Z0-9\-]+\.(com|edu|gov|int|mil|net|org|biz|arpa|info|name|"
            "pro|aero|coop|museum|[a-zA-Z]{2}))[\:]*([0-9]+)*([/]*($|[a-zA-Z0-9\.\,\?\'\\\+&amp;%\$#\=~_\-]+)).*?$",
            command_string)

        self.protocol = host.group(1)
        self.host = host.group(4)
        if host.group(11) is not None:
            self.port = host.group(11)
        if self.protocol == 'https':
            self.port = 443
        self.logger.debug("host = %s, port = %s", self.host, self.port)
        return "%s -o %s -f xml \n" % (command_string, self._output_file_path)


def createPlugin(ignore_info=False):
    return WapitiPlugin(ignore_info=ignore_info)
