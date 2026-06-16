# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

## Tools Inventory


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

**What happens if it fails or returns nothing:** In case no suggestion message is empty the agent returns a predefined message with the selected item only, and continues the loop.

---

## Planning Loop

The agent needs to start by using the `search_listings` tool to search and find a valid clothing item based on the user's query. If found it continues and pass the information over to the next tool `suggest_outfit` along with user's `wardrobe` to generate a message about pairing options with the current wardrobe; otherwise, if no item was found the agent stops the loop at the end of the first tool sending a message stating the not found results and suggesting other options based on price or color.<br> In the case an empty wardrobe is passed over to the `suggest_outfit` tool the agent will default to recommend a second item from the listings that will pair with the original one. If a message is returned at this stage then is passed over to the next tool `create_fit_card` receiving `outfit_suggestion` message and `new_item` object information and creates a post-like message to be used later for social networks. If `outfit_suggestion` message is empty the tool will return a predifined "fit card" message including the item selected only.
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

### Architecture
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
             ▼                                                              ▼
             ■──► message empty  ──► "We've found this item from ... " ────►■ 
             │                                                              |
             ▼                                                              |
     Session: outfit_suggestion = "... outfit messsage ..." ◄───────────────┘ 
             │
             ▼
     create_fit_card(outfit_suggestion, selected_item)
             │
             ■──► message empty ──► "We've found this item from ... " ─────┐
             │                                                             |
             ▼                                                             |
     Session: fit_card: "... fit card message ..." ◄───────────────────────┘
             │
             ▼
       Return session
```

---

## State Management

A session is stored in a dict variable called `_new_session` with the following keys `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`, `outfit_suggestion`, `fit_card` and `error`. With this, each tool will store their respective results, so the next tool will pull the required information from a single source of truth.
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | "No matches were found. Are you interested in other items?" |
| suggest_outfit | Wardrobe is empty | "Pair {selected_item} with other items in the listings" |
| create_fit_card | Outfit input is missing or incomplete | "Just thrifted {selected_item} for {price} on {platform} — and the fit is everything. ♻️ #thrifted #secondhandstyle""  |

### Failure Example

- **No Results Match for search_listings**<br> 
Query: "designer ballgown size XXS under $5"<br>
session["selected_item"] = []<br>
session["error"] = No matches were found for "designer ballgown". Are you interested in other items? Try raising your budget above $5, or trying a different size than XXS, or describing the item differently or by color.<br>

---

## Spec Reflection

Spec was helpful to provide an overview of the whole agent and the specifics for each tool implemented within the agent. It provided a great detailed plan to help me define the entry point parsing the query in `description`, `price` and `size` for search_listing. It also provided a great start for the state management mechanism to be implemented.

At the beginining, I was planning to pass error messages to the state['error'] key for `outfit_suggestion` and `fit_card`; however, in order to give a continuation to the conversation between the user and the agent, the only error was raised if an item was not found. With the last two tools, instead of stoping the loop in the case of getting a outfit_suggestion empty message, a predefined message is  returned stating about the item selected, and a generic fit card as stated on the **Error Handling** section. 

---

## AI Usage

- AI prompt For **outfit_suggestion** tool: "Using Tool 2 block from planning.md I need you to implement the sugget_outfit tool, get first item (item_selected) resulted from search_listings and wardrobe dict using the get_example_wardrobe and get_empyt_wardrobe funtions from dataloader.py. For the suggest_outfit results, if wardrobe is not empy return a fashionista message suggestion to pair the selected_item with entries in the wardrobe, otherwise if wardrobe is empty return outfit suggestion using the selected_item with other entries in data\listings.json"
- AI Prompt For **fit_card** tool: "Using Tool 3 block from planning.md I need you to implement the create_fit_card tool. The tool will get the output from Tool 2 suggest_outfit output and the selected_item (first item from search_listings tool 1 function). The result is a 2-4 sentence string usable as Instagram/Tiktok caption, if outfit suggestion is empty or missing return an error message."

What I overrode was the code resulted form **fit_card** tool, the session error was removed and replaced with a predefined message and store it in session["fit_card"]. 

---
