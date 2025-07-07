from datetime import datetime, date
from datetime import timedelta
import pandas as pd
from dateutil.relativedelta import relativedelta
import math
import numpy as np
import pandas
import redcap
import params
import tokens

def calculate_age_months(dob):
    """Compute the age in years from a date of birth.
    :param dob: Date of birth
    :type dob: Datetime
    :return: Date of birth in years
    :rtype: int
    """
    today = datetime.today()
    months = (today.year - dob.year) * 12 + (today.month - dob.month)
    return months

def days_to_birthday(dob, fu):
    """
    For a date which is about to its birthday, i.e. this/coming month, compute the number of days to the birthday.
    """

    today = datetime.today()
    return (dob + relativedelta(months=+fu) - today).days

def remove_status(redcap_data,redcap_project, fu_status_event,alert='\(AV\)'):
    """
    This was used to remove the AV or BW old alarm. 20240603
    """

    """ THIS PROJECT ONLY DELETE THOSE WITH THE EXACT STATUS ?????? """

    active_alerts = redcap_data.loc[(slice(None), fu_status_event), 'child_fu_status']
    active_alerts = active_alerts.replace(np.nan,'')
    good_alerts =active_alerts[~active_alerts.str.contains(alert)]
    bad_alerts = active_alerts[active_alerts.str.contains(alert)]

    bad_records = bad_alerts.index.get_level_values('record_id').difference(good_AV.index.get_level_values('record_id'))
    print(bad_records)

    to_import_dict = [{'record_id': rec_id, 'child_fu_status': ''} for rec_id in bad_records]
    response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
    print("[OLD VA/BW] Alerts REMOVED: {}".format(response.get('count')))

def get_record_ids_with_custom_status(redcap_data,redcap_project, defined_alerts, fu_status_event):
    """Get the project records ids of the participants with an custom status set up in the child_fu_status field.

    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param defined_alerts: List of strings representing the type of the defined alerts
    :type defined_alerts: list
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str

    :return: Array containing the record ids of those participants with a custom follow up status
    :rtype: pandas.Int64Index
    """
    active_alerts = redcap_data.loc[(slice(None), fu_status_event), 'child_fu_status']

    for k,alert in active_alerts.T.items():
        if alert == " " or alert == "  " or alert == "   " or alert == "    ":
            print(k[0],"(",alert,"(")
    active_alerts = active_alerts[active_alerts.notnull()]

    if active_alerts.empty:
        return None
    custom_status = active_alerts
    for alert in defined_alerts:
        custom_status = custom_status[~active_alerts.str.startswith(alert)]

    empty_status_to_correct = custom_status[(custom_status==' ')|(custom_status=='  ')|(custom_status=='   ')|(custom_status=='    ')|(custom_status=='     ')|(custom_status=='      ')|(custom_status=='       ')]
    custom_status = custom_status[(custom_status!=' ')&(custom_status!='  ')&(custom_status!='   ')&(custom_status!='    ')&(custom_status!='     ')&(custom_status!='      ')]
    custom_status.index = custom_status.index.get_level_values('record_id')

    if not empty_status_to_correct.empty:
        print(empty_status_to_correct)
        records_empty_to_correct = empty_status_to_correct.index.get_level_values('record_id')
        to_import_dict = [{'record_id': rec_id, 'child_fu_status': ''} for rec_id in records_empty_to_correct]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[BLANK STATUS] Alerts REMOVED: {}".format(response.get('count')))
    return custom_status.keys()

def get_active_alerts(redcap_data, alert, fu_status_event, type_='Normal'):
    """Get the project records ids of the participants with an activated alert.
w
    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param alert: String representing the type of alerts to be retrieved
    :type alert: str
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str

    :return: Array containing the record ids of the study participants who have an activated alert.
    :rtype: pandas.Int64Index
    """
    active_alerts = redcap_data.loc[(slice(None), fu_status_event), 'child_fu_status']
    active_alerts = active_alerts[active_alerts.notnull()]
    if active_alerts.empty:
        return None

    if type_ == 'BW':
        active_alerts = active_alerts[active_alerts.str.endswith(alert)]
    else:
        active_alerts = active_alerts[(active_alerts.str.startswith(alert))|(active_alerts.str.startswith('COH.'+alert))]

    active_alerts.index = active_alerts.index.get_level_values('record_id')

    return active_alerts.keys()

def get_list_communities(redcap_project, choice_sep, code_sep):
    """Get list of communities in the health facility catchment area from the health facility REDCap project. This list
    is part of the metadata of the ID.community field.

    :param redcap_project: The REDCap project class
    :type redcap_project: redcap.Project
    :param choice_sep: Character used by REDCap to separate choices in a categorical field (radio, dropdown) when
                       exporting meta-data
    :type choice_sep: str
    :param code_sep: Character used by REDCap to separated code and label in every choice when exporting meta-data
    :type code_sep: str

    :return: A dictionary in which the keys are the community code and the values are the community names.
    :rtype: dict
    """
    community_field = redcap_project.export_metadata(fields=['community'], format_type='df')
    community_choices = community_field['select_choices_or_calculations'].community
    communities_string = community_choices.split(choice_sep)
    return {community.split(code_sep)[0]: community.split(code_sep)[1] for community in communities_string}



""" TO BE VISITED ALERT """
def set_tbv_alerts(redcap_project, redcap_project_df, tbv_alert, tbv_alert_string, redcap_date_format,
                   alert_date_format, choice_sep, code_sep, blocked_records, fu_status_event):
    """Remove the Household to be visited alerts of those participants that have been already visited and setup new
    alerts for these others that took recently AZi/Pbo and require a household visit.
    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param tbv_alert: Code of the To Be Visited alerts
    :type tbv_alert: str
    :param tbv_alert_string: String with the alert to be setup
    :type tbv_alert_string: str
    :param redcap_date_format: Format of the dates in REDCap
    :type redcap_date_format: str
    :param alert_date_format: Format of the date of the last AZi/Pbo dose to be displayed in the alert
    :type alert_date_format: str
    :param choice_sep: Character used by REDCap to separate choices in a categorical field (radio, dropdown) when
                       exporting meta-data
    :type choice_sep: str
    :param code_sep: Character used by REDCap to separated code and label in every choice when exporting meta-data
    :type code_sep: str
    :param blocked_records: Array with the record ids that will be ignored during the alerts setup
    :type blocked_records: pandas.Int64Index
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str
    :return: None
    """

    # Get the project records ids of the participants requiring a household visit
    records_to_be_visited = get_record_ids_tbv(redcap_project_df)

    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_be_visited = records_to_be_visited.difference(blocked_records)

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, tbv_alert, fu_status_event)

    # Check which of the records with alerts are not anymore in the records to be visited (i.e. participants with an
    # activated alerts already visited)
    if records_with_alerts is not None:
        alerts_to_be_removed = records_with_alerts.difference(records_to_be_visited)
        # Import data into the REDCap project: Alerts removal

        to_import_dict = [{'record_id': rec_id, 'child_fu_status': ''} for rec_id in alerts_to_be_removed]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[TO BE VISITED] Alerts removal: {}".format(response.get('count')))
    else:
        print("[TO BE VISITED] Alerts removal: None")

    # Get list of communities in the health facility catchment area
    communities = get_list_communities(redcap_project, choice_sep, code_sep)
    # Build dataframe with fields to be imported into REDCap (record_id and child_fu_status)
    to_import_df = build_tbv_alerts_df(redcap_project_df, records_to_be_visited, communities, tbv_alert_string,
                                       redcap_date_format, alert_date_format)
    # Import data into the REDCap project: Alerts setup
    to_import_dict = [{'record_id': rec_id, 'child_fu_status': participant.child_fu_status}
                      for rec_id, participant in to_import_df.iterrows()]
    response = redcap_project.import_records(to_import_dict)

    print("[TO BE VISITED] Alerts setup: {}".format(response.get('count')))

def get_record_ids_tbv(redcap_data):
    """Get the project record ids of the participants requiring a household visit. Thus, for every project record, check
    if the number of AZi/Pbo doses is higher than the number of household visits (excluding Non-Compliant visits) in
    which the field worker has seen the child. This is therefore the AZi-Supervision index:
         - Higher than zero: Participant requires a household follow up visit;
         - Zero: Participant who has been correctly supervised;
         - Lower than zero: Participant who has ended her follow up.
    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :return: Array of record ids representing those study participants that require a AZi/Pbo supervision household
    visit
    :rtype: pandas.Int64Index
    """

    # To find what HHFU visits Have never been done
    epi1_recordid = redcap_data.loc[(slice(None), 'epipenta1_v0_recru_arm_1'), :].index.get_level_values('record_id')
    hh1_recordid = redcap_data.loc[(slice(None), 'hhafter_1st_dose_o_arm_1'), :].index.get_level_values('record_id')
    #    print(hh1_recordid)

    HH_not_done_yet = epi1_recordid.difference(hh1_recordid)

    #### NEW VERSION OF THE TBV ALERT. ANDREU BOFILL 03/02/2022

    last_hh_done = redcap_data.loc[(slice(None), 'hhafter_1st_dose_o_arm_1'), :].groupby('record_id').last()
    phone_unsuccess = last_hh_done[(last_hh_done['fu_type'] == float(1)) & (
                (last_hh_done['phone_success'] == float(0)) | (last_hh_done['call_caretaker'] == float(0)))]
    ##    phone_drug_react = last_hh_done[(last_hh_done['fu_type']==float(1))&((last_hh_done['hh_drug_react']==float(1))|(last_hh_done['hh_health_complaint']==float(1)))]
    visit_unsuccess = last_hh_done[((last_hh_done['fu_type'] == float(2)) | (last_hh_done['fu_type'] == float(3))) & (
                (last_hh_done['hh_child_seen'] != float(1)) & (last_hh_done['reachable_status'] != float(1)))]
    old_visit_unsuccess = last_hh_done[((last_hh_done['fu_type'] != float(1)) & (
                last_hh_done['fu_type'] != float(2)) & (last_hh_done['fu_type'] != float(3))) & (
                                                   (last_hh_done['hh_child_seen'] == float(0)) & (
                                                       last_hh_done['hh_why_not_child_seen'] == float(1)))]
    #    print(old_visit_unsuccess)
    HH_to_be_done = list(HH_not_done_yet) + list(phone_unsuccess.index.get_level_values('record_id')) + list(
        visit_unsuccess.index.get_level_values('record_id')) + list(
        old_visit_unsuccess.index.get_level_values('record_id'))
    HH_to_be_done_2 = pd.Series(dtype='float64', index=HH_to_be_done).index
    return HH_to_be_done_2

