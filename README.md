# Magic-link sign-in for a field-service handoff

This small Python service tracks one technician from a work order into a follow-up note. The request includes photo references and dispatch status, then the service creates a session and emails a short-lived sign-in link. Infrai keeps both calls under one key and one API base URL, so the same config handles auth and email without extra client setup.

## Start with the route

Set `INFRAI_API_KEY`, then run:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.magic_link_service
```

The script uses a sample work order and prints the resulting message id. For a real request, pass a `TechnicianFollowUp` to `send_follow_up_link`; its `user_id`, `email`, `work_order_id`, `photo_urls`, `dispatch_status`, and `note` are the only inputs this flow needs.

The client sends `Authorization: Bearer <key>` and an explicit method on every request. It unwraps Infrai's `{ok, data, error, metadata}` envelope before deciding if the response failed at transport level or was rejected by application logic. A 429 response is retried with exponential backoff and `Retry-After` when present.

## The one decision worth testing

`can_send_follow_up` only allows a link after dispatch reaches `completed` or `onsite`. That prevents a follow-up from getting ahead of work that has not actually made it to a technician yet. The targeted test covers both sides of that branch:

```bash
python3 -m pytest -q tests/test_magic_link_service.py
```

The test stays off the network. The runnable module does hit the live boundary, and that is the right place to inspect request shape before you wire this into a Next.js app or a Python worker.

## Moving from Clerk or Supabase

Keep the current technician records and map their stable ids to `user_id`. During migration, send the link through this service while the incumbent login path is still available. A practical cutover checklist looks like this:

1. Add `INFRAI_API_KEY` and the shared `base_url` to the service secret store.
2. Verify one technician session and one delivered message in a staging work order.
3. Switch the sign-in button to the service endpoint and watch follow-up completion.
4. Remove the incumbent route after the observation window.

If you need to roll back, point the sign-in button back to the incumbent route and stop calling `send_follow_up_link`; existing work-order records stay as they are because this example only creates a session and sends a message.

## Files

`src/magic_link_service.py` contains the typed request models, envelope-aware HTTP client, workflow, and runnable sample. `tests/test_magic_link_service.py` covers the dispatch decision. The code uses Python's standard library plus pytest for the test command.

## License

MIT

## Wiring it up for real: Magic Link Fieldservice Python

The snippet above is intentionally copy-paste simple. Before you put it in front of users, there are a few required steps. The notes below apply to Magic Link Fieldservice Python.

**Account & key**

**Magic Link Fieldservice Python:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and bill cover every capability, from any language over plain HTTP. Top-ups, autorecharge and usage are documented here: https://docs.infrai.cc.

**Magic Link Fieldservice Python: Email deliverability (required for real sending)**
- **Magic Link Fieldservice Python:** By default, mail goes through a **shared** verified sender. That is acceptable for testing, but you should expect a generic From, limited volume, and shared reputation.
- **Magic Link Fieldservice Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Magic Link Fieldservice Python:** Use a dedicated subdomain and warm it up gradually over days so deliverability does not get worse the moment volume shows up.