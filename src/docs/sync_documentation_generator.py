def generate_initial_sync_doc() -> str:
    """
    Generates documentation for the initial full sync process.
    :return: A string containing the documentation.
    """
    return (
        "# Initial Full Sync Process\n\n"
        "This document outlines the steps for performing the initial full synchronization "
        "of contacts between systems.\n\n"
        "## Steps\n"
        "1. **Export**: Export all existing contacts from the source system.\n"
        "2. **Prepare**: Clean and transform the exported data to match the target system's schema.\n"
        "3. **Import**: Import the prepared data into the target system.\n"
        "4. **Manual Verification**: Perform a manual spot-check to ensure data integrity and completeness.\n"
        "5. **Enable Ongoing Sync**: Once the initial sync is complete and verified, enable real-time "
        "webhooks or scheduled incremental syncs.\n"
    )


def generate_deduplication_strategy_doc() -> str:
    """
    Generates documentation for the deduplication strategy.
    :return: A string containing the documentation.
    """
    return (
        "# Deduplication Strategy\n\n"
        "This document describes the strategy used to identify and handle duplicate contact records.\n\n"
        "## Key Principles\n"
        "1. **Unique Identifier**: Each contact should ideally have a unique identifier (e.g., email address, external ID).\n"
        "2. **Matching Rules**: Define clear rules for identifying potential duplicates. Common rules include "
        "matching by email, name, or a combination of fields.\n"
        "3. **Merge Logic**: Establish a merge strategy to combine duplicate records into a single, comprehensive record. "
        "This typically involves prioritizing data from the most recently updated record or a 'golden record' source.\n"
        "4. **Automated vs. Manual**: Implement automated deduplication where possible, with a process for manual review "
        "and resolution of complex cases.\n"
    )