def build_tbv_alerts_df(redcap_data, record_ids, catchment_communities, alert_string, redcap_date_format,
                        alert_date_format):
    """Build dataframe with record ids, communities, date of last AZi/Pbo dose and follow up status of every study
    participant requiring an AZi/Pbo supervision household visit.
    :param redcap_data:Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param record_ids: Array of record ids representing those study participants that require a AZi/Pbo supervision
    household visit
    :type record_ids: pandas.Int64Index
    :param catchment_communities: Dictionary with the community codes attached to each community name
    :type catchment_communities: dict
    :param alert_string: String with the alert to be setup containing two placeholders (community & last AZi dose date)
    :type alert_string: str
    :param redcap_date_format: Format of the dates in REDCap
    :type redcap_date_format: str
    :param alert_date_format: Format of the date of the last AZi/Pbo dose to be displayed in the alert
    :type alert_date_format: str
    :return: A dataframe with the columns community, last_azi_date and child_fu_status in which each row is identified
    by the REDCap record id and represents a study participant to be visited.
    :rtype: pandas.DataFrame
    """
    # Append to record ids, the participant's community name
    communities_to_be_visited = redcap_data['community'][record_ids]
    communities_to_be_visited = communities_to_be_visited[communities_to_be_visited.notnull()]
    communities_to_be_visited = communities_to_be_visited.apply(int).apply(str).replace(catchment_communities)
    communities_to_be_visited.index = communities_to_be_visited.index.get_level_values('record_id')

    # Append to record ids, the date of last AZi/Pbo dose administered to the participant
    last_azi_doses = redcap_data.loc[record_ids, ['int_azi', 'int_date']]
    last_azi_doses = last_azi_doses[last_azi_doses['int_azi'] == 1]
    last_azi_doses = last_azi_doses.groupby('record_id')['int_date'].max()
    last_azi_doses = last_azi_doses.apply(lambda x: datetime.strptime(x, redcap_date_format))
    last_azi_doses = last_azi_doses.apply(lambda x: x.strftime(alert_date_format))

    # Transform data to be imported into the child_status_fu variable into the REDCap project
    data = {'community': communities_to_be_visited, 'last_azi_date': last_azi_doses}
    data_to_import = pandas.DataFrame(data)
    if not data_to_import.empty:
        data_to_import['child_fu_status'] = data_to_import[['community', 'last_azi_date']].apply(
            lambda x: alert_string.format(community=x[0], last_azi_date=x[1]), axis=1)

    return data_to_import

""" NEXT VISIT ALERT """
def set_nv_alerts(redcap_project, redcap_project_df, nv_alert, nv_alert_string, alert_date_format, days_before,
                  days_after, blocked_records, fu_status_event):
    """Remove the Next Visit alerts of those participants that have already come to the health facility and setup new
    alerts for these others that enter in the flag days_before-days_after interval.

    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param nv_alert: Code of the Next Visit alerts
    :type nv_alert: str
    :param nv_alert_string: String with the alert to be setup
    :type nv_alert_string: str
    :param alert_date_format: Format of the date of the next return date to be displayed in the alert
    :type alert_date_format: str
    :param days_before: Number of days before today to start alerting the participant will come
    :type days_before: int
    :param days_after: Number of days after today to continue alerting the participant will come
    :type days_after: int
    :param blocked_records: Array with the record ids that will be ignored during the alerts setup
    :type blocked_records: pandas.Int64Index
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str

    :return: None
    """

    # Get the project records ids of the participants who are expected to come tho the HF in the interval days_before
    # and days_after from today
    records_to_flag = get_record_ids_nv(redcap_project_df, days_before, days_after)

    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_flag = records_to_flag.difference(blocked_records)

    # TODO: This should be controlled in main by the order in which alerts are flagged.
    # Get the project records ids of the participants requiring a household visit after AZi administration. The TO BE
    # VISITED alert is higher priority than the NEXT VISIT alerts
    records_to_be_visited = get_record_ids_tbv(redcap_project_df)

    # Don't flag with NEXT VISIT those records already marked as TO BE VISITED
    records_to_flag = records_to_flag.difference(records_to_be_visited)

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, nv_alert, fu_status_event)

    # Check which of the records with alerts are not anymore in the records to flag (i.e. participants with an
    # activated alert that already came to the health facility or they become non-compliant)
    if records_with_alerts is not None:
        alerts_to_be_removed = records_with_alerts.difference(records_to_flag)
        # Import data into the REDCap project: Alerts removal
        to_import_dict = [{'record_id': rec_id, 'child_fu_status': ''} for rec_id in alerts_to_be_removed]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[NEXT VISIT] Alerts removal: {}".format(response.get('count')))
    else:
        print("[NEXT VISIT] Alerts removal: None")

    # Build dataframe with fields to be imported into REDCap (record_id and child_fu_status)
    to_import_df = build_nv_alerts_df(redcap_project_df, records_to_flag, nv_alert_string, alert_date_format)

    # Import data into the REDCap project: Alerts setup
    to_import_dict = [{'record_id': rec_id, 'child_fu_status': participant.child_fu_status}
                      for rec_id, participant in to_import_df.iterrows()]
    response = redcap_project.import_records(to_import_dict)
    print("[NEXT VISIT] Alerts setup: {}".format(response.get('count')))

def get_record_ids_nv(redcap_data, days_before, days_after):
    """Get the project record ids of the participants who are expected to come to the HF in the interval days_before and
    days_after from today. Thus, for every project record, check if the return date of the last visit is in this
    interval and the participant didn't come yet.

    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param days_before: Number of days before the return date to start alerting that the participant will come
    :type days_before: int
    :param days_after: Number of days after the return date to continue alerting that the participant should have come
    :type days_after: int

    :return: Array of record ids representing those study participants that will be flagged because their return date is
    between the defined interval
    :rtype: pandas.Int64Index
    """

    # Cast int_next_visit column from str to date and get the last return date
    x = redcap_data
    x['int_next_visit'] = pandas.to_datetime(x['int_next_visit'])
    last_return_dates = x.groupby('record_id')['int_next_visit'].max()
    last_return_dates = last_return_dates[last_return_dates.notnull()]
    days_to_come = datetime.today() - last_return_dates

    before_today = days_to_come[timedelta(days=-days_before) <= days_to_come]
    after_today = days_to_come[days_to_come < timedelta(days=days_after)]
    return set(before_today.keys()) & set(after_today.keys())

def build_nv_alerts_df(redcap_data, record_ids, alert_string, alert_date_format):
    """Build dataframe with record ids and next return date to health facility of every study participant who is
    supposed to come in the next7 days or is still expected in the health facility (still compliant).

    :param redcap_data:Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param record_ids: Array of record ids representing those study participants that require a AZi/Pbo supervision
    household visit
    :type record_ids: pandas.Int64Index
    :param alert_string: String with the alert to be setup containing one placeholders (next return date)
    :type alert_string: str
    :param alert_date_format: Format of the date of the next return date to be displayed in the alert
    :type alert_date_format: str

    :return: A dataframe with the columns return date and child_fu_status in which each row is identified by the REDCap
    record id and represents a study participant who is supposed to come to the health facility.
    :rtype: pandas.DataFrame
    """
    # Append to record ids, the next return date of the participant
    next_return_date = redcap_data.loc[record_ids, ['int_next_visit']]
    next_return_date = next_return_date.groupby('record_id')['int_next_visit'].max()
    next_return_date = next_return_date.apply(lambda x: x.strftime(alert_date_format))

    # Transform data to be imported into the child_status_fu variable into the REDCap project
    data = {'return_date': next_return_date}
    data_to_import = pandas.DataFrame(data)
    if not data_to_import.empty:
        data_to_import['child_fu_status'] = data_to_import[['return_date']].apply(
            lambda x: alert_string.format(return_date=x[0]), axis=1)

    return data_to_import

""" NON-COMPLIANT """
def set_nc_alerts(redcap_project, redcap_project_df, nc_alert, nc_alert_string, choice_sep, code_sep, days_to_nc,
                  blocked_records, fu_status_event):
    """Remove the Non-compliant alerts of those participants that have been already visited and setup new alerts for
    these others that become non-compliant recently.

    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param nc_alert: Code of the Non-Compliant alerts
    :type nc_alert: str
    :param nc_alert_string: String with the alert to be setup
    :type nc_alert_string: str
    :param choice_sep: Character used by REDCap to separate choices in a categorical field (radio, dropdown) when
                       exporting meta-data
    :type choice_sep: str
    :param code_sep: Character used by REDCap to separated code and label in every choice when exporting meta-data
    :type code_sep: str
    :param days_to_nc: Definition of non-compliant participant - days since return date defined during last HF visit
    :type days_to_nc: int
    :param blocked_records: Array with the record ids that will be ignored during the alerts setup
    :type blocked_records: pandas.Int64Index
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str

    :return: None
    """

    # Get the project records ids of the participants requiring a visit because they are non-compliant
    records_to_be_visited = get_record_ids_nc(redcap_project_df, days_to_nc)

    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_be_visited = records_to_be_visited.difference(blocked_records)

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, nc_alert, fu_status_event)

    # Check which of the records with alerts are not anymore in the records to be visited (i.e. participants with an
    # activated alerts already visited)
    if records_with_alerts is not None:
        alerts_to_be_removed = records_with_alerts.difference(records_to_be_visited)

        # Import data into the REDCap project: Alerts removal
        to_import_dict = [{'record_id': rec_id, 'child_fu_status': ''} for rec_id in alerts_to_be_removed]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[NON-COMPLIANT] Alerts removal: {}".format(response.get('count')))
    else:
        print("[NON-COMPLIANT] Alerts removal: None")

    # Get list of communities in the health facility catchment area
    communities = get_list_communities(redcap_project, choice_sep, code_sep)

    # Build dataframe with fields to be imported into REDCap (record_id and child_fu_status)
    to_import_df = build_nc_alerts_df(redcap_project_df, records_to_be_visited, communities, nc_alert_string)

    # Import data into the REDCap project: Alerts setup
    to_import_dict = [{'record_id': rec_id, 'child_fu_status': participant.child_fu_status}
                      for rec_id, participant in to_import_df.iterrows()]
    response = redcap_project.import_records(to_import_dict)
    print("[NON-COMPLIANT] Alerts setup: {}".format(response.get('count')))

