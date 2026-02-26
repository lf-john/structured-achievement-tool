# Mautic Email Warmup Configuration Guide

This document outlines the specific Mautic settings for each week of the email sender warmup plan. Following this schedule helps build a positive sender reputation.

## Weekly Configuration Settings

### Week 1: Initial Ramp-up

*   **Goal:** Establish a consistent, low-volume sending pattern.
*   **Email Queue Processing Frequency (Cron):** Every 30 minutes.
*   **Batch Size per Cron Run:** 25 emails.
*   **Sending Rate Limit:** 5 emails per minute.

### Week 2: Gentle Increase

*   **Goal:** Gradually increase sending volume while monitoring deliverability.
*   **Email Queue Processing Frequency (Cron):** Every 15 minutes.
*   **Batch Size per Cron Run:** 50 emails.
*   **Sending Rate Limit:** 10 emails per minute.

### Week 3: Moderate Volume

*   **Goal:** Scale up to a more significant sending volume.
*   **Email Queue Processing Frequency (Cron):** Every 5 minutes.
*   **Batch Size per Cron Run:** 100 emails.
*   **Sending Rate Limit:** 25 emails per minute.

### Week 4: Full Production Volume

*   **Goal:** Operate at the target production sending rate.
*   **Email Queue Processing Frequency (Cron):** Every 1 minute.
*   **Batch Size per Cron Run:** 200 emails.
*   **Sending Rate Limit:** 50 emails per minute (or as per ESP limits).

---

## How to Change Mautic Settings (UI Method)

1.  Log in to your Mautic admin dashboard.
2.  Navigate to **Settings** (cog icon in the top right).
3.  Click on **Configuration**.
4.  Select the **Email Settings** tab.
5.  Scroll down to the "Message Queue Settings" section.
6.  Adjust the "Number of emails to send per batch" (Batch Size) and "Time in minutes to wait before sending another batch" (Sending Rate Limit converted from emails per minute).
7.  Save the configuration.

---

## How to Adjust Mautic Cron Frequency (Docker)

The Mautic cron jobs control how often the email queue is processed. These are typically managed in the crontab of the Mautic container.

1.  **Find the Mautic container ID or name:**
    ```bash
    docker ps | grep mautic
    ```

2.  **Access the container's shell:**
    Replace `mautic_container_name` with the actual name or ID from the previous step.
    ```bash
    docker exec -it mautic_container_name /bin/bash
    ```

3.  **Edit the crontab:**
    Inside the container, open the crontab for editing. The default editor is usually `vi`.
    ```bash
    crontab -e
    ```

4.  **Locate and modify the queue processing job:**
    Find the line similar to `* * * * * /usr/local/bin/php /var/www/html/bin/console mautic:emails:send`.
    Adjust the schedule according to the weekly plan. For example, for Week 1 (every 30 minutes), you would change it to:
    ```
    */30 * * * * /usr/local/bin/php /var/www/html/bin/console mautic:emails:send
    ```

5.  **Save and exit the editor.** The new cron schedule will be applied automatically.
