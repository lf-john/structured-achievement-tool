# Mautic Email Sending Limit Adjustments

This document outlines the phased adjustments for Mautic's `mailer_spool_msg_limit` and cron job frequency during the email warmup schedule.

## Week 2
- **`mailer_spool_msg_limit`**: Set to `100`
- **Cron Frequency**: 1 time per day

## Week 3
- **`mailer_spool_msg_limit`**: Set to `250`
- **Cron Frequency**: 2 times per day

## Week 4
- **`mailer_spool_msg_limit`**: Set to `500`
- **Cron Frequency**: 4 times per day
