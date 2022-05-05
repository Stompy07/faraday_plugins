#!/usr/bin/env python
"""
Faraday Penetration Test IDE
Copyright (C) 2016  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
"""
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from dateutil.parser import parse

from faraday_plugins.plugins.plugin import PluginXMLFormat

__author__ = 'Blas Moyano'
__copyright__ = 'Copyright 2020, Faraday Project'
__credits__ = ['Blas Moyano']
__license__ = ''
__version__ = '1.0.0'
__status__ = 'Development'


class QualysWebappParser:
    def __init__(self, xml_output):
        self.tree = self.parse_xml(xml_output)
        if self.tree:
            if self.tree.find('RESULTS/WEB_APPLICATION'):
                self.info_results = self.get_results_vul(self.tree.find('RESULTS/WEB_APPLICATION'))
            else:
                self.info_results = self.get_results_vul(self.tree.find('RESULTS'))
            self.info_glossary = self.get_glossary_qid(self.tree.find('GLOSSARY'))
            self.info_appendix = self.get_appendix(self.tree.find('APPENDIX'))
        else:
            self.tree = None

    def parse_xml(self, xml_output):
        try:
            tree = ET.fromstring(xml_output)
        except SyntaxError as err:
            print(f'SyntaxError In xml: {err} {xml_output}')
            return None
        return tree

    @staticmethod
    def get_appendix(tree):
        for appendix_tags in tree:
            yield Appendix(appendix_tags)

    @staticmethod
    def get_glossary_qid(tree):
        for glossary_tags in tree.find('QID_LIST'):
            yield Glossary(glossary_tags)

    @staticmethod
    def get_results_vul(tree):
        for results_tags in tree.find('VULNERABILITY_LIST'):
            yield Results(results_tags)


class Appendix:
    def __init__(self, appendix_tags):
        if appendix_tags.tag == 'SCAN_LIST':
            self.lista_scan = self.get_scan(appendix_tags.find('SCAN'))

        elif appendix_tags.tag == 'WEBAPP':
            self.lista_webapp = self.get_webapp(appendix_tags)

    @staticmethod
    def get_scan(appendix_tags):
        result_scan = {}
        for scan in appendix_tags:
            result_scan[scan.tag] = scan.text
        return result_scan

    @staticmethod
    def get_webapp(appendix_tags):
        result_webapp = {}
        for webapp in appendix_tags:
            result_webapp[webapp.tag] = webapp.text
        return result_webapp


class Glossary:
    def __init__(self, glossary_tags):
        self.lista_qid = self.get_qid_list(glossary_tags)

    def get_qid_list(self, qid_list_tags):
        self.dict_result_qid = {}
        for qid in qid_list_tags:
            self.dict_result_qid[qid.tag] = qid.text
        return self.dict_result_qid


class Results:
    def __init__(self, glossary_tags):
        self.lista_vul = self.get_qid_list(glossary_tags)

    def get_qid_list(self, vul_list_tags):
        self.dict_result_vul = {}
        for vul in vul_list_tags:
            self.dict_result_vul[vul.tag] = vul.text
        return self.dict_result_vul


class QualysWebappPlugin(PluginXMLFormat):

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.identifier_tag = ["WAS_WEBAPP_REPORT", "WAS_SCAN_REPORT"]
        self.id = 'QualysWebapp'
        self.name = 'QualysWebapp XML Output Plugin'
        self.plugin_version = '1.0.0'
        self.version = '1.0.0'
        self.framework_version = '1.0.0'
        self.options = None
        self.protocol = None
        self.port = '80'
        self.address = None

    def parseOutputString(self, output):
        hostnames = []

        parser = QualysWebappParser(output)

        if not parser.info_appendix:
            return

        self.scan_list_result = []
        for host_create in parser.info_appendix:
            self.scan_list_result.append(host_create)

        operating_system = ""
        for k in self.scan_list_result:
            if 'result_scan' in k.__dict__:
                self.credential = k.lista_scan.get('AUTHENTICATION_RECORD')
            elif 'result_webapp' in k.__dict__:
                operating_system = k.lista_webapp.get('OPERATING_SYSTEM')
                if k.lista_webapp.get('URL'):
                    initial_url = k.lista_webapp.get('URL')
                    parsed_url = urlparse(initial_url)
                    hostnames = [parsed_url.netloc]

        glossary = []
        for glossary_qid in parser.info_glossary:
            glossary.append(glossary_qid.dict_result_qid)

        for v in parser.info_results:
            url = urlparse(v.dict_result_vul.get('URL'))
            host_id = self.createAndAddHost(name=url.netloc, os=operating_system, hostnames=hostnames)

            vuln_scan_id = "QUALYS-"+v.dict_result_vul.get('QID')

            # Data in the xml is in different parts, we look into the glossary
            vuln_data = next((item for item in glossary if item["QID"] == vuln_scan_id), None)
            vuln_name = vuln_data.get('TITLE')
            vuln_desc = vuln_data.get('DESCRIPTION') + v.dict_result_vul.get('URL')

            raw_severity = int(vuln_data.get('SEVERITY', 0))
            vuln_severity = raw_severity - 1

            if not v.dict_result_vul.get('FIRST_TIME_DETECTED'):
                run_date = ''
            else:
                run_date = parse(v.dict_result_vul.get('FIRST_TIME_DETECTED'))

            vuln_resolution = vuln_data.get('SOLUTION')

            vuln_ref = []
            if vuln_data.get('CVSS_BASE'):
                vuln_ref = [f"CVSS: {vuln_data.get('CVSS_BASE')}"]

            vuln_data_add = f"ID: {v.dict_result_vul.get('ID')}, DETECTION_ID: {v.dict_result_vul.get('DETECTION_ID')}" \
                            f", CATEGORY: {vuln_data.get('CATEGORY')}, GROUP: {vuln_data.get('GROUP')}" \
                            f", URL: {v.dict_result_vul.get('URL')}, IMPACT: {vuln_data.get('IMPACT')}"

            self.createAndAddVulnToHost(host_id=host_id, name=vuln_name, desc=vuln_desc, ref=vuln_ref,
                                        severity=vuln_severity, resolution=vuln_resolution, run_date=run_date,
                                        external_id=vuln_scan_id, data=vuln_data_add)


def createPlugin(ignore_info=False):
    return QualysWebappPlugin(ignore_info=ignore_info)
