---
trigger: always_on
---

# PROJECT IDENTITY: Brotex R&D Intelligent Assistant
System: Internal RAG Chatbot for Brotex (Textile/R&D focus).
Stack: Python (FastAPI/RAG), Node.js (Express/BullMQ), React (Vite/Tailwind).

## 1. AI PERSONA & BEHAVIOR (CRITICAL)
- **Identity:** When asked "Who are you?", ALWAYS reply: "Tôi là trợ lý ảo AI phục vụ nội bộ công ty Brotex, chuyên hỗ trợ giải đáp các thắc mắc về bộ phận R&D và quy trình công ty."
- **Language Matching:** DETECT the user's language (Vietnamese, Chinese, English) and REPLY in the SAME language.
  - User: "Cotton là gì?" -> Bot: (Vietnamese)
  - User: "Cotton 是什么?" -> Bot: (Chinese)
- **Citations:**
  - Logic: The RAG engine MUST return source documents in the API response.
  - UI Display: DO NOT render raw citation tags (e.g., `[file.pdf:10]`) in the chat text. They should be hidden or shown only in a separate "Sources" UI element.

## 2. UI/UX STANDARDS (ChatGPT-Style)
- **Layout:** Dark Sidebar (Left) + Clean White Main Chat (Right).
- **Sidebar:** Contains "New Chat", "History" (grouped by date), "Settings".
- **Input:** Floating "Capsule" style at the bottom, not a full-width bar.
- **Feedback:** Must show dynamic status: "Queued" -> "Thinking..." -> "Typing".

## 3. PERFORMANCE RULES
- **Backend:** `rag.worker.js` concurrency MUST be `1`.
- **Optimization:** RAG retrieval `k` (top_k) should be optimized (e.g., k=3 instead of 5) to speed up generation if latency is high.