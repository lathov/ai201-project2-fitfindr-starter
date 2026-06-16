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

**What it does:** The search_listing tools will extract and take the clothing object, size and maximum price to pay to query the listing json model. It will get 2 to 3 choices selecting the top result. 
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): the clothing item description
- `size` (str): the clothing item size if applicable (not required)
- `max_price` (float): maximum price to pay for the clothing item

**What it returns:** It returns a list of matching listing dicts which includes the next clothing piece attribitues `title`, `description`, `size` (if applicable), `condition` and `platform`.
<!-- Describe the return value — what fields does a result contain? -->

**What happens if it fails or returns nothing:** The tool will return a message telling the user that no matches were found in the different platforms. Make other suggestions based on the original query and end the loop.
<!-- What should the agent do if no listings match? -->

---

### Tool 2: suggest_outfit

**What it does:** This is the fashionista agent, it will generate a message that creates customer's value from the desire to acquiere a new clothing item, by suggesting a mix and match based on the new item dict returned by the previous stage and the wardrobe saved on the user's profile
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): a dictionary representing a clothing piece with the following attribute keys: `id`, `title`, `description`, `size` (if applicable), `condition` and `platform`
- `wardrobe` (dict): a dictionary represnting the user's wardroble with the following attribute keys: `id`, `name`, `category`, `colors`, `style_tags` and `notes`

**What it returns:** It returns a suggestion message how to mix and match the new item returned with user's existing wardrobe, in a fashionista-like tone 
<!-- Describe the return value -->

**What happens if it fails or returns nothing:** wardrobe's arguments must not be empty and since LLM API's top-k, top-p and temperature must be configure to adhere to mix and match the new item based on the context of a exising wardrobe or empty wardrobe. If the message is empty, a predefined message is returned to the user about the item found and continue the loop.
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
---

### Tool 3: create_fit_card

**What it does:** This tool takes `new_fit` data and `suggestion` message to create a post message suitable for Social Networks such as instagram.
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit_suggestion` (string): message returned by `suggest_outfit`
- `new_item` (dict): dictionary with new item information

**What it returns:** It returns a Post-like fashion/eco-friendly message combining the information from the new item which includes the description, price and platform (for advertisement purposes) with the matching clothes from the user's current wardrobe.
<!-- Describe the return value -->

**What happens if it fails or returns nothing:** In case no suggestion message is empty the agent returns a predefined message is returned only with the selected item, and continues the loop. 
<!-- What should the agent do if the outfit data is incomplete? -->

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?** The agent needs to start by using the `search_listings` tool to search and find a valid clothing item based on the user's query. If found it continues and pass the information over to the next tool `suggest_outfit` along with user's `wardrobe` to generate a message about pairing options with the current wardrobe; otherwise, if no item was found the agent stops the loop at the end of the first tool sending a message stating the not found results and suggesting other options based on price or color.<br> In the case an empty wardrobe is passed over to the `suggest_outfit` tool the agent will default to recommend a second item from the listings that will pair with the original one. If a message is returned at this stage then is passed over to the next tool `create_fit_card` receiving `outfit_suggestion` message and `new_item` object information and creates a post-like message to be used later for social networks. If `outfit_suggestion` message is empty the tool will return a predifined "fit card" message including the item selected only.
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## Query Parsing

**How does the agent turn a free-text query into search parameters?** Before the loop calls `search_listings`, `run_agent` runs a regex/string-based parser (`_parse_query`) — no LLM call, so parsing is fast and deterministic. It extracts:

- **`max_price`**: only a number carrying a price cue (`$`, `under`, `below`, `less than`, `max`, `up to`) is treated as a budget. This prevents item numbers like "501 jeans" or decades like "90s" from being misread as a price.
- **`size`**: an explicit `size M` / `size M/L` phrase, otherwise a standalone size token (XS–XXL). Single-letter sizes are guarded against contractions so the "m" in "I'm" is not read as size M.
- **`description`**: the query with the price phrase, size phrase, and filler words ("show me", "looking for", etc.) stripped out — the remaining keywords are what `search_listings` scores against.

Chosen over an LLM parse because the field set is small and rule-based extraction is cheaper, instant, and easy to unit-test (see `agent_tests.py`).

---

## State Management

**How does information from one tool get passed to the next?** a session is stored in a dict variable called _new_session with the following keys `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`, `outfit_suggestion`, `fit_card` and `error`. With this, each tool will store their respective results, so the next tool will pull the required information from a single source of truth.
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | "No matches were found. Are you interested in other items?" |
| suggest_outfit | Wardrobe is empty | "Pair with other items in the listings" |
| create_fit_card | Outfit input is missing or incomplete | "Just thrifted {selected_item} for {price} on {platform} — and the fit is everything. ♻️ #thrifted #secondhandstyle""  |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```
User Query
    │
    ▼
