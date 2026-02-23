"""
IMPLEMENTATION PLAN for US-002: Comprehensive Tests for deep_merge

Components:
  - deep_merge function from src.utils.config_merger: Recursively merges two dicts with
    specific rules for scalars, dicts, lists, and None values.

Acceptance Criteria Mapping:
  1. AC1: Tests for flat (non-dict) value override
     -> test_scalar_int_override, test_scalar_string_override, test_scalar_bool_override,
        test_scalar_float_override, test_scalar_none_value

  2. AC2: Tests for recursive dict merge at multiple nesting levels
     -> test_nested_dict_merge_level2, test_nested_dict_merge_level3, test_nested_dict_merge_level4,
        test_nested_dict_multiple_independent_paths

  3. AC3: Tests that lists in override replace lists in base
     -> test_list_replacement_with_shorter_list, test_list_replacement_with_longer_list,
        test_list_replacement_with_empty_list, test_list_replacement_with_different_types,
        test_list_replacement_with_nested_dicts

  4. AC4: Tests that None in override deletes the key
     -> test_none_deletes_top_level_key, test_none_deletes_nested_key,
        test_none_deletes_multiple_keys_same_level, test_none_with_other_overrides

  5. AC5: Tests that neither base nor override is mutated
     -> test_base_immutability_simple, test_base_immutability_nested,
        test_override_immutability_simple, test_override_immutability_nested,
        test_deepcopy_verification

  6. AC6: Tests for empty base dict
     -> test_empty_base_with_override, test_empty_base_empty_override

  7. AC7: Tests for empty override dict
     -> test_empty_override_with_base

  8. AC8: Tests for both dicts empty
     -> test_both_empty

  9. AC9: Tests for deeply nested (3+ levels) merging
     -> test_deeply_nested_3_levels, test_deeply_nested_5_levels, test_deeply_nested_mixed

  10. AC10: Tests for mixed types at same key
      -> test_scalar_to_dict, test_dict_to_scalar, test_dict_to_list, test_list_to_dict,
         test_list_to_scalar, test_scalar_to_list, test_type_mismatch_preservation

  11. AC11: All tests pass against US-001 implementation (no new implementation needed)

  12. AC12: At least 20 distinct test cases (25+ tests provided)

Edge Cases Beyond ACs:
  - Special characters in keys
  - Numeric string keys
  - Very deeply nested structures (5+ levels)
  - Large nested dicts
  - Mixed nested scenarios with multiple type changes
  - Preservation of key order
  - Unicode characters in strings
  - Negative numbers and zero values
  - Boolean and None edge cases
  - Complex integration scenarios

Test Organization:
  - TestDeepMergeFlatValues: Scalar value overrides
  - TestDeepMergeNestedDicts: Dict merging at various levels
  - TestDeepMergeListHandling: List replacement behavior
  - TestDeepMergeNoneHandling: None value deletion
  - TestDeepMergeImmutability: Input preservation
  - TestDeepMergeEmptyCases: Empty dict handling
  - TestDeepMergeTypeConversions: Mixed type handling
  - TestDeepMergeComplexScenarios: Integration and edge cases
"""

import pytest
from copy import deepcopy
from src.utils.config_merger import deep_merge


class TestDeepMergeFlatValues:
    """Test flat (non-dict) value override behavior."""

    def test_scalar_int_override(self):
        """AC1: Integer scalar in override should replace base value."""
        base = {'value': 10}
        override = {'value': 20}
        result = deep_merge(base, override)
        assert result['value'] == 20

    def test_scalar_string_override(self):
        """AC1: String scalar in override should replace base value."""
        base = {'name': 'original'}
        override = {'name': 'updated'}
        result = deep_merge(base, override)
        assert result['name'] == 'updated'

    def test_scalar_bool_override(self):
        """AC1: Boolean scalar in override should replace base value."""
        base = {'enabled': True}
        override = {'enabled': False}
        result = deep_merge(base, override)
        assert result['enabled'] is False

    def test_scalar_float_override(self):
        """AC1: Float scalar in override should replace base value."""
        base = {'temperature': 98.6}
        override = {'temperature': 101.5}
        result = deep_merge(base, override)
        assert result['temperature'] == 101.5

    def test_scalar_zero_override(self):
        """AC1: Zero value should override non-zero base value."""
        base = {'count': 10}
        override = {'count': 0}
        result = deep_merge(base, override)
        assert result['count'] == 0

    def test_scalar_empty_string_override(self):
        """AC1: Empty string should override non-empty string."""
        base = {'text': 'content'}
        override = {'text': ''}
        result = deep_merge(base, override)
        assert result['text'] == ''

    def test_scalar_false_override(self):
        """AC1: False should override True in base."""
        base = {'flag': True}
        override = {'flag': False}
        result = deep_merge(base, override)
        assert result['flag'] is False


