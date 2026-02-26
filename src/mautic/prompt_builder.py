class PromptBuilder:
    def build_lead_scoring_prompt(self, contact_record: dict) -> str:
        name = contact_record.get("name", "N/A")
        title = contact_record.get("title", "N/A")
        company = contact_record.get("company", "N/A")
        industry = contact_record.get("industry", "N/A")
        size = contact_record.get("size", "N/A")

        prompt = f"""
        Given the following contact information, provide a lead score from 1-100 and a confidence level from 0.0-1.0.
        Consider the following criteria for scoring:
        - Title/seniority match to Ideal Customer Profile (ICP)
        - Company size within target range (e.g., 500-5000 employees)
        - Industry alignment (e.g., Software, Technology)
        - Geographic relevance (assume high relevance if not specified)

        Contact Details:
        Name: {name}
        Title: {title}
        Company: {company}
        Industry: {industry}
        Size: {size}

        Format your response as: Score: <score>, Confidence: <confidence>
        """
        return prompt

