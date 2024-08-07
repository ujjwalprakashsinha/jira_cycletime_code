import sys
import logging

from helper.credential.credential_manager import CredentialManager
from helper.jira_helper import JiraWorkItem
from helper.constants import JiraJsonKeyConstants as JiraJsonKeyConst, FileFolderNameConstants as FileFolderNameConst, ConfigKeyConstants as ConfigKeyConst, GeneralConstants as GeneralConst, DateUtilConstants as DateUtilConst 
import helper.jira_helper as jh
import helper.file_helper as fh
#import helper.flow_metrics_helper as fm_helper #UNCOMMENT ONLY WHEN DEPENDCY ISSUES ARE RESOLVED
import pandas as pd
from  helper.utils.dateutil import DateUtil

# Function to replace commas with pipes in each string of the list
def replace_commas(lst):
    return [s.replace(',', '|') for s in lst]

# Function to join list items with a pipe delimiter
def join_with_pipe(lst):
    return '|'.join(lst)

def main(output_date_format:str):
    try:
        logging.basicConfig(filename=FileFolderNameConst.APP_LOG_FILENAME.value, filemode="w", level=logging.INFO )
        logger = logging.getLogger(__name__)
        script_path = fh.get_folder_path_for_file(__file__)
        app_config_file_full_path = fh.get_config_file_path(script_path, FileFolderNameConst.CONFIG_FILENAME.value)
        app_config = fh.read_config(app_config_file_full_path) # loading config file for this project
        jira_board_config_full_file_path = fh.get_config_file_path(script_path, app_config[ConfigKeyConst.JIRA_BOARD_CONFIG_FILENAME_KEY.value])
        jira_board_queries_config = fh.read_config(jira_board_config_full_file_path) # loading jira board configuratio  file for this project
        jira_url = app_config[ConfigKeyConst.JIRA_URL_KEY.value]
        active_boards = jh.get_all_active_jira_query_names(jira_board_queries_config)
        print('-----------------------------------------')
        print('List of Active Boards in the config are:')
        print('-----------------------------------------')
        for jira_board in active_boards:
            print(f"{active_boards.index(jira_board)}. {jira_board}")
        print('-----------------------------------------')
        input_index: int =  int(input('Type the number for the option (from the above list): '))
        obj_board = jh.get_jira_query_by_name(active_boards[input_index], jira_board_queries_config)
        if obj_board is None:
            print('!!! Invalid Query Name provided. Exiting code !!!')
            sys.exit()

        cred_manager = CredentialManager()
        jira_token = cred_manager.get_credential(app_config[ConfigKeyConst.JIRA_TOKEN_CONFIG_KEY.value])

        # check for board id, else use the columns from configuration file
        is_query_jira_board_enabled: bool = obj_board.get(JiraJsonKeyConst.QUERY_JIRA_BOARD.value)
        if is_query_jira_board_enabled != None and not obj_board[JiraJsonKeyConst.QUERY_JIRA_BOARD.value]:
            columns = obj_board[JiraJsonKeyConst.COLUMNS.value]
        else:
            cur_jira_board_config = jh.get_jira_board_config_by_id(int(obj_board[JiraJsonKeyConst.BOARD_ID.value]), jira_url, jira_token)
            filter_id = cur_jira_board_config[GeneralConst.FILTER_ID.value]
            #final_jql = f"filter = {filter_id}"
            exclude_query = ""
            excluded_issue_types = ""
            if JiraJsonKeyConst.JQL_EXCLUDE_ISSUE_TYPE.value in obj_board and obj_board[JiraJsonKeyConst.JQL_EXCLUDE_ISSUE_TYPE.value] != "" and obj_board[JiraJsonKeyConst.JQL_EXCLUDE_ISSUE_TYPE.value] != None:
                excluded_issue_types = obj_board[JiraJsonKeyConst.JQL_EXCLUDE_ISSUE_TYPE.value]
                exclude_query = f" and issuetype not in ({excluded_issue_types})" # concatinate the board filter with the config jql if mentioned
            
            obj_board[JiraJsonKeyConst.JQL.value] = f"filter = {filter_id}{exclude_query}"
            columns = cur_jira_board_config[GeneralConst.BOARD_COLUMNS.value]
            print("---------------------------------------")
            print(f"Jira Board name: \n \t{cur_jira_board_config[GeneralConst.BOARD_NAME.value]}")
            print(f"Excluded Issue Type/s: \n \t{excluded_issue_types}")
       
        # define a dictionary to specify the needed jira fields (apart form status change dates info ) which needs to be captured in the output
        # fields 
        #   - created & status = needed for the data and hence must always be here with value None
        dict_needed_jira_field_and_column_mapping: dict = {
            "created": None,
            "status": None,
        }

        if not bool(output_date_format): # check if date format is not passed - empty or None
            # fetch date format from the configuration file
            output_date_format = app_config[ConfigKeyConst.OUTPUT_DATE_FORMAT_KEY.value]

        print(f"Output Date format: \n \t{output_date_format}")
        selected_board_name = obj_board[JiraJsonKeyConst.NAME.value]
        file_name_with_csv_file_extension = FileFolderNameConst.FM_OUTPUT_FILE_POSTFIX.value  + FileFolderNameConst.CSV_FILE_EXTENSION.value 
        fm_output_file_name = selected_board_name + file_name_with_csv_file_extension
        adf_output_file_name = selected_board_name + FileFolderNameConst.ADF_OUTPUT_FILE_POSTFIX.value + file_name_with_csv_file_extension
        merged_file_name = selected_board_name + FileFolderNameConst.MERGED_OUTPUT_FILE_POSTFIX.value + file_name_with_csv_file_extension
        output_folder_path = fh.get_output_folder_path(script_path)
        fm_output_csv_file_fullpath = fh.create_file_and_return_fullpath_with_name(output_folder_path, fm_output_file_name)
        additional_field_csv_file_fullpath = fh.create_file_and_return_fullpath_with_name(output_folder_path, adf_output_file_name)
        merged_file_fullpath = fh.create_file_and_return_fullpath_with_name(output_folder_path, merged_file_name)

        def add_additional_fields_to_query():
            # Add/Update additional fields which are needed in the output csv
            #dict_needed_jira_field_and_column_mapping.update({"project": "Project Key"})
            #dict_needed_jira_field_and_column_mapping.update({"customfield_10002": "Story Point"})
            #dict_needed_jira_field_and_column_mapping.update({"summary": "Title"})
            dict_needed_jira_field_and_column_mapping.update({"status": "Status"})
            dict_needed_jira_field_and_column_mapping.update({"resolution": "Resolution"})
            dict_needed_jira_field_and_column_mapping.update({"issuetype": "Type"})
            dict_needed_jira_field_and_column_mapping.update({"labels": "Labels"})
            dict_needed_jira_field_and_column_mapping.update({"customfield_10005": "Epic Link"})
            dict_needed_jira_field_and_column_mapping.update({"customfield_11115": "Environment"})
            dict_needed_jira_field_and_column_mapping.update({"components": "Components"})

        add_additional_fields_to_query()
        
        obj_jira_data = JiraWorkItem(search_query=obj_board[JiraJsonKeyConst.JQL.value], jira_board_columns=columns,
                                    output_file_name=fm_output_file_name)

        print(f'Please wait, preparing data for "{selected_board_name}"')
        
        jira_fields_needed = list(dict_needed_jira_field_and_column_mapping.keys())
        all_jira_issues = jh.get_jira_issues(obj_jira_data.search_query, jira_fields_needed, jira_url, jira_token)

        print('Extracting status change information...')
        
        flow_metric_dataset = list()
        additonal_field_dataset = list()
        for jira_issue in all_jira_issues:
            jira_issue_with_fm_data = jh.capture_issue_status_change_history(jira_issue=jira_issue, obj_jira_data=obj_jira_data, date_format=output_date_format)
            jira_issue_with_field_data = jh.capture_additional_field_value(jira_issue=jira_issue, field_and_column_mapping=dict_needed_jira_field_and_column_mapping)
            additonal_field_dataset.append(jira_issue_with_field_data.copy())
            flow_metric_dataset.append(jira_issue_with_fm_data.copy())
        
        flow_metric_dataframe = pd.DataFrame(flow_metric_dataset)
        flow_metric_dataframe.to_csv(fm_output_csv_file_fullpath, index=False)
        additonal_field_dataframe = pd.DataFrame(additonal_field_dataset)
        # Add a new column 'Link' with values from column 'ID' to make the url
        additonal_field_dataframe['Link'] = jira_url + "/browse/" + additonal_field_dataframe[GeneralConst.ID_COLUMN_NAME.value] 
        additonal_field_dataframe.to_csv(additional_field_csv_file_fullpath, index=False)
        merged_df = pd.merge(flow_metric_dataframe, additonal_field_dataframe, on=GeneralConst.ID_COLUMN_NAME.value, how='inner')  # how can be 'inner', 'outer', 'left', or 'right'        

        # Changes to the labels column if it exists 
        if "Labels" in merged_df.columns:
            # replace comas with pipe symbol
            merged_df['Labels'] = merged_df['Labels'].apply(join_with_pipe)
        
        # Reorder the columns to place the new column 'Link' in the second position
        if "Link" in merged_df.columns:
            cols = merged_df.columns.tolist()
            cols.remove('Link')
            cols.insert(1, 'Link')
            merged_df = merged_df[cols]

        merged_df.to_csv(merged_file_fullpath, index=False)

        # Get the earliest date in the column
        earliest_date = flow_metric_dataframe.iloc[:, 1].min()
        obj_date_util: DateUtil = DateUtil(output_date_format)
        all_dates_till_today = obj_date_util.get_all_date_till_today(earliest_date)
        all_dates_dataframe = pd.DataFrame(all_dates_till_today)
        date_output_csv_file_fullpath = fh.create_file_and_return_fullpath_with_name(output_folder_path, selected_board_name + "_dates.csv")
        all_dates_dataframe.to_csv(date_output_csv_file_fullpath, index=False)

        print(f"{len(all_jira_issues)} records prepared.")
        print(f'Output Files: \n \t{merged_file_fullpath} \n \t{fm_output_csv_file_fullpath} \n \t{additional_field_csv_file_fullpath}')
        print(f"Please check '{FileFolderNameConst.APP_LOG_FILENAME.value}' file for info on missing status mapping in the record, if any.")

        # ------------ Generate flow metric report if true -----------
        if(app_config.get(ConfigKeyConst.GENERATE_FLOW_METRICS_REPORT_KEY.value)):
            start_column_name =  columns[1][JiraJsonKeyConst.COLUMN_NAME.value]
            done_column_name = columns[len(columns)-1][JiraJsonKeyConst.COLUMN_NAME.value]
            #fm_helper.generate_flow_metrics_report(selected_board_name, output_csv_file_fullpath, start_column_name, done_column_name,GeneralConst.ID_COLUMN_NAME.value, date_format)
        # -------------
    except Exception as e:
        print(f"Error : {e}")
        logger.error(f"Error : {e}")

if __name__ == "__main__": 
    main(output_date_format="")