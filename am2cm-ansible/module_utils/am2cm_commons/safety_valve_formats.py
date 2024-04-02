import logging
from abc import ABC, abstractmethod

import dicttoxml
import xmltodict

LOG = logging.getLogger(__name__)


class SafetyValveInterface(ABC):
    @abstractmethod
    def convert_response_to_dict(self, response_to_convert: str):
        pass

    @abstractmethod
    def convert_dict_to_value_to_write_back(self, dict_to_convert: dict):
        pass


class XmlImplementation(SafetyValveInterface):
    def convert_response_to_dict(self, response_to_convert: str):
        if response_to_convert is None:
            return {}
        if '<configuration>' not in response_to_convert:
            parsed = "<configuration>" + response_to_convert + "</configuration>"  # need configuration for parsing
        else:
            parsed = response_to_convert
        dummy_root_cut_off = (xmltodict.parse(parsed, force_list=('property',)))['configuration']
        return dict((my_item['name'], my_item['value']) for my_item in dummy_root_cut_off['property'])  # flatten

    def convert_dict_to_value_to_write_back(self, dict_to_convert: dict):
        exportable_dict = dict({"property": list({'name': key, 'value': value}
                                                 for key, value in dict_to_convert.items())})
        result = dicttoxml.dicttoxml(exportable_dict["property"], attr_type=False, root=False,
                                     item_func=lambda a: "property")
        return result.decode()


class PropertyFileImplementation(SafetyValveInterface):
    def convert_response_to_dict(self, response_to_convert: str):
        if response_to_convert is None or response_to_convert == "":
            return {}
        split_by_line = [line.split("=") for line in response_to_convert.split("\n")
                         if line and len(line.split('=')) == 2]  # additional check for empty string & incorrect format
        return {key: value for key, value in split_by_line}

    def convert_dict_to_value_to_write_back(self, dict_to_convert: dict):
        return "\n".join("=".join(tuple(my_tuple)) for my_tuple in dict_to_convert.items())