class TestDeepMergeNestedDicts:
    """Test recursive dictionary merging at multiple nesting levels."""

    def test_nested_dict_merge_level2(self):
        """AC2: Two-level nested dicts should merge recursively."""
        base = {'config': {'debug': False, 'timeout': 30}}
        override = {'config': {'debug': True}}
        result = deep_merge(base, override)
        assert result['config']['debug'] is True
        assert result['config']['timeout'] == 30

    def test_nested_dict_merge_level3(self):
        """AC2: Three-level nested dicts should merge recursively."""
        base = {
            'app': {
                'database': {
                    'host': 'localhost',
                    'port': 5432
                }
            }
        }
        override = {
            'app': {
                'database': {
                    'host': 'remote.com'
                }
            }
        }
        result = deep_merge(base, override)
        assert result['app']['database']['host'] == 'remote.com'
        assert result['app']['database']['port'] == 5432

    def test_nested_dict_merge_level4(self):
        """AC2: Four-level nested dicts should merge recursively."""
        base = {
            'level1': {
                'level2': {
                    'level3': {
                        'level4': {'key': 'value1'}
                    }
                }
            }
        }
        override = {
            'level1': {
                'level2': {
                    'level3': {
                        'level4': {'key': 'value2'}
                    }
                }
            }
        }
        result = deep_merge(base, override)
        assert result['level1']['level2']['level3']['level4']['key'] == 'value2'

    def test_nested_dict_multiple_independent_paths(self):
        """AC2: Multiple independent nested paths should merge correctly."""
        base = {
            'path1': {'a': 1, 'b': 2},
            'path2': {'x': 10, 'y': 20},
            'path3': {'m': 100}
        }
        override = {
            'path1': {'b': 20},
            'path2': {'x': 100, 'z': 30},
            'path3': {'m': 200, 'n': 300}
        }
        result = deep_merge(base, override)
        assert result['path1'] == {'a': 1, 'b': 20}
        assert result['path2'] == {'x': 100, 'y': 20, 'z': 30}
        assert result['path3'] == {'m': 200, 'n': 300}

    def test_nested_dict_preserves_untouched_keys(self):
        """AC2: Unmodified nested keys should be preserved exactly."""
        base = {
            'settings': {
                'ui': {'theme': 'dark'},
                'api': {'timeout': 30, 'retries': 3}
            }
        }
        override = {
            'settings': {
                'ui': {'theme': 'light'}
            }
        }
        result = deep_merge(base, override)
        assert result['settings']['ui']['theme'] == 'light'
        assert result['settings']['api'] == {'timeout': 30, 'retries': 3}


