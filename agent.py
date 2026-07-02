"""
agent.py
Conversation logic + LLM calls + guardrails.
"""

import json
import os
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from groq import Groq

from retriever import Retriever
from prompts import (
    ROUTER_SYSTEM,
    CLARIFY_SYSTEM,
    RECOMMEND_SYSTEM,
    COMPARE_SYSTEM,
    REFUSE_SYSTEM,
    QUERY_EXPANSION_SYSTEM,
)

load_dotenv()

# Models
MODEL_FAST = "llama-3.1-8b-instant"       # for router + query expansion (fast, cheap)
MODEL_SMART = "llama-3.3-70b-versatile"    # for recommend + compare + refuse (better reasoning)

TURN_LIMIT = 8


class SHLAgent:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.retriever = Retriever()
        # Fast lookup by exact name
        self._by_name = {item["name"]: item for item in self.retriever.items}

    # ------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------

    def _chat_json(
        self,
        system: str,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 800,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Call Groq with JSON mode. Returns parsed dict or {} on failure."""
        full_messages = [{"role": "system", "content": system}] + messages
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=full_messages,
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = resp.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            print(f"[Agent] LLM error: {e}")
            return {}

    # ------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------

    def _route(self, messages: List[Dict[str, str]]) -> str:
        """Return action: CLARIFY | RECOMMEND | COMPARE | REFUSE"""
        turn_count = sum(1 for m in messages if m["role"] in ("user", "assistant"))
        # Give router a hint about turn budget
        router_msgs = messages + [{
            "role": "user",
            "content": f"[SYSTEM_HINT: This conversation is at turn {turn_count} of {TURN_LIMIT}. Decide action now.]"
        }]
        result = self._chat_json(ROUTER_SYSTEM, router_msgs, MODEL_FAST, max_tokens=100)
        action = result.get("action", "CLARIFY").upper()
        if action not in ("CLARIFY", "RECOMMEND", "COMPARE", "REFUSE"):
            action = "CLARIFY"
        print(f"[Agent] Route → {action} (reason: {result.get('reason', 'n/a')})")
        return action

    # ------------------------------------------------------------
    # Query expansion for retrieval
    # ------------------------------------------------------------

    def _expand_queries(self, messages: List[Dict[str, str]]) -> List[str]:
        """Turn the conversation into 2-4 focused search queries."""
        # Combine user turns into one context
        user_turns = "\n".join(
            m["content"] for m in messages if m["role"] == "user"
        )
        result = self._chat_json(
            QUERY_EXPANSION_SYSTEM,
            [{"role": "user", "content": user_turns}],
            MODEL_FAST,
            max_tokens=200,
        )
        queries = result.get("queries", [])
        if not queries:
            queries = [user_turns[:200]]  # fallback: raw user text
        print(f"[Agent] Queries: {queries}")
        return queries

    # ------------------------------------------------------------
    # Format candidate pool for LLM prompt
    # ------------------------------------------------------------

    def _format_pool(self, items: List[Dict[str, Any]]) -> str:
        lines = []
        for i, it in enumerate(items, 1):
            desc = it["description"][:200] if it["description"] else "(no description)"
            lines.append(
                f"{i}. NAME: {it['name']}\n"
                f"   test_type: {it['test_type']}\n"
                f"   keys: {', '.join(it['keys']) if it['keys'] else '-'}\n"
                f"   duration: {it['duration'] or '-'}\n"
                f"   description: {desc}"
            )
        return "\n\n".join(lines)

    # ------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------

    def _handle_clarify(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        # Just get a clarifying question — plain text, wrap in structure
        try:
            resp = self.client.chat.completions.create(
                model=MODEL_SMART,
                messages=[{"role": "system", "content": CLARIFY_SYSTEM}] + messages,
                max_tokens=150,
                temperature=0.3,
            )
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[Agent] Clarify error: {e}")
            reply = "Could you tell me a bit more about the role and seniority?"

        return {
            "reply": reply,
            "recommendations": [],
            "end_of_conversation": False,
        }

    def _handle_refuse(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        result = self._chat_json(REFUSE_SYSTEM, messages, MODEL_SMART, max_tokens=150)
        return {
            "reply": result.get(
                "reply",
                "I only help with SHL assessment selection. Tell me about the role you're hiring for."
            ),
            "recommendations": [],
            "end_of_conversation": False,
        }

    def _handle_recommend(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        # 1. Expand queries
        queries = self._expand_queries(messages)

        # 2. Retrieve top-15 candidates
        pool = self.retriever.search_multi(queries, k=15)
        if not pool:
            return {
                "reply": "I couldn't find matching assessments. Could you clarify the role?",
                "recommendations": [],
                "end_of_conversation": False,
            }

        # 3. Ask LLM to pick + reply
        pool_str = self._format_pool(pool)
        user_msg = (
            f"CANDIDATE POOL:\n{pool_str}\n\n"
            f"Now pick the best 1-10 items and write a natural reply. "
            f"Match `selected_names` EXACTLY to the pool's NAME field."
        )
        rec_messages = messages + [{"role": "user", "content": user_msg}]
        result = self._chat_json(RECOMMEND_SYSTEM, rec_messages, MODEL_SMART, max_tokens=800)

        reply = result.get("reply", "Here is a shortlist.")
        selected_names = result.get("selected_names", [])
        end_conv = bool(result.get("end_of_conversation", False))

        # 4. VALIDATE — only include items that exist in catalog
        recommendations = []
        seen = set()
        for name in selected_names:
            # Try exact match first
            item = self._by_name.get(name)
            if not item:
                # Case-insensitive fallback
                for real_name, real_item in self._by_name.items():
                    if real_name.lower() == name.lower():
                        item = real_item
                        break
            if item and item["name"] not in seen:
                recommendations.append({
                    "name": item["name"],
                    "url": item["url"],
                    "test_type": item["test_type"],
                })
                seen.add(item["name"])

        # Cap at 10
        recommendations = recommendations[:10]

        # If LLM returned nothing valid, fall back to top pool items
        if not recommendations and pool:
            print("[Agent] WARN: LLM returned no valid names, using top-5 pool")
            for it in pool[:5]:
                recommendations.append({
                    "name": it["name"],
                    "url": it["url"],
                    "test_type": it["test_type"],
                })

        return {
            "reply": reply,
            "recommendations": recommendations,
            "end_of_conversation": end_conv,
        }

    def _handle_compare(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        # Retrieve items mentioned in the query
        queries = self._expand_queries(messages)
        pool = self.retriever.search_multi(queries, k=8)
        pool_str = self._format_pool(pool)
        user_msg = f"CANDIDATE POOL:\n{pool_str}\n\nCompare as user asked."
        cmp_messages = messages + [{"role": "user", "content": user_msg}]
        result = self._chat_json(COMPARE_SYSTEM, cmp_messages, MODEL_SMART, max_tokens=600)

        return {
            "reply": result.get("reply", "I need more detail on what to compare."),
            "recommendations": [],
            "end_of_conversation": False,
        }

    # ------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------

    def chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Main entry. Takes conversation history, returns next agent turn."""
        if not messages:
            return {
                "reply": "Hi! Tell me about the role or assessment need, and I'll shortlist SHL products for you.",
                "recommendations": [],
                "end_of_conversation": False,
            }

        # Count turns — enforce budget
        turn_count = sum(1 for m in messages if m["role"] in ("user", "assistant"))
        if turn_count >= TURN_LIMIT:
            # Force final recommend
            print("[Agent] Turn budget reached — forcing RECOMMEND")
            result = self._handle_recommend(messages)
            result["end_of_conversation"] = True
            return result

        action = self._route(messages)

        if action == "REFUSE":
            return self._handle_refuse(messages)
        if action == "CLARIFY":
            return self._handle_clarify(messages)
        if action == "COMPARE":
            return self._handle_compare(messages)
        # default RECOMMEND
        return self._handle_recommend(messages)


# ------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------

if __name__ == "__main__":
    print("Initializing agent...")
    agent = SHLAgent()
    print("\n" + "=" * 60)
    print("Ready. Try some conversations.\n")

    # Test 1: vague
    print("TEST 1: Vague query")
    print("-" * 60)
    r = agent.chat([{"role": "user", "content": "We need a solution for senior leadership."}])
    print("Reply:", r["reply"])
    print("Recs:", r["recommendations"])
    print("End:", r["end_of_conversation"])

    # Test 2: with clarification
    print("\n\nTEST 2: With clarification (CXO)")
    print("-" * 60)
    r = agent.chat([
        {"role": "user", "content": "We need a solution for senior leadership."},
        {"role": "assistant", "content": "Who is this meant for?"},
        {"role": "user", "content": "CXOs and directors with 15+ years experience, for selection benchmarking."},
    ])
    print("Reply:", r["reply"])
    print("Recs:")
    for rec in r["recommendations"]:
        print(f"  - {rec['name']} ({rec['test_type']}) → {rec['url']}")
    print("End:", r["end_of_conversation"])

    # Test 3: off-topic
    print("\n\nTEST 3: Off-topic (should refuse)")
    print("-" * 60)
    r = agent.chat([{"role": "user", "content": "What's the weather like today?"}])
    print("Reply:", r["reply"])
    print("Recs:", r["recommendations"])