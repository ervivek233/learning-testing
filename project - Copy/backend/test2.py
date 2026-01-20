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


ALLOWED_FILTERS = {
    "company": "company",
    "status": "status",
    "priority": "priority",
    "category": "category",
    "assigned_to": "assigned_to"
}


# --------------------------------------------------
# STEP 3: Define deterministic tool functions
# --------------------------------------------------
def count_open_tickets():
    return f"Total open tickets: {len(df[df['status'] == 'open'])}"

def get_high_priority_tickets():
    high = df[df["priority"] == "high"]
    if high.empty:
        return "No high priority tickets found."
    return high[["ticket_id", "company", "status", "created_date"]].to_dict(
        orient="records"
    )

def tickets_this_month():
    now = datetime.now()
    filtered = df[
        (df["created_date"].dt.month == now.month) &
        (df["created_date"].dt.year == now.year)
    ]
    return f"Tickets created this month: {len(filtered)}"

def tickets_for_month(month: int):
    if month < 1 or month > 12:
        return "Invalid month. Please provide a month between 1 and 12."
    filtered = df[df["created_date"].dt.month == month]
    return f"Tickets created in month {month}: {len(filtered)}"

def filter_tickets(filters: dict):
    filtered_df = df.copy()

    for col, value in filters.items():
        if col in ALLOWED_FILTERS:
            filtered_df = filtered_df[
                filtered_df[ALLOWED_FILTERS[col]].str.lower() == value.lower()
            ]

    if filtered_df.empty:
        return "No tickets found matching the criteria."

    return filtered_df.to_dict(orient="records")


# --------------------------------------------------
# STEP 4: Tool definitions for LLM
# --------------------------------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "count_open_tickets",
            "description": "Get total number of open tickets",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_high_priority_tickets",
            "description": "Get all high priority tickets",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tickets_this_month",
            "description": "Get total tickets created this month",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tickets_for_month",
            "description": "Get tickets created in a specific month",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "integer"}
                },
                "required": ["month"]
            }
        }
    },
    {
  "type": "function",
  "function": {
    "name": "filter_tickets",
    "description": "Filter tickets by column values",
    "parameters": {
      "type": "object",
      "properties": {
        "filters": {
          "type": "object",
          "description": "Key-value pairs for filtering tickets"
        }
      },
      "required": ["filters"]
    }
  }
}

]

# --------------------------------------------------
# STEP 5: Tool name → Python function map
# --------------------------------------------------
tool_map = {
    "count_open_tickets": count_open_tickets,
    "get_high_priority_tickets": get_high_priority_tickets,
    "tickets_this_month": tickets_this_month,
    "tickets_for_month": tickets_for_month
}

# --------------------------------------------------
# STEP 6: FastAPI app setup
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
# STEP 7: Request model
# --------------------------------------------------
class ChatRequest(BaseModel):
    message: str

# --------------------------------------------------
# STEP 8: Chat endpoint
# --------------------------------------------------
@app.post("/chat")
def chat(req: ChatRequest):

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an assistant that answers ONLY questions related to "
                    "incident ticket data. You must select the correct tool to "
                    "answer the user's question."
                )
            },
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
