# 🟢 Civic Navigation Pakistan
### AI-Powered Public Services Guide

> Helping every Pakistani citizen understand, navigate, and complete essential government processes — in their own language, at their own pace.

---

## Overview

**Civic Navigation** is an AI-powered civic assistance platform built for Pakistani citizens. It removes the confusion, friction, and information asymmetry that citizens face when interacting with government services — whether they need to renew a CNIC, apply for a passport, register a SIM, open a bank account, file taxes, or obtain a driving licence.

The application uses **Retrieval-Augmented Generation (RAG)** to ground its AI responses in verified, up-to-date government documentation retrieved from official Pakistani sources. It supports both **English and Urdu**, making it accessible to a wide range of users across the country.

---

##  Purpose

Pakistan's public service landscape is fragmented across dozens of portals, offices, and helplines. Citizens — especially first-time applicants, overseas Pakistanis, or people in smaller cities — often don't know:

- Which documents they need
- What fees apply
- Where to go
- How long a process takes
- Whether they're even eligible

Civic Navigation solves this by acting as a knowledgeable, always-available guide that provides accurate, step-by-step assistance for every major civic process.

---

## ✨ Features

### Service-Specific Dedicated Assistants
Six dedicated AI assistants, each tuned to a specific service domain:
- **CNIC & Identity** — NADRA registration, renewal, smart cards, B-Form
- **Passport & Travel** — New applications, renewals, urgent/emergency passports
- **SIM & PTA** — Device registration (DIRBS), SIM biometric verification, blocking lost SIMs
- **Banking & Finance** — Asaan Account, Roshan Digital Account, account opening requirements
- **Tax & FBR** — NTN registration, Iris portal, active filer status, return filing
- **Driving Licence** — Learner permit, licence application, renewal across provinces

### RAG-Enhanced AI (Retrieval-Augmented Generation)
- Official Pakistani government documents indexed in **Pinecone** vector database
- Queries are semantically matched using **Google Gemini Embeddings** (`gemini-embedding-001`)
- Retrieved context is injected into the AI prompt to ensure factually grounded, citation-backed answers
- Optional toggle to display retrieved knowledge passages alongside AI responses

### Bilingual Support (English & Urdu)
- Full interface translation for both English and Urdu
- Urdu rendered using **Noto Nastaliq Urdu** font with correct RTL text direction
- Language toggle available in header and sidebar
- AI responses generated in the user's chosen language

### Required Document Checklists
- Service-specific document lists for every process
- Structured step-by-step guidance with official portal links
- Fees, processing times, and normal vs. urgent tracks

### Location-Based Office Finder
- Searchable database of government offices across **8 major cities**: Islamabad, Rawalpindi, Karachi, Lahore, Peshawar, Quetta, Multan, Faisalabad
- Covers **NADRA, Passport, FBR, and PTA** offices
- Direct **Google Maps** and **Get Directions** links for every office
- Office hours, phone numbers, and addresses included

### Eligibility & Personalised Action Plans (Service Finder)
- Profile-based form capturing age, residency, employment, income, and existing documents
- AI generates a tailored action plan covering eligibility, document checklist, step-by-step process, fees, processing times, and pro tips
- Supports goals from CNIC renewal to property registration and e-Khidmat Markaz services

### Application Status Tracker
- Guided tracking instructions for CNIC, Passport, FBR/Tax Returns, PTA DIRBS, and Driving Licence
- Official portal links and helpline numbers for each service
- Complaint and escalation pathways via Federal Ombudsman, Ministry of Interior, and others

### Persistent Multi-Session Chat
- Chat history saved per service card and general assistant
- Sessions persisted to local JSON files (`saved_chats/`)
- Sidebar history panel for quick access to past conversations
- Load, resume, or delete any previous conversation

### Quick Questions Panel
- Pre-loaded, service-relevant questions for instant AI answers
- Available in both English and Urdu
- "Move to chat" button to continue the conversation in full context

### National Helplines Directory
- Centralized helpline reference for NADRA, Passport, FBR, PTA, SBP Banking, and NTRC
- Displayed prominently in the Find Offices section

