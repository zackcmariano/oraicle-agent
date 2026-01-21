# Oraicle-Agent

![Oraicle Agent](https://raw.githubusercontent.com/zackcmariano/oraicle-agent/refs/heads/master/assets/oraicle-agent-lib.png)


> **Turn any Google-ADK Agent into a Root Agent - instantly.**

Oraicle-Agent is a **groundbreaking Python library** that extends the Google Agent Development Kit (Google-ADK), enabling **any agent to become a `root_agent` dynamically**, without hacks, forks, or duplicated apps.

This unlocks a **new architectural paradigm** for multi-agent systems:
- Multiple conversational entrypoints
- Direct chat with sub-agents
- True Agent-to-Agent (A2A) orchestration
- Seamless deployment on **Vertex AI Agent Engine**

---

## 🚀 Why Oraicle-Agent exists

Google-ADK assumes:
- One `root_agent` per application
- Sub-agents can’t be direct entrypoints
- One conversational domain per deployment

**Oraicle-Agent breaks this limitation - intentionally and cleanly.**

With Oraicle-Agent, **any agent can become the root of a conversation**, while still participating in a larger A2A system.

> 🔥 This is not a hack.  
> 🔥 This is not a fork.  
> 🔥 This is a new abstraction layer.

---

## ✨ What makes Oraicle-Agent unique?

### ✅ Dynamic Root Agents
Choose *at runtime* which agent owns the conversation.

### ✅ Direct Sub-Agent Chat
Users can talk directly to a specialized agent (teacher, assistant, expert) **without losing context isolation**.

### ✅ A2A-First Architecture
Root agents orchestrate other agents, while still being callable as standalone conversational entities.

### ✅ Google-ADK & Vertex AI Compatible
Works with:
- `adk web`
- ADK loader
- Vertex AI Agent Engine

---

## 🧩 The core idea (one line)

> **Any `Agent` can be a `root_agent` if it is explicitly declared as one.**

Oraicle-Agent formalizes this idea.

---

## 📦 Installation

```bash
pip install oraicle
```

---

## ⚡ Quick Start

```python
from oraicle import autoagent
from google.adk.agents import Agent

history_teacher = Agent(
    name="history_teacher",
    model="gemini-2.0-flash",
    instruction="You are a history teacher."
)

autoagent(history_teacher)
```

---

## ☁️ Deploying to Vertex AI Agent Engine

```python
from app.sub_agents.history_teacher.agent import history_teacher
```

---

## 👤 Identifying the user in Agent Engine Sessions (User ID)

When your agent is deployed on **Vertex AI Agent Engine**, each chat creates a **Session**. In the Agent Engine UI, sessions have default fields like:

- Session ID
- Display name
- **User ID**
- Created
- Last active

By default, many deployments end up with a generic/opaque `User ID`. This makes it hard to audit who started each conversation in:

- Agent Engine **Playground**
- **Gemini Enterprise** chat

Oraicle provides an **optional** helper to resolve a human-readable `user_id` (usually an **email** or **name**) from:

- An explicit parameter you already have (e.g. `user`)
- Request headers (e.g. Google/IAP/forwarded identity headers)
- A JWT found in `Authorization: Bearer ...` (decoded only; no signature verification)

### ✅ How to activate (opt-in)

Import and use `agent_engine_user_id()` and pass its result to ADK when querying the agent:

```python
from oraicle.adk.user_identity import agent_engine_user_id

# If you already receive "user" (like your own API payload):
resolved = agent_engine_user_id(explicit_user=user, default="anonymous")

async for event in adk_app.async_stream_query(
    user_id=resolved.user_id,   # 👈 this becomes Agent Engine "User ID"
    message=user_input,
):
    ...
```

### ✅ Using headers (when available)

If your framework provides a request object with `request.headers`, you can pass it directly:

```python
from oraicle.adk.user_identity import agent_engine_user_id

resolved = agent_engine_user_id(request=request, default="anonymous")

async for event in adk_app.async_stream_query(
    user_id=resolved.user_id,
    message=user_input,
):
    ...
```

### Notes

- **Backward compatible**: this feature is **100% opt-in** (it does nothing unless you import and use it).
- **Security**: JWT decoding here is for **display/identification only**. Do not use it for authorization decisions.

---

## 🔧 Using Tools with Oraicle-Agent

Oraicle-Agent provides **automatic runtime discovery of tools**, allowing sub-agents to use tools **without importing directly from** `app.tools`.

This ensures:
- No PYTHONPATH hacks
- No custom bootstrap commands
- Full compatibility with adk web ./sub_agents
- Clean, scalable architecture

## 📁 Recommended project structure
```bash
app/
├── tools/
│   ├── student_exam.py
│   ├── register_student_grades.py
│   └── any_new_tool.py
│
└── sub_agents/
    └── history_teacher/
        ├── agent.py
        └── prompt.py
```

Each tool should live inside `app/tools` and expose public functions
(optionally using `__all__`).

### ✅ Importing tools inside sub-agents (correct way)
Instead of importing tools directly from app.tools, always import them from oraicle.tools.

❌ **Do NOT do this**
```python
from app.tools.student_exam import student_exam
from app.tools.register_student_grades import register_student_grades
```
### ✅ Do this
```python
from oraicle.tools import student_exam, register_student_grades
```
Oraicle-Agent will **automatically discover and load all tools inside** `app/tools` **at runtime**.

### ⚡ Example: Sub-agent using tools
```python
from google.adk.agents import Agent
from oraicle import autoagent
from oraicle.tools import student_exam, register_student_grades
from .prompt import AGENT_PROMPT

history_teacher = Agent(
    name="history_teacher",
    model="gemini-2.0-flash-lite",
    instruction=AGENT_PROMPT,
    tools=[
        student_exam,
        register_student_grades,
    ],
)

autoagent(history_teacher)
```
No additional configuration is required.

## 🚀 Running locally with ADK
Oraicle-Agent works with the **default ADK command**, no bootstrap needed:
```bash
adk web ./sub_agents
```
All sub-agents will:
- Be discovered automatically
- Act as independent root_agents
- Have full access to shared tools
- Maintain isolated conversational contexts


## 🧠 Why this matters
This design turns `app/tools` into a **runtime tool registry**, not a static import dependency.
You get:
- True plug-and-play tools
- Zero coupling between app and sub-agents
- A clean A2A + Tooling architecture
- Production-safe execution (local & Vertex AI)


## 📄 License

MIT License © 2026  
Built with 🤖 for the GenAI community.