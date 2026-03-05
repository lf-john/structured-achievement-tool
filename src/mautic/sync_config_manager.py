
def configure_sync_frequency(frequency: str, config_storage: dict):
    """
    Sets the sync frequency.
    :param frequency: The desired sync frequency (e.g., "15 minutes", "real-time webhooks").
    :param config_storage: A dictionary to store the configuration.
    """
    if frequency == "never":
        raise ValueError("Invalid sync frequency")
    config_storage["sync_frequency"] = frequency

def configure_batch_size(num_contacts: int, config_storage: dict):
    """
    Calculates and sets an appropriate batch size based on the number of contacts.
    :param num_contacts: The total number of contacts.
    :param config_storage: A dictionary to store the configuration.
    """
    if num_contacts < 0:
        raise ValueError("Number of contacts cannot be negative")

    if num_contacts == 0:
        config_storage["batch_size"] = 0
        return

    # Simple logic for batch size calculation. For 30,000 contacts, 5000 batch size seems reasonable (30000/6).
    # We'll cap the batch size to a max to prevent excessively large batches.
    max_batch_size = 5000
    calculated_batch_size = min(max_batch_size, num_contacts // 6) # Divide by 6 for 30k contacts to get 5k batch size

    # Ensure a minimum batch size if num_contacts is positive but very small
    if calculated_batch_size == 0 and num_contacts > 0:
        calculated_batch_size = min(num_contacts, 100) # Use a small default or num_contacts itself

    config_storage["batch_size"] = calculated_batch_size
