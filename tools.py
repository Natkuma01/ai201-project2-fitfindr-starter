"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    # Load all listings with load_listings().
    listings = load_listings()

    # Filter by max_price and size (if provided).
    filtered = []
    for listing in listings:
        if max_price is not None:
            price_val = listing.get("price")
            if price_val is not None:
                try:
                    if float(price_val) > float(max_price):
                        continue
                except (ValueError, TypeError):
                    continue

        if size is not None and str(size).strip() != "":
            listing_size = str(listing.get("size", "")).strip().lower()
            query_size = str(size).strip().lower()
            pattern = r"\b" + re.escape(query_size) + r"\b"
            if not re.search(pattern, listing_size):
                continue

        filtered.append(listing)

    # Score each remaining listing by keyword overlap with `description`.
    stop_words = {"a", "an", "the", "for", "in", "with", "under", "size", "of", "and", "or", "looking", "to", "i", "im", "my"}
    query_words = [w for w in re.findall(r"[a-zA-Z0-9]+", description.lower()) if w not in stop_words]
    if not query_words:
        query_words = re.findall(r"[a-zA-Z0-9]+", description.lower())

    scored_listings = []
    for item in filtered:
        title_text = item.get("title", "") or ""
        desc_text = item.get("description", "") or ""
        category_text = item.get("category", "") or ""
        brand_text = item.get("brand", "") or ""
        tags_text = " ".join(item.get("style_tags", []) or [])
        colors_text = " ".join(item.get("colors", []) or [])

        combined_text = f"{title_text} {desc_text} {category_text} {brand_text} {tags_text} {colors_text}".lower()
        item_words = set(re.findall(r"[a-zA-Z0-9]+", combined_text))

        score = sum(1 for qw in query_words if qw in item_words)

        # Drop any listings with a score of 0 (no relevant matches).
        if score > 0:
            scored_listings.append((score, item))

    # Sort by score, highest first, and return the listing dicts.
    scored_listings.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored_listings]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    # Check whether wardrobe['items'] is empty.
    items = wardrobe.get("items") if isinstance(wardrobe, dict) else None
    
    # Extract the details of the new item for the prompt.
    item_title = new_item.get("title", "Unknown Item")
    item_desc = new_item.get("description", "")
    item_brand = new_item.get("brand") or "Unknown brand"
    item_price = new_item.get("price")
    item_price_text = f"${item_price:.2f}" if isinstance(item_price, (int, float)) else str(item_price)
    item_colors = ", ".join(new_item.get("colors", []))
    item_tags = ", ".join(new_item.get("style_tags", []))
    item_category = new_item.get("category", "Unknown category")
    
    item_details_str = (
        f"Title: {item_title}\n"
        f"Category: {item_category}\n"
        f"Brand: {item_brand}\n"
        f"Price: {item_price_text}\n"
        f"Colors: {item_colors}\n"
        f"Style Tags: {item_tags}\n"
        f"Description: {item_desc}"
    )

    client = _get_groq_client()

    # If empty: call the LLM with a prompt for general styling ideas.
    if not items:
        system_prompt = (
            "You are a professional fashion stylist. Provide stylish, practical, and highly aesthetic "
            "fashion advice. Speak directly to the user in a warm, encouraging tone."
        )
        user_prompt = f"""I am considering buying this thrifted item:
{item_details_str}

My wardrobe is currently empty. Please provide some general styling ideas and advice for this item.
Include:
1. What types or categories of items would pair well with it (e.g. colors, silhouettes, or specific pieces like baggy jeans or white sneakers).
2. The overall aesthetic vibe this item fits into (e.g. streetwear, minimal, grunge, cottagecore).
3. 1-2 styling combinations/ideas described generally.

Keep your response engaging, concise, and focused on style."""
    # If not empty: format the wardrobe items into a prompt and ask the LLM to suggest specific outfit combinations.
    else:
        wardrobe_list = []
        for idx, w_item in enumerate(items):
            w_name = w_item.get("name", "Unnamed Piece")
            w_cat = w_item.get("category", "Unknown category")
            w_colors = ", ".join(w_item.get("colors", []))
            w_tags = ", ".join(w_item.get("style_tags", []))
            w_notes = w_item.get("notes") or "None"
            wardrobe_list.append(
                f"- {w_name} (Category: {w_cat}, Colors: [{w_colors}], Style Tags: [{w_tags}], Notes: {w_notes})"
            )
        wardrobe_str = "\n".join(wardrobe_list)

        system_prompt = (
            "You are a professional fashion stylist. Suggest creative and stylish outfit combinations. "
            "Speak directly to the user in a helpful, warm, and creative tone."
        )
        user_prompt = f"""I am considering buying this thrifted item:
{item_details_str}

Here is my current wardrobe:
{wardrobe_str}

Please suggest 1-2 complete outfit combinations using this new thrifted item paired with specific, named items from my wardrobe.
Requirements:
1. Reference the wardrobe items by their exact names (e.g., 'Chunky white sneakers' or 'Baggy straight-leg jeans, dark wash') so I know which items you mean.
2. Explain the vibe of each outfit and why the pieces work together.
3. Keep the styling ideas distinct (e.g. one casual everyday fit and one slightly dressier or alternative fit, if the wardrobe allows).

Keep your response engaging, clear, and structured."""

    # Call the LLM and return the response.
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        outfit_suggestion = completion.choices[0].message.content.strip()
        if not outfit_suggestion:
            return (
                "Sorry — I couldn't generate outfit ideas right now. Try again in a moment, or "
                "tell me a little more about your wardrobe (for example: 'blue jeans, white sneakers'). "
                "If this keeps happening, report code OUTFIT_GEN_01 and we'll take a look."
            )
        return outfit_suggestion
    except Exception as e:
        print(f"Error generating outfit: {e}")
        return (
            "Sorry — I couldn't generate outfit ideas right now. Try again in a moment, or "
            "tell me a little more about your wardrobe (for example: 'blue jeans, white sneakers'). "
            "If this keeps happening, report code OUTFIT_GEN_01 and we'll take a look."
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Guard against an empty or whitespace-only outfit string.
    if not outfit or not outfit.strip():
        return (
            "⛔️ Error: Cannot generate fit card because there are no outfit match with your item. "
            "Suggestion: Try adjusting your search keywords to find other listings, or add more items to your wardrobe so we can create a styled combination."
        )
        
    if not new_item or not isinstance(new_item, dict):
        return (
            "⚠️ Error: Cannot generate fit card because the thrift item details are missing. 🛍️ "
            "Suggestion: Make sure that search_listings found a valid item and passed it to the agent."
        )

    client = _get_groq_client()

    # Extract the details of the thrifted item.
    item_title = new_item.get("title", "Unknown Item")
    item_price = new_item.get("price")
    item_price_text = f"${item_price:.2f}" if isinstance(item_price, (int, float)) else str(item_price)
    item_platform = new_item.get("platform", "Unknown Platform")

    system_prompt = (
        "You are a trendy, authentic fashion influencer writing outfit captions for TikTok and Instagram. "
        "Your style is conversational, casual, and relatable, using natural expressions rather than hard marketing copy. "
        "IMPORTANT: Always include highly relevant emojis to match the style vibe of the caption. "
        "For example: use ☀️ or 🏖️ for summer/sunny/warm vibes, ☕ or 💖 for casual/everyday/errand vibes, "
        "🍂 or 🧥 for autumn/winter vibes, 🎸 or 🖤 for grunge/alternative vibes, 🎀 for cottagecore, etc. "
        "Do not write introductory text, explanations, or quotes. Only output the caption."
    )
    
    # Build a prompt that gives the LLM the item details and the outfit.
    user_prompt = f"""Write a short, shareable outfit caption for this thrifted find.

Item Name: {item_title}
Price: {item_price_text}
Platform: {item_platform}
Outfit Suggestion:
{outfit}

Style Guidelines:
- Write exactly 2–4 sentences.
- Feel casual, authentic, and fun (like a real social media OOTD caption, not a product page).
- Naturally mention the item name ('{item_title}'), the price ('{item_price_text}'), and the platform ('{item_platform}') exactly once each.
- Capture the specific outfit vibe.
- Do NOT output extra text or notes, just the caption itself.
"""

    # Call the LLM and return the response.
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.9,
            max_tokens=250
        )
        caption = completion.choices[0].message.content.strip()
        if (caption.startswith('"') and caption.endswith('"')) or (caption.startswith("'") and caption.endswith("'")):
            caption = caption[1:-1].strip()
        return caption
    except Exception as e:
        print(f"Error generating fit card: {e}")
        return (
            f"❌ Error: Failed to generate fit card caption due to an API error. ({e}) ⚠️ "
            "Suggestion: Please check your internet connection or Groq API key configuration and try again."
        )

def assess_price(item: dict) -> str:
    """
    Compare the item's price against other items in the same category in the dataset.
    Returns a string assessment with reasoning.
    """
    category = item.get("category")
    price = item.get("price")
    if not category or price is None:
        return "No price assessment available."
    
    from utils.data_loader import load_listings
    listings = load_listings()
    
    # Find comparable items in the same category
    comparables = [x for x in listings if x.get("category") == category and x.get("price") is not None]
    if not comparables:
        return f"No other items in the '{category}' category to compare price."
        
    prices = [float(x["price"]) for x in comparables]
    avg_price = sum(prices) / len(prices)
    
    diff_pct = ((price - avg_price) / avg_price) * 100
    
    reasoning = f"Based on {len(comparables)} items in the '{category}' category (average price: ${avg_price:.2f})."
    
    if diff_pct < -5:
        return f"🔥 Good Deal: Priced at ${price:.2f}, which is {abs(diff_pct):.1f}% below the category average. {reasoning}"
    elif diff_pct > 5:
        return f"💎 Premium Price: Priced at ${price:.2f}, which is {diff_pct:.1f}% above the category average. {reasoning}"
    else:
        return f"⚖️ Fair Value: Priced at ${price:.2f}, which is close to the category average. {reasoning}"
