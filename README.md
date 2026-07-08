# Custom AI Chatbot with Memory: Stateful Conversational Architecture

## 🚀 Project Overview
[cite_start]This repository contains **Project 1** for the **DecodeLabs Industrial Training Track (Batch: 2026)**[cite: 3, 4]. 

[cite_start]While Large Language Models (LLMs) operate natively as entirely stateless cloud completion engines [cite: 27, 28][cite_start], this project implements a production-grade **Stateful Architecture**[cite: 8]. [cite_start]By maintaining an active in-memory array to store conversation history and dynamically appending every transaction payload [cite: 9, 10][cite_start], this system successfully transforms a stateless endpoint into a fully contextual, live conversational web application[cite: 10, 14].

The frontend architecture was designed and delivered using the **Google Stitch MCP Server Engine**, while the backend control loops, server layers, and testing suites were autonomously orchestrated within the **Google Antigravity IDE**.

---

## 🛠️ Technical Core Architecture

The system coordinates data across a specialized local memory loop processing sequence:

1. [cite_start]**The Structural Validation Gate (The Caliper):** Evaluates all incoming client strings to block empty or whitespace-only transactions before they reach the GenAI API[cite: 84, 86]. [cite_start]This explicitly addresses a critical vulnerability where empty payloads return a `400 Bad Request` error, crashing local processing execution[cite: 84, 85].
2. [cite_start]**In-Memory History Loop:** Validated transactions are serialized into an SDK-compliant list of structured role-content objects[cite: 55, 75]. [cite_start]The data structure tracks inputs via a strict `role` parameter (`"user"` or `"model"`) and a localized `parts` array housing the components[cite: 76, 77, 79, 82].
3. [cite_start]**The Sliding Window Algorithm (FIFO Pruning):** As the historical array grows, network overhead scales aggressively[cite: 102]. [cite_start]The backend monitors array sizes [cite: 110] [cite_start]and applies First-In-First-Out (FIFO) pruning logic to drop the oldest message pairs [cite: 109][cite_start], safeguarding the application against token budget exhaustion and context window overflow crashes[cite: 103, 109].

---

## ⚙️ Tech Stack & Workspace Workflow

* **Frontend Design Engine:** Google Stitch UI Mapper (Broadcast via MCP Interface Tools)
* **Backend Application Server:** Python / Flask Micro-framework
* [cite_start]**Core Intelligence Provider:** Frontier LLM SDK Integration (Secure API-Key Handshake) [cite: 16]
* **Orchestration Environment:** Google Antigravity IDE (Dual Editor Canvas & Agent Manager Workspace)

---

## 🔬 System Audit: The Memory Exam

[cite_start]To verify conversational continuity and memory recall with absolute accuracy, the application successfully passes a rigorous three-phase system audit[cite: 11, 117]:

* [cite_start]**Phase 1: State Initialization:** Ingests user input `"My name is Vipin"`[cite: 118]. [cite_start]The engine creates a localized text entry, returns an acknowledgment string, and commits the state metadata to the list array[cite: 118].
* [cite_start]**Phase 2: Context Distraction:** Ingests user input `"Write a poem about tech"`[cite: 119]. [cite_start]This forces a massive, large-volume text generation sequence designed to stress-test token processing limits and distract the active context tracking window[cite: 120].
* [cite_start]**Phase 3: State Extraction:** Ingests user input `"What is my name?"`[cite: 121]. [cite_start]The system feeds the combined historical payload forward, bypassing the distraction text, and correctly extracts the user's name from the sliding window history, successfully outputting exactly `"Vipin"`[cite: 121, 134].

---

## 🗺️ Production Scaling Matrix (Enterprise Architecture Mapping)

[cite_start]While storing history arrays in local volatile RAM is ideal for local prototyping, it remains ephemeral for SaaS environments during application server restarts or redeployments[cite: 135, 136, 137]. [cite_start]This project maps out three production pathways to isolate state structures into persistent cloud databases linked to unique session IDs[cite: 139, 140]:

| Feature Pillar | [cite_start]Relational Persistence (PostgreSQL) [cite: 152] | [cite_start]NoSQL Cloud Engine (Cloud Firestore) [cite: 143] | [cite_start]Enterprise Scale (Firebase SQL Connect) [cite: 163] |
| :--- | :--- | :--- | :--- |
| **Data Schema Model** | [cite_start]Structured tables utilizing high-performance JSONB columns[cite: 152, 160]. | [cite_start]Schemaless, hierarchical collections with nested subcollections[cite: 145]. | [cite_start]Managed relational database schemas served via secure GraphQL nodes[cite: 164, 166]. |
| **Session Isolation & Key Scales** | [cite_start]Managed via primary/foreign keys[cite: 173]. [cite_start]Constrained by server disk space and connection pools[cite: 157, 173]. | [cite_start]Tied to unique document UUID flags[cite: 173]. [cite_start]Constrained by a **strict 1MB maximum document size limit**[cite: 147, 148]. | [cite_start]Structured through SQL row-level security policies and horizontal Cloud SQL scaling[cite: 164, 173]. |
| **Billing Model Metrics** | [cite_start]Fixed flat-rate infrastructure allocations[cite: 173]. | [cite_start]Pay-per-use dynamics charged per individual read/write operations[cite: 149, 173]. | [cite_start]Tiered transactional usage pricing tied directly to managed Cloud SQL processing matrices[cite: 173]. |

---

## 🛠️ Installation & Workspace Execution

### 1. Clone the Workspace Repository
```bash
git clone [https://github.com/yourusername/stateful-ai-chatbot-memory.git](https://github.com/yourusername/stateful-ai-chatbot-memory.git)
cd stateful-ai-chatbot-memory
