# Exiting Amazon SES Sandbox Mode

To request production access for Amazon SES and move out of sandbox mode, follow these steps:

## 1. Requesting Production Access

1.  Navigate to the [AWS SES console](https://console.aws.amazon.com/ses/).
2.  In the navigation pane, choose **Settings**, then **Sending statistics**.
3.  Choose **Edit your account details**.
4.  For "SES Sending Limits", choose **Request a production access increase**.
5.  Fill out the request form, providing the following information:
    *   **Mail Type:** Transactional, Marketing, or both.
    *   **Website URL:** Your website URL.
    *   **Use Case Description:** A detailed explanation of how you will use SES, including the type of emails you will send (e.g., transactional, marketing, notifications) and how recipients provide consent.
    *   **How will you handle bounces and complaints?**: Explain your process for handling bounces and complaints (e.g., automatically removing bounced email addresses from your mailing lists).

## 2. AWS Review Criteria

AWS reviews your request based on several factors to ensure you are a legitimate sender and to maintain the reputation of the SES service. Key criteria include:

*   **Bounce Rate:** Your bounce rate should be kept as low as possible (ideally below 5%). High bounce rates indicate poor list hygiene or invalid email addresses.
*   **Complaint Rate:** Your complaint rate should be below 0.1% (1 complaint per 1000 emails). High complaint rates indicate that recipients are marking your emails as spam.
*   **Use Case:** The clarity and legitimacy of your described use case. AWS wants to ensure you are not sending unsolicited bulk email.
*   **List Acquisition:** How you acquire your mailing list (e.g., double opt-in).

## 3. Expected Timeline

Typically, AWS processes production access requests within **24-48 hours**. In some cases, it might take longer if AWS requires additional information.

## 4. Sandbox vs. Production Limits

| Feature           | Sandbox Mode                                  | Production Mode (Initial)                        |
| :---------------- | :-------------------------------------------- | :----------------------------------------------- |
| **Sending Limits**| 200 messages per 24-hour period, 1 message/sec| 50,000 messages per 24-hour period, 14 messages/sec |
| **Recipients**    | Can only send to verified email addresses/domains | Can send to any recipient (within limits)        |
| **Email Content** | Full functionality                            | Full functionality                               |
| **Support**       | Standard                                      | Standard (can be increased with support plan)    |

*Note: Production sending limits can be further increased by submitting additional requests through the AWS console.*