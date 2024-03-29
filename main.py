#!/usr/bin/env python
""" Python script to setup alerts for ICARIA field workers. These alerts are for them to know if they have to do a
household visit after AZi/Pbo administration or a Non-Compliant visit. In the context of the ICARIA Clinical Trial, a
household visit is scheduled few days after the administration of the investigational product (azithromycin in this
case). Moreover, if study participants are not coming to the scheduled study visits, another household visit will be
scheduled to capture their status. This script is computing regularly which of the participants requires a household or
Non-Com<pliant visit. This requirement is saved into an eCRF variable in the Screening DCI. This variable will be setup
as part of the REDCap custom record label. Like this, field workers will see in a glance which participants they need to
visit at their households."""

from datetime import datetime
import pandas as pd
import redcap
import params
import alerts

__author__ = "Maximo Ramirez Robles"
__copyright__ = "Copyright 2023, ISGlobal Maternal, Child and Reproductive Health"
__credits__ = ["Maximo Ramirez Robles"]
__license__ = "MIT"
__version__ = "0.0.1"
__date__ = "20210323"
__maintainer__ = "Andreu Bofill"
__email__ = "andreu.bofill@isglobal.org"
__status__ = "Dev"

if __name__ == '__main__':
    # Alerts system @ ICARIA TRIAL REDCap projects
    """
    ## THIS WORKS TO ELIMINATE THE SCREENING FAILURE PARTICIPANTS
    for project_key in params.TRIAL_PROJECTS:
        ######
        project = redcap.Project(params.URL, params.TRIAL_PROJECTS[project_key])
        # Get all records for each ICARIA REDCap project (TRIAL)
        print("\n[{}] Getting records from the ICARIA TRIAL REDCap projects:".format(datetime.now()))
        print("[{}] Getting all records from {}...".format(datetime.now(), project_key))
        df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)
        dfres = df.reset_index()
        dfres = dfres[(dfres['redcap_event_name']=='epipenta1_v0_recru_arm_1')&(dfres['study_number'].isna())]
        dfres = dfres.set_index('record_id')[['child_fu_status']].drop_duplicates()
        to_import_dict = [{'record_id': rec_id, 'child_fu_status':'Screening Failure'}
                          for rec_id in dfres.index]
        response = project.import_records(to_import_dict)
   """
    for project_key in params.TRIAL_PROJECTS:
        ######
        project = redcap.Project(params.URL, params.TRIAL_PROJECTS[project_key])

        # Get all records for each ICARIA REDCap project (TRIAL)
        print("\n[{}] Getting records from the ICARIA TRIAL REDCap projects:".format(datetime.now()))
        print("[{}] Getting all records from {}...".format(datetime.now(), project_key))
        df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)

        # Custom status

        custom_status_ids = alerts.get_record_ids_with_custom_status(
            redcap_data=df,
            defined_alerts=params.TRIAL_DEFINED_ALERTS,
            fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT
        )
        # ALERT SYSTEM: The order of the alerts here matters. The first alert to be flagged has the lowest priority.
        # I.e. they will be overwritten by the following alerts if the flagging condition is met for more than one
        # alert.

        # Households to be visited
        if params.TBV_ALERT in params.TRIAL_DEFINED_ALERTS:
            alerts.set_tbv_alerts(
                redcap_project=project,
                redcap_project_df=df,
                tbv_alert=params.TBV_ALERT,
                tbv_alert_string=params.TBV_ALERT_STRING,
                redcap_date_format=params.REDCAP_DATE_FORMAT,
                alert_date_format=params.ALERT_DATE_FORMAT,
                choice_sep=params.CHOICE_SEP,
                code_sep=params.CODE_SEP,
                blocked_records=custom_status_ids,
                fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT
            )

        # Next visit
        if params.NV_ALERT in params.TRIAL_DEFINED_ALERTS:
            # Update REDCap data as it has may been modified by previous alerts
            df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)
            alerts.set_nv_alerts(
                redcap_project=project,
                redcap_project_df=df,
                nv_alert=params.NV_ALERT,
                nv_alert_string=params.NV_ALERT_STRING,
                alert_date_format=params.ALERT_DATE_FORMAT,
                days_before=params.DAYS_BEFORE_NV,
                days_after=params.DAYS_AFTER_NV,
                blocked_records=custom_status_ids,
                fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT
            )
        """
        # Mortality surveillance visits
        if params.MS_ALERT in params.TRIAL_DEFINED_ALERTS:
            # Update REDCap data as it has may been modified by previous alerts
            fields = project.export_field_names()
            field_names = [field['export_field_name'] for field in fields]
            df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)

            # mramirez - 20220217: The group of participants whose last EPI visit was more than one month ago (MS) also
            # includes the non-compliant participants recently contacted but that they have not come to the HF after
            # this contact. Therefore, those participants will be also flagged to be contacted through this new
            # procedure, even though they could have been contacted recently. In order to avoid re-contacting as less
            # participants as possible, only recruited participants since 2021-11-29 will be considered, i.e. recruited
            # participants 2.5 months ago.

            #recruited_since = df.query("screening_date >'2021-11-29 00:00:00'")
            #record_ids = recruited_since.index.get_level_values(0)
            #df = df.query("record_id in @record_ids")

            alerts.set_ms_alerts(
                redcap_project=project,
                redcap_project_df=df,
                ms_alert=params.MS_ALERT,
                ms_alert_string=params.MS_ALERT_STRING,
                choice_sep=params.CHOICE_SEP,
                code_sep=params.CODE_SEP,
                days_after_epi=params.DAYS_AFTER_EPI,
                event_names=params.TRIAL_EPI_EVENT_NAMES,
                excluded_epi_visits=params.MS_EXCLUDED_EPI_VISITS,
                blocked_records=custom_status_ids,
                fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT
            )

        # Non-compliant visits
        if params.NC_ALERT in params.TRIAL_DEFINED_ALERTS:
            # Update REDCap data as it has may been modified by previous alerts
            fields = project.export_field_names()
            field_names = [field['export_field_name'] for field in fields]
            df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)

            alerts.set_nc_alerts(
                redcap_project=project,
                redcap_project_df=df,
                nc_alert=params.NC_ALERT,
                nc_alert_string=params.NC_ALERT_STRING,
                choice_sep=params.CHOICE_SEP,
                code_sep=params.CODE_SEP,
                days_to_nc=params.DAYS_TO_NC,
                blocked_records=custom_status_ids,
                fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT
            )
        """
            # NEW Mortality surveillance visits
        if params.MS_ALERT in params.TRIAL_DEFINED_ALERTS:
            # Update REDCap data as it has may been modified by previous alerts
            fields = project.export_field_names()
            field_names = [field['export_field_name'] for field in fields]
            df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)

            alerts.set_new_ms_alerts(
                redcap_project=project,
                redcap_project_df=df,
                ms_alert=params.NEW_MS_ALERT,
                ms_alert_string=params.NEW_MS_ALERT_STRING,
                choice_sep=params.CHOICE_SEP,
                code_sep=params.CODE_SEP,
                days_after_epi=params.NEW_DAYS_AFTER_EPI,
                event_names=params.TRIAL_ALL_EVENT_NAMES,
                excluded_epi_visits=params.NEW_MS_EXCLUDED_EPI_VISITS,
                blocked_records=custom_status_ids,
                fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT
            )


        # MRV2 VISIT ALERT. 15 MONTH OF AGE
        if params.MRV2_ALERT in params.TRIAL_DEFINED_ALERTS:
            # Update REDCap data as it has may been modified by previous alerts
            df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)

            alerts.set_mrv2_alerts(
                redcap_project=project,
                redcap_project_df=df,
                mrv2_alert=params.MRV2_ALERT,
                mrv2_alert_string=params.MRV2_ALERT_STRING,
                alert_date_format=params.ALERT_DATE_FORMAT,
                days_before=params.DAYS_BEFORE_MRV2,
                blocked_records=custom_status_ids,
                fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT,
                months=params.MRV2_MONTHS
            )
        # Birth's weights not collected Alert
        if params.BW_ALERT in params.TRIAL_DEFINED_ALERTS:
            # Update REDCap data as it has may been modified by previous alerts
            df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)
            alerts.set_bw_alerts(
                redcap_project=project,
                redcap_project_df=df,
                bw_alert=params.BW_ALERT,
                blocked_records=custom_status_ids,
                fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT
            )

        # End of Follow Up
        if params.END_FU_ALERT in params.TRIAL_DEFINED_ALERTS:
            # Update REDCap data as it has may been modified by previous alerts
            df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)


            alerts.set_end_fu_alerts(
                redcap_project=project,
                redcap_project_df=df,
                end_fu_alert=params.END_FU_ALERT,
                end_fu_alert_string=params.END_FU_ALERT_STRING,
                completed_alert_string= params.COMPLETION_STRING,
                unreachable_alert_string=params.UNREACHABLE_STRING,
                alert_date_format=params.ALERT_DATE_FORMAT,
                days_before=params.DAYS_BEFORE_END_FU,
                blocked_records=custom_status_ids,
                study="TRIAL",  # 18 months and end of follow up household visit
                fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT,
                months=params.END_FU_TRIAL
            )
        """
        # ICARIA NON-CONTEMPORARY COHORT
        if params.NON_CONT_COHORT_ALERT in params.TRIAL_DEFINED_ALERTS:
            # Update REDCap data as it has may been modified by previous alerts
            df = project.export_records(format='df', fields=params.ALERT_LOGIC_FIELDS)

            alerts.set_nc_cohort_alerts(
                project_key=project_key,
                redcap_project=project,
                redcap_project_df=df,
                cohort_alert=params.NON_CONT_COHORT_ALERT,
                cohort_alert_string=params.NON_CONT_COHORT_ALERT,
                blocked_records=custom_status_ids,
                fu_status_event=params.TRIAL_CHILD_FU_STATUS_EVENT
            )
        """
    # Alerts system @ ICARIA COHORT REDCap projects
    for project_key in params.COHORT_PROJECTS:
        project = redcap.Project(params.URL, params.COHORT_PROJECTS[project_key])
        # Get all records for each ICARIA REDCap project (COHORT)
        print("\n[{}] Getting records from the ICARIA COHORT REDCap projects:".format(datetime.now()))
        print("[{}] Getting all records from {}...".format(datetime.now(), project_key))
        fields = project.export_field_names()
        field_names = [field['export_field_name'] for field in fields]
        df = project.export_records(format='df', fields=field_names)
        # Custom status
        custom_status_ids = alerts.get_record_ids_with_custom_status(
            redcap_data=df,
            defined_alerts=params.COHORT_DEFINED_ALERTS,
            fu_status_event=params.COHORT_CHILD_FU_STATUS_EVENT
        )

        # End of Follow Up
        if params.COHORT_MRV2_ALERT in params.COHORT_DEFINED_ALERTS:
            alerts.set_end_fu_alerts(
                redcap_project=project,
                redcap_project_df=df,
                end_fu_alert=params.COHORT_MRV2_ALERT,
                end_fu_alert_string=params.COHORT_MRV2_ALERT_STRING,
                alert_date_format=params.ALERT_DATE_FORMAT,
                days_before=params.DAYS_BEFORE_END_FU,
                blocked_records=custom_status_ids,
                study="COHORT",  # 15 months and end of follow up tests
                fu_status_event=params.COHORT_CHILD_FU_STATUS_EVENT,
                months=params.END_FU_COHORT
            )
