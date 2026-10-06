# Payments Assistant: React front end

A small React + TypeScript page (built with Vite) for the payments assistant API: ask a question, read a cited answer or a refusal, open the sources, rate the answer.

```
cd capstone/frontend
npm ci
npm run dev        # http://localhost:5173, proxies /ask, /feedback and /health to the API on :8000
npm test           # 43 tests (Vitest + Testing Library)
npm run build      # typecheck, then build into dist/
```

Run the API next to it from the **repository root** (it reads `.env` from the current folder):

```
PAYRAG_API_KEY=local-key uv run --project capstone --all-groups python -m uvicorn payments_rag.api:app --port 8000
```

In production there is no separate front-end host: the API serves the built files at `/` (from `payments_rag/web/` inside the deployment zip, or `capstone/frontend/dist` when run from the source tree), so the page and the API are one origin and need no CORS.

## The API key

The key is **not** in the build. You paste it into the page; it is kept in `sessionStorage` (this tab only, gone when the tab closes), sent as the `X-API-Key` header, and never written to `localStorage`. Anything shipped inside a web page is public, which is why the key is typed in rather than baked in. This protects against strangers spending money on the model; it is a shared secret, not user accounts, so anyone you give the key to can use it.

## Safety choices

- The answer is rendered as text and React elements only (never as HTML), so a hostile answer cannot inject markup. A test checks this.
- Only `https` source addresses become links, and they open with `rel="noopener noreferrer"`.
- The server sends a strict Content-Security-Policy (own scripts, styles and connections only, no framing); the page uses no inline script or style.
- Error messages are fixed text; whatever the server says about a failure is never shown.

## Layout

| File | What it holds |
|---|---|
| `src/api.ts` | The API client and its typed errors (auth, validation, rate limit with Retry-After, server, network) |
| `src/citations.ts` | Splits an answer into text and `[n]` markers; parses a source label into document, section and link |
| `src/App.tsx` | The page: key field, question box (Enter to send, 1000-character counter), examples, status, errors, history |
| `src/components/AnswerCard.tsx` | One answer: citation badges that jump to the sources, the refusal state, feedback buttons |
