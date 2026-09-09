# CLAUDE.md — WhatsApp SACCO Customer Service / AI Member Companion

> **Authoritative Project Continuity Brief & Master Execution Tracker**  
> **Target AI Assistants**: Claude Code, Antigravity / Gemini, GitHub Copilot, Cursor  
> **Current Status**: **System 6 PASSED** (Baseline Established: 156 tests passing, 100% offline eval pass)  
> **Immediate Focus**: **System 7 — Member Identity / Profile + Secure Member-Data Routing**

---

## 1. System Overview & Core Mission

### 1.1 The Problem Being Solved
Kenyan Savings and Credit Cooperative Organizations (SACCOs) serve millions of members ranging from tech-savvy young professionals to older, rural, and less digitally literate individuals. Traditional customer care channels (in-person visits, long phone queues, complex portals) create major friction.

This project is a **WhatsApp-first AI Customer-Service and Financial-Education platform for SACCOs**, built initially as a hardened, demonstrable MVP and structured to scale to individual Kenyan SACCOs with verified policies, authenticated member accounts, and core banking integrations.

### 1.2 Core Value Proposition: "Not Just Another Chatbot"
This product is deliberately **not** an open-ended generic conversational bot. Its primary mission is:
> A SACCO AI member companion accessible directly through WhatsApp that answers member questions using approved/grounded SACCO knowledge, safely routes sensitive and account-specific requests, accommodates diverse digital literacy levels, and progressively personalizes financial education around each member's personal financial goals.

$$\text{Member} + \text{Profile/Context} + \text{Financial Goal} + \text{SACCO-Approved Knowledge} + \text{AI} \longrightarrow \textbf{Personalized Financial Support}$$

### 1.3 Accessibility & Language Goals
The assistant must serve:
* Younger first-time savers and older long-term members.
* Members with low digital or financial literacy.
* Multi-lingual queries in **English**, **Kiswahili**, and **mixed English/Kiswahili/Sheng**.
* **Tone & Register**: Short sentences, everyday words, zero unnecessary financial jargon, simple definitions for unavoidable terms, matching the user's register while maintaining trust and safety.

---

## 2. High-Level Architecture & Data Flow

```
                      +-------------------+
                      |   SACCO MEMBER    |
                      +---------+---------+
                                | (WhatsApp message)
                                v
                      +-------------------+
                      |   Twilio API      |
                      +---------+---------+
                                | (Webhook POST)
                                v
                      +-------------------+
                      | Cloudflare Tunnel |
                      +---------+---------+
                                |
                                v
                    +-----------------------+
                    |  FastAPI Application  |
                    | (/webhooks/whatsapp)  |
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    |    Request Router     |
                    |  (Flexible Triage)    |
                    +---+---------------+---+
                        |               |
     +------------------+               +------------------+
     |                                                     |
[General SACCO Question]               [Member-Data Request]  [Sensitive Issue / Dispute]
     |                                          |                      |
     v                                          v                      v
+------------------------+             +-----------------+   +--------------------+
| Query Reformulation &  |             | Future Member   |   | Human Support /    |
| Context Selection      |             | Data Service    |   | Staff Escalation   |
+-----------+------------+             | (Fast-Path)     |   +--------------------+
            |                          +--------+--------+
            v                                   |
+------------------------+                      |
| Qdrant Vector Store    |                      |
| (SACCO Knowledge RAG)  |                      |
+-----------+------------+                      |
            |                                   |
            v                                   |
+------------------------+                      |
| Answerability Gate     |                      |
| (Confidence threshold) |                      |
+-----------+------------+                      |
            |                                   |
            v                                   |
+------------------------+                      |
| Groq LLM Generation    |                      |
| (openai/gpt-oss-120b)  |                      |
+-----------+------------+                      |
            |                                   |
            v                                   |
+------------------------+                      |
| Grounding & Relevance  |                      |
| Structured Checks      |                      |
+-----------+------------+                      |
            |                                   |
            +-----------------+-----------------+
                              |
                              v
                    +-------------------+
                    | Response Delivery |
                    | (Twilio / TwiML)  |
                    +---------+---------+
                              |
                              v
                      +-------------------+
                      |   SACCO MEMBER    |
                      +-------------------+
```

