"""
IMPLEMENTATION PLAN for US-001: deep_merge utility function

Components:
  - deep_merge(base: dict, override: dict) -> dict: Recursively merges two configuration
    dictionaries with specific rules for handling scalars, dicts, lists, and None values.

Test Cases:
  1. AC1: deep_merge returns a new dict and does not mutate base or override
     -> test_returns_new_dict, test_does_not_mutate_base, test_does_not_mutate_override
  2. AC2: Scalar override values replace base values
     -> test_scalar_override_replaces_base_value
  3. AC3: Dict values at the same key are merged recursively
     -> test_nested_dicts_merged_recursively
  4. AC4: List in override replaces list in base (no appending)
     -> test_list_override_replaces_base_list
  5. AC5: None value in override removes the key from the result entirely
     -> test_none_value_removes_key
  6. AC6: Keys present in base but absent in override are preserved
     -> test_base_keys_preserved
  7. AC7: Keys present in override but absent in base are added to result
     -> test_override_keys_added
  8. AC8: Deeply nested dicts are merged correctly
     -> test_deeply_nested_dicts_merged
  9. AC9: Function signature is deep_merge(base: dict, override: dict) -> dict
     -> test_function_signature
  10. AC10: Module is importable from src.utils.config_merger
      -> test_module_importable

Edge Cases:
  - Empty base dict
  - Empty override dict
  - Both dicts empty
  - Multiple levels of nesting
  - Mixed types in nested structures
  - Lists with various content types
  - Special characters in keys
  - Large nested structures
"""

import pytest
from copy import deepcopy


class TestDeepMergeImportability:
    """Test that the deep_merge module and function are properly importable."""

    def test_module_importable(self):
        """AC10: Module should be importable from src.utils.config_merger."""
        try:
            from src.utils.config_merger import deep_merge
            assert callable(deep_merge)
        except ImportError as e:
            pytest.fail(f"Failed to import deep_merge from src.utils.config_merger: {e}")

    def test_function_has_correct_signature(self):
        """AC9: Function signature should be deep_merge(base: dict, override: dict) -> dict."""
        from src.utils.config_merger import deep_merge
        import inspect

        sig = inspect.signature(deep_merge)
        params = list(sig.parameters.keys())

        assert len(params) == 2, f"Expected 2 parameters, got {len(params)}"
        assert params[0] == 'base', f"First parameter should be 'base', got '{params[0]}'"
        assert params[1] == 'override', f"Second parameter should be 'override', got '{params[1]}'"


class TestDeepMergeBasicBehavior:
    """Test basic behavior of deep_merge function."""

    def test_returns_new_dict(self):
        """AC1: deep_merge should return a new dict."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1}
        override = {'b': 2}

        result = deep_merge(base, override)

        assert isinstance(result, dict)
        assert result is not base
        assert result is not override

    def test_does_not_mutate_base_dict(self):
        """AC1: deep_merge should not mutate the base dict."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1, 'nested': {'x': 10}}
        base_copy = deepcopy(base)
        override = {'b': 2, 'nested': {'y': 20}}

        deep_merge(base, override)

        assert base == base_copy, "Base dict should not be mutated"

    def test_does_not_mutate_override_dict(self):
        """AC1: deep_merge should not mutate the override dict."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1}
        override = {'b': 2, 'nested': {'y': 20}}
        override_copy = deepcopy(override)

        deep_merge(base, override)

        assert override == override_copy, "Override dict should not be mutated"


class TestDeepMergeScalarValues:
    """Test scalar value handling in deep_merge."""

    def test_scalar_override_replaces_base_value_int(self):
        """AC2: Scalar override values should replace base values (int)."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1}
        override = {'a': 2}

        result = deep_merge(base, override)

        assert result['a'] == 2

    def test_scalar_override_replaces_base_value_string(self):
        """AC2: Scalar override values should replace base values (string)."""
        from src.utils.config_merger import deep_merge

        base = {'name': 'old_name'}
        override = {'name': 'new_name'}

        result = deep_merge(base, override)

        assert result['name'] == 'new_name'

    def test_scalar_override_replaces_base_value_bool(self):
        """AC2: Scalar override values should replace base values (bool)."""
        from src.utils.config_merger import deep_merge

        base = {'enabled': True}
        override = {'enabled': False}

        result = deep_merge(base, override)

        assert result['enabled'] is False

    def test_scalar_override_replaces_base_value_float(self):
        """AC2: Scalar override values should replace base values (float)."""
        from src.utils.config_merger import deep_merge

        base = {'value': 1.5}
        override = {'value': 2.7}

        result = deep_merge(base, override)

        assert result['value'] == 2.7


