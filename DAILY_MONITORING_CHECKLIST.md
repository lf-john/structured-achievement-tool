
# Daily Email Warmup Monitoring Checklist

This document outlines the daily checks required to monitor the health of the email warmup process.

## 1. AWS SES Sending Statistics

Check the Simple Email Service (SES) sending statistics to monitor email deliverability and reputation.

**Command:**
```bash
aws ses get-send-statistics
```

**What to check for:**
- **BounceRate:** Should be below 2%. A high bounce rate indicates issues with the email list quality.
- **ComplaintRate:** Should be below 0.1%. A high complaint rate indicates recipients are marking emails as spam.
- **DeliveryRate:** Should be consistently high.

## 2. AWS SES Account Sending Enabled

Verify that the AWS account's ability to send email is enabled. If this is disabled, it means AWS has suspended your sending capabilities due to reputation issues.

**Command:**
```bash
aws ses get-account-sending-enabled
```

**What to check for:**
- The output should show `"Enabled": true`. If `false`, immediately investigate the cause.

## 3. Mautic Email Queue Status

Check the status of the email queue in your Mautic instance to ensure emails are being processed and sent as expected.

**How to check:**
1.  Log in to your Mautic dashboard.
2.  Navigate to **Settings** (gear icon) > **System Info**.
3.  Look for the **Email Queue** section.

**What to check for:**
- **Pending Messages:** This number should be decreasing over time. If it's stuck or growing unexpectedly, it could indicate a problem with the cron job that processes the queue.
- **Sent Messages:** This number should be increasing according to your warmup schedule.
- **Failed Messages:** This number should be zero or very low. Investigate any failed messages to understand the cause.
