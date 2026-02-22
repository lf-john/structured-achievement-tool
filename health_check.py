#!/usr/bin/env python3
"""
SAT Health Check - Proves the full loop works
Tests the complete flow: Task classification -> Decomposition -> Verification
"""
import os
import sys
import tempfile
from src.core.story_agent import StoryAgent

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"✓ {text}")

def print_error(text):
    print(f"✗ {text}")

def test_classification(agent):
    """Test 1: Classification works"""
    print_header("TEST 1: Classification")

    test_cases = [
        ("Build a login feature", "development"),
        ("Fix the authentication bug", "debug"),
        ("Setup nginx reverse proxy", "config"),
        ("What is the current architecture?", "research"),
    ]

    for request, expected_type in test_cases:
        try:
            result = agent.classify(request)
            task_type = result.get("task_type")
            confidence = result.get("confidence", 0)

            if task_type == expected_type:
                print_success(f"'{request[:40]}...' → {task_type} (confidence: {confidence:.2f})")
            else:
                print_error(f"Expected {expected_type}, got {task_type}")
                return False
        except Exception as e:
            print_error(f"Classification failed: {e}")
            return False

    return True

def test_decomposition(agent):
    """Test 2: Decomposition works"""
    print_header("TEST 2: Decomposition")

    test_cases = [
        ("Create a user authentication system", "development"),
        ("Setup docker-compose for the app", "config"),
        ("Research best practices for API design", "research"),
    ]

    for request, task_type in test_cases:
        try:
            prd = agent.decompose(request, task_type)

            # Verify PRD structure
            assert "stories" in prd, "PRD missing 'stories'"
            assert isinstance(prd["stories"], list), "Stories must be a list"
            assert len(prd["stories"]) > 0, "PRD has no stories"

            # Verify each story has required fields
            for story in prd["stories"]:
                assert "id" in story, "Story missing 'id'"
                assert "title" in story, "Story missing 'title'"
                assert "type" in story, "Story missing 'type'"

            print_success(f"'{request[:40]}...' → {len(prd['stories'])} stories")
            for story in prd['stories'][:3]:  # Show first 3
                print(f"    - {story['id']}: {story['title']}")
            if len(prd['stories']) > 3:
                print(f"    ... and {len(prd['stories']) - 3} more")

        except AssertionError as e:
            print_error(f"Decomposition structure invalid: {e}")
            return False
        except Exception as e:
            print_error(f"Decomposition failed: {e}")
            return False

    return True

def test_full_loop(agent):
    """Test 3: Full loop integration"""
    print_header("TEST 3: Full Loop Integration")

    request = "Add a simple calculator function with tests"

    try:
        # Step 1: Classify
        print("Step 1: Classifying task...")
        classification = agent.classify(request)
        task_type = classification.get("task_type")
        print_success(f"Classified as: {task_type}")

        # Step 2: Decompose
        print("\nStep 2: Decomposing into stories...")
        prd = agent.decompose(request, task_type)
        print_success(f"Generated {len(prd['stories'])} stories")

        # Step 3: Verify structure
        print("\nStep 3: Verifying PRD structure...")
        assert "project" in prd, "Missing project info"
        assert "stories" in prd, "Missing stories"

        for idx, story in enumerate(prd['stories'], 1):
            assert "id" in story, f"Story {idx} missing id"
            assert "title" in story, f"Story {idx} missing title"
            assert "type" in story, f"Story {idx} missing type"
            assert "acceptanceCriteria" in story, f"Story {idx} missing AC"
            print(f"  ✓ Story {idx}: {story['id']} - {story['title']}")

        print_success("PRD structure is valid")

        return True

    except Exception as e:
        print_error(f"Full loop failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_logic_core_integration(agent):
    """Test 4: Logic Core is accessible"""
    print_header("TEST 4: Logic Core Integration")

    try:
        # Verify agent has logic core
        assert hasattr(agent, 'logic'), "Agent missing logic core"
        print_success("Agent has logic core")

        # Verify logic core has project path
        assert hasattr(agent.logic, 'p'), "Logic core missing project path"
        print_success(f"Logic core initialized with project: {agent.logic.p}")

        return True

    except Exception as e:
        print_error(f"Logic core check failed: {e}")
        return False

def test_templates_exist(agent):
    """Test 5: Templates are accessible"""
    print_header("TEST 5: Templates")

    try:
        # Verify template directory
        assert hasattr(agent, 'template_dir'), "Missing template_dir"
        template_dir = agent.template_dir

        required_templates = ['classify.md', 'decompose.md']
        for template in required_templates:
            template_path = os.path.join(template_dir, template)
            assert os.path.exists(template_path), f"Missing template: {template}"
            print_success(f"Template found: {template}")

        return True

    except Exception as e:
        print_error(f"Template check failed: {e}")
        return False

def main():
    print_header("SAT HEALTH CHECK")
    print("Testing the complete Structured Achievement Tool flow")

    # Initialize
    project_path = os.path.expanduser("~/projects/structured-achievement-tool")
    print(f"Project path: {project_path}\n")

    try:
        agent = StoryAgent(project_path=project_path)
        print_success("StoryAgent initialized successfully")
    except Exception as e:
        print_error(f"Failed to initialize StoryAgent: {e}")
        return 1

    # Run all tests
    tests = [
        ("Templates", test_templates_exist),
        ("Logic Core", test_logic_core_integration),
        ("Classification", test_classification),
        ("Decomposition", test_decomposition),
        ("Full Loop", test_full_loop),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func(agent)
            results.append((name, success))
        except Exception as e:
            print_error(f"Test {name} crashed: {e}")
            results.append((name, False))

    # Summary
    print_header("HEALTH CHECK SUMMARY")
    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "PASS" if success else "FAIL"
        symbol = "✓" if success else "✗"
        print(f"{symbol} {name}: {status}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All health checks PASSED! The SAT loop is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) FAILED. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