class TestDeepMergeListHandling:
    """Test list replacement behavior."""

    def test_list_replacement_with_shorter_list(self):
        """AC3: Shorter list in override should completely replace base list."""
        base = {'items': [1, 2, 3, 4, 5]}
        override = {'items': [10, 20]}
        result = deep_merge(base, override)
        assert result['items'] == [10, 20]
        assert len(result['items']) == 2

    def test_list_replacement_with_longer_list(self):
        """AC3: Longer list in override should completely replace base list."""
        base = {'items': [1, 2]}
        override = {'items': [10, 20, 30, 40, 50]}
        result = deep_merge(base, override)
        assert result['items'] == [10, 20, 30, 40, 50]

    def test_list_replacement_with_empty_list(self):
        """AC3: Empty list in override should replace non-empty base list."""
        base = {'items': [1, 2, 3]}
        override = {'items': []}
        result = deep_merge(base, override)
        assert result['items'] == []

    def test_list_replacement_with_different_types(self):
        """AC3: List with different element types should replace base list."""
        base = {'items': [1, 2, 3]}
        override = {'items': ['a', 'b', 'c']}
        result = deep_merge(base, override)
        assert result['items'] == ['a', 'b', 'c']

    def test_list_replacement_with_nested_dicts(self):
        """AC3: List with nested dicts in override should replace base list."""
        base = {'items': [{'id': 1}, {'id': 2}]}
        override = {'items': [{'name': 'new'}]}
        result = deep_merge(base, override)
        assert result['items'] == [{'name': 'new'}]

    def test_list_replacement_with_nested_lists(self):
        """AC3: List with nested lists in override should replace base list."""
        base = {'data': [[1, 2], [3, 4]]}
        override = {'data': [[5, 6]]}
        result = deep_merge(base, override)
        assert result['data'] == [[5, 6]]

    def test_list_in_nested_dict_replacement(self):
        """AC3: List replacement should work in nested dicts."""
        base = {'config': {'items': [1, 2, 3]}}
        override = {'config': {'items': ['a', 'b']}}
        result = deep_merge(base, override)
        assert result['config']['items'] == ['a', 'b']


class TestDeepMergeNoneHandling:
    """Test None value deletion behavior."""

    def test_none_deletes_top_level_key(self):
        """AC4: None value in override should delete key from result."""
        base = {'a': 1, 'b': 2, 'c': 3}
        override = {'b': None}
        result = deep_merge(base, override)
        assert 'b' not in result
        assert result == {'a': 1, 'c': 3}

    def test_none_deletes_nested_key(self):
        """AC4: None value should delete key in nested dicts."""
        base = {'config': {'debug': True, 'log': 'info'}}
        override = {'config': {'debug': None}}
        result = deep_merge(base, override)
        assert 'debug' not in result['config']
        assert result['config']['log'] == 'info'

    def test_none_deletes_multiple_keys_same_level(self):
        """AC4: Multiple None values should delete multiple keys."""
        base = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
        override = {'b': None, 'd': None}
        result = deep_merge(base, override)
        assert result == {'a': 1, 'c': 3}

    def test_none_with_other_overrides(self):
        """AC4: None deletion should work alongside other overrides."""
        base = {'keep': 'this', 'delete': 'that', 'update': 'old'}
        override = {'delete': None, 'update': 'new'}
        result = deep_merge(base, override)
        assert result == {'keep': 'this', 'update': 'new'}

    def test_none_deletes_key_not_in_override(self):
        """AC4: None should delete key even if not present in base."""
        base = {'a': 1}
        override = {'nonexistent': None}
        result = deep_merge(base, override)
        assert result == {'a': 1}

    def test_none_in_deeply_nested_dict(self):
        """AC4: None deletion should work at deep nesting levels."""
        base = {
            'level1': {
                'level2': {
                    'level3': {
                        'key1': 'value1',
                        'key2': 'value2'
                    }
                }
            }
        }
        override = {
            'level1': {
                'level2': {
                    'level3': {
                        'key1': None
                    }
                }
            }
        }
        result = deep_merge(base, override)
        assert 'key1' not in result['level1']['level2']['level3']
        assert result['level1']['level2']['level3']['key2'] == 'value2'


