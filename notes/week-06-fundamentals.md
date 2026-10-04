# Week 6 fundamentals: orchestration, structured outputs and tool calling

The code is in `capstone/src/payments_rag/graph/`, `structured.py` and `tools.py`. Results are in `week-06.md`; this file explains the ideas.

Contents: 1. Why a graph, not a chain or a free agent · 2. State, nodes, edges, reducers · 3. Conditional edges and bounded loops · 4. Retries · 5. Checkpoints and human in the loop · 6. Structured outputs · 7. Tool calling · 8. Semantic Kernel · 9. Failure modes · 10. Interview check

---

## 1. Why a graph, not a chain or a free agent

Three ways to wire several model calls together:

| Style | How control flows | Good for | Weak at |0
|---|---|---|---|
| **Chain** | fixed sequence: A then B then C | simple pipelines | any decision or retry ("if the search was weak, try again") |
| **Graph** (LangGraph) | you define the nodes and the allowed transitions; the state decides which edge is taken | RAG with checks, retries and approvals, where you want to know every path | open-ended tasks with unknown steps |
| **Free agent loop** | the model decides what to do next, repeatedly | exploratory tasks | predictability, cost control, testing, auditing |

For a compliance-sensitive assistant you want the middle one: the *model* does language work inside a node, but the *program* decides where control goes, so every path can be listed, tested and bounded.

In this repo the pipeline from Week 5 (`ask`) is a chain: search, check, answer or refuse. The graph adds a router in front, a bounded retry of the search with a rewritten query, a validated structured answer with one regeneration, and an optional human decision.

```
route -> retrieve -> grade -> generate -> validate -> done
   |         ^         |                      |
   |         +-rewrite-+ (once)              +-> generate again (once) -> refuse if still bad
   +-> decline / small talk                   (optional: grade -> human review -> generate or refuse)
```

---

## 2. State, nodes, edges, reducers

- **State** is one shared record every node reads. Here a `TypedDict`: the question, the current query, the hits, the grade, the draft, the reply, a trace.
- **A node** is a function `state -> partial update`. It returns only what it changed; the framework merges it in. This is why nodes are easy to test: give a state, check the returned fields. In this repo the nodes are plain functions with no LangGraph import, and `build.py` only wires them.
- **An edge** says which node runs next. A **conditional edge** calls a function on the state and returns the next node's name.
- **A reducer** says how an update merges into a field. By default a new value replaces the old one. The `trace` field uses `operator.add`, so each node appends its step instead of overwriting the list. Without a reducer, parallel or repeated nodes silently overwrite each other.
- **Keep state plain.** Dicts, strings and numbers only (hits are stored as dicts, not as `Hit` objects). A checkpointer has to save the state and restore it later, possibly in another process; custom classes make that fragile.

---

## 3. Conditional edges and bounded loops

A loop in a graph (grade says "weak", rewrite the query, search again) can run forever if nothing limits it. Every loop here has a counter in the state and a cap:

- search rewrites: at most **1** (`attempts < MAX_REWRITES`);
- answer regeneration after a failed validation: at most **1** (`regenerations < MAX_REGENERATIONS`).

After the cap the graph takes the exit edge, which is a **refusal with a reason**. The rule: *every retry loop has a counter, and the exit is a safe outcome, not an exception.* Each cap costs a model call or two, so it is also a cost bound.

**Which branch a failure takes** is a design decision worth stating:

- weak evidence (the answerability grade is not "full") means *rewrite once*; the filters chosen earlier are dropped on the rewrite, because a wrong filter may be what hid the answer;
- a draft that fails validation means *regenerate once with the reason as feedback*;
- anything still failing means *refuse*, never "answer anyway".

---

## 4. Retries

Two different kinds of failure, handled differently:

| Failure | Example | Handling |
|---|---|---|
| **Transient** | rate limit (429), timeout, connection reset, server error | retry the same call after a wait, a few times |
| **Content** | the model returned malformed JSON, an uncited answer, a wrong region | not fixed by repeating the identical request; handled by the graph (regenerate with feedback, or refuse) |
| **Bug** | a `ValueError` in your own code | do not retry; let it surface |

LangGraph's `RetryPolicy` is attached per node with a predicate saying which exceptions count as transient (here: names such as `RateLimitError`, `APITimeoutError`, `APIConnectionError`, `InternalServerError`, plus timeouts and connection errors). The test suite checks both sides: a transient error is retried and succeeds; a `ValueError` is raised after one attempt.

**Hidden retries.** The OpenAI SDK also retries 429s itself with a short backoff and no log line. A throttled deployment can therefore look like *slow* calls, not errors. During this week's evaluation single calls took about 6 s while the run was going, against 0.4 to 1.1 s on a quiet deployment, and a 429 appeared the moment a second process called it; I believe hidden retries explain the gap but did not log them to prove it. If latency jumps, check the deployment's request-per-minute limit before blaming the model.

---

## 5. Checkpoints and human in the loop

A **checkpointer** saves the state after each node, keyed by a `thread_id`. That enables two things:

- **Pause and resume.** A node calls `interrupt(payload)`; the run stops and returns the payload to the caller; later `Command(resume=value)` continues from the same point with `value` as the interrupt's result. The pause can last minutes or days if the checkpointer is durable (a database), and the resume can happen in a different process.
- **Inspection.** You can read the state at any step, which is useful for debugging a wrong answer.

In this repo (optional, `review=True`): when the grade is "partial" after the rewrite, the graph pauses with the passages and asks a person to answer or refuse. "None" evidence never pauses (nothing to review). `MemorySaver` keeps checkpoints in memory, enough for tests and the CLI demo; production needs a persistent one.

When human review earns its cost: high-stakes answers, evidence that is borderline, and the first weeks of a system's life when you are learning where it is wrong. It does not scale to every question.

---

## 6. Structured outputs

Free-text replies are parsed with regular expressions that break on small wording changes. Structured outputs ask for **JSON that matches a schema**, in two layers:

1. **On the wire**: the request carries a JSON schema (`response_format` with `strict: true`), so the service constrains the model's output to it.
2. **In your process**: the reply is parsed again with **Pydantic**. A constraint on the wire is not a guarantee here: a different model, an older API version or a truncated reply can still break it.

Strict mode needs the schema to forbid extra fields and make every field required (nullable if optional), so the Pydantic models here set `extra="forbid"` and have no defaults. A reply that does not fit raises `StructuredOutputError`; the caller decides what to do.

What structure buys, with this repo's models:

| Model | Fields | Enforced |
|---|---|---|
| `Route` | `label` (in_scope / out_of_scope / chit_chat), `reason` | the label is one of three values; a made-up label is rejected |
| `QueryRewrite` | `query` | a string field exists |
| `CitedAnswer` | `answer`, `citations` (list of ints), `confidence` (high / medium / low) | the citation numbers are integers the validator can check against the passages |

Note `confidence`: it is the model's *own estimate*, not a calibrated probability. It is stored and shown, but nothing should be gated on it without measuring how well it predicts correctness.

**Structure is not truth.** A perfectly valid `CitedAnswer` can still cite the wrong passage. That is why the graph has a separate `validate` node: it checks the citations exist, every sentence carries one, and the answer is not empty. Whether the cited passage really supports the sentence is what the Week 5 faithfulness evaluation measures.

---

## 7. Tool calling

**Tool calling lets the model propose a function call; it never runs one.** You describe a function (name, description, a JSON schema for its arguments). The model replies with the function name and arguments it would use. Your code validates them and decides whether and how to run anything.

In this repo the tool is `search_corpus(query, jurisdictions, published_from, published_to)`:

- the model is *forced* to call it (`tool_choice`), so the reply is always arguments, never prose;
- the schema limits `jurisdictions` to the regions that exist (EU, India, US, global), so the model cannot invent one;
- dates are re-checked in our code (a non-`YYYY-MM-DD` value is dropped), then the arguments become a `SearchFilter` for our own search, which validates values again before building the query string.

**Security point.** The arguments come from a model that read user text, so they are untrusted input, like form fields. They are validated and escaped, never concatenated into a query. This is the same reason prompt injection matters in Week 10: whatever the model emits is an input to the next system.

**Quality risk.** A filter chosen wrongly silently removes the right passages (for example "India" for a question that a "global" document answers). Two defences: the prompt says to filter only when a region or date is clearly named, and the graph drops the filters when the first search finds weak evidence. The planning step is optional and should be switched on only if measurement shows it helps.

---

## 8. Semantic Kernel

Semantic Kernel (SK) is Microsoft's orchestration SDK, an alternative to LangGraph. Its core ideas:

- **Plugin**: a class whose methods marked `@kernel_function` are described to the model.
- **Automatic function calling** (`FunctionChoiceBehavior.Auto()`): the model chooses which plugin functions to call, and how many times, before answering. This replaced SK's older **planners** (Handlebars, Stepwise), which were deprecated in favour of native tool calling.
- **Filters**: hooks around function calls and prompts, for logging, approval or policy.

How it compares, as a rule of thumb: SK's strength is fit with the Microsoft ecosystem (Azure, .NET, enterprise plugins); LangGraph's strength is explicit control flow (state, conditional edges, checkpoints, interrupts). SK's automatic function calling is closer to the "free agent loop" of section 1; the graph is the one with bounded, testable paths. The sample (`capstone/examples/semantic_kernel_sample.py`) is deliberately small and runs in a throwaway environment; it is not evaluated.

---

## 9. Failure modes to expect

| Symptom | Likely cause | Where to look |
|---|---|---|
| Good questions refused after validation | the model wrote an uncited sentence twice | the validation message in the trace; the prompt; the strictness of the sentence rule |
| Answers slow, calls take seconds each | a rate limit with hidden SDK retries | the deployment's request and token limits |
| Router declines a real question | scope description too narrow or the question is oddly worded | the router's reason; add examples |
| Router lets an off-topic question through | scope description too broad | the grade step then refuses it, at the cost of a search |
| Filter hides the answer | the planner chose a region or date wrongly | the `plan:` entry in the trace |
| A loop that never ends | no counter, or a counter never incremented | every loop needs a cap in state |
| State lost on resume | custom objects in state, or a non-persistent checkpointer | keep state plain; use a database checkpointer |

---

## 10. Interview check: can you answer these out loud?

- [ ] Chain vs graph vs agent loop: when would you pick each? *(Section 1.)*
- [ ] What is a reducer and what goes wrong without one? *(A node's update replaces the field instead of merging, so repeated nodes overwrite each other.)*
- [ ] How do you stop a retry loop in a graph from running forever? *(A counter in state and an exit edge that is a safe outcome.)*
- [ ] Transient errors vs content errors: how does retry handling differ? *(Section 4.)*
- [ ] Why can a throttled model look like a slow model? *(SDK retries 429s silently, so latency grows without errors.)*
- [ ] How does human in the loop work in LangGraph and what does it need? *(`interrupt`, a checkpointer, a thread id, `Command(resume=...)`.)*
- [ ] Why validate a structured output twice, and is a valid structure a correct answer? *(Wire constraint is not a guarantee; structure is not truth.)*
- [ ] What does tool calling actually do, and what must you do with the arguments? *(The model proposes; you validate and execute; arguments are untrusted input.)*
- [ ] What happened to SK planners, and how do you do planning now? *(Deprecated; automatic function calling.)*
- [ ] Where does a model-chosen filter go wrong, and how did you contain it? *(Wrongly narrows the search; prompt says to filter only when clear; filters are dropped on the retry.)*
