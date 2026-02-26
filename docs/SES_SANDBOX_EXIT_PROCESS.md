# Amazon SES Sandbox Exit Process

This document outlines the process for requesting production access for Amazon Simple Email Service (SES), including AWS review criteria, expected timelines, and the differences between sandbox and production limits.

## 1. Requesting Production Access

To request production access for Amazon SES, follow these steps:

1.  **Navigate to the Amazon SES Console:** Go to the AWS Management Console and open the SES service.
2.  **Access Sending Limits:** In the navigation pane, choose "Sending Statistics" or "Sending Limits."
3.  **Request a Limit Increase:** Click on the "Request a Production Access" button or a similar option to open a new support case.
4.  **Complete the Form:** Fill out the request form with the following critical information:
    *   **Region:** Specify the AWS region where you want production access.
    *   **Mail Type:** Clearly state the type of emails you will be sending (e.g., transactional, marketing, system notifications).
    *   **Website URL:** Provide the URL of your website or application that will be using SES.
    *   **Use Case Description:** Detail how you plan to use SES. Be specific and include information on how you will manage bounce and complaint rates (e.g., automated suppression lists, double opt-in for marketing emails).
    *   **Sending Quota:** Request an initial sending quota (e.g., 50,000 emails per day, 14 emails per second). Start with a realistic estimate and you can request further increases later.

## 2. AWS Review Criteria

AWS reviews production access requests based on several factors to maintain the reputation of its email sending service and prevent abuse. Key criteria include:

*   **Bounce Rate:** Your bounce rate should ideally be below 5%. High bounce rates indicate poor list hygiene or invalid recipients.
*   **Complaint Rate:** Your complaint rate should be below 0.1% (1 complaint per 1000 emails). High complaint rates suggest users are receiving unwanted emails and are marking them as spam.
*   **Use Case Description:** AWS assesses the legitimacy and clarity of your use case. A well-defined use case with clear strategies for managing recipient engagement and feedback is crucial.
*   **Opt-in Process:** For marketing emails, AWS often looks for evidence of a clear opt-in process (e.g., double opt-in) to ensure recipients have explicitly agreed to receive your emails.
*   **Content Quality:** While not explicitly reviewed at this stage, the nature of your content and its compliance with email best practices (e.g., CAN-SPAM, GDPR) is implicitly part of their assessment of your use case.

## 3. Expected Timeline

The typical timeline for an AWS SES production access review is **24-48 hours**. However, it can sometimes take longer, especially if the request is incomplete or requires further clarification from AWS. It's advisable to submit your request well in advance of when you need production sending capabilities.

## 4. Sandbox vs. Production Limits

Understanding the differences between sandbox and production environments is key:

| Feature           | Sandbox Environment                               | Production Environment                                 |
| :---------------- | :------------------------------------------------ | :----------------------------------------------------- |
| **Sending Quota** | Low daily sending limits (e.g., 200 emails/day)   | Higher, user-requested daily sending limits            |
|                   | Low maximum send rate (e.g., 1 email/second)      | Higher, user-requested maximum send rate               |
| **Recipient**     | Can only send to verified email addresses         | Can send to any email address                          |
| **Cost**          | Free tier benefits apply to initial limits        | Standard SES pricing applies based on usage            |
| **Reputation**    | Does not impact your sender reputation directly   | Directly impacts your sender reputation and deliverability |
| **Feedback**      | Bounce and complaint notifications are still received | Critical for maintaining sender health and reputation  |

Transitioning to production allows you to send emails to unverified recipients and at significantly higher volumes, but it also places a greater responsibility on you to maintain good sending practices and monitor your reputation.
