import logging
import random


class MauticLeadVerificationService:
    def __init__(self, mautic_api_client):
        self.mautic_api_client = mautic_api_client
        self.logger = logging.getLogger(self.__class__.__name__)

    def verify_total_contact_count(self, expected_count, excluded_records=0):
        try:
            contacts_response = self.mautic_api_client.get_contacts(limit=1)
            total_mautic_contacts = contacts_response.get("totalCount", 0)
            adjusted_expected_count = expected_count + excluded_records

            if total_mautic_contacts == adjusted_expected_count:
                self.logger.info(f"Total contact count verified: {total_mautic_contacts} matches expected {adjusted_expected_count}.")
                return True
            else:
                self.logger.error(f"Total contact count mismatch. Expected: {adjusted_expected_count}, Found: {total_mautic_contacts}.")
                return False
        except Exception as e:
            self.logger.error(f"Error verifying total contact count: {e}")
            return False

    def verify_segment_counts(self, expected_segments):
        try:
            segments_response = self.mautic_api_client.get_segments(limit=50)
            mautic_segments = {segment["name"]: segment["contacts"] for segment in segments_response.get("segments", {}).values()}

            all_match = True
            for segment_name, expected_count in expected_segments.items():
                if segment_name not in mautic_segments:
                    self.logger.error(f"Segment '{segment_name}' not found in Mautic.")
                    all_match = False
                    continue

                actual_count = mautic_segments[segment_name]
                if actual_count != expected_count:
                    self.logger.error(f"Segment '{segment_name}' count mismatch. Expected: {expected_count}, Found: {actual_count}.")
                    all_match = False
                elif expected_count == 0 and actual_count == 0:
                    self.logger.info(f"Segment '{segment_name}' count verified as zero as expected.")
                elif expected_count > 0 and actual_count == 0:
                    self.logger.error(f"Segment '{segment_name}' count is zero, but a non-zero count was expected.")
                    all_match = False
                else:
                    self.logger.info(f"Segment '{segment_name}' count verified: {actual_count} matches expected {expected_count}.")
            return all_match
        except Exception as e:
            self.logger.error(f"Error verifying segment counts: {e}")
            return False

    def sample_contacts_for_field_mapping(self, sample_size=10, fields_to_verify=None):
        if fields_to_verify is None:
            fields_to_verify = []

        try:
            contacts_response = self.mautic_api_client.get_contacts(limit=sample_size, start=0) # Fetch sample_size contacts
            all_contacts = list(contacts_response.get("contacts", {}).values())

            if len(all_contacts) < sample_size:
                self.logger.warning(f"Not enough contacts ({len(all_contacts)}) available to sample {sample_size}.")
                return False

            sample_contacts = random.sample(all_contacts, sample_size)

            all_fields_present_and_match = True
            for contact in sample_contacts:
                for field in fields_to_verify:
                    if isinstance(fields_to_verify, dict): # For tests that specify exact values
                        expected_value = fields_to_verify[field]
                        actual_value = contact.get(field)
                        if actual_value != expected_value:
                            self.logger.error(f"Contact ID {contact.get('id')}: Field '{field}' value mismatch. Expected: {expected_value}, Found: {actual_value}.")
                            all_fields_present_and_match = False
                    else: # For tests that just check for presence
                        if field not in contact or contact.get(field) is None:
                            self.logger.error(f"Contact ID {contact.get('id')}: Missing or null expected field '{field}'.")
                            all_fields_present_and_match = False
            return all_fields_present_and_match
        except Exception as e:
            self.logger.error(f"Error sampling contacts for field mapping: {e}")
            return False

    def confirm_demographic_lead_scores(self, sample_contact_ids, expected_scores):
        try:
            all_scores_match = True
            for contact_id in sample_contact_ids:
                contact_response = self.mautic_api_client.get_contact_by_id(contact_id)
                contact = contact_response.get("contact", {})

                actual_lead_score = contact.get("fields", {}).get("core", {}).get("lead_score", {}).get("value")
                expected_lead_score = expected_scores.get(contact_id, {}).get("lead_score")

                if actual_lead_score != expected_lead_score:
                    self.logger.error(f"Contact ID {contact_id}: Lead score mismatch. Expected: {expected_lead_score}, Found: {actual_lead_score}.")
                    all_scores_match = False
                else:
                    self.logger.info(f"Contact ID {contact_id}: Lead score verified: {actual_lead_score} matches expected {expected_lead_score}.")
            return all_scores_match
        except Exception as e:
            self.logger.error(f"Error confirming demographic lead scores: {e}")
            return False

    def confirm_no_duplicate_contacts(self):
        try:
            contacts_response = self.mautic_api_client.get_contacts(limit=None) # Get all contacts
            all_contacts = list(contacts_response.get("contacts", {}).values())

            emails = [contact.get("email") for contact in all_contacts if isinstance(contact, dict) and contact.get("email")]
            if len(emails) != len(set(emails)):
                self.logger.error("Duplicate contacts found based on email address.")
                return False
            self.logger.info("No duplicate contacts found.")
            return True
        except Exception as e:
            self.logger.error(f"Error confirming no duplicate contacts: {e}")
            return False
