# PRD: AI Enquiry Agent for Supermarket

Nov 10, 2026 · @raneesh

## Overview

We will build an AI agent that answers shopper enquiries for the supermarket across WhatsApp, the website, in-store kiosks and phone, resolving routine questions instantly and handing complex ones to staff with full context.

**Problem.** Store staff and the helpdesk spend much of the day answering the same questions: is an item in stock, what does it cost, what is on offer, when does the store close, where is my order. Queues at the customer service desk and unanswered phone calls and messages lead to lost sales and lower satisfaction, especially at peak hours and on weekends.

**Vision.** A shopper gets an accurate, friendly answer in under 10 seconds, in their own language, at any hour. Staff are freed for work that needs a human, and managers see what customers actually ask for.

**Product summary**

- **What it is:** a conversational agent connected to live store data (inventory, prices, promotions, orders, loyalty).
- **Who it serves:** shoppers first; store staff and managers as secondary users.
- **What it is not:** it does not replace the cashier or the customer service desk; it triages and resolves, then escalates.

## Goals, non-goals and success metrics

The agent succeeds if it resolves most routine enquiries without a human while keeping answers accurate and customers satisfied. Targets below are starting proposals to be calibrated during the pilot.

**Goals**

- Resolve at least 70% of enquiries end to end without staff involvement by the end of the pilot.
- Answer in under 5 seconds for 90% of messages.
- Cut average customer service desk and phone call volume for routine questions by 40%.
- Reach a customer satisfaction (CSAT) score of at least 4.2 out of 5 on resolved chats.
- Give managers weekly insight into top questions, stock-out demand and complaint themes.

**Non-goals (v1)**

- Taking payments or processing refunds inside the chat.
- Running a full online ordering and delivery platform.
- Replacing the in-store staff or the grievance process.
- Voice-only call automation (phone is phase 3).

| Metric | Definition | Target |
| --- | --- | --- |
| Containment rate | Enquiries resolved without human handoff | ≥ 70% |
| Answer accuracy | Share of audited answers judged correct | ≥ 95% |
| First response time | Median time to first reply | < 5 s |
| CSAT | Post-chat rating, 1–5 | ≥ 4.2 |
| Handoff quality | Escalations that reach staff with full context | 100% |
| Wrong price or stock claims | Audited answers contradicting live data | < 1% |
