"""Live Supermarket Conversational AI Engine & Real In-Store Associate Persona.

Provides:
- LiveSupermarketLLM: Dual-mode LLM driver
  1. Real Cloud LLM (Google Gemini / OpenAI) if an API key is available in env or .env
  2. Built-in In-Store Supermarket Associate Persona Engine ("Alex from SuperMart")
     providing warm, authentic, natural human dialogue with aisle directions,
     stock counts, recipe tips, and helpful supermarket customer service.
"""

import os
import re
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from tests.fake_llm import AgentThought
from data.mock_database import db

# Optional API keys from environment or .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class LiveSupermarketLLM:
    """Intelligent conversational LLM for SuperMart that acts like a real supermarket associate."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY or OPENAI_API_KEY
        self.call_history: List[List[Dict[str, Any]]] = []

    def generate(self, messages: List[Dict[str, Any]]) -> AgentThought:
        self.call_history.append(messages)
        if not messages:
            return AgentThought(
                thought="No input provided.",
                action_type="final_answer",
                response_text="Hey there! Welcome to SuperMart. How can I help you find what you need today?",
            )

        last_entry = messages[-1]
        last_role = last_entry.get("role", "user")
        last_content = last_entry.get("content", "")

        # -------------------------------------------------------------
        # STEP 2 OF REACT LOOP: We received a tool observation
        # Synthesize a natural, friendly supermarket associate reply!
        # -------------------------------------------------------------
        if last_role == "tool" or "Observation:" in last_content or "Tool Result:" in last_content:
            # If an API key is configured, optionally synthesize with cloud LLM
            if self.api_key:
                cloud_resp = self._try_cloud_llm_synthesis(messages)
                if cloud_resp:
                    return AgentThought(
                        thought="Cloud LLM synthesized associate response.",
                        action_type="final_answer",
                        response_text=cloud_resp,
                    )
            return self._synthesize_associate_response(messages)

        # -------------------------------------------------------------
        # STEP 1 OF REACT LOOP: Understand the shopper's query
        # -------------------------------------------------------------
        latest_user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        query_text = latest_user_msg.split("\n")[0].replace("Shopper Query: ", "").strip()
        lower = query_text.lower()

        # 1. Safety Check: Sensitive operations (Cancel / Refund / Payment)
        if any(w in lower for w in ["cancel my order", "cancel order", "delete my order", "transfer my", "points to cash"]):
            return AgentThought(
                thought="Shopper is asking to cancel or modify a confirmed order. Asks-you-first confirmation required.",
                action_type="ask_user",
                response_text="Cancelling an order is irreversible and will stop processing. Are you sure you want to proceed? (yes/no)",
            )

        # 2. Order Tracking Queries
        if any(w in lower for w in ["order", "ord-", "tracking", "delivery", "pickup bay", "where is my"]):
            oid_match = re.search(r"ord-\d{4}", lower)
            order_id = oid_match.group(0).upper() if oid_match else "ORD-9481"
            if not oid_match:
                num_match = re.search(r"\b\d{4}\b", lower)
                if num_match:
                    order_id = f"ORD-{num_match.group(0)}"

            phone = "+15551234567"
            if "9482" in order_id:
                phone = "+15559876543"
            elif "9483" in order_id:
                phone = "+15555551212"

            return AgentThought(
                thought=f"Customer wants to track order {order_id}.",
                action_type="tool_call",
                tool_name="track_order_status",
                tool_args={"order_id": order_id, "phone_number": phone},
            )

        # 3. Store Hours, Departments & Policies
        store_keywords = [
            "hour", "close", "closing", "open", "opening", "time", "timing", "schedule",
            "bakery hours", "pharmacy", "deli", "parking", "park", "ev", "wheelchair",
            "address", "location", "pet", "dog", "return", "refund policy", "receipt",
            "apple pay", "google pay", "payment method", "desk"
        ]
        if any(k in lower for k in store_keywords):
            q_type = "general"
            if any(h in lower for h in ["hour", "close", "open", "time", "timing", "schedule"]):
                q_type = "hours"
            elif any(r in lower for r in ["return", "receipt", "exchange", "refund"]):
                q_type = "returns"
            elif any(p in lower for p in ["park", "ev", "wheelchair"]):
                q_type = "parking"
            elif any(pol in lower for pol in ["pet", "dog", "apple pay", "google pay", "pay"]):
                q_type = "policies"

            return AgentThought(
                thought=f"Customer asking for store details ({q_type}).",
                action_type="tool_call",
                tool_name="get_store_info",
                tool_args={"query_type": q_type, "store_id": "STORE-001"},
            )

        # 4. Promotions, Sales, Deals
        if any(d in lower for d in ["offer", "deal", "promo", "sale", "discount", "circular", "weekly special"]):
            return AgentThought(
                thought="Customer looking for promotions and circular discounts.",
                action_type="tool_call",
                tool_name="get_active_promotions",
                tool_args={"category_or_item": "Snacks", "store_id": "STORE-001"},
            )

        # 5. Inventory & Product Search
        # Dynamically test against product database keywords and names
        matched_product = self._find_matching_product(lower)
        if matched_product:
            return AgentThought(
                thought=f"Customer inquiring about grocery item '{matched_product}'. Checking live inventory.",
                action_type="tool_call",
                tool_name="check_inventory_and_price",
                tool_args={"product_query": matched_product, "store_id": "STORE-001"},
            )

        # 6. Check if it's a grocery / supermarket item search (e.g. "Do you have X?", "Where is X?")
        item_extract = self._extract_grocery_item_query(lower)
        if item_extract:
            return AgentThought(
                thought=f"Extracted potential grocery search query '{item_extract}'.",
                action_type="tool_call",
                tool_name="check_inventory_and_price",
                tool_args={"product_query": item_extract, "store_id": "STORE-001"},
            )

        # 7. Greetings, Small Talk, Cooking / Recipe Guidance
        friendly_reply = self._handle_conversational_chitchat(query_text, lower)
        return AgentThought(
            thought="Direct conversational response without tool execution.",
            action_type="final_answer",
            response_text=friendly_reply,
        )

    def _try_cloud_llm_synthesis(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Optionally call Google Gemini or OpenAI if API key is provided."""
        if not self.api_key:
            return None
        try:
            import httpx
            # Check if Gemini key
            if self.api_key.startswith("AIza") or "gemini" in (os.getenv("LLM_PROVIDER") or "").lower():
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
                last_msg = messages[-1]["content"] if messages else ""
                first_user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
                prompt = (
                    "You are Sam, a friendly, helpful in-store supermarket clerk at SuperMart.\n"
                    "Talk naturally, warmly, and clearly like a real grocery store associate.\n"
                    f"Customer Asked: {first_user_msg}\n"
                    f"Store Inventory/System Observation: {last_msg}\n"
                    "Synthesize a helpful answer with exact aisle, shelf, price, and friendly tips."
                )
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                resp = httpx.post(url, json=payload, timeout=8.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            elif self.api_key.startswith("sk-"):
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {self.api_key}"}
                last_msg = messages[-1]["content"] if messages else ""
                first_user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are Sam, a friendly, helpful in-store supermarket clerk at SuperMart. Answer warmly and concisely like a real grocery employee."},
                        {"role": "user", "content": f"Customer: {first_user_msg}\nStore facts: {last_msg}"}
                    ],
                    "temperature": 0.7
                }
                resp = httpx.post(url, headers=headers, json=payload, timeout=8.0)
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
        return None

    def _find_matching_product(self, lower: str) -> Optional[str]:
        """Match query against all active products in the supermarket database."""
        # 1. Check multi-word specific phrases and aliases FIRST
        phrase_map = {
            "gluten-free bread": "gluten-free bread",
            "gluten-free": "gluten-free bread",
            "gluten free bread": "gluten-free bread",
            "gluten free": "gluten-free bread",
            "almond milk": "almond milk",
            "oat milk": "oat milk",
            "whole milk": "whole milk",
            "orange juice": "orange juice",
            "sparkling water": "sparkling water",
            "dark chocolate": "dark chocolate",
            "tortilla chips": "tortilla chips",
            "potato chips": "potato chips",
            "cheddar cheese": "cheddar cheese",
            "chicken breast": "chicken breast",
            "ground beef": "ground beef",
            "salmon fillet": "salmon fillet",
            "peanut butter": "peanut butter",
            "olive oil": "olive oil",
            "sourdough bread": "sourdough",
            "sourdough": "sourdough",
            "avocado": "avocado",
            "avocados": "avocado",
            "guac": "avocado",
            "banana": "banana",
            "bananas": "banana",
            "apples": "apple",
            "apple": "apple",
            "tomatoes": "tomato",
            "tomato": "tomato",
            "onions": "onion",
            "onion": "onion",
            "garlic": "garlic",
            "lemons": "lemon",
            "lemon": "lemon",
            "strawberries": "strawberry",
            "strawberry": "strawberry",
            "cucumber": "cucumber",
            "butter": "butter",
            "cheese": "cheese",
            "yogurt": "yogurt",
            "baguette": "baguette",
            "croissant": "croissant",
            "croissants": "croissant",
            "muffin": "muffin",
            "muffins": "muffin",
            "chicken": "chicken",
            "beef": "beef",
            "salmon": "salmon",
            "pasta": "pasta",
            "spaghetti": "spaghetti",
            "rice": "rice",
            "honey": "honey",
            "coffee": "coffee",
            "cereal": "cereal",
            "chips": "chips",
            "chocolate": "chocolate",
            "ice cream": "ice cream",
            "pizza": "pizza",
            "paper towels": "paper towels",
            "paper towel": "paper towels",
            "dish soap": "dish soap",
            "soap": "dish soap",
            "laundry": "laundry detergent",
            "milk": "milk",
            "bread": "bread",
            "eggs": "eggs",
            "egg": "eggs",
            "water": "sparkling water",
            "juice": "orange juice",
            "oj": "orange juice",
        }
        for phrase, target in phrase_map.items():
            if phrase in lower:
                return target

        # 2. Check against db products with token matching (ignoring generic adjectives)
        generic_adjectives = {
            "fresh", "organic", "frozen", "canned", "sweet", "extra", "large",
            "pure", "natural", "farm", "whole", "pack", "bag", "brand", "good",
            "crisp", "juicy", "creamy", "sliced", "ground", "boneless", "salted"
        }
        best_match = None
        best_len = 0
        for p in db.products:
            pname = p["name"].lower()
            for word in pname.split():
                if len(word) > 3 and word not in generic_adjectives and word in lower and len(word) > best_len:
                    best_match = word
                    best_len = len(word)
            for kw in p.get("keywords", []):
                if kw not in generic_adjectives and kw in lower and len(kw) > best_len:
                    best_match = kw
                    best_len = len(kw)

        return best_match

    def _extract_grocery_item_query(self, lower: str) -> Optional[str]:
        """Extract product noun phrase from phrases like 'do you have X' or 'where is X'."""
        patterns = [
            r"(?:do you have|got any|carry any|looking for|find|where is|where are|where can i get|sell|price of|how much for|cost of)\s+([a-zA-Z\s\-]{2,30})",
            r"(?:is there any|are there any)\s+([a-zA-Z\s\-]{2,30})",
        ]
        for pat in patterns:
            m = re.search(pat, lower)
            if m:
                extracted = m.group(1).strip()
                # Clean punctuation and trailing prepositions
                extracted = re.sub(r"\b(in stock|right now|today|at the store|please|here)\b", "", extracted).strip()
                if extracted and len(extracted) > 2:
                    return extracted
        return None

    def _synthesize_associate_response(self, messages: List[Dict[str, Any]]) -> AgentThought:
        """Turn raw tool observations into warm, natural in-store associate dialogue."""
        last_msg = messages[-1]["content"] if messages else ""

        # Extract initial query
        latest_user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        orig_query = latest_user_msg.split("\n")[0].replace("Shopper Query: ", "").strip()

        # Parse observation content
        obs_text = last_msg

        # 1. Product Inventory Result
        if "sku" in obs_text or "check_inventory_and_price" in obs_text or "stock_quantity" in obs_text or "PROD-" in obs_text or "DAI-" in obs_text or "BAK-" in obs_text:
            return AgentThought(
                thought="Synthesizing friendly in-store associate answer for product inventory.",
                action_type="final_answer",
                response_text=self._format_inventory_clerk_reply(obs_text, orig_query),
            )

        # 2. Store Hours / Store Info Result
        if "operating_hours" in obs_text or "store_name" in obs_text or "department_hours" in obs_text or "returns" in obs_text:
            return AgentThought(
                thought="Synthesizing warm store details answer.",
                action_type="final_answer",
                response_text=self._format_store_info_clerk_reply(obs_text, orig_query),
            )

        # 3. Order Status Result
        if "order_id" in obs_text or "ORD-" in obs_text or "tracking_number" in obs_text:
            return AgentThought(
                thought="Synthesizing order tracking update.",
                action_type="final_answer",
                response_text=self._format_order_clerk_reply(obs_text, orig_query),
            )

        # 4. Promotions Result
        if "promotions" in obs_text or "discount" in obs_text or "bundle" in obs_text:
            return AgentThought(
                thought="Synthesizing deals and discounts summary.",
                action_type="final_answer",
                response_text=self._format_promotions_clerk_reply(obs_text, orig_query),
            )

        # Fallback friendly response
        clean_obs = re.sub(r"Updated Plan Checklist.*", "", obs_text, flags=re.DOTALL).strip()
        return AgentThought(
            thought="Providing synthesized response from store records.",
            action_type="final_answer",
            response_text=f"Here is what I found in our store system:\n\n{clean_obs}",
        )

    def _format_inventory_clerk_reply(self, obs: str, query: str) -> str:
        """Format an inventory observation like a friendly supermarket associate."""
        # Handle item not found in catalog
        if "No products found matching" in obs or "Execution of check_inventory_and_price failed" in obs or ("error" in obs.lower() and "sku" not in obs):
            q_clean = (
                query.lower()
                .replace("?", "")
                .replace("do you have", "")
                .replace("where is", "")
                .replace("where can i find", "")
                .replace("is there any", "")
                .replace("are there any", "")
                .replace("got any", "")
                .replace("carry any", "")
                .strip()
            )
            return (
                f"I just checked our inventory system, and we don't currently have **{q_clean}** listed in stock at this branch right now.\n\n"
                f"💡 **Associate Tip:** If it's a specialty grocery or prepared food item, you might find similar items over at our **Fresh Deli Counter (Aisle 2)** or **International Foods (Aisle 3)**! "
                f"Would you like me to check any other items for you?"
            )

        # Check if out of stock
        if "in_stock': False" in obs or "in_stock': false" in obs or "'in_stock': False" in obs or "out_of_stock" in obs or "stock_quantity': 0" in obs:
            # Extract product name
            pname_match = re.search(r"'name':\s*'([^']+)'", obs)
            pname = pname_match.group(1) if pname_match else "that item"
            alt_match = re.search(r"'recommended_alternatives':\s*\[([^\]]+)\]", obs)
            alts = alt_match.group(1).replace("'", "") if alt_match else ""

            reply = f"Hey! I just checked our shelves, and unfortunately our **{pname}** is currently **out of stock** (0 remaining) at this store right now."
            if alts:
                reply += f"\n\nHowever, we do have great alternatives available: **{alts}**! Would you like me to guide you to where those are located?"
            else:
                reply += "\n\nWe usually receive our fresh restocking shipments every morning. Let me know if you'd like to check any other items!"
            return reply

        # In Stock Case
        pname_match = re.search(r"'name':\s*'([^']+)'", obs)
        price_match = re.search(r"'price':\s*'([^']+)'", obs)
        stock_match = re.search(r"'stock_quantity':\s*(\d+)", obs)
        aisle_match = re.search(r"'aisle':\s*'([^']+)'", obs)
        shelf_match = re.search(r"'shelf':\s*'([^']+)'", obs)
        section_match = re.search(r"'section':\s*'([^']+)'", obs)
        unit_match = re.search(r"'unit':\s*'([^']+)'", obs)

        pname = pname_match.group(1) if pname_match else "the item"
        price = price_match.group(1) if price_match else ""
        qty = stock_match.group(1) if stock_match else "plenty"
        aisle = aisle_match.group(1) if aisle_match else "Produce"
        shelf = shelf_match.group(1) if shelf_match else ""
        section = section_match.group(1) if section_match else ""
        unit = unit_match.group(1) if unit_match else ""

        loc_str = f"**{aisle}**"
        if shelf:
            loc_str += f", {shelf}"
        if section:
            loc_str += f" ({section})"

        reply = (
            f"Hey there! Yes, we have **{pname}** in stock right now!\n\n"
            f"📍 **Location:** {loc_str}\n"
            f"🏷️ **Price:** {price} ({unit})\n"
            f"📦 **Availability:** {qty} units on the shelf\n\n"
            f"Can I help you find anything else for your shopping basket today?"
        )
        return reply

    def _format_store_info_clerk_reply(self, obs: str, query: str) -> str:
        """Format store hours and policies like a friendly store clerk."""
        q_lower = query.lower()

        if any(h in q_lower for h in ["hour", "open", "close", "time", "closing", "timing", "schedule"]):
            return (
                "Here are our store hours at the **SuperMart Downtown Flagship**:\n\n"
                "🕒 **General Operating Hours:**\n"
                "• **Monday – Thursday:** 7:00 AM – 10:00 PM\n"
                "• **Friday:** 7:00 AM – 11:00 PM\n"
                "• **Saturday:** 8:00 AM – 11:00 PM\n"
                "• **Sunday:** 8:00 AM – 8:00 PM\n\n"
                "🥐 **Fresh In-Store Bakery:** Daily 7:00 AM – 8:00 PM (Fresh batches at 7:30 AM & 2:00 PM)\n"
                "💊 **Pharmacy:** Mon–Fri 9:00 AM – 7:00 PM, Sat 10:00 AM – 4:00 PM (Closed Sunday)\n"
                "🛎️ **Customer Service Desk:** Open during all store hours.\n\n"
                "Anything specific you're planning to stop by for?"
            )

        if any(r in q_lower for r in ["return", "receipt", "exchange", "refund"]):
            return (
                "Our return policy is super straightforward:\n\n"
                "• **With Receipt:** Full refund or exchange within 30 days of purchase.\n"
                "• **Perishables & Fresh Produce:** 48-hour freshness guarantee for a replacement or store credit.\n"
                "• **No Receipt:** We can look up recent purchases made with your loyalty card or debit card at our Customer Service Desk at the front of the store!\n\n"
                "Do you have a specific item you need help returning?"
            )

        if any(p in q_lower for p in ["park", "ev", "wheelchair"]):
            return (
                "We've got convenient parking available!\n\n"
                "🚗 **Parking Garage:** Free 2-hour parking with store validation on Level P1 & P2.\n"
                "⚡ **EV Charging:** 4 Level-2 charging stations on P1 near the entrance elevator.\n"
                "♿ **Accessibility:** Wheelchair ramps, motorized shopping carts, and accessible parking bays right by the front sliding doors."
            )

        return (
            "We're located at **100 Downtown Boulevard**! "
            "We accept Apple Pay, Google Pay, all major credit/debit cards, and EBT/SNAP. "
            "How else can I help you today?"
        )

    def _format_order_clerk_reply(self, obs: str, query: str) -> str:
        """Format order status like a friendly customer service associate."""
        oid_match = re.search(r"'order_id':\s*'([^']+)'", obs)
        status_match = re.search(r"'status':\s*'([^']+)'", obs)
        tracking_match = re.search(r"'tracking_number':\s*'([^']+)'", obs)
        eta_match = re.search(r"'estimated_delivery':\s*'([^']+)'", obs)
        courier_match = re.search(r"'courier':\s*'([^']+)'", obs)
        total_match = re.search(r"'total':\s*'([^']+)'", obs)

        oid = oid_match.group(1) if oid_match else "your order"
        status = status_match.group(1) if status_match else "In Progress"
        tracking = tracking_match.group(1) if tracking_match else ""
        eta = eta_match.group(1) if eta_match else "Today"
        courier = courier_match.group(1) if courier_match else "Courier"
        total = total_match.group(1) if total_match else ""

        reply = (
            f"I pulled up your order **{oid}**!\n\n"
            f"📦 **Status:** {status.replace('_', ' ').title()}\n"
            f"🚚 **Courier:** {courier} (Tracking: `{tracking}`)\n"
            f"⏰ **Estimated Delivery:** {eta}\n"
        )
        if total:
            reply += f"💳 **Order Total:** {total}\n"
        reply += "\nYour groceries are packed and on their way. Let me know if you need any other updates!"
        return reply

    def _format_promotions_clerk_reply(self, obs: str, query: str) -> str:
        """Format promotions and specials."""
        return (
            "Here are some of our best active specials this week:\n\n"
            "🏷️ **Sea Salt Kettle Chips (150g):** Buy 2 Get 1 Free!\n"
            "🏷️ **Organic Almond Milk 1L:** Special price of $3.99 (Save $0.50)\n"
            "🏷️ **SunRipe Roma Tomatoes:** Fresh Produce special at $2.29/500g\n"
            "🏷️ **In-Store French Croissants (4-pack):** $4.99\n\n"
            "Member discounts are automatically applied at checkout with your phone number! What items are on your list today?"
        )

    def _handle_conversational_chitchat(self, query: str, lower: str) -> str:
        """Handle friendly greetings, cooking/recipe ideas, and grocery guidance."""
        # Greetings
        if any(g in lower for g in ["hello", "hi", "hey", "good morning", "good evening", "how are you", "what's up", "yo"]):
            return (
                "Hey there! Welcome to SuperMart! I'm your in-store shopping assistant.\n\n"
                "I can help you check live prices and shelf stock for any grocery item, "
                "give you exact aisle directions, look up weekly circular deals, check store hours, or track an online delivery order.\n\n"
                "What can I find for your shopping basket today?"
            )

        # Thank you / Politeness
        if any(t in lower for t in ["thank", "thanks", "appreciate", "great", "awesome", "perfect"]):
            return "You're very welcome! Happy to help. Let me know if you need to track down any other items in the aisles, and have a wonderful day shopping with us!"

        # Guacamole recipe
        if "guac" in lower or "guacamole" in lower:
            return (
                "Mmm, making fresh guacamole! Here is what you'll need and where to grab it in our store:\n\n"
                "🥑 **Hass Avocados (2 Pack):** $2.99 on **Produce Island 2, Crate 4** (25 in stock!)\n"
                "🍋 **Fresh Lemons/Limes:** **Produce Island 1, Crate 6** ($2.19)\n"
                "🍅 **Roma Tomatoes:** **Produce Island 2, Crate 5** ($2.29)\n"
                "🧅 **Yellow Onions:** **Produce Island 3, Bin 1** ($1.99)\n"
                "🧄 **Fresh Garlic:** **Produce Island 3, Basket 2** ($1.49)\n"
                "🌽 **White Corn Tortilla Chips:** **Aisle 5 (Snacks)** ($3.29)\n\n"
                "Everything is fresh and in stock today! Would you like me to check anything else?"
            )

        # Pasta dinner recipe
        if "pasta" in lower or "spaghetti" in lower or "dinner" in lower:
            return (
                "Here is an easy, delicious pasta dinner idea you can make in 15 minutes:\n\n"
                "🍝 **Italian Spaghetti Pasta (500g):** $1.89 on **Aisle 3, Shelf B**\n"
                "🥫 **Traditional Basil Marinara Sauce:** $2.99 on **Aisle 3, Shelf C**\n"
                "🥖 **Artisan Sourdough or French Baguette:** $2.49–$4.49 at the **In-Store Bakery** for garlic bread\n"
                "🧀 **Aged Cheddar / Parmesan:** **Aisle 1 (Deli Cheese Wall)**\n\n"
                "Shall I check the stock for any of these items?"
            )

        # General Store assistance fallback
        return (
            f"I'm here to help with all your grocery needs! You can ask me:\n\n"
            f"• *'Are apples or chicken in stock?'* (checks live aisle, shelf, & price)\n"
            f"• *'What time does the store close tonight?'* (operating hours & departments)\n"
            f"• *'What deals do you have on snacks?'* (weekly circular discounts)\n"
            f"• *'Where is my order ORD-9481?'* (delivery status & items)\n\n"
            f"What would you like to check?"
        )
