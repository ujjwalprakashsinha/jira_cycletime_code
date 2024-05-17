from enum import Enum


class JiraJsonKeyConstants(Enum):
    BOARDS = "boards"
    NAME = "name"
    JQL = "jql"
    ACTIVE = "active"
    COLUMNS = "columns"
    COLUMN_NAME = "column_name"
    STATUSES = "statuses"


class DateUtilConstants(Enum):
    DATE_FORMAT_TWIG = "yyyymmdd"
    DATE_FORMAT_STANDARD = "dd.mm.yyyy"


class FileFolderNameConstants(Enum):
    CONFIG_FILENAME = "config.json"
    OUTPUT_FOLDERNAME = "outputFiles"
    TWIG_OUTPUT_FILE_POSTFIX = "_twig_jira_data.csv"
    COLUMN_OUTPUT_FILE_POSTFIX = "_column_jira_data.csv"
    CONFIG_FOLDERNAME = "config"


class ConfigKeyConstants(Enum):
    JIRA_URL_KEY = "jira_url"
    JIRA_TOKEN_VARNAME_KEY = "jira_token_env_varname"
    OUTPUT_DATE_FORMAT_KEY = "output_date_format"
    JIRA_BOARD_CONFIG_FILENAME = "jira_board_config_filename"