def get_record_ids_nc(redcap_data, days_to_nc):
    """Get the project record ids of the participants requiring a household visit because they are non-compliant, i.e.
    they were expected in the Health Facility more than some weeks ago. Thus, for every project record, check
    if the return date of the last visit was more than some weeks ago and the participant hasn't a non-compliant visit
    yet.

    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param days_to_nc: Number of days since the return date defined during the last visit to the HF to be considered as
                       a non-compliant participant
    :type days_to_nc: int

    :return: Array of record ids representing those study participants that are non-compliant (according to the
    definition) and require a household visit to follow up on their status
    :rtype: pandas.Int64Index
    """

    # Cast int_next_visit column from str to date and get the last return date
    x = redcap_data
    x['int_next_visit'] = pandas.to_datetime(x['int_next_visit'])
    x['comp_date'] = pandas.to_datetime(x['comp_date'])
    last_return_dates = x.groupby('record_id')['int_next_visit'].max()
    last_return_dates = last_return_dates[last_return_dates.notnull()]
    last_nc_visits = x.groupby('record_id')['comp_date'].max()
    last_nc_visits = last_nc_visits[last_return_dates.keys()]
    already_visited = last_nc_visits > last_return_dates
    days_delayed = datetime.today() - last_return_dates[~already_visited]

    # Remove those participants who have already completed the EPI schedule, so AZi/Pbo3 already received
    completed_epi = x.query(
        "redcap_event_name == 'epimvr2_v6_iptisp6_arm_1' and "
        "intervention_complete == 2"
    )

    non_compliants = days_delayed[days_delayed > timedelta(days=days_to_nc)].keys()
    if completed_epi is not None:
        record_ids_completed_epi = completed_epi.index.get_level_values('record_id')
        non_compliants = non_compliants.difference(record_ids_completed_epi)

    return non_compliants

def build_nc_alerts_df(redcap_data, record_ids, catchment_communities, alert_string):
    """Build dataframe with record ids, communities, non-compliant days and follow up status of every study participant
    who is non-compliant and requires a supervision household visit.

    :param redcap_data:Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param record_ids: Array of record ids representing those non-compliant participants that require a supervision
    household visit
    :type record_ids: pandas.Int64Index
    :param catchment_communities: Dictionary with the community codes attached to each community name
    :type catchment_communities: dict
    :param alert_string: String with the alert to be setup containing two placeholders (community & non-compliant weeks)
    :type alert_string: str

    :return: A dataframe with the columns community, nc_days and child_fu_status in which each row is identified by the
    REDCap record id and represents a study participant to be visited due to non-compliance.
    :rtype: pandas.DataFrame
    """
    # Append to record ids, the participant's community name
    communities_to_be_visited = redcap_data['community'][record_ids]
    communities_to_be_visited = communities_to_be_visited[communities_to_be_visited.notnull()]
    communities_to_be_visited = communities_to_be_visited.apply(int).apply(str).replace(catchment_communities)
    communities_to_be_visited.index = communities_to_be_visited.index.get_level_values('record_id')

    # Append to record ids, the number of days since the return date set during the last HF visit
    nc_days = redcap_data.loc[record_ids, 'int_next_visit']
    nc_days = nc_days[nc_days.notnull()]
    nc_days = pandas.to_datetime(nc_days)
    nc_days = nc_days.groupby('record_id').max()
    nc_days = datetime.today() - nc_days

    # Transform data to be imported into the child_status_fu variable into the REDCap project
    data = {'community': communities_to_be_visited, 'nc_days': nc_days}
    data_to_import = pandas.DataFrame(data)
    if not data_to_import.empty:
        data_to_import['child_fu_status'] = data_to_import[['community', 'nc_days']].apply(
            lambda x: alert_string.format(community=x[0], weeks=math.floor(x[1].days / 7)), axis=1)

    return data_to_import

""" MORTALITY SURVEILLANCE """
def set_new_ms_alerts(redcap_project, redcap_project_df, ms_alert, ms_alert_string, choice_sep, code_sep,
                      days_after_epi,
                      event_names, excluded_epi_visits, blocked_records, fu_status_event):
    """Remove the mortality surveillance alerts of those participants that have been already contacted and setup new
    alerts for these others in which one month has passed since the last EPI visit.

    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param ms_alert: Code of the mortality surveillance alerts
    :type ms_alert: str
    :param ms_alert_string: String with the alert to be setup
    :type ms_alert_string: str
    :param choice_sep: Character used by REDCap to separate choices in a categorical field (radio, dropdown) when
                       exporting meta-data
    :type choice_sep: str
    :param code_sep: Character used by REDCap to separated code and label in every choice when exporting meta-data
    :type code_sep: str
    :param days_after_epi: Days after the last EPI visit when the mortality surveillance must ne done
    :type days_after_epi: int
    :param event_names: Dictionary in which the keys are the REDCap event codes and values the event names
    :type event_names: dict
    :param excluded_epi_visits: List of EPI visits not considered in the mortality surveillance schema
    :type excluded_epi_visits: list
    :param blocked_records: Array with the record ids that will be ignored during the alerts setup
    :type blocked_records: pandas.Int64Index
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str

    :return: None
    """

    # Get the project records ids of the participants requiring a contact to know their vital status
    records_to_be_contacted, last_visit_dates = get_record_ids_new_ms(redcap_project_df, days_after_epi,
                                                                      excluded_epi_visits)
    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_be_contacted = records_to_be_contacted.difference(blocked_records)

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, ms_alert, fu_status_event)
    # Check which of the records with alerts are not anymore in the records to be contacted (i.e. participants with an
    # activated alerts already contacted)
    if records_with_alerts is not None:
        alerts_to_be_removed = records_with_alerts.difference(records_to_be_contacted)
        # Import data into the REDCap project: Alerts removal
        to_import_dict = [{'record_id': rec_id, 'child_fu_status': ''} for rec_id in alerts_to_be_removed]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[MORTALITY-SURVEILLANCE] Alerts removal: {}".format(response.get('count')))
    else:
        print("[MORTALITY-SURVEILLANCE] Alerts removal: None")

    # Build dataframe with fields to be imported into REDCap (record_id and child_fu_status)
    to_import_df = build_new_ms_alerts_df(redcap_project_df, records_to_be_contacted, ms_alert_string, event_names,
                                          last_visit_dates)

    # Import data into the REDCap project: Alerts setup
    to_import_dict = [{'record_id': rec_id, 'child_fu_status': participant.child_fu_status}
                      for rec_id, participant in to_import_df.iterrows()]
    response = redcap_project.import_records(to_import_dict)
    print("[MORTALITY-SURVEILLANCE] Alerts setup: {}".format(response.get('count')))

