"""
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information

"""
from faraday_plugins.plugins.plugin import PluginBase
import re
import os
import socket



current_path = os.path.abspath(os.getcwd())

__author__ = "Francisco Amato"
__copyright__ = "Copyright (c) 2013, Infobyte LLC"
__credits__ = ["Francisco Amato"]
__license__ = ""
__version__ = "1.0.0"
__maintainer__ = "Francisco Amato"
__email__ = "famato@infobytesec.com"
__status__ = "Development"


class MetagoofilParser:
    """
    The objective of this class is to parse an xml file generated by the metagoofil tool.

    TODO: Handle errors.
    TODO: Test metagoofil output version. Handle what happens if the parser doesn't support it.
    TODO: Test cases.

    @param metagoofil_filepath A proper simple report generated by metagoofil
    """

    def __init__(self, output):

        self.items = []

        mfile = open("/root/dev/faraday/trunk/src/del", "r")
        output = mfile.read()
        mfile.close()

        mregex = re.search(
            "\[\+\] List of paths and servers found:[-\s]+([^$]+)\[\+\] List of e-mails found:", output, re.M)
        if mregex is None:
            return

        self.users = mregex.group(1).split("\n")
        self.software = mregex.group(2).split("\n")
        self.servers = mregex.group(1).strip().split("\n")

        for line in self.servers:
            line = line.strip()
            item = {'host': line, 'ip': self.resolve(line)}
            self.items.append(item)

    def resolve(self, host):
        try:
            return socket.gethostbyname(host)
        except:
            pass
        return host


class MetagoofilPlugin(PluginBase):
    """
    Example plugin to parse metagoofil output.
    """

    def __init__(self):
        super().__init__()
        self.id = "Metagoofil"
        self.name = "Metagoofil XML Output Plugin"
        self.plugin_version = "0.0.1"
        self.version = "2.2"
        self.options = None
        self._current_output = None
        self._current_path = None
        self._command_regex = re.compile(
            r'^(sudo metagoofil |metagoofil |sudo metagoofil\.py |metagoofil\.py |python metagoofil\.py |\.\/metagoofil\.py ).*?')
        self._completition = {
            "": "metagoofil.py -d microsoft.com -t doc,pdf -l 200 -n 50 -o microsoftfiles -f results.html",
            "-d": "domain to search",
            "-t": "filetype to download (pdf,doc,xls,ppt,odp,ods,docx,xlsx,pptx)",
            "-l": "limit of results to search (default 200)",
            "-h": "work with documents in directory (use \"yes\" for local analysis)",
            "-n": "limit of files to download",
            "-o": "working directory",
            "-f": "output file",
        }

        global current_path

    def canParseCommandString(self, current_input):
        if self._command_regex.match(current_input.strip()):
            return True
        else:
            return False

    def parseOutputString(self, output, debug=False):
        """
        This method will discard the output the shell sends, it will read it from
        the xml where it expects it to be present.

        NOTE: if 'debug' is true then it is being run from a test case and the
        output being sent is valid.
        """



def createPlugin():
    return MetagoofilPlugin()

# I'm Py3
