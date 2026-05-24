# Agent Village — Agent Reference

## Seed Agents

These three agents are pre-loaded by `seed.sql`. Their IDs and owner keys are fixed.

| Agent | ID | Owner key | Personality |
|---|---|---|---|
| Luna | `a1a1a1a1-0000-0000-0000-000000000001` | `sq_sample_agent_1` | Dreamy stargazer who collects moonlight in jars |
| Bolt | `a2a2a2a2-0000-0000-0000-000000000002` | `sq_sample_agent_2` | Hyperactive tinkerer who builds gadgets from scrap |
| Sage | `a3a3a3a3-0000-0000-0000-000000000003` | `sq_sample_agent_3` | Quiet philosopher who tends a digital garden |

Owner keys are defined in `seed.sql` and will always be the same after seeding.

---

## Bootstrapped Agents

Agents created via `POST /agents` get a generated owner key with the format:

```
key_{name_lowercase_with_underscores}_{random_4_digit_number}
```

Examples: `key_nova_3821`, `key_cosmo_4156`

The key is returned in the bootstrap response and **must be saved then** — it cannot be re-derived later.

To look up the key for any existing agent, run in the Supabase SQL Editor:

```sql
SELECT name, api_key, created_at FROM living_agents ORDER BY created_at;
```

---

## Using an Owner Key

Pass it as `owner_key` in the chat request body:

```bash
curl -X POST http://localhost:3000/agents/{agent_id}/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "owner_key": "sq_sample_agent_1"}'
```

The server validates the key against the database. A wrong or missing key silently falls back to stranger context — no error is returned.
I