class TestDeepMergeNestedDicts:
    """Test nested dictionary merging in deep_merge."""

    def test_nested_dicts_merged_recursively(self):
        """AC3: Dict values at the same key should be merged recursively."""
        from src.utils.config_merger import deep_merge

        base = {'config': {'a': 1, 'b': 2}}
        override = {'config': {'b': 20, 'c': 30}}

        result = deep_merge(base, override)

        assert result['config']['a'] == 1
        assert result['config']['b'] == 20
        assert result['config']['c'] == 30

    def test_deeply_nested_dicts_merged(self):
        """AC8: Deeply nested dicts should be merged correctly."""
        from src.utils.config_merger import deep_merge

        base = {
            'level1': {
                'level2': {
                    'level3': {
                        'a': 1,
                        'b': 2
                    }
                }
            }
        }
        override = {
            'level1': {
                'level2': {
                    'level3': {
                        'b': 20,
                        'c': 30
                    }
                }
            }
        }

        result = deep_merge(base, override)

        assert result['level1']['level2']['level3']['a'] == 1
        assert result['level1']['level2']['level3']['b'] == 20
        assert result['level1']['level2']['level3']['c'] == 30

    def test_multiple_nested_paths(self):
        """AC3: Multiple nested paths should be merged independently."""
        from src.utils.config_merger import deep_merge

        base = {
            'path1': {'x': 1},
            'path2': {'y': 2}
        }
        override = {
            'path1': {'x': 10},
            'path2': {'y': 20, 'z': 30}
        }

        result = deep_merge(base, override)

        assert result['path1']['x'] == 10
        assert result['path2']['y'] == 20
        assert result['path2']['z'] == 30


class TestDeepMergeListHandling:
    """Test list handling in deep_merge."""

    def test_list_override_replaces_base_list(self):
        """AC4: List in override should replace list in base entirely (no appending)."""
        from src.utils.config_merger import deep_merge

        base = {'items': [1, 2, 3]}
        override = {'items': [4, 5]}

        result = deep_merge(base, override)

        assert result['items'] == [4, 5]

    def test_list_with_empty_override_list(self):
        """AC4: Empty list in override should replace base list."""
        from src.utils.config_merger import deep_merge

        base = {'items': [1, 2, 3]}
        override = {'items': []}

        result = deep_merge(base, override)

        assert result['items'] == []

    def test_list_with_different_types(self):
        """AC4: List replacement should work with different element types."""
        from src.utils.config_merger import deep_merge

        base = {'items': [1, 2, 3]}
        override = {'items': ['a', 'b', 'c']}

        result = deep_merge(base, override)

        assert result['items'] == ['a', 'b', 'c']

    def test_list_with_nested_structures(self):
        """AC4: List replacement should work with nested structures."""
        from src.utils.config_merger import deep_merge

        base = {'items': [{'x': 1}, {'y': 2}]}
        override = {'items': [{'z': 3}]}

        result = deep_merge(base, override)

        assert result['items'] == [{'z': 3}]


class TestDeepMergeNoneValues:
    """Test None value handling in deep_merge."""

    def test_none_value_removes_key(self):
        """AC5: None value in override should remove the key from the result entirely."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1, 'b': 2}
        override = {'a': None}

        result = deep_merge(base, override)

        assert 'a' not in result
        assert result['b'] == 2

    def test_none_value_removes_nested_key(self):
        """AC5: None value in nested override should remove nested key."""
        from src.utils.config_merger import deep_merge

        base = {'config': {'a': 1, 'b': 2}}
        override = {'config': {'a': None}}

        result = deep_merge(base, override)

        assert 'a' not in result['config']
        assert result['config']['b'] == 2

    def test_none_value_at_multiple_levels(self):
        """AC5: None values should remove keys at multiple nesting levels."""
        from src.utils.config_merger import deep_merge

        base = {
            'level1': {
                'level2': {
                    'x': 1,
                    'y': 2
                }
            }
        }
        override = {
            'level1': {
                'level2': {
                    'x': None
                }
            }
        }

        result = deep_merge(base, override)

        assert 'x' not in result['level1']['level2']
        assert result['level1']['level2']['y'] == 2

    def test_none_removes_only_specified_key(self):
        """AC5: None should only remove the specific key, not others."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1, 'b': 2, 'c': 3}
        override = {'b': None}

        result = deep_merge(base, override)

        assert result['a'] == 1
        assert 'b' not in result
        assert result['c'] == 3


