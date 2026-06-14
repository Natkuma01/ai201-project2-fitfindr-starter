from unittest.mock import patch, MagicMock  # help to test without API keys, use mock data to test
import pytest
from tools import search_listings, suggest_outfit, create_fit_card

# ─── Happy Path Tests ─────────────────────────────────────────────────────────
# search_listings function
def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

# suggest_outfit function
def test_suggest_outfit_happy_path():
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop", "category": "tops"}
    wardrobe = {"items": [{"name": "Blue Jeans", "category": "bottoms", "colors": ["blue"], "style_tags": ["casual"]}]}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "Pair the Vintage Tee with Blue Jeans."
    
    with patch("tools._get_groq_client", return_value=mock_client):
        res = suggest_outfit(new_item, wardrobe)
        assert res == "Pair the Vintage Tee with Blue Jeans."

# create_fit_card function
def test_create_fit_card_happy_path():
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop"}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "Just scored this Vintage Tee for $20.00 on depop!"
    
    with patch("tools._get_groq_client", return_value=mock_client):
        res = create_fit_card("Pair it with jeans.", new_item)
        assert "Vintage Tee" in res
        assert "$20.00" in res
        assert "depop" in res


# ─── search_listings Failure Modes ───────────────────────────────────────────

def test_search_listings_invalid_price():
    """Failure Mode: Handle missing or invalid prices in the listings dataset gracefully."""
    mock_listings = [
        {"title": "Valid Tee", "price": 20.0, "size": "M", "colors": ["red"], "style_tags": ["vintage"]},
        {"title": "Invalid Price Tee", "price": "not-a-float", "size": "M", "colors": ["red"], "style_tags": ["vintage"]},
    ]
    with patch("tools.load_listings", return_value=mock_listings):
        # Searching under $25
        results = search_listings("tee", size="M", max_price=25.0)
        # Should only return the one with valid price <= 25, others should be skipped
        assert len(results) == 1
        assert results[0]["title"] == "Valid Tee"


def test_search_listings_missing_price():
    """Failure Mode: If a price is missing (None), it is not filtered out by max_price (current tools.py behavior)."""
    mock_listings = [
        {"title": "Missing Price Tee", "size": "M", "colors": ["red"], "style_tags": ["vintage"]},
    ]
    with patch("tools.load_listings", return_value=mock_listings):
        results = search_listings("tee", size="M", max_price=25.0)
        assert len(results) == 1
        assert results[0]["title"] == "Missing Price Tee"



def test_search_listings_empty_description():
    """Failure Mode: An empty description query returns an empty list instead of raising an error."""
    results = search_listings("", size="M", max_price=25.0)
    assert results == []


def test_search_listings_empty_size():
    """Failure Mode: Empty size filter string should skip size filtering."""
    mock_listings = [
        {"title": "Tee M", "price": 20.0, "size": "M", "colors": ["red"], "style_tags": ["vintage"]},
        {"title": "Tee L", "price": 20.0, "size": "L", "colors": ["red"], "style_tags": ["vintage"]},
    ]
    with patch("tools.load_listings", return_value=mock_listings):
        # Empty string or whitespace-only size filter
        results = search_listings("tee", size=" ", max_price=25.0)
        assert len(results) == 2


def test_search_listings_negative_price():
    """Failure Mode: A negative max price yields no results since item prices are non-negative."""
    mock_listings = [
        {"title": "Tee M", "price": 20.0, "size": "M", "colors": ["red"], "style_tags": ["vintage"]},
    ]
    with patch("tools.load_listings", return_value=mock_listings):
        results = search_listings("tee", size=None, max_price=-10.0)
        assert results == []


# ─── suggest_outfit Failure Modes ─────────────────────────────────────────────

def test_suggest_outfit_missing_api_key():
    """Failure Mode: GROQ_API_KEY environment variable is not set, raising ValueError."""
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop", "category": "tops"}
    with patch("os.environ.get", return_value=None):
        with pytest.raises(ValueError, match="GROQ_API_KEY not set"):
            suggest_outfit(new_item, {"items": []})


def test_suggest_outfit_empty_wardrobe():
    """Failure Mode: Wardrobe has no items, falling back to general styling advice."""
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop", "category": "tops"}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "General Styling: Pair with baggy jeans."
    
    with patch("tools._get_groq_client", return_value=mock_client):
        res = suggest_outfit(new_item, {"items": []})
        assert "General Styling" in res
        
        # Verify the prompt instructs LLM about the empty wardrobe
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt = kwargs["messages"][1]["content"]
        assert "My wardrobe is currently empty" in prompt


def test_suggest_outfit_none_wardrobe():
    """Failure Mode: Wardrobe input is None, which should fall back to general styling advice."""
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop", "category": "tops"}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "General Styling: Pair with baggy jeans."
    
    with patch("tools._get_groq_client", return_value=mock_client):
        res = suggest_outfit(new_item, None)
        assert "General Styling" in res


def test_suggest_outfit_api_failure():
    """Failure Mode: Groq API call raises an exception, returning a friendly user-facing fallback error."""
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop", "category": "tops"}
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API Connection Error")
    
    with patch("tools._get_groq_client", return_value=mock_client):
        res = suggest_outfit(new_item, {"items": []})
        assert "Sorry — I couldn't generate outfit ideas right now." in res
        assert "OUTFIT_GEN_01" in res


def test_suggest_outfit_api_empty_response():
    """Failure Mode: Groq API returns empty content, returning a friendly user-facing fallback error."""
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop", "category": "tops"}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = "   "
    
    with patch("tools._get_groq_client", return_value=mock_client):
        res = suggest_outfit(new_item, {"items": []})
        assert "Sorry — I couldn't generate outfit ideas right now." in res
        assert "OUTFIT_GEN_01" in res


# ─── create_fit_card Failure Modes ────────────────────────────────────────────

def test_create_fit_card_missing_api_key():
    """Failure Mode: GROQ_API_KEY environment variable is not set, raising ValueError."""
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop"}
    with patch("os.environ.get", return_value=None):
        with pytest.raises(ValueError, match="GROQ_API_KEY not set"):
            create_fit_card("Outfit suggestion details", new_item)


def test_create_fit_card_empty_outfit():
    """Failure Mode: Outfit suggestion input is missing or empty, returning a descriptive error string directly."""
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop"}
    res1 = create_fit_card("", new_item)
    res2 = create_fit_card("   ", new_item)
    assert "Error: Cannot generate fit card because there are no outfit match with your item." in res1
    assert "Error: Cannot generate fit card because there are no outfit match with your item." in res2


def test_create_fit_card_invalid_item():
    """Failure Mode: Thrift item details are missing or invalid, returning a descriptive error string directly."""
    res1 = create_fit_card("Outfit suggestion", None)
    res2 = create_fit_card("Outfit suggestion", "not-a-dict")
    assert "Error: Cannot generate fit card because the thrift item details are missing." in res1
    assert "Error: Cannot generate fit card because the thrift item details are missing." in res2


def test_create_fit_card_api_failure():
    """Failure Mode: Groq API call fails, returning an error message string containing the exception info."""
    new_item = {"title": "Vintage Tee", "price": 20.0, "platform": "depop"}
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Groq rate limit hit")
    
    with patch("tools._get_groq_client", return_value=mock_client):
        res = create_fit_card("Pair with baggy jeans.", new_item)
        assert "Error: Failed to generate fit card caption due to an API error." in res
        assert "Groq rate limit hit" in res