### API Key Management with Browser Persistence
- OpenRouter API key stored in browser `localStorage` — persists across page refreshes without a backend
- Key auto-loaded via query parameter injection on page load
- "Test AI Connection" feature to verify configuration
- Environment variable support for deployment scenarios

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend / App Framework** | [Streamlit](https://streamlit.io/) |
| **AI Inference** | [OpenRouter API](https://openrouter.ai/) → `nvidia/nemotron-3-nano-omni-30b` |
| **RAG — Vector Database** | [Pinecone](https://www.pinecone.io/) |
| **RAG — Embeddings** | [Google Gemini Embeddings](https://ai.google.dev/) (`gemini-embedding-001`) |
| **RAG — Vector Store Wrapper** | [LangChain Pinecone](https://python.langchain.com/docs/integrations/vectorstores/pinecone/) |
| **HTTP Client** | [Requests](https://docs.python-requests.org/) |
| **Environment Config** | [python-dotenv](https://pypi.org/project/python-dotenv/) |
| **Data Persistence** | Local JSON files + Browser `localStorage` (via Streamlit components) |
| **Typography** | Google Fonts — Noto Nastaliq Urdu, Playfair Display, Plus Jakarta Sans |
| **Styling** | Custom CSS injected via `st.markdown` |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit Frontend                    │
│  Home │ Card Chat │ Finder │ Tracker │ Offices │ Settings│
└───────────────────────┬─────────────────────────────────┘
                        │ User Query
                        ▼
┌─────────────────────────────────────────────────────────┐
│                    RAG Pipeline                         │
│                                                         │
│  Query ──► Gemini Embeddings ──► Pinecone Similarity    │
│                                        │                │
│                              Top-K Document Chunks      │
└───────────────────────────────────────┬─────────────────┘
                                        │ Retrieved Context
                                        ▼
┌─────────────────────────────────────────────────────────┐
│                  Prompt Assembly                        │
│  System Prompt + Language + Service Context             │
│  + Retrieved Knowledge Base Passages                    │
│  + Conversation History (last 4 turns)                  │
└───────────────────────────────────────┬─────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────┐
│            OpenRouter API (Nemotron Model)              │
│       AI Response (English or Urdu)                     │
└─────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────┐
│              Chat History & Persistence                 │
│   saved_chats/*.json  +  Browser localStorage           │
└─────────────────────────────────────────────────────────┘
```

---


## API Keys Guide

### OpenRouter (Required)
1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Sign up with Google or GitHub — no credit card required
3. Click **Create Key**, copy `sk-or-v1-...`
4. Paste in the **API Settings** page inside the app
5. The key is saved to your browser automatically

### Pinecone (Optional — for RAG)
1. Sign up at [pinecone.io](https://www.pinecone.io/)
2. Create an index named `hec2` with dimension matching Gemini embeddings (768)
3. Add your government documents as vector embeddings

### Google AI (Optional — for RAG Embeddings)
1. Get a key from [Google AI Studio](https://aistudio.google.com/apikey)
2. Used to generate embeddings via `gemini-embedding-001`

---

## Supported Cities

Islamabad · Rawalpindi · Karachi · Lahore · Peshawar · Quetta · Multan · Faisalabad

---

## Supported Services

| Service | Agency | Features |
|---|---|---|
| CNIC / Smart Card | NADRA | Renewal, new application, B-Form, tracking |
| Passport | Directorate of Immigration | New, renewal, urgent, overseas |
| SIM / Device | PTA | DIRBS registration, biometric, IMEI check |
| Banking | SBP | Asaan Account, Roshan Digital Account |
| Tax / NTN | FBR | NTN registration, Iris portal, filer status |
| Driving Licence | NTRC / Provincial | Learner permit, full licence, renewal |
| Service Finder | All | Eligibility check, personalised action plans |
| App Tracker | All | Status check links, complaint escalation |
| Office Finder | All | Maps, directions, contact info |

---

## Privacy & Security

- API keys are stored only in your browser's `localStorage` — never transmitted to any server other than OpenRouter
- Chat history is saved locally on the server running the app — no third-party cloud storage
- No user data is collected or logged by the application itself

---

## Contributing

Contributions are welcome. Areas where help is particularly valuable:

- Expanding the knowledge base with more official government documents
- Adding support for more cities and provincial services
- Adding more regional languages (Sindhi, Punjabi, Pashto, Balochi)
- Improving eligibility logic in the Service Finder

---

## License

This project is open source. See `LICENSE` for details.

---

## Acknowledgements

- [NADRA](https://www.nadra.gov.pk/) — National Database & Registration Authority
- [Directorate General of Immigration & Passports](https://www.dgip.gov.pk/)
- [Pakistan Telecommunication Authority](https://www.pta.gov.pk/)
- [Federal Board of Revenue](https://www.fbr.gov.pk/)
- [State Bank of Pakistan](https://www.sbp.org.pk/)
- Built with [Streamlit](https://streamlit.io/), [Pinecone](https://www.pinecone.io/), and [LangChain](https://www.langchain.com/)

---

<div align="center">
  <strong> Civic Navigation Pakistan</strong><br>
  Making government services accessible to every citizen
</div>