def get_record_ids_new_ms(redcap_data, days_after_epi, excluded_epi_visits):
    """Get the project record ids of the participants requiring a contact to know their vital status, i.e. if they are
    alive or death. Thus, for every project record, check if the date of the last EPI visit was more than some weeks ago
    and the participant hasn't a mortality surveillance contact yet.

    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param days_after_epi: Number of days since the last visit date when the mortality surveillance contact must be done
    :type days_after_epi: int
    :param excluded_epi_visits: List of EPI visits that are not considered in the mortality surveillance schema
    :type excluded_epi_visits: list

    :return: Array of record ids representing those study participants that require a contact to know their vital status
    (alive or death)
    :rtype: pandas.Int64Index
    """

    # Cast int_date and a1m_date columns from str to date and get the last EPI visit and mortality surveillance dates
    x = redcap_data
    x['int_date'] = pandas.to_datetime(x['int_date'])
    x['a1m_date'] = pandas.to_datetime(x['a1m_date'])
    x['hh_date'] = pandas.to_datetime(x['hh_date'])
    #x['ae_date'] = pandas.to_datetime(x['ae_date'])
    #x['sae_awareness_date'] = pandas.to_datetime(x['sae_awareness_date'])
    x['ms_date_contact'] = pandas.to_datetime(x['ms_date_contact'])
    x['unsch_date'] = pandas.to_datetime(x['unsch_date']) ### TO BE CHANGED POTENTIALLY
    x['mig_date'] = pandas.to_datetime(x['mig_date'])
    x['comp_date'] = pandas.to_datetime(x['comp_date'])
    x['ch_his_date'] = pandas.to_datetime(x['ch_his_date'])
    x['sae_hosp_admin_date'] = pandas.to_datetime(x['sae_hosp_admin_date'])
    x['rtss_vacc_rtss1_date'] = pandas.to_datetime(x['rtss_vacc_rtss1_date'])
    x['rtss_vacc_rtss2_date'] = pandas.to_datetime(x['rtss_vacc_rtss2_date'])
    x['rtss_vacc_rtss3_date'] = pandas.to_datetime(x['rtss_vacc_rtss3_date'])
    x['rtss_vacc_rtss4_date'] = pandas.to_datetime(x['rtss_vacc_rtss4_date'])
    x['rtss_date'] = pandas.to_datetime(x['rtss_date'])

    x = x.query("redcap_event_name not in @excluded_epi_visits")

    """
    
    
    A CANVIAR!!!!!! 
        
    ['int_date', 'a1m_date', 'hh_date', 'ms_date_contact', 'unsch_date','sae_hosp_admin_date','comp_date', 'ch_his_date', 'rtss_date',
     'rtss_vacc_rtss1_date', 'rtss_vacc_rtss2_date', 'rtss_vacc_rtss3_date','rtss_vacc_rtss4_date',
     'int_vacc_bcg_date','int_vacc_opv1_date','int_vacc_opv2_date','int_vacc_opv3_date',
     'int_vacc_ipv_date','int_vacc_ipv2_date','int_vacc_penta1_date','int_vacc_penta2_date',
     'int_vacc_penta3_date','int_vacc_pneumo1_date','int_vacc_pneumo2_date','int_vacc_pneumo3_date',
     'int_vacc_rota1_date','int_vacc_rota2_date','int_vacc_mrv1_date','int_vacc_mrv2_date',
     'int_vacc_yellow_fever_date','int_vacc_vit_a_date','int_vacc_deworm_date',
    """

    dates_df = x.groupby('record_id')[
        ['int_date', 'a1m_date', 'hh_date', 'ms_date_contact', 'unsch_date', 'mig_date', 'sae_hosp_admin_date', 'rtss_date',
         'comp_date', 'ch_his_date','rtss_vacc_rtss1_date','rtss_vacc_rtss2_date','rtss_vacc_rtss3_date','rtss_vacc_rtss4_date']].max().reset_index().set_index('record_id')
    last_visit_dates = dates_df.apply(pd.to_datetime).max(axis=1)
    #    last_visit_dates = x.groupby('record_id')['int_date'].max()
    last_visit_dates = last_visit_dates[last_visit_dates.notnull()]
    # last_ms_contacts = x.groupby('record_id')['a1m_date'].max()
    # last_ms_contacts = last_ms_contacts[last_visit_dates.keys()]
    # already_contacted = last_ms_contacts > last_visit_dates
    last_visit_dates_dfres = last_visit_dates.reset_index().set_index('record_id')
    last_visit_dates_dfres = last_visit_dates_dfres.rename(columns={0:"last_visit"})
    last_visit_dates_dfres['last_visit'] = last_visit_dates_dfres['last_visit'].dt.strftime('%Y-%m-%d')
    today = datetime.today().date()

    datediff = []
    for record_id,date_ in last_visit_dates_dfres.T.items():
        last_visit = datetime.strptime(date_['last_visit'], "%Y-%m-%d").date()
        #print(last_visit)
        #print((today-last_visit).days)
        datediff.append((today-last_visit).days)
    last_visit_dates_dfres['datediff'] = datediff
    #print(last_visit_dates_dfres)
    days_since_last_epi_visit = last_visit_dates_dfres['datediff']
    # Remove those participants who have already completed the study follow up, so household visit at 18th month of age
    # has been carried out
    completed_fu = x.query(
        "redcap_event_name == 'hhat_18th_month_of_arm_1' and "
        "household_follow_up_complete == 2"
    )

    to_be_surveyed = days_since_last_epi_visit[days_since_last_epi_visit > days_after_epi].keys()

    #print (to_be_surveyed)
    if completed_fu is not None:
        record_ids_completed_fu = completed_fu.index.get_level_values('record_id')
        to_be_surveyed = to_be_surveyed.difference(record_ids_completed_fu)
    return to_be_surveyed, last_visit_dates[list(to_be_surveyed)]

def build_new_ms_alerts_df(redcap_data, record_ids, alert_string, event_names, last_visit_dates):
    """Build dataframe with record ids, last EPI visit and follow up status of every study participant who requires to
    be contacted to know on her vital status (alive or death).

    :param redcap_data:Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param record_ids: Array of record ids representing those participants that require to be contacted to know their
                       vital status (alive or death)
    :type record_ids: pandas.Int64Index
    :param alert_string: String with the alert to be setup containing one placeholder (last EPI visit)
    :type alert_string: str
    :param event_names: Dictionary with the event codes attached to each event name
    :type: dict

    :return: A dataframe with the columns last EPI visit and child_fu_status in which each row is identified by the
    REDCap record id and represents a study participant to be contacted to know her vital status (alive or death).
    :rtype: pandas.DataFrame
    """
    # Append to record ids, the name of the last EPI visit
    last_epi_visit = redcap_data.loc[record_ids, 'int_date']
    # last_epi_visit = redcap_data.loc[list(record_ids)][['int_date','a1m_date','hh_date', 'ae_date','sae_awareness_date','ms_date','unsch_date','mig_date','comp_date']]
    last_epi_visit = last_epi_visit[last_epi_visit.notnull()]
    new_last_visit = pd.DataFrame(columns=['redcap_event_name'])
    for k, el in last_visit_dates.T.items():
        if k in record_ids:
            last_visit = redcap_data.loc[k][['int_date', 'a1m_date', 'hh_date', 'ms_date_contact',
                 'unsch_date', 'mig_date', 'sae_hosp_admin_date', 'rtss_date',
                 'comp_date', 'ch_his_date', 'rtss_vacc_rtss1_date',
                 'rtss_vacc_rtss2_date', 'rtss_vacc_rtss3_date',
                 'rtss_vacc_rtss4_date']]
            """
              [['int_date', 'a1m_date', 'hh_date', 'sae_hosp_admin_date',
                 'ms_date_contact', 'unsch_date', 'mig_date', 'comp_date', 'ch_his_date',
                 'rtss_vacc_rtss1_date','rtss_vacc_rtss2_date','rtss_vacc_rtss3_date','rtss_vacc_rtss4_date']]
                 
            """
            last_visit = last_visit[last_visit.eq(el)]
            last_visit = last_visit[last_visit.notnull()]
            last_visit = last_visit.dropna(how='all')
            new_last_visit.loc[k] = last_visit.index[0]
    last_epi_visit = pandas.to_datetime(last_epi_visit)
    last_epi_visit = last_epi_visit.reset_index()
    idx = last_epi_visit.groupby('record_id')['int_date'].transform(max) == last_epi_visit['int_date']
    last_epi_visit = last_epi_visit[idx]
    last_epi_visit.index = last_epi_visit['record_id']

    new_last_visit = new_last_visit['redcap_event_name'].replace(event_names)
    # Transform data to be imported into the child_status_fu variable into the REDCap project
    data = {'last_epi_visit': new_last_visit}
    data_to_import = pandas.DataFrame(data)
    if not data_to_import.empty:
        data_to_import['child_fu_status'] = data_to_import[['last_epi_visit']].apply(
            lambda x: alert_string.format(last_epi_visit=x[0]), axis=1)

    return data_to_import

""" MRV2 VISIT ALERT. MONTH 15 OF AGE """
def set_mrv2_alerts(redcap_project, redcap_project_df, mrv2_alert, mrv2_alert_string, alert_date_format,
                    days_before, blocked_records, fu_status_event, months):
    """Remove the End of F/U alerts of those participants that haven been already visited for the end of the
    the trial/study follow up. Setup alerts for those participants who are going to end follow up in days_before days.

    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param mrv2_alert: Code of the End of F/U alerts
    :type mrv2_alert: str
    :param mrv2_alert_string: String with the alert to be setup
    :type mrv2_alert_string: str
    :param alert_date_format: Format of the date of the end of follow up visit to be displayed in the alert
    :type alert_date_format: str
    :param days_before: Number of days before today to start alerting the need pf the end of follow up visit
    :type days_before: int
    :param blocked_records: Array with the record ids that will be ignored during the alerts setup
    :type blocked_records: pandas.Int64Index
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str
    :param months: Number of months of age when participants end follow up
    :type months: int

    :return: None
    """

    records_to_flag = []
    records_to_flag = get_record_ids_end_15m(redcap_project_df, days_before, mrv2_age=15, about_to_turn=14)
    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_flag = records_to_flag.difference(blocked_records)
    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, mrv2_alert, fu_status_event)

    # Check which of the records with alerts are not anymore in the records to flag (i.e. participants who were already
    # visited at home for the end of the trial follow up
    if records_with_alerts is not None:
        alerts_to_be_removed = records_with_alerts.difference(records_to_flag)

        # Import data into the REDCap project: Alerts removal
        to_import_dict = [{'record_id': rec_id, 'child_fu_status': ''} for rec_id in alerts_to_be_removed]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[MRV2 VISIT] Alerts removal: {}".format(response.get('count')))
    else:
        print("[MRV2 VISIT] Alerts removal: None")
    # Build dataframe with fields to be imported into REDCap (record_id and child_fu_status)
    to_import_df = build_end_fu_alerts_df(
        redcap_data=redcap_project_df,
        record_ids=records_to_flag,
        alert_string=mrv2_alert_string,
        alert_date_format=alert_date_format,
        months=months
    )
    # Import data into the REDCap project: Alerts setup
    to_import_dict = [{'record_id': rec_id, 'child_fu_status': participant.child_fu_status}
                      for rec_id, participant in to_import_df.iterrows()]
    response = redcap_project.import_records(to_import_dict)
    print("[MRV2 VISIT] Alerts setup: {}".format(response.get('count')))

def get_record_ids_end_15m(redcap_data, days_before, mrv2_age=15, about_to_turn=14):
    """ICARIA Clinical Trial F/U: Get the project record ids of the participants who are turning 18 months in
    days_before days from today. Thus, for every project record, check if, according to her date of birth, she will be
    more than 18 months in days_before days and the participant wasn't already visited at home for the end of follow up
    visit.
    WROOOOOOOONG. I NEED TO ACTUALIZE IT !!!!


    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param days_before: Number of days before the participant turns 18 months to start alerting that about the need of
                        the end of follow up home visit
    :type days_before: int

    :return: Array of record ids representing those study participants that will be flagged because they will turn 18
    months of age in the days indicated in the days_before parameter and they have not been visited at home yet for the
    end of the trial follow up.
    :rtype: pandas.Int64Index
    """

    # Cast child_dob column from str to date
    x = redcap_data
    x['child_dob'] = pandas.to_datetime(x['child_dob'])
    dobs = x.groupby('record_id')['child_dob'].max()
    dobs = dobs[dobs.notnull()]

    # Filter those participants who are about to turn to 18 months
    # First: Filter those older than 14 months old
    about_15m = dobs[dobs.apply(calculate_age_months) >= about_to_turn]
    # Second: Filter those that will turn 15m
    if about_15m.size > 0:
        about_15m = about_15m[about_15m.apply(days_to_birthday, fu=mrv2_age) < days_before]

    # Remove those participants who have already been visited for the MRV2 visit

    finalized = x.query(
        "redcap_event_name == 'epimvr2_v6_iptisp6_arm_1' and "
        "intervention_complete != ''"
    )

    about_15m_not_seen = about_15m.index
    if finalized is not None:
        record_ids_seen = finalized.index.get_level_values('record_id')
        about_15m_not_seen = about_15m_not_seen.difference(record_ids_seen)
    return about_15m_not_seen


