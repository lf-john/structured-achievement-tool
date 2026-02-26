# Daily Email Warmup Monitoring Checklist for logicalfront.net

This checklist outlines the daily tasks for monitoring the email warmup process to ensure optimal sender reputation and identify any issues early.

## 1. SES Sending Statistics Checks

- **Bounce Rate:** Monitor the bounce rate to ensure it stays below the expected threshold (refer to `EMAIL_WARMUP_PLAN_logicalfront.net.md`). High bounce rates can negatively impact sender reputation.
- **Complaint Rate:** Monitor the complaint rate. High complaint rates indicate users are marking emails as spam, which severely damages sender reputation.
- **Delivery Rate:** Track the overall delivery rate to ensure emails are reaching their intended recipients.

**AWS CLI Commands for SES Reputation:**

- Check sending statistics (including bounces, complaints, and deliveries):
  ```bash
  aws ses get-send-statistics --query 'SendDataPoints[*].[Timestamp,Bounces,Complaints,DeliveryAttempts,Rejects]' --output table
  ```
- Check if account sending is enabled (should always be true during warmup):
  ```bash
  aws ses get-account-sending-enabled
  ```
- Check account reputation (provides overall health):
  ```bash
  aws ses get-account-reputation
  ```

## 2. Mautic Queue Status Checks

- **Pending Count:** Monitor the number of emails currently in the Mautic sending queue. A consistently high or increasing pending count might indicate a bottleneck or issue with the Mautic-SES integration.
- **Sent Count:** Verify that the number of sent emails aligns with the daily maximum send volume specified in the warmup schedule (`EMAIL_WARMUP_PLAN_logicalfront.net.md`).
- **Failed Count:** Check for any failed email attempts in Mautic. Investigate failures to understand root causes (e.g., invalid email addresses, temporary SES issues).

## 3. General Observations

- Review email logs for any unusual patterns or error messages.
- Monitor any notifications from AWS Health Dashboard regarding SES.
- Regularly review the `EMAIL_WARMUP_PLAN_logicalfront.net.md` to ensure adherence to the daily send volume and audience segmentation.