class TestDeepMergeImmutability:
    """Test that input dictionaries are not mutated."""

    def test_base_immutability_simple(self):
        """AC5: Base dict should not be mutated in simple merge."""
        base = {'a': 1, 'b': 2}
        base_copy = deepcopy(base)
        override = {'a': 10}
        deep_merge(base, override)
        assert base == base_copy

    def test_base_immutability_nested(self):
        """AC5: Base dict should not be mutated with nested dicts."""
        base = {'config': {'host': 'localhost', 'port': 5432}}
        base_copy = deepcopy(base)
        override = {'config': {'host': 'remote.com'}}
        deep_merge(base, override)
        assert base == base_copy

    def test_base_immutability_with_none(self):
        """AC5: Base dict should not be mutated when override has None."""
        base = {'a': 1, 'b': 2}
        base_copy = deepcopy(base)
        override = {'a': None}
        deep_merge(base, override)
        assert base == base_copy

    def test_override_immutability_simple(self):
        """AC5: Override dict should not be mutated in simple merge."""
        base = {'a': 1}
        override = {'b': 2, 'c': 3}
        override_copy = deepcopy(override)
        deep_merge(base, override)
        assert override == override_copy

    def test_override_immutability_nested(self):
        """AC5: Override dict should not be mutated with nested dicts."""
        base = {'x': 1}
        override = {'config': {'debug': True, 'level': 'info'}}
        override_copy = deepcopy(override)
        deep_merge(base, override)
        assert override == override_copy

    def test_nested_list_immutability_base(self):
        """AC5: Base lists should not be mutated during merge."""
        base = {'items': [1, 2, 3]}
        base_copy = deepcopy(base)
        override = {'items': [4, 5]}
        deep_merge(base, override)
        assert base == base_copy

    def test_nested_list_immutability_override(self):
        """AC5: Override lists should not be mutated during merge."""
        base = {}
        override = {'items': [1, 2, 3]}
        override_copy = deepcopy(override)
        deep_merge(base, override)
        assert override == override_copy

    def test_deepcopy_verification(self):
        """AC5: Result should be independent copy, not reference."""
        base = {'data': {'value': 10}}
        override = {}
        result = deep_merge(base, override)
        # Modify result deeply
        result['data']['value'] = 999
        # Base should be unchanged
        assert base['data']['value'] == 10


class TestDeepMergeEmptyCases:
    """Test handling of empty dictionaries."""

    def test_empty_base_with_override(self):
        """AC6: Empty base dict should result in override values."""
        base = {}
        override = {'a': 1, 'b': 2, 'c': {'d': 3}}
        result = deep_merge(base, override)
        assert result == {'a': 1, 'b': 2, 'c': {'d': 3}}

    def test_empty_base_empty_override(self):
        """AC6 & AC8: Both empty should result in empty dict."""
        base = {}
        override = {}
        result = deep_merge(base, override)
        assert result == {}

    def test_empty_override_with_base(self):
        """AC7: Empty override dict should preserve base values."""
        base = {'a': 1, 'b': 2, 'c': {'d': 3}}
        override = {}
        result = deep_merge(base, override)
        assert result == {'a': 1, 'b': 2, 'c': {'d': 3}}

    def test_both_empty(self):
        """AC8: Both empty dicts should return empty result."""
        base = {}
        override = {}
        result = deep_merge(base, override)
        assert result == {}
        assert isinstance(result, dict)

    def test_empty_nested_dict_in_override(self):
        """AC2 & AC6: Empty dict in override should merge (not replace)."""
        base = {'config': {'a': 1, 'b': 2}}
        override = {'config': {}}
        result = deep_merge(base, override)
        assert result['config'] == {'a': 1, 'b': 2}


class TestDeepMergeDeeplyNested:
    """Test deeply nested dictionary structures."""

    def test_deeply_nested_3_levels(self):
        """AC9: Three-level nested structure should merge correctly."""
        base = {
            'l1': {
                'l2': {
                    'l3': {'key': 'value'}
                }
            }
        }
        override = {
            'l1': {
                'l2': {
                    'l3': {'key': 'new_value'}
                }
            }
        }
        result = deep_merge(base, override)
        assert result['l1']['l2']['l3']['key'] == 'new_value'

    def test_deeply_nested_5_levels(self):
        """AC9: Five-level nested structure should merge correctly."""
        base = {
            'a': {'b': {'c': {'d': {'e': {'value': 1}}}}}
        }
        override = {
            'a': {'b': {'c': {'d': {'e': {'value': 2}}}}}
        }
        result = deep_merge(base, override)
        assert result['a']['b']['c']['d']['e']['value'] == 2

    def test_deeply_nested_mixed_merge(self):
        """AC9: Deep nesting with mixed operations."""
        base = {
            'services': {
                'api': {
                    'endpoints': {
                        'users': {
                            'get': True,
                            'delete': True
                        }
                    }
                }
            }
        }
        override = {
            'services': {
                'api': {
                    'endpoints': {
                        'users': {
                            'delete': False
                        }
                    }
                }
            }
        }
        result = deep_merge(base, override)
        assert result['services']['api']['endpoints']['users']['get'] is True
        assert result['services']['api']['endpoints']['users']['delete'] is False

    def test_deeply_nested_with_none(self):
        """AC9 & AC4: Deep nesting with None deletion."""
        base = {
            'a': {'b': {'c': {'d': {'e': 1, 'f': 2}}}}
        }
        override = {
            'a': {'b': {'c': {'d': {'e': None}}}}
        }
        result = deep_merge(base, override)
        assert 'e' not in result['a']['b']['c']['d']
        assert result['a']['b']['c']['d']['f'] == 2


