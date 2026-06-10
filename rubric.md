# Project Requirements & Rubric (source of truth)

This file is the verbatim set of requirements for the capstone. Every design and
implementation decision in ReefScout should trace back to something here. Treat it
as the source of truth; `plan.md` maps our work to these items.

---

## Learning objectives

By the end of this project you should be able to:

- Design and implement a multi-component AI system that combines prompt engineering, grounding, and agentic patterns.
- Deploy a working application that handles real inputs from real users without breaking.
- Evaluate whether your system actually works, using concrete metrics or structured test cases.
- Articulate what your system does and does not do, and why you made the architectural choices you did.
- Iterate on a codebase based on instructor feedback and your own testing.

---

## What counts as "agentic"

An agentic system is one where the LLM (not a hardcoded Python script) makes autonomous
decisions about what to do next.

- **Agentic:** The model receives a user request, decides it needs to call a tool, calls the
  tool, reads the result, and decides what to do next based on that result. The model is in the
  driver's seat. Your code provides tools and an execution loop; the model decides when and how
  to use them.
- **Not agentic:** Your Python code calls the LLM once with a prompt and returns the response
  (a prompt-response app). Your code calling different functions based on if/else logic is also
  not agentic — that is just routing in your application layer. The model has to be the one
  making the decision.

**The test:** If you removed the LLM from your system and replaced it with a lookup table or a
set of if-statements, would the system behave the same way? If yes, the LLM is not making
decisions and the system is not agentic.

---

## MCP requirement

The application must implement at least one MCP (Model Context Protocol) tool. This means:

- You define a tool with a name, description, and input schema.
- You expose that tool to the model through the tools parameter in your API call (or through an MCP server).
- The model decides whether and when to call it based on the user's request.
- Your code executes the tool and returns the result to the model.
- The model uses the result in its response or decides to call another tool.

An MCP tool does something the model cannot do from its training data alone: query a live API,
search a database, read a file, fetch real-time data, write to storage, or call an external
service. If the tool returns canned sample data or a hardcoded response, it is a mock, not a tool.

---

## Rubric (2 points each)

These are not boxes to check in a particular way. Interpret each through the lens of the project.

1. **Deployment** — The project is publicly accessible and the instructor can interact with a
   working version. Not localhost. Not a screenshot. A URL that can be opened and used. If the app
   is asleep, that is fine as long as it wakes up and runs. If it crashes on load, that is a fail.

2. **Prompt engineering** — Clear evidence of deliberate prompt design. You experimented with
   different prompts, documented what changed between versions, and made intentional choices about
   wording, structure, and constraints. At least two versions of a prompt should be visible, with
   the reasoning for moving from one to the other. A single never-revised prompt does not count.

3. **System prompt(s)** — A purposeful system prompt shapes the behavior, voice, scope, or
   constraints of the model. It defines a role, sets boundaries, or establishes output format. Not
   the framework default and not empty. If the system has multiple agents, each should have its own
   system prompt tailored to its role.

4. **Grounding** — The model is given the right context to do its job rather than guessing from
   training data alone. Retrieval (RAG), structured input from a database or API, few-shot examples,
   or curated domain knowledge injected into the prompt. Key question: does the model have access to
   information it could not have known from pretraining? If yes, you have grounding.

5. **MCP tool (definition)** — At least one tool defined with a name, description, and input schema,
   exposed to the model through the tools parameter or an MCP server. The instructor will read the
   code to verify. The definition should make clear what the tool does, what inputs it expects, and
   what it returns. Defining a tool that is never called does not count.

6. **MCP tool (execution)** — The model actually calls the tool during a real interaction, the code
   executes it, and the result is returned to the model. Evidence in code (a tool-call loop that
   reads tool_use blocks and dispatches to handler functions) and ideally a traced execution in the
   eval/write-up. A tool that only fires in a test but never in the live app does not count.

7. **Agentic behavior** — The model makes at least one autonomous decision during execution: which
   tool to call, whether to call a tool at all, whether to loop again or stop, or how to route a
   request. The decision point must be in the model's response, not in an if-statement in the code.
   If the code always calls the same sequence of functions in the same order regardless of what the
   model says, that is a pipeline, not an agent.

8. **Code on GitHub** — A public GitHub repository with a meaningful commit history. The instructor
   should be able to clone the repo, read the code, and understand the architecture. If private, add
   the instructor as a collaborator (**debruinz**). A repo with one commit that dumps everything tells
   less than one with ten commits that show the project evolving.

9. **Build log** — Documentation of the prompts, decisions, and experiments that shaped the project
   so someone else could understand the process. What did you try? What did not work? What did you
   change and why? Can live in a README, a `BUILD_LOG.md`, or the submission write-up.

10. **Originality** — A distinctive idea, perspective, or angle. Not a tutorial you followed or a
    generic chatbot with a new skin. Evidence that you thought about a real problem and designed a
    solution around it.

11. **Intellectual ownership** — You can explain what the project does, why it works, and where it
    breaks. You are the author, not a passenger. If AI tools wrote code, you understand it and can
    modify it. If the README was LLM-generated, there should be evidence you edited it and added your
    own thinking. The human touch in the product matters.

12. **Iteration** — Evidence you tested the system, found weaknesses, and improved it. Draft feedback
    should be visibly addressed in the final submission. Show what changed between draft and final and
    why. A draft issue still present in the final is a miss.

13. **Evaluation** — You defined what "good" looks like and tested against it. Quantitative (accuracy
    on test inputs, pass rates, latency) or qualitative (structured review against defined criteria).
    Actual test cases with actual results, not a claim that "the system works well." An evaluation with
    documented failures is more credible than one where everything passes.

14. **Documentation** — A README/write-up detailed enough that someone outside the class could
    understand the architecture, deploy the application, and evaluate its outputs. Describe the
    architecture, explain what each component does, document setup, and include at least one example of
    a complete interaction. The project should stand on its own.

---

## How ReefScout maps to the rubric (quick reference)

| # | Item | How ReefScout satisfies it |
|---|---|---|
| 1 | Deployment | FastAPI on Render free tier; free no-key APIs so it doesn't crash on load |
| 2 | Prompt engineering | Versioned system prompts in repo + a prompt log documenting v1 → v2 changes |
| 3 | System prompt(s) | Purposeful system prompt defining the marine-companion role, scope, output format |
| 4 | Grounding | Live conditions/tides/sightings + authoritative taxonomy injected via tools |
| 5 | MCP tool (definition) | 6 tools defined on a FastMCP server with names, descriptions, input schemas |
| 6 | MCP tool (execution) | Backend tool-call loop reads tool_use blocks, dispatches to the MCP server |
| 7 | Agentic behavior | Model chooses which tools to chain, when to verify, when to stop |
| 8 | Code on GitHub | Public repo, incremental commits; add **debruinz** if kept private |
| 9 | Build log | `BUILD_LOG.md` capturing experiments, dead ends, decisions |
| 10 | Originality | Marine field companion with occurrence-based ID verification — not a generic bot |
| 11 | Intellectual ownership | Architecture rationale documented; author can explain failure modes |
| 12 | Iteration | Eval-driven changes + draft-feedback changelog |
| 13 | Evaluation | Structured test cases (planning + ID) with pass/fail criteria and recorded results |
| 14 | Documentation | README with architecture, setup, and a full example interaction trace |