class TestDeepMergeKeyPreservation:
    """Test key preservation in deep_merge."""

    def test_base_keys_preserved_when_absent_in_override(self):
        """AC6: Keys present in base but absent in override should be preserved."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1, 'b': 2}
        override = {'b': 20}

        result = deep_merge(base, override)

        assert result['a'] == 1

    def test_override_keys_added_when_absent_in_base(self):
        """AC7: Keys present in override but absent in base should be added."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1}
        override = {'b': 2}

        result = deep_merge(base, override)

        assert result['a'] == 1
        assert result['b'] == 2

    def test_mixed_key_operations(self):
        """AC6 & AC7: Base keys preserved and override keys added in same call."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1, 'b': 2, 'c': 3}
        override = {'b': 20, 'd': 4}

        result = deep_merge(base, override)

        assert result['a'] == 1
        assert result['b'] == 20
        assert result['c'] == 3
        assert result['d'] == 4


class TestDeepMergeEdgeCases:
    """Test edge cases for deep_merge."""

    def test_empty_base_dict(self):
        """Edge case: Empty base dict should result in override dict values."""
        from src.utils.config_merger import deep_merge

        base = {}
        override = {'a': 1, 'b': 2}

        result = deep_merge(base, override)

        assert result == {'a': 1, 'b': 2}

    def test_empty_override_dict(self):
        """Edge case: Empty override dict should result in base dict values."""
        from src.utils.config_merger import deep_merge

        base = {'a': 1, 'b': 2}
        override = {}

        result = deep_merge(base, override)

        assert result == {'a': 1, 'b': 2}

    def test_both_dicts_empty(self):
        """Edge case: Both empty dicts should return empty dict."""
        from src.utils.config_merger import deep_merge

        base = {}
        override = {}

        result = deep_merge(base, override)

        assert result == {}

    def test_special_characters_in_keys(self):
        """Edge case: Keys with special characters should be handled correctly."""
        from src.utils.config_merger import deep_merge

        base = {'key-with-dash': 1, 'key_with_underscore': 2}
        override = {'key-with-dash': 10}

        result = deep_merge(base, override)

        assert result['key-with-dash'] == 10
        assert result['key_with_underscore'] == 2

    def test_numeric_string_keys(self):
        """Edge case: Numeric string keys should be handled correctly."""
        from src.utils.config_merger import deep_merge

        base = {'1': 'a', '2': 'b'}
        override = {'1': 'x'}

        result = deep_merge(base, override)

        assert result['1'] == 'x'
        assert result['2'] == 'b'

    def test_empty_nested_dict_override(self):
        """Edge case: Empty dict in override should not replace base nested dict."""
        from src.utils.config_merger import deep_merge

        base = {'config': {'a': 1, 'b': 2}}
        override = {'config': {}}

        result = deep_merge(base, override)

        # Empty dict in override should merge (not replace), preserving base values
        assert result['config']['a'] == 1
        assert result['config']['b'] == 2

    def test_scalar_to_dict_replacement(self):
        """Edge case: Scalar in base replaced by dict in override."""
        from src.utils.config_merger import deep_merge

        base = {'value': 'scalar'}
        override = {'value': {'nested': 'dict'}}

        result = deep_merge(base, override)

        assert result['value'] == {'nested': 'dict'}

    def test_dict_to_scalar_replacement(self):
        """Edge case: Dict in base replaced by scalar in override."""
        from src.utils.config_merger import deep_merge

        base = {'value': {'nested': 'dict'}}
        override = {'value': 'scalar'}

        result = deep_merge(base, override)

        assert result['value'] == 'scalar'

    def test_dict_to_list_replacement(self):
        """Edge case: Dict in base replaced by list in override."""
        from src.utils.config_merger import deep_merge

        base = {'value': {'nested': 'dict'}}
        override = {'value': [1, 2, 3]}

        result = deep_merge(base, override)

        assert result['value'] == [1, 2, 3]

    def test_list_to_dict_replacement(self):
        """Edge case: List in base replaced by dict in override."""
        from src.utils.config_merger import deep_merge

        base = {'value': [1, 2, 3]}
        override = {'value': {'nested': 'dict'}}

        result = deep_merge(base, override)

        assert result['value'] == {'nested': 'dict'}

    def test_complex_nested_structure_with_all_types(self):
        """Edge case: Complex nested structure with scalars, dicts, lists, and None."""
        from src.utils.config_merger import deep_merge

        base = {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'credentials': {
                    'user': 'admin',
                    'password': 'secret'
                },
                'options': [1, 2, 3]
            },
            'logging': {
                'level': 'info'
            }
        }
        override = {
            'database': {
                'host': 'prod.example.com',
                'credentials': {
                    'password': 'new_secret'
                },
                'options': ['a', 'b'],
                'pool_size': 20
            },
            'logging': {
                'level': None
            },
            'cache': {
                'enabled': True
            }
        }

        result = deep_merge(base, override)

        # Verify merged structure
        assert result['database']['host'] == 'prod.example.com'
        assert result['database']['port'] == 5432
        assert result['database']['credentials']['user'] == 'admin'
        assert result['database']['credentials']['password'] == 'new_secret'
        assert result['database']['options'] == ['a', 'b']
        assert result['database']['pool_size'] == 20
        assert 'level' not in result['logging']
        assert result['cache']['enabled'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
