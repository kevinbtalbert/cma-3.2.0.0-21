#!/usr/bin/env python3

import argparse
import json
import logging
import os
import re

log_dir = os.getenv('DIFF_LOG_DIR', default=os.path.dirname(__file__))
log_file = os.path.basename(__file__).replace(".py", "_log.log")
LOGGER_FORMAT = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)s - %(funcName)s]: %(message)s'
logging.basicConfig(format=LOGGER_FORMAT, filename=os.path.join(log_dir, log_file),
                    filemode="w", level=logging.INFO)
console_log = logging.StreamHandler()
console_log.setLevel(logging.INFO)
console_log.setFormatter(logging.Formatter(LOGGER_FORMAT))
logging.getLogger().addHandler(console_log)

LOG = logging.getLogger(__name__)


class ConfigRules:
    def __init__(self, config_file_path: str):
        self._config_file = config_file_path
        self._config_rules = ""
        self._ignore_configs = []
        self._ignore_config_properties = {}

        self._parse_rules()

    def _parse_rules(self):
        with open(self._config_file, 'r') as config_file:
            self._config_rules = json.load(config_file)

        self._ignore_configs = self._config_rules.get("ignore_configs")
        self._ignore_config_properties = self._config_rules.get("ignore_config_properties")

    def get_ignored_properties_for_config(self, config_name: str) -> set:
        ignored = []
        if self._ignore_config_properties.get(config_name) is not None:
            ignored.extend(self._ignore_config_properties.get(config_name))
        if self._ignore_config_properties.get("all_configs") is not None:
            ignored.extend(self._ignore_config_properties.get("all_configs"))

        return set(ignored)

    def get_ignored_properties_for_all_configs(self) -> set:
        return set(self._ignore_config_properties.get("all_configs")) \
            if self._ignore_config_properties.get("all_configs") is not None else set()

    def get_ignored_configurations(self) -> set:
        return set(self._ignore_configs)


