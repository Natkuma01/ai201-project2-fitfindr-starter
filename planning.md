# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches through all the mock thrift listings and finds items that match what the user is looking for. It filters by keywords, size, and price.

**Input parameters:**
- `description` (str): Keywords describing what the user wants (e.g., "vintage graphic tee")
- `size` (str or None): An optional size filter (e.g., "M" or "S/M") — case-insensitive. If None, all sizes match.
- `max_price` (float or None): An optional price ceiling. If None, all prices match.

**What it returns:**
A list of matching listing dicts sorted by best match first. Each listing includes: id, title, description, category, style_tags, size, condition, price, colors, brand, and platform. Returns an empty list if nothing matches.

**What happens if it fails or returns nothing:**
If no listings match, return an empty list and the agent stops the interaction. It tells the user no items were found instead of trying to suggest outfits with nothing.

---

### Tool 2: suggest_outfit

**What it does:**
Takes a thrifted item the user found and their existing wardrobe, then uses the LLM to suggest 1–2 complete outfit combinations. If the wardrobe is empty, it gives general styling advice instead.

**Input parameters:**
- `new_item` (dict): The thrift listing the user is considering — includes title, description, colors, category, style_tags, etc.
- `wardrobe` (dict): The user's wardrobe with an 'items' key containing their existing clothes. May be empty.

**What it returns:**
A non-empty string with outfit suggestions. Describes specific pieces from the wardrobe (if available) paired with the new item, or general styling advice if the wardrobe is empty.

**What happens if it fails or returns nothing:**
If the wardrobe has no items, the tool still returns general styling ideas (for example, "This tee would pair well with..."). If the LLM response is empty, return a clear, friendly user-facing message. Example: "Sorry — I couldn't generate outfit ideas right now. Try again in a moment, or tell me a little more about your wardrobe (for example: 'blue jeans, white sneakers'). If this keeps happening, report code OUTFIT_GEN_01 and we'll take a look." Internally log the raw LLM output and the request parameters for debugging, but never expose raw traces to the user; always offer a next step (retry, add details, or contact support, etc..)

---

### Tool 3: create_fit_card

**What it does:**
Takes the outfit suggestion and the thrifted item details, then uses the LLM to generate a short, casual 2–4 sentence caption suitable for Instagram or TikTok. The caption naturally mentions the item name, price, and where it came from.

**Input parameters:**
- `outfit` (str): The outfit suggestion text from suggest_outfit.
- `new_item` (dict): The thrift listing with title, price, platform, colors, style_tags, etc.

**What it returns:**
A 2–4 sentence string that reads like a real OOTD post. It includes the item name, price, and platform once each, sounds casual and authentic, and captures the outfit vibe.

**What happens if it fails or returns nothing:**
If the outfit string is empty or missing, return an error message instead of crashing. Do not raise an exception.

---

### Additional Tools (if any)

### Tool 4: parse_query

**What it does:**
Takes the user's natural language query and extracts the structured search parameters. It pulls out the item description, optional size, and optional price ceiling from the text.

**Input parameters:**
- `query` (str): The user's natural language request (e.g., "I'm looking for a vintage graphic tee under $30, size M")

**What it returns:**
A dict with three keys:
- `description` (str): Keywords for what the user wants
- `size` (str or None): Size filter, or None if not mentioned
- `max_price` (float or None): Price ceiling, or None if not mentioned

**What happens if it fails or returns nothing:**
If the query is empty or too vague to extract anything useful, return a dict with empty description and None for size and price. The agent can then ask the user to clarify.

---

## Planning Loop

**How does your agent decide which tool to call next?**
1. Start with user query -> call parse_query to extract description, size, and max_price, store in session["parsed"]

2. Call search_listings with parsed parameters -> get back search_results, store in session["search_results"]

3. Check if search_results is empty:
   - **If yes:** Set session["error"] to "No listings match your search" and return the session early. Stop here.
   - **If no:** Pick the best result (first one), set session["selected_item"] = results[0], and proceed.

4. Call suggest_outfit with selected_item and wardrobe -> get back outfit suggestion string, store in session["outfit_suggestion"]

5. Call create_fit_card with outfit_suggestion and selected_item -> get back caption string, store in session["fit_card"]

6. Return the completed session with all results filled in.

