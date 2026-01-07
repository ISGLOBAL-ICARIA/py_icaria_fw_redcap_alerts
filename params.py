import tokens
from datetime import datetime

currentMonth = datetime.now().month

# REDCap parameters
URL = tokens.URL
TRIAL_PROJECTS = tokens.REDCAP_PROJECTS_ICARIA
COHORT_PROJECTS = tokens.REDCAP_PROJECTS_COHORT
CHOICE_SEP = " | "
CODE_SEP = ", "
REDCAP_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
TRIAL_CHILD_FU_STATUS_EVENT = "epipenta1_v0_recru_arm_1"
COHORT_CHILD_FU_STATUS_EVENT = "ipti_1__10_weeks_r_arm_1"
TRIAL_EPI_EVENT_NAMES = {
    'epipenta1_v0_recru_arm_1': 'PENTA1',
    'epipenta2_v1_iptis_arm_1': 'PENTA2',
    'epipenta3_v2_iptis_arm_1': 'PENTA3',
    'epivita_v3_iptisp3_arm_1': 'VITA-6M',
    'epimvr1_v4_iptisp4_arm_1': 'MRV1',
    'epivita_v5_iptisp5_arm_1': 'VITA-12M',
    'epimvr2_v6_iptisp6_arm_1': 'MRV2'
}

TRIAL_ALL_EVENT_NAMES = {
    'epipenta1_v0_recru_arm_1': 'PENTA1',
    'epipenta2_v1_iptis_arm_1': 'PENTA2',
    'epipenta3_v2_iptis_arm_1': 'PENTA3',
    'epivita_v3_iptisp3_arm_1': 'VITA-6M',
    'epirtss_m7_visit_arm_1': 'RTSS-7M',
    'epirtss_m8_visit_arm_1': 'RTSS-8M',
    'epimvr1_v4_iptisp4_arm_1': 'MRV1',
    'epivita_v5_iptisp5_arm_1': 'VITA-12M',
    'epimvr2_v6_iptisp6_arm_1': 'MRV2',
    'hhafter_1st_dose_o_arm_1': 'HHA1D',
    'cohort_after_mrv_2_arm_1': 'COHAMRV2',
    'after_1_month_from_arm_1': 'AFTERPENTA1',
    'after_1_month_from_arm_1b': 'AFTERVITA6M',
    'after_1_month_from_arm_1c': 'AFTERMRV1',
    'after_1_month_from_arm_1d': 'AFTERVITA12M',
    'after_1_month_from_arm_1e': 'AFTERMRV2',
    'adverse_events_arm_1': 'AE',
    'out_of_schedule_arm_1': 'OUTSCH'
}

# Alerts general parameters
ALERT_DATE_FORMAT = "%b %d"

# TO BE VISITED ALERT
TBV_ALERT = "TBV"
TBV_ALERT_STRING = TBV_ALERT + "@{community} AZi/Pbo@{last_azi_date}"

# NON-COMPLIANT ALERT
""" DEACTIVATED """
DAYS_TO_NC = 28  # Defined by PI as 4 weeks (after expected return date)
NC_ALERT = "NC"
NC_ALERT_STRING = NC_ALERT + "@{community} ({weeks} weeks)"

# NEXT VISIT ALERT
DAYS_BEFORE_NV = 7  # Defined by In-Country Technical Coordinator
DAYS_AFTER_NV = DAYS_TO_NC  # Defined by In-Country Technical Coordinator
NV_ALERT = "NEXT VISIT"
NV_ALERT_STRING = NV_ALERT + ": {return_date}"

# AZIVAC ALERT
AZIVAC_ALERT = "(AV)"
AZIVAC_ALERT_SERIOUS = "(AVS)"

# NEXT VISIT ALERT
DAYS_BEFORE_NV = 7  # Defined by In-Country Technical Coordinator
DAYS_AFTER_NV = DAYS_TO_NC  # Defined by In-Country Technical Coordinator
NV_ALERT = "NEXT VISIT"
NV_ALERT_STRING = NV_ALERT + ": {return_date}"