class TestDeepMergeTypeConversions:
    """Test mixed type handling at same keys."""

    def test_scalar_to_dict(self):
        """AC10: Scalar in base replaced by dict in override."""
        base = {'value': 'string'}
        override = {'value': {'nested': 'dict'}}
        result = deep_merge(base, override)
        assert result['value'] == {'nested': 'dict'}

    def test_dict_to_scalar(self):
        """AC10: Dict in base replaced by scalar in override."""
        base = {'value': {'nested': 'dict'}}
        override = {'value': 'string'}
        result = deep_merge(base, override)
        assert result['value'] == 'string'

    def test_dict_to_list(self):
        """AC10: Dict in base replaced by list in override."""
        base = {'value': {'key': 'val'}}
        override = {'value': [1, 2, 3]}
        result = deep_merge(base, override)
        assert result['value'] == [1, 2, 3]

    def test_list_to_dict(self):
        """AC10: List in base replaced by dict in override."""
        base = {'value': [1, 2, 3]}
        override = {'value': {'key': 'val'}}
        result = deep_merge(base, override)
        assert result['value'] == {'key': 'val'}

    def test_list_to_scalar(self):
        """AC10: List in base replaced by scalar in override."""
        base = {'value': [1, 2, 3]}
        override = {'value': 'string'}
        result = deep_merge(base, override)
        assert result['value'] == 'string'

    def test_scalar_to_list(self):
        """AC10: Scalar in base replaced by list in override."""
        base = {'value': 'string'}
        override = {'value': [1, 2, 3]}
        result = deep_merge(base, override)
        assert result['value'] == [1, 2, 3]

    def test_type_mismatch_preservation(self):
        """AC10: Type mismatches should replace entirely, not merge."""
        base = {
            'int_val': 10,
            'str_val': 'text',
            'list_val': [1, 2],
            'dict_val': {'key': 'value'}
        }
        override = {
            'int_val': 'now_string',
            'str_val': 99,
            'list_val': {'now': 'dict'},
            'dict_val': ['now', 'list']
        }
        result = deep_merge(base, override)
        assert result['int_val'] == 'now_string'
        assert result['str_val'] == 99
        assert result['list_val'] == {'now': 'dict'}
        assert result['dict_val'] == ['now', 'list']

    def test_nested_type_conversion(self):
        """AC10: Type conversions should work in nested structures."""
        base = {
            'config': {
                'setting1': {'nested': 'value'},
                'setting2': [1, 2, 3]
            }
        }
        override = {
            'config': {
                'setting1': 'simple_value',
                'setting2': {'complex': 'object'}
            }
        }
        result = deep_merge(base, override)
        assert result['config']['setting1'] == 'simple_value'
        assert result['config']['setting2'] == {'complex': 'object'}


