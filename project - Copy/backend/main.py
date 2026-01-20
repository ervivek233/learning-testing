import os
import json
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

# --------------------------------------------------
# STEP 1: Load environment variables
# --------------------------------------------------
load_dotenv()

# --------------------------------------------------
# STEP 2: Load dataset ONCE at startup
# --------------------------------------------------
df = pd.read_csv("incidents.csv")
df["created_date"] = pd.to_datetime(df["created_date"])
df["closed_date"] = pd.to_datetime(df["closed_date"], errors="coerce")

# --------------------------------------------------
# STEP 3: Allowed columns (security + validation)
# --------------------------------------------------
ALLOWED_FILTERS = {
    "company",
    "status",
    "priority",
    "category",
    "assigned_to"
}

ALLOWED_GROUP_BY = {
    "company",
    "status",
    "priority",
    "category",
    "assigned_to",
    "month"
}



SYSTEM_PROMPT = """
You are a data assistant for an incident management system.

You MUST convert the user's question into a tool call.

Available filter fields:
- company
- status
- priority
- category
- assigned_to

Rules:
1. If the user asks to SHOW or LIST tickets, use filter_tickets.
2. If the user asks HOW MANY or TOTAL, use count_tickets.
3. ALWAYS populate the filters object when values are mentioned.
4. NEVER call a tool with empty arguments if filters are present in the question.
5. For months like January, February, etc., use date_filter with month number (1–12).

Return ONLY a tool call. Do not answer in text.
"""

# --------------------------------------------------
# STEP 4: Minimal deterministic tool functions
# --------------------------------------------------
def apply_filters(df_in, filters=None, date_filter=None):
    df_out = df_in.copy()

    if filters:
        for col, value in filters.items():
            if col in ALLOWED_FILTERS:
                df_out = df_out[
                    df_out[col].str.lower() == str(value).lower()
                ]

    if date_filter:
        if "month" in date_filter:
            df_out = df_out[
                df_out["created_date"].dt.month == int(date_filter["month"])
            ]
        if "year" in date_filter:
            df_out = df_out[
                df_out["created_date"].dt.year == int(date_filter["year"])
            ]

    return df_out


def count_tickets(filters: dict = None, date_filter: dict = None):
    filtered_df = apply_filters(df, filters, date_filter)
    return f"Total tickets: {len(filtered_df)}"


def filter_tickets(filters: dict = None, date_filter: dict = None):
    filtered_df = apply_filters(df, filters, date_filter)

    if filtered_df.empty:
        return "No tickets found matching the criteria."

    return filtered_df.to_dict(orient="records")


def group_by_tickets(group_by: str, filters: dict = None, date_filter: dict = None):
    if group_by not in ALLOWED_GROUP_BY:
        return "Invalid group_by column."

    filtered_df = apply_filters(df, filters, date_filter)

    if filtered_df.empty:
        return "No data available for grouping."

    if group_by == "month":
        result = filtered_df.groupby(filtered_df["created_date"].dt.month).size()
    else:
        result = filtered_df.groupby(group_by).size()

    return result.to_dict()

# --------------------------------------------------
# STEP 5: Tool definitions for LLM
# --------------------------------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "count_tickets",
            "description": "Count tickets using optional filters and date constraints",
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": { "type": "object" },
                    "date_filter": { "type": "object" }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "filter_tickets",
            "description": "Retrieve ticket records using filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "filters": { "type": "object" },
                    "date_filter": { "type": "object" }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "group_by_tickets",
            "description": "Group tickets by a column",
            "parameters": {
                "type": "object",
                "properties": {
                    "group_by": { "type": "string" },
                    "filters": { "type": "object" },
                    "date_filter": { "type": "object" }
                },
                "required": ["group_by"]
            }
        }
    }
]

# --------------------------------------------------
# STEP 6: Tool name → function map
# --------------------------------------------------
tool_map = {
    "count_tickets": count_tickets,
    "filter_tickets": filter_tickets,
    "group_by_tickets": group_by_tickets
}

# --------------------------------------------------
# STEP 7: FastAPI app setup
# --------------------------------------------------
app = FastAPI()
client = OpenAI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# STEP 8: Request model
# --------------------------------------------------
class ChatRequest(BaseModel):
    message: str

# --------------------------------------------------
# STEP 9: Chat endpoint
# --------------------------------------------------
@app.post("/chat")
def chat(req: ChatRequest):

    response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": req.message}
    ],
    tools=tools,
    tool_choice="auto"
)


    tool_calls = response.choices[0].message.tool_calls

    if not tool_calls:
        return {"reply": "I can answer questions related to incident tickets only."}

    tool_call = tool_calls[0]
    tool_name = tool_call.function.name
    args = json.loads(tool_call.function.arguments or "{}")

    result = tool_map[tool_name](**args)

    return {"reply": result}