""" END FOLLOW UP """
def set_end_fu_alerts(redcap_project, redcap_project_df, end_fu_alert,end_fu_alert_string, alert_date_format,
                      days_before, blocked_records, study, fu_status_event,months, completed_alert_string=None,
                      unreachable_alert_string=None):
    """Remove the End of F/U alerts of those participants that haven been already visited for the end of the
    the trial/study follow up. Setup alerts for those participants who are going to end follow up in days_before days.

    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param end_fu_alert: Code of the End of F/U alerts
    :type end_fu_alert: str
    :param end_fu_alert_string: String with the alert to be setup
    :type end_fu_alert_string: str
    :param alert_date_format: Format of the date of the end of follow up visit to be displayed in the alert
    :type alert_date_format: str
    :param days_before: Number of days before today to start alerting the need pf the end of follow up visit
    :type days_before: int
    :param blocked_records: Array with the record ids that will be ignored during the alerts setup
    :type blocked_records: pandas.Int64Index
    :param study: String indicating the study where to control the end of follow up [TRIAL, COHORT]
    :type study: str
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str
    :param months: Number of months of age when participants end follow up
    :type months: int

    :return: None
    """

    records_to_flag = []
    if study == "TRIAL":
        records_to_flag, records_completed, records_unreachable = get_record_ids_end_trial_fu(
            redcap_project_df, days_before)
    if study == "COHORT":
        # Ge        # Get the project records ids of the participants who are turning 18 months in days_before days from todayt the project records ids of the participants who are turning 15 months in days_before days from today
        records_to_flag = get_record_ids_end_cohort_fu(redcap_project_df,days_before)

    # print(records_to_flag)
    # print(blocked_records)
    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_flag = records_to_flag.difference(blocked_records)
    # print(records_to_flag)

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, end_fu_alert,fu_status_event)
    xres = redcap_project_df.reset_index()
    # Check which of the records with alerts are not anymore in the records to flag (i.e. participants who were already
    # visited at home for the end of the trial follow up
    if records_with_alerts is not None:
        alerts_to_be_removed = records_with_alerts.difference(records_to_flag)
        # Import data into the REDCap project: Alerts removal
        to_import_dict = [{'record_id': rec_id, 'child_fu_status': ''} for rec_id in alerts_to_be_removed]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[END F/U] Alerts removal: {}".format(response.get('count')))
    else:
        print("[END F/U] Alerts removal: None")
    # Build dataframe with fields to be imported into REDCap (record_id and child_fu_status)
    to_import_df = build_end_fu_alerts_df(redcap_data=redcap_project_df,record_ids=records_to_flag,alert_string=end_fu_alert_string,alert_date_format=alert_date_format,months=months)

    # Import data into the REDCap project: Alerts setup
    to_import_dict = [
        {'record_id': rec_id, 'child_fu_status': participant.child_fu_status}
        for rec_id, participant in to_import_df.iterrows()]
    response = redcap_project.import_records(to_import_dict)
    print("[END F/U] Alerts setup: {}".format(response.get('count')))

    # COMPLETED PARTICIPANTS ALERT PART
    # BASED ON THE
    if unreachable_alert_string is not None:
        to_import_df = pandas.DataFrame(index=records_unreachable, columns=['child_fu_status'])
        to_import_df['child_fu_status'] = unreachable_alert_string

        to_import_df = to_import_df.reset_index(drop=False).drop_duplicates().set_index('record_id')
        # Import data into the REDCap project: Alerts setup
        to_import_dict = [{'record_id': rec_id,'child_fu_status': participant.child_fu_status}
                          for rec_id, participant in to_import_df.iterrows()]

        real_unreachable = records_unreachable.difference(records_completed)
        response = redcap_project.import_records(to_import_dict)

        print("[UNREACHABLE PARTICIPANTS] Alerts setup: {}".format(response.get('count')))
        print("[REAL UNREACHABLE PARTICIPANTS] Alerts setup: {}".format(len(real_unreachable)))
    if completed_alert_string is not None:
        to_import_df = pandas.DataFrame(index=records_completed,columns=['child_fu_status'])
        to_import_df['child_fu_status'] = completed_alert_string
        to_import_df = to_import_df.reset_index(drop=False).drop_duplicates().set_index('record_id')

        # Import data into the REDCap project: Alerts setup
        to_import_dict = [{'record_id': rec_id,'child_fu_status': participant.child_fu_status}
                          for rec_id, participant in to_import_df.iterrows()]

        response = redcap_project.import_records(to_import_dict)
        print("[COMPLETED PARTICIPANTS] Alerts setup: {}".format(response.get('count')))


def get_record_ids_end_trial_fu(redcap_data, days_before, fu_age=18, about_to_turn=17):
    """ICARIA Clinical Trial F/U: Get the project record ids of the participants who are turning 18 months in
    days_before days from today. Thus, for every project record, check if, according to her date of birth, she will be
    more than 18 months in days_before days and the participant wasn't already visited at home for the end of follow up
    visit.

    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param days_before: Number of days before the participant turns 18 months to start alerting that about the need of
                        the end of follow up home visit
    :type days_before: int

    :return: Array of record ids representing those study participants that will be flagged because they will turn 18
    months of age in the days indicated in the days_before parameter and they have not been visited at home yet for the
    end of the trial follow up.
    :rtype: pandas.Int64Index
    """

    # Cast child_dob column from str to date
    x = redcap_data
    x['child_dob'] = pandas.to_datetime(x['child_dob'])
    dobs = x.groupby('record_id')['child_dob'].max()
    dobs = dobs[dobs.notnull()]

    # Filter those participants who are about to turn to 18 months
    # First: Filter those older than 17 months old
    about_18m = dobs[dobs.apply(calculate_age_months) >= about_to_turn]
    # Second: Filter those that will turn 18m
    if about_18m.size > 0:
        about_18m = about_18m[about_18m.apply(days_to_birthday, fu=fu_age) < days_before]

    # Remove those participants who have already been visited and seen at home for the end of the trial follow up
    finalized = x.query(
        "redcap_event_name == 'hhat_18th_month_of_arm_1' and "
        "redcap_repeat_instrument == 'household_follow_up' and "
            "(hh_child_seen == 1 or phone_child_status == 1 or phone_child_status == 4 or hh_why_not_child_seen == 1 or  "
            "hh_why_not_child_seen == 4 or hh_why_not_child_seen == 5)"
    )
    unreachable = x.query(
        "redcap_event_name == 'hhat_18th_month_of_arm_1' and "
        "redcap_repeat_instrument == 'household_follow_up' and "
        "reachable_status == 2")


    about_18m_not_seen = about_18m.index
    record_ids_seen = None
    records_unreachable = None
    if finalized is not None:
        record_ids_seen = finalized.index.get_level_values('record_id')
        about_18m_not_seen = about_18m_not_seen.difference(record_ids_seen)
    if unreachable is not None:
        records_unreachable = unreachable.index.get_level_values('record_id')
        about_18m_not_seen = about_18m_not_seen.difference(records_unreachable)

    return about_18m_not_seen, record_ids_seen, records_unreachable

def get_record_ids_end_cohort_fu(redcap_data, days_before):
    """ICARIA Cohort Study F/U: Get the project record ids of the participants who are turning 15 months in days_before
    days from today. Thus, for every project record, check if, according to her date of birth, she will be more than 15
    months in days_before days and the participant wasn't already visited for the end of follow up visit.

    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param days_before: Number of days before the participant turns 15 months to start alerting that about the need of
                        the end of follow up visit
    :type days_before: int

    :return: Array of record ids representing those study participants that will be flagged because they will turn 15
    months of age in the days indicated in the days_before parameter and they have not been visited at home yet for the
    end of the trial follow up.
    :rtype: pandas.Int64Index
    """

    # Cast child_dob column from str to date
    x = redcap_data
    x['child_dob'] = pandas.to_datetime(x['child_dob'])
    dobs = x.groupby('record_id')['child_dob'].max()
    dobs = dobs[dobs.notnull()]

    # Filter those participants who are about to turn to 15 months
    # First: Filter those older than 14 months old
    about_15m = dobs[dobs.apply(calculate_age_months) >= 14]
    # Second: Filter those that will turn 15m
    if about_15m.size > 0:
        about_15m = about_15m[about_15m.apply(days_to_birthday, fu=15) < days_before]

    # Remove those participants who have already been visited for the end of the trial follow up
    finalized = x.query(
        "redcap_event_name == 'after_mrv_2_arm_1' and "
        # "redcap_repeat_instrument == 'household_follow_up' and "
        "tests_complete == 2"
    )

    about_15m_not_seen = about_15m.index
    if finalized is not None:
        record_ids_seen = finalized.index.get_level_values('record_id')
        about_15m_not_seen = about_15m_not_seen.difference(record_ids_seen)

    return about_15m_not_seen

