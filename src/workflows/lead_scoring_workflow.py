# src/workflows/lead_scoring_workflow.py
import json
from typing import Dict, Any
from src.utils.ollama_client import OllamaClient
from src.utils.mautic_client import MauticClient

class LeadScoringWorkflow:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.ollama_client = OllamaClient(
            api_url=config["ollama_api_url"],
            model=config["ollama_model"]
        )
        self.mautic_client = MauticClient(
            api_url=config["mautic_api_url"],
            token=config["mautic_api_token"]
        )

    def run(self, contact_id: int, contact_data: Dict[str, Any]) -> bool:
        """
        Runs the lead scoring workflow for a single contact.
        """
        print(f"Scoring contact ID: {contact_id}")
        
        # 1. Get score from Ollama
        scoring_result = self.ollama_client.score_lead(contact_data)
        
        if "error" in scoring_result or "score" not in scoring_result:
            print(f"Failed to get score for contact {contact_id}. Reason: {scoring_result.get('error', 'Unknown')}")
            return False

        score = scoring_result["score"]
        print(f"Contact {contact_id} scored: {score} with {scoring_result['confidence']} confidence.")

        # 2. Update Mautic contact
        # For this example, we assume the contact_id is known and passed in.
        # In a real scenario, you might need to fetch the contact from Mautic first.
        success = self.mautic_client.update_contact_score(contact_id, score)

        return success

def main():
    """
    Example usage of the workflow.
    In a real application, this would be triggered by a Mautic webhook, a message queue, or a cron job.
    """
    # Dummy contact data for demonstration
    contact_id = 123
    contact_data = {
        "name": "Jane Doe",
        "title": "VP of Marketing",
        "company": "TechCorp",
        "industry": "SaaS",
        "company_size": 250,
        "location": "San Francisco, USA"
    }

    workflow = LeadScoringWorkflow()
    success = workflow.run(contact_id, contact_data)

    if success:
        print("Lead scoring workflow completed successfully.")
    else:
        print("Lead scoring workflow failed.")

if __name__ == "__main__":
    main()
