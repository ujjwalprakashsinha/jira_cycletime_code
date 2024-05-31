import csv
from datetime import datetime

import os
import sys
import yaml
import logging

from credential.credential_manager import CredentialManager
from utils.dateutil import DateUtil
from jira_projects.rawJiraDataBase import JiraDataBase
from constants import JiraJsonKeyConstants as JiraJsonKeyConst, FileFolderNameConstants as FileFolderNameConst, ConfigKeyConstants as ConfigKeyConst, GeneralConstants
import helper.jira_helper as jira_helper

# ***** The Main code execution starts here ****
try:
    logging.basicConfig(filename=FileFolderNameConst.APP_LOG_FILENAME.value, filemode="w", level=logging.INFO )
    logger = logging.getLogger("__name__")
    exe_path = os.path.dirname(__file__)
    config_file_full_path = jira_helper.get_config_file_path(exe_path, FileFolderNameConst.CONFIG_FILENAME.value)
    with open(config_file_full_path) as file:  # loading config file for this project
        config = yaml.safe_load(file)
    jira_board_config_full_file_path = jira_helper.get_config_file_path(exe_path, config[ConfigKeyConst.JIRA_BOARD_CONFIG_FILENAME.value])
    with open(jira_board_config_full_file_path) as file:  # load jira board query configuration file
        jira_board_queries_config = yaml.safe_load(file)
    
    jira_url = config[ConfigKeyConst.JIRA_URL_KEY.value]
    active_queries = jira_helper.get_all_active_jira_query_names(jira_board_queries_config)
    print(f'List of Active Queries in the config are: {active_queries}')
    query_name = input('Write name of a Query to execute (from the above list): ')
    obj_query = jira_helper.get_jira_query_by_name(query_name, jira_board_queries_config)
    if obj_query is None:
        print('!!! Invalid Query Name provided. Exiting code !!!')
        sys.exit()

    cred_manager = CredentialManager()
    jira_token = cred_manager.get_credential(config[ConfigKeyConst.JIRA_TOKEN_VARNAME_KEY.value])

    # check for board id, else use the columns from configuration file
    if obj_query[JiraJsonKeyConst.QUERY_JIRA_BOARD.value]:
        cur_jira_board_config = jira_helper.get_jira_board_config_by_id(int(obj_query[JiraJsonKeyConst.BOARD_ID.value]), jira_token, jira_url)
        filter_id = cur_jira_board_config[GeneralConstants.FILTER_ID.value]
        if JiraJsonKeyConst.JQL_ISSUE_TYPE.value in obj_query and obj_query[JiraJsonKeyConst.JQL_ISSUE_TYPE.value] != "":
            obj_query[JiraJsonKeyConst.JQL.value] = f"filter = {filter_id} and {obj_query[JiraJsonKeyConst.JQL_ISSUE_TYPE.value]}"
        columns = cur_jira_board_config[GeneralConstants.BOARD_COLUMNS.value]
    else:
        columns = obj_query[JiraJsonKeyConst.COLUMNS.value]
    output_file_name = obj_query[JiraJsonKeyConst.NAME.value] + FileFolderNameConst.TWIG_OUTPUT_FILE_POSTFIX.value
    obj_jira_data = JiraDataBase(search_query=obj_query[JiraJsonKeyConst.JQL.value], jira_board_columns=columns,
                                 output_file_name=output_file_name)

    print(f'Please wait, we are preparing data for "{obj_query[JiraJsonKeyConst.NAME.value]}"')

    jira_fields_needed = ["status", "created"]
    all_jira_issues = jira_helper.get_jira_issues(obj_jira_data.search_query, jira_fields_needed, jira_url, jira_token)

    print('Extracting status change information...')
    output_folder_path = jira_helper.get_output_folder_path(exe_path)
    os.makedirs(name=output_folder_path, exist_ok=True)
    output_csv_file_fullpath = os.path.join(output_folder_path, obj_jira_data.file_name)
    with open(output_csv_file_fullpath, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        header = obj_jira_data.csv_single_row_list.keys()
        csv_writer.writerow(header)
        for jira_issue in all_jira_issues:
            obj_jira_data.set_row_values_to_blank()
            # assign created date as the value for first column which has mapped status
            # (exclude columns with no mapped status on jira board like backlog in Kanban board sometime)
            obj_jira_data.csv_single_row_list[obj_jira_data.get_first_column_having_mapped_status()] = jira_issue.fields.created
            obj_jira_data.set_issue_id(jira_issue.key)
            mapped_column_final_issue_status = obj_jira_data.get_mapped_column_for_status(
                current_status=jira_issue.fields.status.name)
            for history in jira_issue.changelog.histories:
                for item in history.items:
                    if item.field == "status" and item.toString != item.fromString :  # checking for status change in the history & that status did not change to same
                        mapped_column_current_issue_status = obj_jira_data.get_mapped_column_for_status(
                            current_status=item.toString)
                        if mapped_column_current_issue_status == '' or mapped_column_current_issue_status is None:
                            logger.info(f'Info: Status mapping missing for: {item.toString} | Issue ID: {obj_jira_data.csv_single_row_list[JiraDataBase._idColumnName]} | Change Date: {history.created}')
                            break

                        obj_jira_data.set_board_column_value(mapped_column_for_status=mapped_column_current_issue_status,
                                                       status_change_date=history.created)
                        obj_jira_data.clear_later_workflow_column_value(
                            mapped_column_for_status=mapped_column_current_issue_status)

            obj_jira_data.clear_later_workflow_column_value(mapped_column_final_issue_status)
            # add the change date (needed format) to the csv_row_list object and add to csv
            date_utility = DateUtil(config[ConfigKeyConst.OUTPUT_DATE_FORMAT_KEY.value])
            for column in obj_jira_data.jira_board_columns:
                obj_jira_data.csv_single_row_list[column[JiraJsonKeyConst.COLUMN_NAME.value]] = date_utility.convert_jira_date(
                    obj_jira_data.csv_single_row_list[column[JiraJsonKeyConst.COLUMN_NAME.value]])

            csv_writer.writerow(obj_jira_data.csv_single_row_list.values())
    print(f"{len(all_jira_issues)} records prepared.")
    print(f'OUTPUT File: {output_csv_file_fullpath}')
    print(f"Please check {FileFolderNameConst.APP_LOG_FILENAME.value} file for info on missing status mapping in the record, if any.")
except Exception as e:
    print(f"Error : {e}")