def build_end_fu_alerts_df(redcap_data, record_ids, alert_string, alert_date_format, months):
    """Build dataframe with record ids and dates when they turn the specified months of every study participant who is
    turning the specified months in the next days or she has already the specified months but she hasn't been visited
    for the end of the trial follow up.

    :param redcap_data:Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param record_ids: Array of record ids representing those study participants that require the end of follow up
                       household visit
    :type record_ids: pandas.Int64Index
    :param alert_string: String with the alert to be setup containing one placeholders (X months birthday)
    :type alert_string: str
    :param alert_date_format: Format of the date of the X months birthday to be displayed in the alert
    :type alert_date_format: str
    :param months: Number of months of age when participants end follow up
    :type months: int

    :return: A dataframe with the columns months birthday and child_fu_status in which each row is identified by the
    REDCap record id and represents a study participant who is supposed to be visited for the end of the follow up.
    :rtype: pandas.DataFrame
    """
    # Append to record ids, the 18 moths birthday of the participant

    birthday = redcap_data.loc[record_ids, ['child_dob']]
    birthday = birthday.groupby('record_id')['child_dob'].max()  # To move from a DataFrame to a Series
    birthday = birthday.apply(lambda dob: dob + relativedelta(months=+months))  # Add specified months to dob
    birthday = birthday.apply(lambda x: x.strftime(alert_date_format))

    # Transform data to be imported into the child_status_fu variable into the REDCap project
    data = {'birthday': birthday}
    data_to_import = pandas.DataFrame(data)
    if not data_to_import.empty:
        data_to_import['child_fu_status'] = data_to_import[['birthday']].apply(
            lambda x: alert_string.format(birthday=x[0]), axis=1)

    return data_to_import

""" BIRTH WEIGHT ALERT """
def set_bw_alerts(redcap_project, redcap_project_df, bw_alert, blocked_records, fu_status_event):
    """
    To alert of those participants without information about Birth Weight

    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param bw_alert: Code of the Birth Weight alert.
    :type bw_alert: str
    :param blocked_records: Array with the record ids that will be ignored during the alerts setup
    :type blocked_records: pandas.Int64Index
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: st
    :return: None
    """

    REDCAP_QUERY = redcap_project_df.query("redcap_event_name == 'epipenta1_v0_recru_arm_1'")

    BW_REDCAP = REDCAP_QUERY[
        (REDCAP_QUERY['child_birth_weight_known'].isnull())]  # (REDCAP_QUERY['child_weight_birth'].isnull())

    # Remove those ids that must be ignored
    records_bw = BW_REDCAP.index.get_level_values(0)
    if blocked_records is not None:
        records_bw = records_bw.difference(blocked_records)

    records_with_alerts = get_active_alerts(redcap_project_df, bw_alert, fu_status_event, type_='BW')

    if records_with_alerts is not None:
        alerts_to_be_removed = records_with_alerts.difference(records_bw)
        # Import data into the REDCap project: Alerts removal
        to_import_dict = [
            {'record_id': rec_id, 'child_fu_status': str(REDCAP_QUERY['child_fu_status'][rec_id][0]).split("(BW)")[0]} for
            rec_id in alerts_to_be_removed]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[BIRTH WEIGHT] Alerts removal: {}".format(response.get('count')))
    else:
        print("[BIRTH WEIGHT] Alerts removal: None")

    df_to_set_alarm = BW_REDCAP.reset_index()[['record_id', 'child_fu_status']]
    to_import_list = []
    for k, el in df_to_set_alarm.T.items():
        if el.record_id in records_bw:
            id = el.record_id
            if str(el.child_fu_status) == 'nan':
                status = "(BW)"
            else:
                if "COMPLETED" in str(el.child_fu_status):
                    status = str(el.child_fu_status).split("(BW)")[0]
                else:
                    status = str(el.child_fu_status).split("(BW)")[0] + "(BW)"

            to_import_list.append({'record_id': id, 'child_fu_status': status})
    response = redcap_project.import_records(to_import_list)
    print("[BIRTH WEIGHT] Alerts setup: {}".format(response.get('count')))

""" AZIVAC ALERT """


def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month
def set_azivac_alerts(redcap_project, redcap_project_df, av_alert, blocked_records, fu_status_event):
    """
    To alert of those participants without information about Birth Weight

    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param av_alert: Code of the Birth Weight alert.
    :type av_alert: str
    :param blocked_records: Array with the record ids that will be ignored during the alerts setup
    :type blocked_records: pandas.Int64Index
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str
    :return: None
    """


    REDCAP_QUERY = redcap_project_df.query("redcap_event_name == 'epipenta1_v0_recru_arm_1'")
    V4_REDCAP_QUERY = redcap_project_df.query("redcap_event_name == 'epimvr1_v4_iptisp4_arm_1'")
    V5_REDCAP_QUERY = redcap_project_df.query("redcap_event_name == 'epivita_v5_iptisp5_arm_1'")
    V4_REDCAP_QUERY['azivac_study_number'] = V4_REDCAP_QUERY['azivac_study_number'].fillna('')
    V5_REDCAP_QUERY['azivac_study_number'] = V5_REDCAP_QUERY['azivac_study_number'].fillna('')


    if not V4_REDCAP_QUERY.empty:
        AV_REDCAP_V4 = V4_REDCAP_QUERY[(V4_REDCAP_QUERY['azivac_study_number']!='')&(~V4_REDCAP_QUERY['azivac_date'].isnull())]
        AV_REDCAP_V5 = V5_REDCAP_QUERY[(V5_REDCAP_QUERY['azivac_study_number']!='')&(~V5_REDCAP_QUERY['azivac_date'].isnull())]
        AVRES5 = AV_REDCAP_V5.reset_index()
        #print(AVRES5['record_id'])
        #print(AVRES5[AVRES5['record_id']=='16040268'])
        if not AV_REDCAP_V4.empty:
            AV_REDCAP_V4[['azivac_date']] = AV_REDCAP_V4[['azivac_date']].apply(pd.to_datetime)

            # Get only those participants with AziVac collection done between 1M and 4M ago
            #AV_REDCAP_V4 = AV_REDCAP_V4[((datetime.today() - AV_REDCAP_V4['azivac_date']).dt.days >= 30)&((datetime.today() - AV_REDCAP_V4['azivac_date']).dt.days <=120)]

            #AV_REDCAP_AL1 = AV_REDCAP_V4[((datetime.today() - AV_REDCAP_V4['azivac_date']).dt.days >= 30)&((datetime.today() - AV_REDCAP_V4['azivac_date']).dt.days <=91)]
            #AV_REDCAP_AL2 = AV_REDCAP_V4[((datetime.today() - AV_REDCAP_V4['azivac_date']).dt.days > 91)&((datetime.today() - AV_REDCAP_V4['azivac_date']).dt.days <=121)]

            AL1_tf = []
            AL2_tf = []
            for k,el in AV_REDCAP_V4.T.items():
                #datetime_object = datetime.strptime(el,'%y-%m-%d %H:%M:%S')
                dm = diff_month(date.today(),el['azivac_date'])
                #print(k,el['azivac_date'],dm)
                if 2 > dm >= 1:
                    AL1_tf.append(True)
                else:
                    AL1_tf.append(False)

                if 4 > dm >= 2:
                    AL2_tf.append(True)
                else:
                    AL2_tf.append(False)

            #for k, el in AV_REDCAP_AL1.T.items():
            #    if k[0] not in AV_REDCAP_V4[AL1_tf].reset_index()['record_id'].unique():
            #        print(k[0])

            AV_REDCAP_AL1 = AV_REDCAP_V4[AL1_tf]
            AV_REDCAP_AL2 = AV_REDCAP_V4[AL2_tf]

            ## ALARM 1
            build_azivac(redcap_project, redcap_project_df, av_alert,blocked_records, fu_status_event, AV_REDCAP_AL1,AVRES5)
            build_azivac(redcap_project, redcap_project_df, params.AZIVAC_ALERT_SERIOUS, blocked_records, fu_status_event, AV_REDCAP_AL2, AVRES5,print_=True)
            #build_azivac(redcap_project, redcap_project_df, av_alert, blocked_records, fu_status_event, AV_REDCAP_AL2, AVRES5, print_=True)
        #       set_azivac_part2(redcap_project, redcap_project_df, av_alert2,blocked_records, fu_status_event, AV_REDCAP_AL2,AVRES5)
        else:
            print("[AZIVAC] Alerts removal: None")
            print("[AZIVAC] Alerts setup: None")

    else:
        print("[AZIVAC] Alerts removal: None")
        print("[AZIVAC] Alerts setup: None")

def build_azivac(redcap_project, redcap_project_df, av_alert, blocked_records, fu_status_event,AV_REDCAP_AL1,AVRES5,print_=False):
    REDCAP_QUERY = redcap_project_df.query("redcap_event_name == 'epipenta1_v0_recru_arm_1'")

    records_av_al1 = AV_REDCAP_AL1.index.get_level_values(0)
#    print(records_av_al1)
   # Remove those ids with already endline collected
    if list(AVRES5['record_id']) is not None:
        records_av_al1 = records_av_al1.difference(list(AVRES5['record_id']))

    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_av_al1 = records_av_al1.difference(blocked_records)

    if params.azivac_blocked_records is not None:
#        print(params.azivac_blocked_records)
        records_av_al1 = records_av_al1.difference(params.azivac_blocked_records)

    records_with_alerts_al1 = get_active_alerts(redcap_project_df, av_alert, fu_status_event, type_='BW')
#    print(records_with_alerts_al1)
    if records_with_alerts_al1 is not None:
        alerts_to_be_removed_al1 = records_with_alerts_al1.difference(records_av_al1)
        # Import data into the REDCap project: Alerts removal
        to_import_dict = [
            {'record_id': rec_id, 'child_fu_status': str(REDCAP_QUERY['child_fu_status'][rec_id][0]).split('(')[0]} for
            rec_id in alerts_to_be_removed_al1]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[AZIVAC] Alerts removal: {}".format(response.get('count')))
    else:
        print("[AZIVAC] Alerts removal: None")


    RC_query_res = REDCAP_QUERY.reset_index()
    df_to_set_alarm_al1 = RC_query_res[RC_query_res['record_id'].isin(records_av_al1)][['record_id','child_fu_status']]
    to_import_list = []
    for k, el in df_to_set_alarm_al1.T.items():
        if el.record_id in records_av_al1:
            id = el.record_id
            if str(el.child_fu_status) == 'nan':
                status = av_alert
            else:
                if "COMPLETED" in str(el.child_fu_status):
                    status = str(el.child_fu_status).split('(')[0]
                else:
                    status = str(el.child_fu_status).split('(')[0] + av_alert
            to_import_list.append({'record_id': id, 'child_fu_status': status})