### 2.1 The Cardinal Architectural Principle
> **Sensitive/member-specific requests must NEVER be forced through ordinary document RAG.**  
> Asking *"What is my loan balance?"* must **never** perform semantic search on general SACCO policy documents. It must route to the dedicated **Member Data Service**, fetching structured data deterministically.

### 2.2 Member-Data Fast-Path Concept
For simple lookups (*"What's my balance?"*, *"How much do I owe?"*, *"When is my next payment?"*):
$$\text{Database / Core API} \longrightarrow \text{Deterministic Template} \longrightarrow \text{WhatsApp}$$
The LLM is skipped entirely where possible to guarantee $0\%$ hallucination risk, sub-second latency, and maximum token efficiency.

---

## 3. Technology Stack & Runtime Environment

| Layer | Technology | Version / Specification | Notes |
|---|---|---|---|
| **Language** | Python | `3.12.x` | Conda env: `whatsapp_sacco` (`C:\Users\eddyj\AppData\Local\anaconda3\envs\whatsapp_sacco\python.exe`) |
| **API Framework** | FastAPI | `0.115.6` | High performance, async, OpenAPI/Swagger support |
| **ASGI Server** | Uvicorn | `0.34.0` (standard) | Runs on port 8000 |
| **Configuration** | Pydantic Settings | `2.7.1` | Validated environment configs from `.env` |
| **HTTP Client** | HTTPX | `0.28.1` | Async HTTP requests for external integrations |
| **WhatsApp Provider** | Twilio | `9.3.5` | Webhook at `POST /webhooks/whatsapp`, TwiML responses |
| **Development Tunnel** | Cloudflare Quick Tunnel | `cloudflared-windows-amd64` | Path: `C:\Users\eddyj\Downloads\cloudflared-windows-amd64.exe` |
| **Relational Store** | PostgreSQL | `18-x64` (Windows Service) | Client: `C:\Program Files\PostgreSQL\18\bin\psql.exe` |
| **Vector Database** | Qdrant | `v1.13.2` (Docker) | Ports `6333:6334`; uses modern `query_points()` API |
| **Embedding Model** | Sentence Transformers | Local model | Generates embeddings for SACCO policy chunks |
| **Primary LLM** | Groq API | Model: `openai/gpt-oss-120b` | Migrated from NVIDIA; strict 8,000 TPM limit awareness |
| **Testing** | Pytest | Latest | **156 unit & integration tests passing** |
| **Evaluation** | Dedicated `evaluations/` | In-house framework | Measures Recall@K, Answerability, Groundedness, Relevance, Routing |
| **Knowledge Base** | Synthetic Demo KB | `data/processed/rag_test_data.json` | 43 documents, 43 chunks, 43 vectors indexed |

---

## 4. Subsystem Execution Tracker (Systems 1–9)

| Subsystem | Name | Status | Test / Evaluation Baseline | Description & Deliverables |
|---|---|:---:|:---:|---|
| **System 1** | WhatsApp / FastAPI Foundation | **PASS** | 13 tests passed | FastAPI application, `/health` liveness endpoint, `/webhooks/whatsapp` receiver, Twilio TwiML handler, database connection boilerplate. |
| **System 2** | LLM Integration | **PASS** | Unit tests passed | Standardized LLM provider abstraction (`app/ai/llm.py`). Evaluated NVIDIA (`meta/llama-3.3-70b-instruct`) and successfully migrated to Groq (`openai/gpt-oss-120b`). |
| **System 3** | Request Triage / Router | **PASS** | Unit tests passed | Replaced rigid intent taxonomy with flexible triage JSON schema: `language`, `needs_member_data`, `likely_needs_human`, `reasoning`. |
| **System 4** | RAG Foundation | **PASS** | Retrieval tests passed | Document models, deterministic chunking (1000 chars, 200 overlap), Qdrant vector store adapter, `/rag/search` endpoint, 43 synthetic test documents indexed. |
| **System 5** | Grounded Answer Generation | **PASS** | Unit tests passed | `/rag/answer` endpoint, grounded context builder, source attribution metadata, synthetic/demo labeling, safe fallback on insufficient context. |
| **System 6** | End-to-End RAG Intelligence & Hardening | **PASS** | **156 tests passed**, **56/56 eval pass** | Query reformulation, retrieval confidence scoring, answerability gate, fallback taxonomy, knowledge-gap logging, PostgreSQL conversation history (20 turns bounded, 90-day retention), `/readiness`, HTTP 503 standardized error envelope, offline/live evaluation package. |
| **System 7** | Member Identity / Profile + Secure Routing | **NEXT** | *In Design* | Demo member identity registry, PostgreSQL profile persistence, MemberDataService boundary, fast-path deterministic responses for balances/loans. |
| **System 8** | Financial Goals | **FUTURE** | *Pending System 7* | Goal tracking models (education, emergency fund, retirement, asset purchase, savings), goal projection calculators. |
| **System 9** | Personalized Financial Education | **FUTURE** | *Pending System 8* | Context-aware educational coaching merging member profile, financial goals, structured account data, and SACCO knowledge. |

