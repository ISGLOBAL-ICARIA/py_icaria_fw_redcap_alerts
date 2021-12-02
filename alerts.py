from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import math
import pandas


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
    community_field = redcap_project.export_metadata(fields=['community'], format='df')
    community_choices = community_field['select_choices_or_calculations'].community
    communities_string = community_choices.split(choice_sep)
    return {community.split(code_sep)[0]: community.split(code_sep)[1] for community in communities_string}


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
    azi_doses = redcap_data.groupby('record_id')['int_azi'].sum()
    times_hh_child_seen = redcap_data.groupby('record_id')['hh_child_seen'].sum()
    azi_supervision = azi_doses - times_hh_child_seen

    return azi_supervision[azi_supervision > 0].keys()


def get_record_ids_nc(redcap_data, days_to_nc):
    """Get the project record ids of the participants requiring a household visit because they are non-compliant, i.e.
    they were expected in the Health Facility more than some weeks ago. Thus, for every project record, check
    if the return date of the last visit was more than some weeks ago and the participant hasn't a non-compliant visit
    yet.

    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param days_to_nc: Number of days from the return date defined during the last visit to the HF to be considered as
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

    return days_delayed[days_delayed > timedelta(days=days_to_nc)].keys()


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


def get_record_ids_end_fu(redcap_data, days_before):
    """Get the project record ids of the participants who are turning 18 months in days_before days from today. Thus,
    for every project record, check if, according to her date of birth, she will be more than 18 months in days_before
    days and the participant wasn't already visited at home for the end of follow up visit.

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
    about_18m = dobs[datetime.today().year - dobs.dt.year >= 1]  # Filter those older than 1 year old
    about_18m = about_18m[datetime.today().month - about_18m.dt.month >= 5]  # Filter those older than 17 months old
    about_18m = about_18m[about_18m.dt.day - datetime.today().day <= days_before]  # Filter those that will turn 18m

    # Remove those participants who have already been visited and seen at home for the end of the trial follow up
    finalized = x.query(
        "redcap_event_name == 'hhat_18th_month_of_arm_1' and "
        "redcap_repeat_instrument == 'household_follow_up' and "
        "hh_child_seen == 1"
    )

    about_18m_not_seen = about_18m.index
    if finalized is not None:
        record_ids_seen = finalized.index.get_level_values('record_id')
        about_18m_not_seen = about_18m_not_seen.difference(record_ids_seen)

    return about_18m_not_seen


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


def build_nv_alerts_df(redcap_data, record_ids, alert_string, alert_date_format):
    """Build dataframe with record ids and next return date to health facility of every study participant who is
    supposed to come in the next 7 days or is still expected in the health facility (still compliant).

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


def build_end_fu_alerts_df(redcap_data, record_ids, alert_string, alert_date_format):
    """Build dataframe with record ids and dates when they turn 18 months of every study participant who is
    turning 18 months in the next days or she has already 18 months but she hasn't been visited for the end of the trial
    follow up.

    :param redcap_data:Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param record_ids: Array of record ids representing those study participants that require the end of follow up
                       household visit
    :type record_ids: pandas.Int64Index
    :param alert_string: String with the alert to be setup containing one placeholders (18 months birthday)
    :type alert_string: str
    :param alert_date_format: Format of the date of the 18 months birthday to be displayed in the alert
    :type alert_date_format: str

    :return: A dataframe with the columns 18 months birthday and child_fu_status in which each row is identified by the
    REDCap record id and represents a study participant who is supposed to be visited for the end of the follow up.
    :rtype: pandas.DataFrame
    """
    # Append to record ids, the 18 moths birthday of the participant
    birthday_18m = redcap_data.loc[record_ids, ['child_dob']]
    birthday_18m = birthday_18m.groupby('record_id')['child_dob'].max()  # To move from a DataFrame to a Series
    birthday_18m = birthday_18m.apply(lambda dob: dob + relativedelta(months=+18))  # Add 18 months to dates of birth
    birthday_18m = birthday_18m.apply(lambda x: x.strftime(alert_date_format))

    # Transform data to be imported into the child_status_fu variable into the REDCap project
    data = {'birthday_18m': birthday_18m}
    data_to_import = pandas.DataFrame(data)
    if not data_to_import.empty:
        data_to_import['child_fu_status'] = data_to_import[['birthday_18m']].apply(
            lambda x: alert_string.format(birthday_18m=x[0]), axis=1)

    return data_to_import


def get_active_alerts(redcap_data, alert):
    """Get the project records ids of the participants with an activated alert.

    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param alert: String representing the type of alerts to be retrieved
    :type alert: str

    :return: Array containing the record ids of the study participants who have an activated alert.
    :rtype: pandas.Int64Index
    """
    active_alerts = redcap_data.loc[(slice(None), 'epipenta1_v0_recru_arm_1'), 'child_fu_status']
    active_alerts = active_alerts[active_alerts.notnull()]
    if active_alerts.empty:
        return None

    active_alerts = active_alerts[active_alerts.str.startswith(alert)]
    active_alerts.index = active_alerts.index.get_level_values('record_id')

    return active_alerts.keys()


def get_record_ids_with_custom_status(redcap_data, defined_alerts):
    """Get the project records ids of the participants with an custom status set up in the child_fu_status field.

    :param redcap_data: Exported REDCap project data
    :type redcap_data: pandas.DataFrame
    :param defined_alerts: List of strings representing the type of the defined alerts
    :type defined_alerts: list

    :return: Array containing the record ids of those participants with a custom follow up status
    :rtype: pandas.Int64Index
    """
    active_alerts = redcap_data.loc[(slice(None), 'epipenta1_v0_recru_arm_1'), 'child_fu_status']
    active_alerts = active_alerts[active_alerts.notnull()]
    if active_alerts.empty:
        return None

    custom_status = active_alerts
    for alert in defined_alerts:
        custom_status = custom_status[~active_alerts.str.startswith(alert)]

    custom_status.index = custom_status.index.get_level_values('record_id')

    return custom_status.keys()


# TO BE VISITED
def set_tbv_alerts(redcap_project, redcap_project_df, tbv_alert, tbv_alert_string, redcap_date_format,
                   alert_date_format, choice_sep, code_sep, blocked_records):
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

    :return: None
    """

    # Get the project records ids of the participants requiring a household visit
    records_to_be_visited = get_record_ids_tbv(redcap_project_df)

    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_be_visited = records_to_be_visited.difference(blocked_records)

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, tbv_alert)

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