#    if print_:
#        print(to_import_list)
    response = redcap_project.import_records(to_import_list)
    print("[AZIVAC] Alerts setup: {}".format(response.get('count')))




############################################################################################
######################### NON-CONTEMPORARY COHORT STUDY ####################################
############################################################################################

""" NON-CONTEMPORARY COHORT STUDY """
def set_nc_cohort_alerts(project_key, redcap_project, redcap_project_df, cohort_alert, cohort_alert_string,
                         blocked_records, fu_status_event):
    """
    Determine which are the possible Cohort participants, based on the non-ICARIA COHORT participants range of age,
    month, and HF. Those participants changes every day, since the tw weeks after the 3rd dosis administration could
    add new participants every day.

    :param project_key: The id of the REDCap project HF
    :type project_key: str
    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param cohort_alert: Code of the End of F/U alerts
    :type cohort_alert: str
    :param cohort_alert_string: String with the alert to be setup
7    :type cohort_alert_string: str
    :param blocked_records: Array with the record ids that will be ignored during the alerts setup
    :type blocked_records: pandas.Int64Index
    :param fu_status_event: ID of the REDCap project event in which the follow up status variable is contained
    :type fu_status_event: str
    :return: None
    """
    records_to_flag = []
    current_month = datetime.now().month
    # Retrive from non-icaria cohorts, the range of age and number of participants per letter that we need to recruit
    cohort_list_df = pd.read_excel(tokens.COHORT_RECRUITMENT_PATH,
                                   str(current_month))
    big_project_key = project_key.split(".")[0]
    if big_project_key.split(".")[0] in cohort_list_df['HF'].unique():
        min_age = cohort_list_df[cohort_list_df['HF'] == big_project_key][
            'min_age'].unique()[0]
        max_age = cohort_list_df[cohort_list_df['HF'] == big_project_key][
            'max_age'].unique()[0]
        nletter = cohort_list_df[cohort_list_df['HF'] == big_project_key][
            'target_letter'].unique()[0]
        letters_to_be_contacted = get_record_ids_nc_cohort(redcap_project_df,
                                                           max_age, min_age)
        # Determine if we have already recruited the number of cohort participants needed for this HF-month
        need_to_stop = cohort_stopping_sistem(redcap_project_df, nletter,
                                              project_key)
        if need_to_stop == False:
            records_to_be_contacted = letters_to_be_contacted[
                'record_id'].unique()
            records_to_be_contacted_index = pd.DataFrame(
                index=records_to_be_contacted).index
        else:
            # If the stopping rules are true, then the alert shouldn't be labeled, so we set the df empty
            records_to_be_contacted_index = pd.DataFrame(index=[]).index
        # Remove those ids that must be ignored
        if blocked_records is not None:
            records_to_flag = records_to_be_contacted_index.difference(
                blocked_records)
        # Get the project records ids of the participants with an active alert
        records_with_alerts = get_active_alerts(redcap_project_df, cohort_alert,
                                                fu_status_event)
        # Check which of the records with alerts are not anymore in the records to flag (i.e. participants who were
        # already visited at home for the end of the trial follow up
        if records_with_alerts is not None:
            alerts_to_be_removed = records_with_alerts.difference(
                records_to_flag)
            # Import data into the REDCap project: Alerts removal
        #            REDCAP_QUERY = redcap_project_df.query("redcap_event_name == 'epipenta1_v0_recru_arm_1'")
        #            to_import_dict = [{'record_id': rec_id, 'child_fu_status':
        #                str(REDCAP_QUERY['child_fu_status'][rec_id][0]).split(cohort_alert_string)[-1]} for rec_id in alerts_to_be_removed]
        #              response = redcap_project.import_records(to_import_dict, overwrite='overwrite')

        #            print("[ICARIA COHORT] Alerts removal: {}".format(response.get('count')))
        #        else:
        #            print("[ICARIA COHORT] Alerts removal: None")

        to_import_removed_cohorts = remove_labels_cohorts(redcap_project_df)
        # Import data into the REDCap project: Alerts setup
        to_import_removed_cohorts = [{'record_id': rec_id,
                                      'child_fu_status': participant.child_fu_status}
                                     for rec_id, participant in
                                     to_import_removed_cohorts.iterrows()]
        response = redcap_project.import_records(to_import_removed_cohorts)
        print("[ICARIA COHORT PARTICIPANTS] Removal: {}".format(
            response.get('count')))

        # Build dataframe with fields to be imported into REDCap (record_id and child_fu_status)
        #        to_import_df = build_cohort_alerts_df(
        #            record_ids=records_to_flag,
        #            alert_string=cohort_alert_string,
        #            redcap_project=redcap_project
        #        )
        # Import data into the REDCap project: Alerts setup
        #        to_import_dict = [{'record_id': rec_id, 'child_fu_status': participant.child_fu_status}
        #                          for rec_id, participant in to_import_df.iterrows()]
        ##        to_import_dict = [{'record_id': rec_id, 'child_fu_status':
        ##            str(REDCAP_QUERY['child_fu_status'][rec_id][0]).split(cohort_alert_string)[-1]} for rec_id,participant in
        ##                          to_import_df.iterrows()]

        #        response = redcap_project.import_records(to_import_dict)

        #        print("[ICARIA COHORT] Alerts setup: {}".format(response.get('count')))

        to_import_actual_cohorts = set_label_cohorts(redcap_project)
        to_import_actual_cohorts = [{'record_id': rec_id,
                                     'child_fu_status': participant.child_fu_status}
                                    for rec_id, participant in
                                    to_import_actual_cohorts.iterrows()]
        response = redcap_project.import_records(to_import_actual_cohorts)
        print("[ICARIA COHORT PARTICIPANTS] setup: {}".format(
            response.get('count')))

def get_record_ids_nc_cohort(redcap_data, max_age, min_age):
    """
    :param redcap_data: Data frame containing all data exported from the REDCap project
    :type redcap_data: pandas.DataFrame
    :param min_age: Minimum age that the cohort children can have in this HF-month
    :type str
    :param max_age: Maximum age that the cohort children can have in this HF-month
    :type str
    :return:
    """

    ## 1 CRITERIA: Having received at least 4 doses of SP
    x = redcap_data
    xres = x.reset_index()

    sp_doses = xres[xres['int_sp']==float(1)]
    sp_doses = xres[xres['int_sp']==float(1)].groupby('record_id')['int_sp'].count()
    record_id_only_4_doses = xres[xres['int_sp']==float(1)].groupby('record_id').count()[sp_doses == 4].index
    record_id_4_doses = xres[xres['int_sp']==float(1)].groupby('record_id').count()[sp_doses > 4].index

    ## 2 CRITERIA: >2 weeks from 3rd dosis of of SP
    # AIXÒ S'HA DE MIRAR BÉ, LO DE L'SP < 14 DIES. PERQUÈ LES XIFRES VAN VARIANT MOLT.
    last_SP = xres[(xres['int_sp'] == 1) & (xres['record_id'].isin(record_id_only_4_doses))].groupby('record_id')[
        'int_date'].last().reset_index()
    more_14days = []
    for k, el in last_SP.T.items():
        days_from_SP = datetime.today() - datetime.strptime(el['int_date'], "%Y-%m-%d %H:%M:%S")
        if days_from_SP.days >= 14:
            more_14days.append(True)
        else:
            more_14days.append(False)
    try:
        record_id_only_4_doses = last_SP[more_14days]['record_id']
    except:
        record_id_only_4_doses = []
    record_id_4_doses = list(record_id_4_doses)
    for el in list(record_id_only_4_doses):
        if el not in record_id_4_doses:
            record_id_4_doses.append(el)

    ## 3 CRITERIA: Within age range criteria
    records_range_age = get_record_ids_range_age(redcap_data, min_age, max_age)
    cohorts_to_be_contacted = list(set(record_id_4_doses).intersection(list(records_range_age)))
    # 4 CRITERIA: Not death or migrated participants
    try:
        deaths = xres[(xres['redcap_event_name'] == 'end_of_fu_arm_1') & (~xres['death_reported_date'].isnull())][
            'record_id'].unique()
    except:
        deaths = []
    try:
        migrated = xres[(xres['redcap_event_name'] == 'out_of_schedule_arm_1') & (~xres['mig_date'].isnull())][
            'record_id'].unique()
    except:
        migrated = []
    # 5 CRITERIA: Not already recruited in Cohort study
    already_cohorts = xres[(xres['redcap_event_name'] == 'cohort_after_mrv_2_arm_1') & (~xres['ch_his_date'].isnull())][
        'record_id'].unique()
    # 6 CRITERIA: Participant is not completed
    completed_participants = xres[(xres['redcap_event_name']=='hhat_18th_month_of_arm_1')&(~xres['hh_date'].isnull())]['record_id'].unique()
    letters_to_be_contacted = xres[(xres['record_id'].isin(cohorts_to_be_contacted)) &
                                   (~xres['record_id'].isin(list(deaths))) &
                                   (~xres['record_id'].isin(list(migrated))) &
                                   (~xres['record_id'].isin(list(already_cohorts))) &
                                   (~xres['record_id'].isin(list(completed_participants))) &
                                   (xres['redcap_event_name'] == 'epipenta1_v0_recru_arm_1')][
        ['record_id', 'int_random_letter']]

    #print(completed_participants)
    # print(letters_to_be_contacted.groupby('int_random_letter').count())
    return letters_to_be_contacted