# END OF FOLLOW UP
DAYS_BEFORE_END_FU = 0  # Defined by In-Country Technical Coordinator
END_FU_ALERT = "END F/U"
END_FU_ALERT_STRING = END_FU_ALERT + " Pending: {birthday}"

END_FU_TRIAL = 18   # By protocol
COMPLETION_STRING = "COMPLETED. 18 months of age"
UNREACHABLE_STRING = "UNREACHABLE. 18 months of age"
UNREACHABLE_STR = "UNREACHABLE"

# NEW MORTALITY SURVEILLANCE
#NEW_DAYS_AFTER_EPI = 92  # Defined by PI as 3 month (after any EPI visit since Penta3 - included)
NEW_DAYS_AFTER_EPI = 46  # Defined by PI to reduce the MS threshold to 1.5 month on 28/04/2024
NEW_MS_ALERT = "SURVEILLANCE AFTER"
NEW_MS_ALERT_STRING = NEW_MS_ALERT + " {last_epi_visit}"
NEW_MS_EXCLUDED_EPI_VISITS = []  # Defined by In-country Tech. Coord.

# MRV2 ALERT. 15 MONTH OF AGE
MRV2_ALERT = "MRV2 Pending"
MRV2_ALERT_STRING = MRV2_ALERT
MRV2_MONTHS = 15
DAYS_BEFORE_MRV2 = 0 # Defined by In-Country Technical Coordinator


# COHORT ALERT.
""" DEACTIVATED """
FINALIZED_COHORT_STRING = "COH."
OTHER_COHORT_ALERT = "COHORT Pending"
NON_CONT_COHORT_ALERT = "(COHORT pending)"
NON_CONT_COHORT_ALERT_STRING = NON_CONT_COHORT_ALERT


# BIRTHS WEIGHTS ALERT. If not collected
""" DEACTIVATED """
BW_ALERT = "(BW)"
BW_ALERT_STRING = BW_ALERT


# ENABLED ALERTS: Subset of [TBV_ALERT, NV_ALERT, MS_ALERT, NC_ALERT, END_FU_ALERT]

#NC_ALERT dismissed 20221027 abofill
TRIAL_DEFINED_ALERTS = [TBV_ALERT, END_FU_ALERT,NEW_MS_ALERT, MRV2_ALERT,COMPLETION_STRING,UNREACHABLE_STRING,AZIVAC_ALERT,AZIVAC_ALERT_SERIOUS,'(AV)(AVS)']

# NON-ICARIA COHORT PROJECT ALERT #
COHORT_MRV2_ALERT = "MRV2"
COHORT_MRV2_ALERT_STRING = "MRV2 Pending: {birthday}"

COHORT_DEFINED_ALERTS = [COHORT_MRV2_ALERT]

# DATA DICTIONARY FIELDS USED BY THE DIFFERENT ALERTS - IMPROVE PERFORMANCE OF API CALLS
ALERT_LOGIC_FIELDS = ['record_id', 'child_dob', 'screening_date', 'community', 'int_azi','int_next_visit', 'int_date',
                      'int_sp', 'intervention_complete', 'hh_child_seen','hh_why_not_child_seen','hh_date','study_number',
                      'call_caretaker','reachable_status','household_follow_up_complete', 'a1m_date', 'comp_date',
                      'phone_success','child_birth_weight_known','phone_success','fu_type','int_random_letter',
                      'death_reported_date', 'ae_date','sae_awareness_date','ms_date_contact','unsch_date','mig_date','comp_date',
                      'ch_his_date','phone_child_status','child_fu_status','azivac_study_number','azivac_date',
                      'rtss_vacc_rtss1_date','rtss_vacc_rtss2_date','rtss_vacc_rtss3_date','rtss_vacc_rtss4_date',
                      'sae_hosp_admin_date','rtss_date']

subprojects = {'HF01':['HF01.01','HF01.02'],'HF02':['HF02.01','HF02.02'],'HF08':['HF08.01','HF08.02','HF08.03'],
               'HF12':['HF12.01','HF12.02'],'HF16':['HF16.01','HF16.02','HF16.03','HF16.04']}

azivac_blocked_records = tokens.azivac_blocked_records_dict.keys()
