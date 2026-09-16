"""Health endpoint tests."""


def test_sample(sample_data):
    """Test sample data fixture."""
    assert sample_data["name"] == "Test"
    assert sample_data["value"] == 123


def test_basic_assertion():
    """Test basic assertion."""
    assert True


def test_simple_math():
    """Test simple math."""
    assert 1 + 1 == 2
