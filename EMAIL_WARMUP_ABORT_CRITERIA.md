# Email Warmup Abort Criteria and Remediation Plan

This document outlines the specific criteria under which the email warmup process must be paused and the corresponding steps to resolve the underlying issues.

## 1. Abort Criteria

Immediately pause all email sending activities if any of the following thresholds are met or conditions occur:

- **High Bounce Rate:** The bounce rate exceeds **5%** over a 24-hour period.
- **High Complaint Rate:** The complaint rate exceeds **0.1%** over a 24-hour period.
- **AWS SES Account Status Change:** The AWS Simple Email Service (SES) account enters a **"PAUSED"** or **"PROBATION"** state.

## 2. Remediation Steps

### 2.1. High Bounce or Complaint Rate

1.  **Halt Campaigns:** Immediately pause all active email campaigns within Mautic.
2.  **Investigate Root Cause:**
    *   **Bounces:** Analyze the bounce reports in SES/Mautic to identify the types of bounces (hard vs. soft) and the list segments responsible. This often points to a stale or low-quality email list.
    *   **Complaints:** Review the content of the emails that generated complaints. The messaging may be perceived as irrelevant or spammy.
3.  **Clean Email Lists:** Use an email verification service (e.g., ZeroBounce, Hunter) to scrub the problematic list segments and remove invalid addresses.
4.  **Revise Content:** Adjust email subject lines, body content, and calls-to-action to be more engaging and relevant to the target audience.
5.  **Gradual Resumption:** Once the issue is addressed, resume sending with a small, highly engaged segment of the list. Monitor metrics closely before scaling back to the full campaign.

### 2.2. AWS SES Account Status Change (Paused/Probation)

1.  **Halt All Sending:** Immediately confirm that all email sending from the platform is stopped.
2.  **Review AWS Notification:** Log in to the AWS Management Console and navigate to the SES section. Carefully read the notification from AWS, as it will contain the specific reason for the status change.
3.  **Follow AWS Guidance:** Execute the remediation steps provided by AWS. This may involve:
    *   Appealing the decision with a detailed plan of correction.
    *   Resolving the underlying issue that triggered the status change (e.g., high bounce/complaint rates).
    *   Providing additional information to AWS Support.
4.  **Await Resolution:** Do **not** resume any email sending activities until AWS has officially lifted the restriction and returned the account to a healthy status.
