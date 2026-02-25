"""
IMPLEMENTATION PLAN for US-001:

Components:
  - generate_spf_record(domain: str, includes: list[str]) -> str: Constructs a base SPF record string (e.g., "v=spf1 include:example.com ~all").
  - merge_spf_records(existing_record: str, new_include: str) -> str: Merges a new 'include' mechanism into an existing SPF record, adhering to the 'only one SPF record' rule. It should correctly insert the new include while preserving 'v=spf1' and the 'all' mechanism (e.g., ~all, -all).
  - document_spf_guidance(domain: str, new_include: str, existing_record: str | None) -> str: Generates a comprehensive documentation string including the record type, host, full SPF value, and detailed guidance on merging with an existing record if present.

Test Cases:
  1. AC 1 (New Record): `document_spf_guidance` generates the correct SPF record for a domain with no existing record, including `include:amazonses.com`.
  2. AC 1 (Merge Simple): `document_spf_guidance` generates correct merged SPF record for a domain with a simple existing SPF record (e.g., "v=spf1 ~all").
  3. AC 1 (Merge Complex): `document_spf_guidance` generates correct merged SPF record for a domain with a complex existing SPF record (e.g., "v=spf1 include:other.com mx ~all").
  4. AC 2 (New Record Guidance): `document_spf_guidance` provides correct default host and value when no existing record.
  5. AC 2 (Merge Guidance): `document_spf_guidance` provides detailed merging guidance when an existing record is present.
  6. Edge Case (Already Included): `merge_spf_records` correctly handles an existing SPF record that already includes `include:amazonses.com` without duplication.
  7. Edge Case (Existing No All): `merge_spf_records` correctly adds `~all` if not present in the existing record during a merge.
  8. Edge Case (Invalid existing SPF): `merge_spf_records` gracefully handles an existing record without "v=spf1" or invalid structure, perhaps by returning the new record and a warning. (For now, assume valid existing SPF for generation, but note for implementation).
  9. Negative Case (Empty domain): `document_spf_guidance` raises an error or returns an empty string for an empty domain.

Edge Cases:
  - No existing SPF record.
  - Existing SPF record is simple (`v=spf1 ~all`).
  - Existing SPF record is complex (`v=spf1 include:other.com mx -all`).
  - Existing SPF record already contains `include:amazonses.com`.
  - Existing SPF record without an 'all' mechanism (`~all`, `-all`, `?all`).
  - Empty or invalid domain input.

Test Utilities:
  - pytest for test execution.
"""
import pytest
import sys
from unittest.mock import patch, MagicMock

# Assuming these functions will be in a module like src.utils.spf_generator
# We expect these imports to fail initially, leading to TDD-RED state.
from src.utils.spf_generator import generate_spf_record, merge_spf_records, document_spf_guidance

class TestSPFRecordGenerator:

    def test_ac1_new_record_documented_includes_amazonses(self):
        domain = "logicalfront.net"
        new_include = "include:amazonses.com"
        expected_substring = "v=spf1 include:amazonses.com ~all"
        result = document_spf_guidance(domain, new_include, None)
        assert expected_substring in result
        assert "TXT" in result
        assert "Host: logicalfront.net" in result

    def test_ac1_merge_simple_existing_record(self):
        domain = "logicalfront.net"
        new_include = "include:amazonses.com"
        existing_record = "v=spf1 ~all"
        expected_substring = "v=spf1 include:amazonses.com ~all"
        result = document_spf_guidance(domain, new_include, existing_record)
        assert expected_substring in result
        assert "TXT" in result
        assert "Host: logicalfront.net" in result

    def test_ac1_merge_complex_existing_record(self):
        domain = "logicalfront.net"
        new_include = "include:amazonses.com"
        existing_record = "v=spf1 include:other.com mx -all"
        expected_substring = "v=spf1 include:other.com include:amazonses.com mx -all"
        result = document_spf_guidance(domain, new_include, existing_record)
        assert expected_substring in result
        assert "TXT" in result
        assert "Host: logicalfront.net" in result

    def test_ac2_new_record_guidance_provided(self):
        domain = "logicalfront.net"
        new_include = "include:amazonses.com"
        result = document_spf_guidance(domain, new_include, None)
        assert "Record Type: TXT" in result
        assert "Host: logicalfront.net" in result
        assert "Full Value: v=spf1 include:amazonses.com ~all" in result
        assert "No existing SPF record found" in result

    def test_ac2_merge_guidance_provided_for_existing_record(self):
        domain = "logicalfront.net"
        new_include = "include:amazonses.com"
        existing_record = "v=spf1 mx ~all"
        result = document_spf_guidance(domain, new_include, existing_record)
        assert "Existing SPF record detected" in result
        assert "To correctly merge" in result
        assert "only one SPF record per domain" in result
        assert "updated SPF record" in result

    def test_edge_case_already_included_no_duplication(self):
        existing_record = "v=spf1 include:other.com include:amazonses.com ~all"
        new_include = "include:amazonses.com"
        expected_merged_record = "v=spf1 include:other.com include:amazonses.com ~all"
        result = merge_spf_records(existing_record, new_include)
        assert result == expected_merged_record

    def test_edge_case_existing_no_all_adds_default(self):
        existing_record = "v=spf1 include:other.com"
        new_include = "include:amazonses.com"
        expected_merged_record = "v=spf1 include:other.com include:amazonses.com ~all"
        result = merge_spf_records(existing_record, new_include)
        assert result == expected_merged_record

    def test_negative_case_empty_domain_in_document_spf_guidance(self):
        domain = ""
        new_include = "include:amazonses.com"
        with pytest.raises(ValueError, match="Domain cannot be empty"):
            document_spf_guidance(domain, new_include, None)