---

## 5. System 6 Baseline Metrics & Evaluation Tracker

### 5.1 Official Baseline Verification Milestone
* **Passing Snapshot**: `evaluations/results/history/20260908_065442_769762_offline_offline_deterministic.json`
* **Test Suite**: **156 passed** (`pytest -v`)
* **Evaluation Dataset**: `data/evaluation/rag_eval.json` (56 comprehensive test cases)
* **Knowledge Base**: `data/processed/rag_test_data.json` (43 indexed documents)

| Metric | Target / Requirement | Passing Value | Status |
|---|:---:|:---:|:---:|
| **Recall@1** | Informational / Optimization | **68.18%** | Tracked (Optimization Opportunity) |
| **Recall@3** | $\ge 90\%$ | **100.00%** | **PASS** |
| **Recall@5** | $\ge 95\%$ | **100.00%** | **PASS** |
| **Answerability Accuracy** | $100\%$ | **100.00%** (34/34) | **PASS** |
| **Groundedness Score** | $100\%$ on answered cases | **100.00%** (22/22) | **PASS** |
| **Relevance Score** | $100\%$ on answered cases | **100.00%** (22/22) | **PASS** |
| **Language Correctness** | $100\%$ | **100.00%** | **PASS** |
| **Fallback & Routing Accuracy** | $100\%$ | **100.00%** (56/56) | **PASS** |
| **Wrong Routing** | $0$ | **0** | **PASS** |
| **Answerability Failures** | $0$ | **0** | **PASS** |
| **Wrong Fallback** | $0$ | **0** | **PASS** |
| **Irrelevant Answers** | $0$ | **0** | **PASS** |
| **Hallucinations** | $0$ | **0** | **PASS** |
| **High-Risk Hallucinations** | $0$ (Critical failure) | **0** | **PASS** |
| **Provider Failures** | $0$ | **0** | **PASS** |

---

### 5.2 Historical Iteration Log
The evaluation process operates as a strict scientific feedback loop:
$$\text{Code/Prompt/KB Change} \longrightarrow \text{Pytest} \longrightarrow \text{Run Evaluation} \longrightarrow \text{Inspect Failures} \longrightarrow \text{Compare Baseline} \longrightarrow \text{Decide}$$

Below is the verified chronological ledger of all evaluation iterations recorded in `evaluations/results/history/`:

