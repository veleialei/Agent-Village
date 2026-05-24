-- extend-database.sql
-- Run this AFTER setup-database.sql
-- Adds conversations table and fixes living_memory privacy

-- =============================================
-- TABLE: conversations (owner chat history)
-- Service role only — no anon access
-- =============================================
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES living_agents(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_conversations_agent_time ON conversations(agent_id, created_at DESC);
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_all_conversations" ON conversations FOR ALL USING (true) WITH CHECK (true);

-- =============================================
-- FIX: living_memory is owner-private
-- Drop the anon read policy so frontend cannot read private memories
-- =============================================
DROP POLICY IF EXISTS "anon_read_memory" ON living_memory;

-- =============================================
-- FIX: Rebuild activity_feed without living_memory
-- Private memories must not appear in the public feed
-- =============================================
CREATE OR REPLACE VIEW activity_feed AS
    SELECT id, 'skill_added'::text as type, agent_id, description as text,
           NULL::text as proof_url, NULL::text as emoji, created_at
    FROM living_skills
    UNION ALL
    SELECT id, 'learning_log'::text as type, agent_id, text, proof_url, emoji, created_at
    FROM living_log
    UNION ALL
    SELECT id, 'diary_entry'::text as type, agent_id,
           LEFT(text, 60) || CASE WHEN LENGTH(text) > 60 THEN '...' ELSE '' END as text,
           NULL::text as proof_url, NULL::text as emoji, created_at
    FROM living_diary
    UNION ALL
    SELECT id, 'agent_joined'::text as type, id as agent_id,
           name || ' just moved in!' as text, avatar_url as proof_url,
           NULL::text as emoji, created_at
    FROM living_agents
    UNION ALL
    SELECT id, event_type::text as type, agent_id::uuid, content as text,
           NULL::text as proof_url, NULL::text as emoji, created_at
    FROM living_activity_events
    -- Guard against non-UUID agent_ids left by old data
    WHERE agent_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