# NON-COMPLIANT
def set_nc_alerts(redcap_project, redcap_project_df, nc_alert, nc_alert_string, choice_sep, code_sep, days_to_nc,
                  blocked_records):
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

    :return: None
    """

    # Get the project records ids of the participants requiring a visit because they are non-compliant
    records_to_be_visited = get_record_ids_nc(redcap_project_df, days_to_nc)

    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_be_visited = records_to_be_visited.difference(blocked_records)

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, nc_alert)

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


# NEXT VISIT
def set_nv_alerts(redcap_project, redcap_project_df, nv_alert, nv_alert_string, alert_date_format, days_before,
                  days_after, blocked_records):
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

    :return: None
    """

    # Get the project records ids of the participants who are expected to come tho the HF in the interval days_before
    # and days_after from today
    records_to_flag = get_record_ids_nv(redcap_project_df, days_before, days_after)

    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_flag = records_to_flag.difference(blocked_records)

    # Get the project records ids of the participants requiring a household visit after AZi administration. The TO BE
    # VISITED alert is higher priority than the NEXT VISIT alerts
    records_to_be_visited = get_record_ids_tbv(redcap_project_df)

    # Don't flag with NEXT VISIT those records already marked as TO BE VISITED
    records_to_flag = records_to_flag.difference(records_to_be_visited)

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, nv_alert)

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


def remove_nv_alerts(redcap_project, redcap_project_df, nv_alert):
    """Remove the Next Visit alerts of those participants who have this alert already setup.

    :param redcap_project: A REDCap project class to communicate with the REDCap API
    :type redcap_project: redcap.Project
    :param redcap_project_df: Data frame containing all data exported from the REDCap project
    :type redcap_project_df: pandas.DataFrame
    :param nv_alert: Code of the Next Visit alerts
    :type nv_alert: str

    :return: None
    """

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, nv_alert)

    # Remove all NEXT VISIT alerts
    if records_with_alerts is not None:
        # Import data into the REDCap project: Alerts removal
        to_import_dict = [{'record_id': rec_id, 'child_fu_status': ''} for rec_id in records_with_alerts]
        response = redcap_project.import_records(to_import_dict, overwrite='overwrite')
        print("[NEXT VISIT] Alerts removal (FORCED): {}".format(response.get('count')))
    else:
        print("[NEXT VISIT] Alerts removal (FORCED): None")


# END FOLLOW UP
def set_end_fu_alerts(redcap_project, redcap_project_df, end_fu_alert, end_fu_alert_string, alert_date_format,
                      days_before, blocked_records):
    """Remove the End of F/U alerts of those participants that haven been already visited at home for the end of the
    the trial follow up. Setup alerts for those participants who are going to turn 18 months in days_before days.

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

    :return: None
    """

    # Get the project records ids of the participants who are turning 18 months in days_before days from today
    records_to_flag = get_record_ids_end_fu(redcap_project_df, days_before)

    # Remove those ids that must be ignored
    if blocked_records is not None:
        records_to_flag = records_to_flag.difference(blocked_records)

    # Get the project records ids of the participants with an active alert
    records_with_alerts = get_active_alerts(redcap_project_df, end_fu_alert)

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
    to_import_df = build_end_fu_alerts_df(redcap_project_df, records_to_flag, end_fu_alert_string, alert_date_format)

    # Import data into the REDCap project: Alerts setup
    to_import_dict = [{'record_id': rec_id, 'child_fu_status': participant.child_fu_status}
                      for rec_id, participant in to_import_df.iterrows()]
    response = redcap_project.import_records(to_import_dict)
    print("[END F/U] Alerts setup: {}".format(response.get('count')))