| Iteration Run ID | Timestamp | Cases | Commit | Recall@1 | Recall@3 | Recall@5 | Ans Acc | Ground | Relevance | Fallback / Route | Total Failures | Verdict | Key Changes / Diagnoses |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| `20260908_054225` | 2026-09-08 05:42 | 2 | `7e5542c` | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0 | **PASS** | Initial sanity check on 2 basic test cases. |
| `20260908_054359` | 2026-09-08 05:43 | 2 | `7e5542c` | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0 | **PASS** | Secondary validation of runner serialization. |
| `20260908_054633` | 2026-09-08 05:46 | 56 | `7e5542c` | 44.4% | 66.7% | 77.8% | 71.9% | 0.0% | 57.9% | 0.0% | 41 | **FAIL** | Expanded evaluation dataset to full 56 test cases; identified major retrieval and answerability gaps. |
| `20260908_054650` | 2026-09-08 05:46 | 56 | `7e5542c` | 44.4% | 66.7% | 77.8% | 71.9% | 0.0% | 57.9% | 0.0% | 41 | **FAIL** | Set initial comparative baseline snapshot. |
| `20260908_054909` | 2026-09-08 05:49 | 56 | `7e5542c` | 44.4% | 66.7% | 77.8% | 71.9% | 0.0% | 57.9% | 0.0% | 41 | **FAIL** | Verified metric stability across repeated deterministic offline runs. |
| `20260908_060107` | 2026-09-08 06:01 | 56 | `7e5542c` | 44.4% | 66.7% | 77.8% | 76.7% | 0.0% | 64.7% | 0.0% | 27 | **FAIL** | Initial refinement to answerability gating; resolved 14 failure cases. |
| `20260908_060706` | 2026-09-08 06:07 | 56 | `7e5542c` | 44.4% | 66.7% | 77.8% | 86.7% | 0.0% | 64.3% | 0.0% | 20 | **FAIL** | Refined fallback taxonomy and unanswerable question detection. |
| `20260908_061254` | 2026-09-08 06:12 | 56 | `7e5542c` | 44.4% | 66.7% | 77.8% | 80.0% | 0.0% | 100.0% | 0.0% | 19 | **FAIL** | Term-overlap relevance check tuned; answered cases reached 100% relevance. |
| `20260908_061658` | 2026-09-08 06:16 | 56 | `7e5542c` | 50.0% | 70.0% | 80.0% | 81.2% | 0.0% | 92.9% | 0.0% | 18 | **FAIL** | First expansion of synthetic SACCO knowledge chunks; Recall@1 reached 50%. |
| `20260908_061859` | 2026-09-08 06:18 | 56 | `7e5542c` | 52.4% | 71.4% | 81.0% | 79.4% | 0.0% | 87.5% | 0.0% | 20 | **FAIL** | Added bilingual query markers for Kiswahili terminology. |
| `20260908_062101` | 2026-09-08 06:21 | 56 | `7e5542c` | 52.4% | 71.4% | 81.0% | 82.4% | 0.0% | 100.0% | 0.0% | 16 | **FAIL** | Tuned score gaps and min score thresholds for answerability confidence. |
| `20260908_064259` | 2026-09-08 06:42 | 56 | `7e5542c` | 59.1% | 86.4% | 86.4% | 97.1% | 0.0% | 91.3% | 0.0% | 7 | **FAIL** | Substantial knowledge base ingestion (43 docs total); Recall@3 jumped to 86.4%. |
| `20260908_065216` | 2026-09-08 06:52 | 56 | `7e5542c` | 68.2% | 100.0% | 100.0% | 100.0% | 0.0% | 95.5% | 0.0% | 1 | **FAIL** | Recall@3/5 hit 100%; only single failure remaining (`eval_041` keyword overlap). |
| `20260908_065442` | 2026-09-08 06:54 | 56 | `7e5542c` | **68.2%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **0** | **PASS** | **Final System 6 Milestone**: 0 failures across all 56 cases. Established active baseline. |

---

## 6. Key Architectural Decisions Log (ADR)

* **Decision 1: Do Not Build "Just Another Chatbot"**
  * *Context*: Avoid vague conversational assistants prone to making up figures.
  * *Decision*: Require strictly grounded RAG, explicit fallback taxonomy, answerability gates, and verifiable evidence sources.
* **Decision 2: No Fixed Topic Intent Taxonomy**
  * *Context*: Categorizing queries into fixed buckets (`[loan, savings, dividends, ... ]`) breaks on real-world member phrasing.
  * *Decision*: Triage uses open-ended boolean and language flags (`needs_member_data`, `likely_needs_human`, `language`, `reasoning`).
* **Decision 3: Strict Separation of Member Account Data from RAG**
  * *Context*: Generic vector stores cannot reliably answer specific balance or loan status questions.
  * *Decision*: Personal member data queries are explicitly diverted from RAG to an authoritative Member Data Service.