**The agent only skips to the end if search_listings finds nothing.**

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture
The actual diagram refers to the milestone2_archtecture.png in the root directory
```mermaid
flowchart TD
    %% Input
    Query["User input query & wardrobe choice"] --> UI["Gradio UI (app.py)"]
    
    %% UI Level check
    UI --> CheckQuery{Is query empty?}
    CheckQuery -->|Yes| ErrUI["[ERROR] 'Please enter a query...' &rarr; return"]
    CheckQuery -->|No| Loop["Planning Loop (run_agent)"]
    
    %% Step 1: Parse Query
    Loop --> T_Parse["parse_query(query)"]
    T_Parse --> S_Parsed["Session: parsed = {description, size, max_price}"]
    
    %% Step 2: Search Listings
    S_Parsed --> T_Search["search_listings(description, size, max_price)"]
    T_Search --> DbRead[("Load data/listings.json")]
    DbRead --> FilterScore["Filter by size & max_price<br/>Score description word overlap<br/>(Drop score = 0 matches)"]
    
    %% Step 3: Check Results
    FilterScore --> CheckResults{Are search results empty?}
    
    %% Error Path (No results found)
    CheckResults -->|Yes| Err["[ERROR] 'No listings found...' &rarr; return"]
    Err --> S_Error["Session: error = 'No listings...'"]
    
    %% Success Path
    CheckResults -->|No| S_Selected["Session: selected_item = results[0]"]
    
    %% Step 4: Suggest Outfit
    S_Selected --> T_Suggest["suggest_outfit(selected_item, wardrobe)"]
    T_Suggest --> CheckWardrobe{Is wardrobe empty?}
    
    CheckWardrobe -->|Yes| LLM_General["Prompt Groq:<br/>General styling advice"]
    CheckWardrobe -->|No| LLM_Wardrobe["Prompt Groq:<br/>Outfit combinations with wardrobe items"]
    
    LLM_General --> S_Outfit["Session: outfit_suggestion = '...'"]
    LLM_Wardrobe --> S_Outfit
    
    %% Step 5: Fit Card
    S_Outfit --> T_FitCard["create_fit_card(outfit_suggestion, new_item)"]
    T_FitCard --> CheckOutfit{Is outfit empty or missing?}
    
    CheckOutfit -->|Yes| Card_Error["Return error string directly<br/>'Error: Cannot generate fit card...'"]
    CheckOutfit -->|No| LLM_Caption["Prompt Groq:<br/>2-4 sentence OOTD caption"]
    
    Card_Error --> S_FitCard_Err["Session: fit_card = 'Error: Cannot...'"]
    LLM_Caption --> S_FitCard_Success["Session: fit_card = '...'"]
    
    %% Final Return
    S_FitCard_Success --> Ret["Return session / Display outputs"]
    S_FitCard_Err --> Ret
    S_Error -->|error path returns here| Ret
    ErrUI --> Ret

    %% Styling definitions
    classDef default fill:#F8FAFC,stroke:#1E293B,stroke-width:1.5px,color:#0F172A,font-family:monospace;
    classDef error fill:#FFF1F2,stroke:#E11D48,stroke-width:1.5px,color:#9F1239,font-family:monospace;
    classDef session fill:#F1F5F9,stroke:#475569,stroke-width:1px,color:#334155,font-family:monospace;
    classDef loop fill:#EFF6FF,stroke:#2563EB,stroke-width:1.5px,color:#1E40AF,font-family:monospace;
    classDef decision fill:#FFFDE7,stroke:#EAB308,stroke-width:1.5px,color:#854D0E,font-family:monospace;
    classDef external fill:#F5F3FF,stroke:#7C3AED,stroke-width:1.5px,color:#5B21B6,font-family:monospace;
    
    class Loop,UI loop;
    class Err,S_Error,Card_Error,ErrUI,S_FitCard_Err error;
    class S_Parsed,S_Selected,S_Outfit,S_FitCard_Success session;
    class CheckQuery,CheckResults,CheckWardrobe,CheckOutfit decision;
    class LLM_General,LLM_Wardrobe,LLM_Caption,DbRead,FilterScore,T_Parse,T_Search,T_Suggest,T_FitCard external;
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

**Tool 1 (parse_query):** I'll give Claude the Tool 4 spec from planning.md and ask it to implement the function using regex or string splitting to extract description, size, and price from the query. Before trusting it, I'll check that it handles queries with all three parameters, queries missing some parameters, and empty queries. Then I'll test it with 5 different query examples.

**Tool 2 (search_listings):** I'll give Claude the Tool 1 spec and ask it to implement the function using load_listings() from the data loader. Before running it, I'll verify that the generated code filters by all three parameters (description, size, max_price), handles case-insensitive size matching, and returns an empty list when nothing matches. Then I'll test it with 3 queries (one with results, one with no results, one with partial filters).

**Tool 3 (suggest_outfit):** I'll give Claude the Tool 2 spec and ask it to implement the function using the Groq LLM. I'll check that it calls the LLM with a well-formatted prompt, handles empty wardrobes by giving general styling advice, and always returns a non-empty string. Then I'll test it with both an empty wardrobe and a full wardrobe.

**Tool 4 (create_fit_card):** I'll give Claude the Tool 3 spec and ask it to implement the function using the Groq LLM with higher temperature for creativity. I'll verify that it guards against empty outfit strings, includes item name/price/platform naturally, and returns a 2–4 sentence caption. Then I'll test it with 2 different items to ensure the captions vary.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the full planning.md file and ask it to implement run_agent() in agent.py following the planning loop exactly as described. I'll ask it to call parse_query first, then search_listings, then handle the empty-results case, then call suggest_outfit and create_fit_card in sequence. I'll verify that the session dict is initialized correctly, populated with results after each step, and returned at the end. Then I'll test run_agent with both a successful query and a no-results query to confirm the error handling works.

---

## A Complete Interaction (Step by Step)
The FitFindr takes the user’s text query and chosen wardrobe, then turn that into a search, outfit idea, and fit card. 
The search_listings function from the tools.py is triggered first by the parsed query and returns matching thrift listings. If it finds nothing, the app stops and displays an error. If a listing is found, suggest_outfit is triggered next with the selected item and the user’s wardrobe to create styling ideas. 
Lastly, create_fit_card function makes a short caption from the outfit suggestion and item details.

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
Now the agent reads the query, pulls out the item description, size, and price, and calls the serach_listing function from the tools.py file, with that info.

**Step 2:**
The seach_listings function retrn matching thrift items, the agent picks the best one, and then calls the suggest_outfit function with that item plus the user's wardrobe

**Step 3:**
The suggest_outfit function returns styling ideas, and the agent calls the create_fit_card function with the outfit text and the selected item.

**Final output to user:**
The user gets the top listing, a simple outfit suggestion, and a short fit card caption.