Planning Loop
    │
    └──► search_listings(description, size, max_price)
             │
             ■──► results empty ──► [ERROR] "No Listing Found..."  ──► return
             │                         
         results[item, ...]            
             │
             ▼                  
          Session: selected_item=results[0]
             │
             ▼
     suggest_outfit(selected_item, wardrobe)
             │
             ■──► wardrobe empty ──► "Item will go ... other list item.." ──┐ 
             │                                                              |
             ▼                                                              │
             ■──► message empty  ──► "We've found this item from ... " ────►│ 
             │                                                              |
             ▼                                                              |
     Session: outfit_suggestion = "... outfit messsage ..." ◄───────────────┘ 
             │
             ▼
     create_fit_card(outfit_suggestion, selected_item)
             │
             ■── message empty  ──► "We've found this item from ... " ─────┐
             │                                                             |
             ▼                                                             |
     Session: fit_card: "... fit card message ..." ◄───────────────────────┘
             │
             ▼
       Return session
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:** 
- For `search_listings` tool, I will give Claude the Tool 1 block (inputs params, results, error handler) from `planning.md` and ask it to implement the  function using the `load_listings()` from `data_loader.py`. Before run it, I will check the generated code outputs the correct results based on the three filters passed, and how the empty result is handled. It will be tested with 3 queries.
- For `suggest_outfit` tool, I will give Claude the Tool 2 block (input params, results, error handler) from `planning.md` and ask it to implement the function using the first result from `search_listings` and both, the `get_example_wardrobe` and `get_empty_wardrobe` from `data_loader.py`. Before run it I will check the generated code outputs and the correct results based on two scenarios: selected_item + example_wardrobe and new_item + empty_wardrobe, and how the empty result is handled. It will be tested with 2 different queries.
- For `create_fit_card` tool, I will give Claude the Tool 3 block (suggestion and selected_item) from `planning.md` and ask it to implement the function using the results from previous tools. It will be tested with 2 different queries.

**Milestone 4 — Planning loop and state management:** 
- For the loop and state management I will give Claude the Complete Interaction (Step by Step) block along with the diagram from the Architecture block, and ask it to implement `run_agent()` method parsing the user query to extract item description, size and maximum price, and start the loop based on the step by step instructions; and it will be also asked to implement `_new_session()` function to keep the session state. Before run it it will check the generated code outputs and the correct results based on different scenarios item_found, not_found, sample_wardrobe, empty_wardrobe and how empty results are handle with all tools together. It will be tested with 2 different queries.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:** `search_listings("vintage graphic tee", max_price=30.0)` returns: 3 matching lists sorted by relevance. FitFndr picks the top result: "Graphic Tee — 2003 Tour Bootleg Style" — $24.0, Depop, Good Condition.
<!-- What does the agent do first? Which tool is called? With what input? -->

**Step 2:** `suggest_outfit(new_item=<graphic_tee_info>, wardrobe=<user_wardrobe>)` returns: "Pair this with your wide-leg khaki trousers and your chunky white sneakers for classic 2000s look"
<!-- What happens next? What was returned from step 1? What tool is called now? -->

**Step 3:** `create_fit_card(outfit=<suggestion>, new_item=<graphic_tee_info>)` returns: "Gave a second chance to this graphic tee for just $24 from Depop, goes incredible with my khakies and my white sneakers"
<!-- Continue until the full interaction is complete -->

**Final output to user:** `results_aggregation([<graphic_tee_info>, <suggestion>, <fit_card>])` result: "Give a second chance to this "Graphic Tee - 2003 Tour Bootleg Style" from Depop for just only $24, it will pair excellent with your khaki trousers and your white chunky sneakers; here is a cool post you can use in your favorite social network: "Gave a second chance to this graphic tee for just $24 from Depop, goes incredible with my khakies and my white sneakers""
<!-- What does the user actually see at the end? -->