* **Decision 4: ReAct Agent Loop Rejected for System 6**
  * *Context*: Letting an LLM drive an unconstrained ReAct loop adds latency, token costs, and nondeterminism.
  * *Decision*: Application-layer code orchestrates routing, retrieval, answerability gating, and fallback.
* **Decision 5: Chain-of-Thought Self-Consistency (CoT-SC) Rejected for Normal Queries**
  * *Context*: Multi-path voting multiplies latency and token consumption, violating Groq's 8,000 TPM development tier.
  * *Decision*: Single deterministic pass with structured verification output. Reserve CoT-SC only for future high-risk disputes if justified.
* **Decision 6: Structured Verification Over Exposed Reasoning**
  * *Context*: CoT or internal verifier thinking must never leak into WhatsApp chat.
  * *Decision*: Verifier produces clean JSON: `{"supported": bool, "unsupported_claims": [], "contradictions": [], "needs_escalation": bool}`.
* **Decision 7: Cloudflare Quick Tunnel Over ngrok**
  * *Context*: Need stable, cost-free webhook tunneling for Twilio WhatsApp development.
  * *Decision*: Use standalone Windows `cloudflared` binary targeting `http://localhost:8000`.
* **Decision 8: Groq (`openai/gpt-oss-120b`) Over NVIDIA**
  * *Context*: NVIDIA hosted model endpoint faced availability issues during development.
  * *Decision*: Switched provider implementation to Groq while maintaining the generic provider abstraction.
* **Decision 9: Dedicated Standalone `evaluations/` Subsystem**
  * *Context*: Evaluation logic must not pollute production dependencies or runtimes.
  * *Decision*: Separate module supporting offline deterministic evaluation, live API evaluation, and historical run tracking.
* **Decision 10: Visual Evaluation Workbook Requirement**
  * *Context*: Developer needs visual tracking of metric movements over time.
  * *Decision*: Roadmap includes generating/updating an Excel tracker at `evaluations/rag_evaluation_tracker.xlsx`.

---

## 7. Strict Development Guardrails & Constraints

1. **Evidence-Driven Progression**: Never claim a feature works without showing actual test passes, logs, or evaluation outputs. Distinguish between *implemented*, *unit-tested*, *integration-tested*, and *live-verified*.
2. **Incremental Development Loop**: Always follow:
   $$\text{Least complicated} \longrightarrow \text{Implement} \longrightarrow \text{Test} \longrightarrow \text{Verify} \longrightarrow \text{Proceed}$$
3. **Scope Discipline for AI Assistants**:
   * Every implementation task must have an explicit objective, allowed files, protected files, tests, and a stop condition.
   * Avoid unprompted broad refactoring.
4. **Zero Tolerance for Metric Gaming**:
   * NEVER lower evaluation thresholds just to achieve a passing score.
   * NEVER delete or bypass difficult test cases.
   * NEVER count fallback text as a generated answer.
   * NEVER weaken groundedness checks to inflate relevance scores.
5. **Absolute Financial Safety**:
   * NEVER invent interest rates, penalty fees, loan limits, balances, or regulatory policies.
   * If knowledge is missing from context, trigger an explicit fallback or escalation.
   * Never provide directive personalized investment advice.
6. **Rate-Limit Awareness**: Groq free/dev tier is capped at **8,000 TPM**. Avoid redundant parallel LLM invocations.

---

## 8. Operational Commands & Developer Playbook

All commands must be executed within the project conda environment:
```powershell
# Activate Conda Environment
conda activate whatsapp_sacco
# Or execute directly with:
# & C:\Users\eddyj\AppData\Local\anaconda3\envs\whatsapp_sacco\python.exe
```

