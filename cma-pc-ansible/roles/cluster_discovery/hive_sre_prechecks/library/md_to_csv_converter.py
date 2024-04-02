#!/usr/bin/python
import csv
import json
import logging
import os
import re
import shutil

from ansible.module_utils.am2cm_commons.logging_utils import configure_logging, get_transition_log_dir
from ansible.module_utils.basic import AnsibleModule

configure_logging(os.path.basename(__file__).replace(".py", "-module.log"))
LOG = logging.getLogger(__name__)

EMPTY_TABLE_STR = "> **Results empty**"
REGEXP_SECTIONS_SPLIT = re.compile('^[ \t]*## ', flags=re.MULTILINE)
REGEXP_MD_TABLE = re.compile(r'(^\|.+\|?$\n?)+', flags=re.MULTILINE)
REGEXP_MD_TABLE_ALIGNMENT_ROW = re.compile(r'^\|:?-+:?\|')
REGEXP_CLEAN_MD_TITLE_BRACES = re.compile(r'\([^)]*\)')
REGEXP_CLEAN_MD_TITLE_SYMBOLS = re.compile(r'[^\w\s_]')
REGEXP_CLEAN_MD_TITLE_MULTI_UNDERSCORES = re.compile(r'_{2,}')


def parse_md(md_content):
    sections = REGEXP_SECTIONS_SPLIT.split(md_content)
    top_title = sections[0].strip().split("\n")[0].replace('# ', '')
    top_title = clean_section_title(top_title)

    # If only top section (#) is present without subsections
    if len(sections) == 1:
        content = sections[0].strip().split("\n", 1)[1].strip()
        return {top_title: parse_section(content)}

    # If top section (#) + subsections (##) are present
    section_name_to_parse_result = {}
    for section in sections[1:]:
        section_parts = section.strip().split('\n', 1)
        title = clean_section_title(section_parts[0])
        if len(section_parts) > 1:
            content = section_parts[1].strip()
        else:
            content = ''

        section_name_to_parse_result[top_title + "_" + title] = parse_section(content)
    return section_name_to_parse_result


def parse_section(content):
    if EMPTY_TABLE_STR in content:
        text_content = content.replace(EMPTY_TABLE_STR, '').strip()
        parse_result = {"text": text_content, "table": []}
    else:
        table_match = REGEXP_MD_TABLE.search(content)
        if table_match:
            table_content = table_match.group()
            table_rows = [row for row in table_content.split("\n")
                          if row.strip() and not REGEXP_MD_TABLE_ALIGNMENT_ROW.match(row)]
            table = [list(map(str.strip, row.split("|")[1:-1])) for row in table_rows]
            text_content = content.replace(table_content, '').strip()
            parse_result = {"text": text_content, "table": table}
        else:
            parse_result = {"text": content, "table": []}
    return parse_result


def clean_section_title(title):
    title = title.replace(' ', '_').lower()
    # Remove any data in braces from title. This is additional info which is not needed
    title = REGEXP_CLEAN_MD_TITLE_BRACES.sub('', title)
    # Remove symbols like !@#$%^&*()_+ etc.
    title = REGEXP_CLEAN_MD_TITLE_SYMBOLS.sub('', title)
    # Replace multiple underscores with single one
    title = REGEXP_CLEAN_MD_TITLE_MULTI_UNDERSCORES.sub('_', title)
    title = title.strip('_')
    return title


def save_to_files(output_dir, parse_results):
    for title, content in parse_results.items():
        with open(os.path.join(output_dir, "{}.md".format(title)), "w") as txt_file:
            txt_file.write(content["text"])

        with open(os.path.join(output_dir, "{}.csv".format(title)), "w") as csv_file:
            writer = csv.writer(csv_file, lineterminator='\n')
            writer.writerows(content["table"])


def run_module():
    module_args = dict(
        input_dir=dict(type='str', required=True),
        output_dir=dict(type='str', required=True),
    )

    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )
    result['original_message'] = json.dumps(module.params)  # concatenate the params here, if there were any...
    LOG.info("inputs: {}".format(result['original_message']))

    input_dir = module.params['input_dir']
    output_dir = module.params['output_dir']

    if not os.path.isdir(input_dir):
        module.fail_json(msg="input_dir is not a directory")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for file in os.listdir(input_dir):
        source_filepath = os.path.join(input_dir, file)
        if file.endswith(".md"):
            with open(source_filepath, "r") as md_file:
                md_content = md_file.read()
                parse_results = parse_md(md_content)
                save_to_files(output_dir, parse_results)
        else:
            shutil.copy(source_filepath, os.path.join(output_dir, file))

    result['changed'] = True
    result["message"] = "Parse results saved to {}".format(output_dir)
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
