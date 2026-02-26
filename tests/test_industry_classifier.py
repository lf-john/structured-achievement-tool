import pytest
from src.industry_classifier import classify_industry

@pytest.mark.parametrize("description, expected_industry", [
    ("A leading hospital chain providing excellent patient care.", "healthcare"),
    ("This clinic specializes in pediatric medical services.", "healthcare"),
    ("A pharmaceutical company developing new drugs.", "healthcare"),
    ("A major university with a focus on cutting-edge research.", "higher_ed"),
    ("This college offers a wide range of courses for students.", "higher_ed"),
    ("The professor leads a research group on campus.", "higher_ed"),
    ("An automotive factory with advanced assembly lines.", "manufacturing"),
    ("This company handles industrial production and logistics.", "manufacturing"),
    ("A key player in the supply chain for electronic components.", "manufacturing"),
    ("A software company developing mobile apps.", "other"),
    ("A retail business selling clothes.", "other"),
    ("A financial services firm.", "other"),
    ("This hospital is on a university campus, which has many students.", "higher_ed"),
])
def test_classify_industry(description, expected_industry):
    assert classify_industry(description) == expected_industry

def test_classify_industry_empty_string():
    assert classify_industry("") == "other"

def test_classify_industry_no_keywords():
    assert classify_industry("A generic business description.") == "other"