class BlueprintDiff:

    def __init__(self, config_rules: ConfigRules):
        self.host_group_pairs = None
        self.config_rules = config_rules

    def process_configuration_diffs(self, base_config_list: list, target_config_list: list) -> dict:
        result = dict()
        added = []
        removed = []

        for base_config in [x for x in base_config_list
                            if list(x.keys())[0] not in self.config_rules.get_ignored_configurations()]:
            # for base_config in base_config_list:
            if len(base_config) > 1:
                raise Exception('Configuration item has multiple entries! Structure is incorrect!')
            found = False
            for target_config in [x for x in target_config_list
                                  if list(x.keys())[0] not in self.config_rules.get_ignored_configurations()]:
                # for target_config in target_config_list:
                if len(target_config) > 1:
                    raise Exception('Configuration item has multiple entries! Structure is incorrect!')
                if list(target_config.keys())[0] == list(base_config.keys())[0]:
                    found = True
                    break
            if not found:
                removed.append(list(base_config.keys())[0])

        for target_config in [x for x in target_config_list
                              if list(x.keys())[0] not in self.config_rules.get_ignored_configurations()]:
            # for target_config in target_config_list:
            if len(target_config) > 1:
                raise Exception('Configuration item has multiple entries! Structure is incorrect!')
            found = False
            for base_config in [x for x in base_config_list
                                if list(x.keys())[0] not in self.config_rules.get_ignored_configurations()]:
                # for base_config in base_config_list:
                if len(base_config) > 1:
                    raise Exception('Configuration item has multiple entries! Structure is incorrect!')
                if list(target_config.keys())[0] == list(base_config.keys())[0]:
                    found = True
                    break
            if not found:
                added.append(list(target_config.keys())[0])

        if len(added) > 0:
            result['added_configurations'] = added
        if len(removed) > 0:
            result['removed_configurations'] = removed

        return result

    def _add_or_update_dictionary(self, key: str, dictionary: dict, add_this: dict):
        if key not in dictionary.keys():
            dictionary[key] = add_this
        else:
            dictionary.get(key).update(add_this)

    def process_properties_diffs(self, base_config_list: list, target_config_list: list, configurations_diff: dict,
                                 include_value_changes: bool) -> dict:
        properties_diffs = dict()
        for config in [x for x in base_config_list
                       if list(x.keys())[0] not in self.config_rules.get_ignored_configurations()]:
            config_name = list(config.keys())[0]
            if configurations_diff.get('removed_configurations') is None or config_name not in configurations_diff.get(
              'removed_configurations'):
                base_properties: dict = config.get(config_name).get('properties')
                target_properties = dict()
                for target_config in [x for x in target_config_list
                                      if list(x.keys())[0] not in self.config_rules.get_ignored_configurations()]:
                    if list(target_config.keys())[0] == config_name:
                        target_properties = target_config.get(list(target_config.keys())[0]).get('properties')

                added_prop = []
                removed_prop = []
                for base_prop in [x for x in base_properties
                                  if x not in self.config_rules.get_ignored_properties_for_config(config_name)]:
                    found = False
                    for target_prop in [x for x in target_properties
                                        if x not in self.config_rules.get_ignored_properties_for_config(config_name)]:
                        if target_prop == base_prop:
                            found = True
                            break
                    if not found:
                        removed_prop.append(base_prop)

                for target_prop in [x for x in target_properties
                                    if x not in self.config_rules.get_ignored_properties_for_config(config_name)]:
                    found = False
                    for base_prop in [x for x in base_properties
                                      if x not in self.config_rules.get_ignored_properties_for_config(config_name)]:
                        if target_prop == base_prop:
                            found = True
                            break
                    if not found:
                        added_prop.append(target_prop)

                if len(added_prop) > 0:
                    self._add_or_update_dictionary(config_name, properties_diffs, {'added_properties': added_prop})
                if len(removed_prop) > 0:
                    self._add_or_update_dictionary(config_name, properties_diffs, {'removed_properties': removed_prop})

                if include_value_changes:
                    value_changes = self.process_property_value_changes(
                        {key: val for key, val in base_properties.items()
                         if key not in self.config_rules.get_ignored_properties_for_config(config_name)},
                        {key: val for key, val in target_properties.items()
                         if key not in self.config_rules.get_ignored_properties_for_config(config_name)})
                    if len(value_changes) != 0:
                        self._add_or_update_dictionary(config_name, properties_diffs, {'value_changes': value_changes})

        return properties_diffs

    def process_property_value_changes(self, base_property_dict: dict, target_property_dict: dict) -> dict:
        changes = dict()
        for base_prop in base_property_dict:
            # TODO: process "content" blocks
            base_value = base_property_dict.get(base_prop)
            target_value = target_property_dict.get(base_prop)
            if target_value is None:
                continue

            replaced_value = self._replace_host_group_in_value(target_value, self.host_group_pairs)

            if base_value != replaced_value:
                changes[base_prop] = {'base_value': base_value,
                                      'target_value': target_value}
                LOG.error(f"'base_prop': {base_prop}, 'base_value': {base_value}, "
                          f"'target_value': {target_value}, 'replaced_value': {replaced_value} ")

        return changes

    def get_host_group_pairs(self, base: dict, target: dict) -> dict:
        if len(base) != len(target):
            raise Exception("Given jsons have different amount of host_groups! Unable to compare!")

        base_hosts = dict()
        target_hosts = dict()
        for i in range(0, len(base)):
            hostnames = []
            for host in base[i]['hosts']:
                hostnames.append(host['hostname'])

            base_hosts[base[i]['name']] = hostnames

            hostnames = []
            for host in target[i]['hosts']:
                hostnames.append(host['hostname'])

            target_hosts[target[i]['name']] = hostnames

        matching = dict()
        for source in base_hosts:
            for target in target_hosts:
                if sorted(base_hosts[source]) == sorted(target_hosts[target]):
                    matching[source] = target
                    break

        if len(matching) != len(base_hosts):
            raise Exception('Not all host_groups have pairs!')

        return matching

    def run_blueprint_validators(self, blueprint: json):
        pass

    def load_blueprint(self, file_path: str) -> json:
        blueprint: json
        with open(file_path, 'r') as bp:
            try:
                blueprint = json.load(bp)
            except Exception:
                LOG.error(f"Cannot read '{file_path}'! Not a json file!")
                raise

        self.run_blueprint_validators(blueprint)

        return blueprint

    def handle_configurations_block(self, base_bp, target_bp):
        self.host_group_pairs = self.get_host_group_pairs(base_bp['host_groups'], target_bp['host_groups'])
        configuration_diffs = self.process_configuration_diffs(base_bp['configurations'], target_bp['configurations'])
        config_prop_diffs = self.process_properties_diffs(
            base_bp['configurations'], target_bp['configurations'], configuration_diffs, True)

        final_result = dict()
        final_result.update({'host_group_pairs': self.host_group_pairs})
        final_result.update({'configuration_list_diffs': configuration_diffs})
        final_result.update({'config_property_diffs': config_prop_diffs})

        return final_result

    def _replace_host_group_in_value(self, target_value: str, host_group_pairs: dict) -> str:
        if not re.match(r".*%HOSTGROUP::host_group_\d+%.*", target_value):
            return target_value

        delimiter = '%HOSTGROUP'
        splitted_target_values = target_value.split(delimiter)
        result_value = ''
        for index, splitted_target_value in enumerate(splitted_target_values):
            replaced_target_value = splitted_target_value
            for (base_host_group, target_host_group) in host_group_pairs.items():
                replaced_target_value = replaced_target_value.replace(f"::{target_host_group}%",
                                                                      f"::{base_host_group}%")
                if splitted_target_value != replaced_target_value:
                    break

            result_value = result_value + replaced_target_value + \
                           (delimiter if index < len(splitted_target_values) - 1 else '')

        return result_value


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-b", "--base-bp", action='store',
                        help="Path blueprint file to be used as the base", default="base_bp.json")
    parser.add_argument("-t", "--target-bp", action='store',
                        help="Path to blueprint file to be compared with base", default="target_bp.json")
    parser.add_argument("-r", "--result-file", action='store',
                        help="Path to save result file to", default="comparison_result.json")
    parser.add_argument("-c", "--config-rules-file", action='store',
                        help="Path to configuration rules file", default="rules.json")
    args = parser.parse_args()

    config_rules = ConfigRules(args.config_rules_file)
    bp_diff = BlueprintDiff(config_rules)

    base_bp = bp_diff.load_blueprint(args.base_bp)
    target_bp = bp_diff.load_blueprint(args.target_bp)

    final_result = bp_diff.handle_configurations_block(base_bp, target_bp)

    with open(args.result_file, "w+") as result:
        result.write(json.dumps(final_result, indent=2, sort_keys=False))


if __name__ == '__main__':
    main()