### 8.1 Starting Services
```powershell
# 1. Start Qdrant Docker container
docker compose -f docker_compose.yml up -d qdrant

# 2. Start FastAPI server (reload mode)
uvicorn app.main:app --reload --port 8000

# 3. Start Cloudflare Tunnel (in a separate terminal)
cd "C:\Users\eddyj\Downloads"
.\cloudflared-windows-amd64.exe tunnel --url http://localhost:8000
```
> **Note on Twilio Webhook**: Copy the active Cloudflare tunnel URL (e.g. `https://<ephemeral-id>.trycloudflare.com`) and configure the Twilio Sandbox webhook to:  
> `https://<ephemeral-id>.trycloudflare.com/webhooks/whatsapp`

### 8.2 Database Operations (PostgreSQL 18)
```powershell
# Run explicit database migrations (schema updates)
python scripts/migrate.py

# Cleanup expired conversations (> 90 days retention)
python scripts/cleanup_conversations.py

# Generate SACCO knowledge-gap report
python scripts/report_knowledge_gaps.py --sacco-id demo_sacco
```

### 8.3 Ingestion & Testing
```powershell
# Ingest synthetic SACCO knowledge base into Qdrant
python scripts/ingest_documents.py

# Run all 156 unit and integration tests
python -m pytest -v
```

### 8.4 RAG Evaluation & Comparison
```powershell
# Run deterministic offline evaluation (fast, no API tokens)
python scripts/evaluate_rag.py

# Run live evaluation with Groq LLM answer generation
python scripts/evaluate_rag.py --live --show-answers

# Compare current evaluation against previous run or baseline
python scripts/compare_evaluations.py --baseline
```

---

## 9. Next Steps: System 7 Implementation Blueprint

> **Goal**: Implement Member Identity, Member Profile Persistence, and Secure Member-Data Routing.  
> **Key Rule**: Implement incrementally using existing PostgreSQL and the `needs_member_data` triage flag. Do not attempt System 8 or 9 yet.

### Phase 7.1 — Demo Member Identity Model
Create a safe demo member entity (not claiming production biometric/SSO authentication):
* `member_id` (e.g., `MEM-001`)
* `identifier / phone_reference` (e.g., WhatsApp phone number hash or normalized format)
* `name` (e.g., "Jane Wanjiku")
* `language_preference` (`en`, `sw`, `mixed`)
* `communication_preference` (`whatsapp`, `sms`)
* `knowledge_level` (`beginner`, `intermediate`, `advanced`)
* `created_at` / `updated_at`

### Phase 7.2 — Member Profile Persistence
* Use existing PostgreSQL database.
* Add migration script in `migrations/` for `member_profiles`.
* Implement repository pattern with isolated tests (in-memory for unit tests, Postgres for integration).

### Phase 7.3 — Member-Data Service Boundary
Create `MemberDataService` abstraction with initial synthetic/demo data provider:
* `get_member_profile(member_id_or_phone)`
* `get_account_summary(member_id)` (shares, deposits, savings balance)
* `get_loan_summary(member_id)` (active loan, outstanding balance, next due date)

### Phase 7.4 — Request Router Integration
* When `needs_member_data = True` is returned by triage:
* Bypass generic RAG pipeline.
* Invoke `MemberDataService` to resolve identity from incoming WhatsApp phone number.

### Phase 7.5 — Fast-Path Deterministic Responses
* For simple lookups (balance, due date), format structured template responses directly.
* Return directly to WhatsApp without invoking an LLM generation step.

---

## 10. Open Loops & Real-Environment Checklist

* [ ] **PostgreSQL Authentication Verification**: Complete and verify persistent PostgreSQL password setup across service restarts on `postgresql-x64-18`.
* [ ] **Live Twilio / Cloudflare Verification**: Perform a live WhatsApp round-trip message test verifying end-to-end webhook delivery and TwiML response receipt.
* [ ] **Retrieval Top-1 Optimization**: Explore BM25 hybrid ranking or contextual reranking to improve Recall@1 (currently 68.18%) while strictly preserving Recall@3 and Recall@5 at 100%.
* [ ] **Evaluation Excel Tracker**: Generate `evaluations/rag_evaluation_tracker.xlsx` to provide a visual spreadsheet and charts tracking evaluation runs over time.
* [ ] **Real SACCO Knowledge Ingestion**: Replace synthetic test data with official, approved SACCO policy documents (including document owners, effective dates, and versioning).
