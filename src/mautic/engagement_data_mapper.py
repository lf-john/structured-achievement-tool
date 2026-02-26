import logging
from datetime import datetime

class EngagementDataMapper:
    def __init__(self):
        pass

    def map_to_suitecrm_format(self, mautic_data: dict) -> dict:
        """
        Maps Mautic engagement data to SuiteCRM's expected format.
        """
        suitecrm_payload = {}
        event_type = mautic_data.get('event_type')
        details = mautic_data.get('details', {})

        if event_type == 'email.open':
            suitecrm_payload['last_email_open'] = datetime.now().strftime('%Y-%m-%d')
            # Assuming email is present in details for identification
            if 'email' in details: # To match test case, though SuiteCRM might use contact_id for lookup
                suitecrm_payload['email'] = details['email']
        elif event_type == 'email.click':
            suitecrm_payload['last_email_click'] = datetime.now().strftime('%Y-%m-%d')
            if 'url' in details:
                suitecrm_payload['last_clicked_url'] = details['url']
            # Assuming email is present in details for identification
            if 'email' in details:
                suitecrm_payload['email'] = details['email']
        elif event_type == 'form.submit':
            if 'form_name' in details:
                suitecrm_payload['form_submitted'] = details['form_name']
            if 'fields' in details:
                for field_name, field_value in details['fields'].items():
                    suitecrm_payload[field_name] = field_value
        elif event_type == 'lead.score_change':
            if 'new_score' in details:
                suitecrm_payload['lead_score'] = details['new_score']
        elif event_type == 'campaign.membership_change':
            if 'campaign_name' in details:
                suitecrm_payload['campaign_membership'] = details['campaign_name']
            if 'stage' in details:
                suitecrm_payload['campaign_stage'] = details['stage']
        else:
            logging.warning(f"Unknown Mautic event type: {event_type}, skipping mapping.")

        return suitecrm_payload