def get_record_ids_range_age(redcap_data,min_age,max_age,date_='2023-03-01'):
    xre = redcap_data.reset_index()
    #end_date = datetime.strptime(date_, "%Y-%m-%d").date()
    end_date = datetime.strptime("2023-"+str(date.today().month)+"-01", "%Y-%m-%d").date()
    dob_count = 0

    dobs = list(xre[xre['redcap_event_name'] == 'epipenta1_v0_recru_arm_1']['child_dob'])
    dob_df = pd.DataFrame(index=xre.record_id.unique(), columns=['dob_diff'])

    for record_id in xre.record_id.unique():
        try:
            start_date = datetime.strptime(dobs[dob_count], "%Y-%m-%d")
            delta = relativedelta(end_date, start_date)

            res_months = delta.months + (delta.years * 12)
            if delta.days != 0:
                res_months+=1
            #print(record_id,start_date,end_date,delta,res_months,delta.months,delta.days)
            dob_df.loc[record_id]['dob_diff']= res_months
        except:
            pass
            #try:
            #    print(record_id, dobs[dob_count])
            #except:
            #    print(record_id)
        dob_count += 1
    #print(dob_df[(dob_df['dob_diff']<= max_age) & (dob_df['dob_diff'] >= min_age)])
    return dob_df[(dob_df['dob_diff']<= max_age) & (dob_df['dob_diff'] >= min_age)].index

def cohort_stopping_sistem(redcap_project,nletter,projectkey,date_='2023-06'):
    """
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame

    :return: List of record ids per letter
    """

    date_ = "-".join(str(date.today()).split("-")[:-1])

    if "." in str(projectkey):
        cohorts_from_this_months = pd.DataFrame()
        for el in params.subprojects[str(projectkey).split(".")[0]]:
            project = redcap.Project(params.URL, params.TRIAL_PROJECTS[el])
            df = project.export_records(format_type='df', fields=params.ALERT_LOGIC_FIELDS)
            xres = df.reset_index()
            actual_cohorts = xres[xres['redcap_event_name']=='cohort_after_mrv_2_arm_1'][['record_id','ch_his_date']]
            letters_ = xres[(xres['record_id'].isin(list(actual_cohorts['record_id'].unique())))&(xres['redcap_event_name']=='epipenta1_v0_recru_arm_1')][['record_id','int_random_letter']]
            STOP = False
            actual_cohorts = actual_cohorts.dropna()
            if actual_cohorts.empty:
                pass
            else:
                records_dates_=actual_cohorts[actual_cohorts['ch_his_date'].str.contains(date_)]
                cohorts_from_this_months_subproj = pd.merge(records_dates_,letters_, on='record_id')

                if cohorts_from_this_months.empty:
                    cohorts_from_this_months = cohorts_from_this_months_subproj
                else:
                    cohorts_from_this_months = pd.concat([cohorts_from_this_months,cohorts_from_this_months_subproj])
                #print(cohorts_from_this_months)

        if cohorts_from_this_months.empty:
            return STOP

    else:
        xres = redcap_project.reset_index()
        actual_cohorts = xres[xres['redcap_event_name']=='cohort_after_mrv_2_arm_1'][['record_id','ch_his_date']]
        letters_ = xres[(xres['record_id'].isin(list(actual_cohorts['record_id'].unique())))&(xres['redcap_event_name']=='epipenta1_v0_recru_arm_1')][['record_id','int_random_letter']]
        STOP = False
        if actual_cohorts.empty:
            return STOP
        #print(actual_cohorts)
        actual_cohorts = actual_cohorts.dropna()
        records_dates_=actual_cohorts[actual_cohorts['ch_his_date'].str.contains(date_)]
        if projectkey == 'HF11' and date_=='2023-03':
            records_dates_ = (records_dates_[~records_dates_['record_id'].isin([240,239])])
        cohorts_from_this_months = pd.merge(records_dates_,letters_, on='record_id')


    #print(cohorts_from_this_months.groupby('int_random_letter').count()['record_id'])
    if len(cohorts_from_this_months.groupby('int_random_letter').count())==6 and sum(list(cohorts_from_this_months.groupby('int_random_letter').count()['record_id']>=nletter))==6: #False not in list(cohorts_from_this_months.groupby('int_random_letter').count()['record_id']>=nletter):
        STOP = True
        print ("It has been recruited all minimum participants per letter ("+str(nletter)+") and the alert for this HF needs to stop.")
    elif len(cohorts_from_this_months.groupby('int_random_letter').count())>=2:
        sum_ = 0
        for el in cohorts_from_this_months.groupby('int_random_letter').count()['record_id']:
            if el > nletter:
                el = nletter
            sum_+= el
        nletter_comp = nletter + (nletter*6 - sum_)
        if sum(list(cohorts_from_this_months.groupby('int_random_letter').count()['record_id']>=nletter_comp))>=4:
            print("It has been recruited the minimum participants per letter + compensation (" + str(nletter) + ") in, at least, 4 letters, and the alert for this HF needs to stop.")
            STOP = True
    return STOP

def remove_labels_cohorts(redcap_data):
    """
    Determine (if exist) which labeld cohort participants should be removed because of their removal from the substudy

    :param redcap_data: A REDCap project class to communicate with the REDCap API
    :type redcap_data: redcap.Project
    """

    xres = redcap_data.reset_index()
    actual_cohorts = list(xres[xres['redcap_event_name'] == 'cohort_after_mrv_2_arm_1']['record_id'])
    if xres[~xres['child_fu_status'].isnull()].empty:
        return pd.DataFrame(columns=['child_fu_status'])
    actual_labeled_cohort = xres[(xres['redcap_event_name'] == 'epipenta1_v0_recru_arm_1') &
                                 (xres['child_fu_status'].str.contains('COH\.'))][['record_id', 'child_fu_status']]

    list_labels_to_remove = list(set(actual_labeled_cohort['record_id']) - set(actual_cohorts))
    df_to_remove_alarm = pd.DataFrame(index=list_labels_to_remove, columns=['child_fu_status'])
    for k, el in actual_labeled_cohort.T.items():
        if el['record_id'] in list_labels_to_remove:
            df_to_remove_alarm['child_fu_status'][el['record_id']] = el['child_fu_status'].replace("COH.", "")

    return df_to_remove_alarm

def set_label_cohorts(redcap_project):
    """
    Get list of participants and label that need to be prompted as Cohort participants

    :param redcap_data: A REDCap project class to communicate with the REDCap API
    :type redcap_data: redcap.Project
    :return
    """
    redcap_data = redcap_project.export_records(format_type='df', fields=params.ALERT_LOGIC_FIELDS)

    xres = redcap_data.reset_index()

    if xres[~xres['child_fu_status'].isnull()].empty:
        return pd.DataFrame(columns=['child_fu_status'])

    actual_cohorts = list(xres[(xres['redcap_event_name'] == 'cohort_after_mrv_2_arm_1')&(~xres['ch_his_date'].isnull())]['record_id'])
    actual_child_fu_status = xres[(xres['record_id'].isin(actual_cohorts)) &
                                  (xres['redcap_event_name'] == 'epipenta1_v0_recru_arm_1')][['record_id', 'child_fu_status']]
    df_to_set_alarm = pd.DataFrame(index=list(actual_cohorts), columns=['child_fu_status'])
    actual_labeled_cohort = xres[(xres['redcap_event_name'] == 'epipenta1_v0_recru_arm_1') &
                                 (xres['child_fu_status'].str.contains('COH\.'))][['record_id', 'child_fu_status']]
    list_labels_to_remove = list(set(actual_labeled_cohort['record_id']) - set(actual_cohorts))
    df_to_remove_alarm = pd.DataFrame(index=list_labels_to_remove, columns=['child_fu_status'])

    for k, el in actual_labeled_cohort.T.items():
        if el['record_id'] in list_labels_to_remove:
            df_to_remove_alarm['child_fu_status'][el['record_id']] = el['child_fu_status'].replace("COH.", "")
    for k, el in actual_child_fu_status.T.items():
        if el['record_id'] not in list_labels_to_remove:
            if str(el['child_fu_status']) == 'nan' or str(el['child_fu_status']) == 'NaN' or el['child_fu_status'] is None:
                df_to_set_alarm['child_fu_status'][el['record_id']] = params.FINALIZED_COHORT_STRING
            elif str(params.FINALIZED_COHORT_STRING) in str(el['child_fu_status']):
                df_to_set_alarm['child_fu_status'][el['record_id']] = el['child_fu_status'].replace("(COHORT pending)","")
            else:
                df_to_set_alarm['child_fu_status'][el['record_id']] = params.FINALIZED_COHORT_STRING + str(
                    el['child_fu_status'].replace("(COHORT pending)", ""))
    return df_to_set_alarm


def build_cohort_alerts_df(record_ids, alert_string, redcap_project):
    """Build dataframe with data of the Cohort alert on those participants yet to be recruited in the cohort study

    :param record_ids: Array of record ids representing those study participants that require the cohort recruitment
    :type record_ids: pandas.Int64Index
    :param alert_string: String with the alert to be setup
    :type alert_string: str
    :param redcap_project:Exported REDCap project data
    :type redcap_project: pandas.DataFrame
    :return: A dataframe with the column child_fu_status in which each row is identified by the REDCap record id and
     represents a study participant who is supposed to be recruited for the Cohort study.
    :rtype: pandas.DataFrame
    """

    redcap_data = redcap_project.export_records(format_type='df', fields=params.ALERT_LOGIC_FIELDS)

    fustatus = redcap_data.loc[record_ids, ['child_fu_status']]
    fustatus = fustatus.groupby('record_id')['child_fu_status'].last()  # To move from a DataFrame to a Series

    df_to_set_alarm = pd.DataFrame(index=record_ids, columns=['child_fu_status'])
    for k, el in fustatus.T.items():
        if el == None:
            df_to_set_alarm['child_fu_status'][k] = alert_string
        elif el == alert_string:
            df_to_set_alarm['child_fu_status'][k] = alert_string
        else:
            df_to_set_alarm['child_fu_status'][k] = alert_string + el.split(alert_string)[-1]

    return df_to_set_alarm
