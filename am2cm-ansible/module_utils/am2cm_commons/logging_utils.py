import logging
import os

from ansible.module_utils.am2cm_commons import constants


def get_transition_log_dir():
    transition_log_dir = os.environ['TRANSITION_LOG_DIR'] if os.environ.get('TRANSITION_LOG_DIR') else '.'
    if transition_log_dir != '.':
        os.makedirs(transition_log_dir, exist_ok=True)
    return transition_log_dir


def get_transition_tag_log_file():
    return os.environ['TRANSITION_TAG_LOG_FILE'] if os.environ.get('TRANSITION_TAG_LOG_FILE') else None


def configure_logging(filename):
    log_dir = get_transition_log_dir()
    logfile = os.path.join(log_dir, filename)
    logging.basicConfig(format=constants.LOGGER_FORMAT, filename=logfile, level=constants.LOGLEVEL)

    console_log = logging.StreamHandler()
    console_log.setLevel(constants.LOGLEVEL)
    console_log.setFormatter(logging.Formatter(constants.LOGGER_FORMAT))
    logging.getLogger().addHandler(console_log)

    transition_tag_logfile = get_transition_tag_log_file()
    if transition_tag_logfile:
        tag_logfile = os.path.join(log_dir, transition_tag_logfile)
        tag_file_handler = logging.FileHandler(tag_logfile)
        tag_file_handler.setLevel(constants.LOGLEVEL)
        tag_file_handler.setFormatter(logging.Formatter(constants.LOGGER_FORMAT))
        logging.getLogger().addHandler(tag_file_handler)