class TestDeepMergeComplexScenarios:
    """Test complex integration scenarios and edge cases."""

    def test_comprehensive_real_world_config(self):
        """Complex real-world configuration merge scenario."""
        base = {
            'database': {
                'primary': {
                    'host': 'localhost',
                    'port': 5432,
                    'ssl': False
                },
                'replica': None,
                'backup_enabled': True
            },
            'api': {
                'timeout': 30,
                'retries': 3,
                'endpoints': ['v1', 'v2']
            }
        }
        override = {
            'database': {
                'primary': {
                    'host': 'prod.example.com',
                    'ssl': True
                },
                'replica': {
                    'host': 'replica.example.com',
                    'port': 5432
                },
                'backup_enabled': None
            },
            'api': {
                'timeout': 60,
                'endpoints': ['v3']
            }
        }
        result = deep_merge(base, override)

        # Verify complex merge
        assert result['database']['primary']['host'] == 'prod.example.com'
        assert result['database']['primary']['port'] == 5432
        assert result['database']['primary']['ssl'] is True
        assert result['database']['replica'] == {'host': 'replica.example.com', 'port': 5432}
        assert 'backup_enabled' not in result['database']
        assert result['api']['timeout'] == 60
        assert result['api']['retries'] == 3
        assert result['api']['endpoints'] == ['v3']

    def test_special_characters_in_keys(self):
        """Edge case: Keys with special characters should work."""
        base = {
            'key-with-dash': 1,
            'key_with_underscore': 2,
            'key.with.dot': 3,
            'key with space': 4
        }
        override = {
            'key-with-dash': 10,
            'key.with.dot': 30
        }
        result = deep_merge(base, override)
        assert result['key-with-dash'] == 10
        assert result['key_with_underscore'] == 2
        assert result['key.with.dot'] == 30
        assert result['key with space'] == 4

    def test_numeric_string_keys(self):
        """Edge case: Numeric strings as keys should work."""
        base = {
            '1': 'one',
            '2': 'two',
            '3': 'three'
        }
        override = {
            '2': 'TWO',
            '4': 'four'
        }
        result = deep_merge(base, override)
        assert result['1'] == 'one'
        assert result['2'] == 'TWO'
        assert result['3'] == 'three'
        assert result['4'] == 'four'

    def test_unicode_string_values(self):
        """Edge case: Unicode characters in values should work."""
        base = {'greeting': 'Hello'}
        override = {'greeting': '你好世界', 'emoji': '🚀'}
        result = deep_merge(base, override)
        assert result['greeting'] == '你好世界'
        assert result['emoji'] == '🚀'

    def test_negative_numbers(self):
        """Edge case: Negative numbers should work correctly."""
        base = {'value': -10}
        override = {'value': -50}
        result = deep_merge(base, override)
        assert result['value'] == -50

    def test_zero_values(self):
        """Edge case: Zero should override any non-zero value."""
        base = {'int': 100, 'float': 3.14}
        override = {'int': 0, 'float': 0.0}
        result = deep_merge(base, override)
        assert result['int'] == 0
        assert result['float'] == 0.0

    def test_boolean_false_override_true(self):
        """Edge case: False should override True."""
        base = {'flag': True}
        override = {'flag': False}
        result = deep_merge(base, override)
        assert result['flag'] is False

    def test_boolean_true_override_false(self):
        """Edge case: True should override False."""
        base = {'flag': False}
        override = {'flag': True}
        result = deep_merge(base, override)
        assert result['flag'] is True

    def test_multiple_consecutive_merges(self):
        """Integration: Chained merges should work correctly."""
        base = {'a': 1, 'b': 2}
        override1 = {'b': 20, 'c': 3}
        override2 = {'c': 30, 'd': 4}

        result1 = deep_merge(base, override1)
        result2 = deep_merge(result1, override2)

        assert result2 == {'a': 1, 'b': 20, 'c': 30, 'd': 4}

    def test_large_nested_structure(self):
        """Integration: Large nested structure should merge efficiently."""
        base = {
            f'key{i}': {
                f'subkey{j}': j for j in range(10)
            } for i in range(10)
        }
        override = {
            'key0': {'subkey0': 999},
            'key5': {'subkey5': 888}
        }
        result = deep_merge(base, override)

        assert result['key0']['subkey0'] == 999
        assert result['key0']['subkey1'] == 1
        assert result['key5']['subkey5'] == 888
        assert result['key5']['subkey0'] == 0
        assert result['key9']['subkey9'] == 9


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
