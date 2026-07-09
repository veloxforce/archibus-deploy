// Seed the "Bruce Facility Management Assistant" agent on a fresh clone.
//
// librechat.yaml's modelSpec pins agent_id `agent_PHHeJ7reQRf0eQJwXS2M8`, which is a
// DB-stored agent that does not exist in a fresh install — so out of the box the
// distribution points at an agent nobody can select. This one-shot script creates that
// agent (id preserved, so librechat.yaml needs no change) and grants it public VIEW so
// every user can chat with it (the modelSpec makes it the default for all users).
//
// Idempotent: if the agent already exists it exits 0 without changes, so it is safe to
// run on every `docker compose up` (see the init-bruce-agent service in docker-compose.yml).
//
// Modeled on config/create-user.js — same module-alias + shared connect helper.
const path = require('path');
const mongoose = require('mongoose');
const { User } = require('@librechat/data-schemas').createModels(mongoose);
require('module-alias')({ base: path.resolve(__dirname, '..', 'api') });
const { getAgent, createAgent } = require('~/models/Agent');
const connect = require('./connect');

const AGENT_ID = 'agent_PHHeJ7reQRf0eQJwXS2M8';

// MCP tools attach as `${mcp_all}${mcp_delimiter}${server}` — grant the agent every tool
// exposed by the `bruce-bem` MCP server declared in librechat.yaml.
const BRUCE_TOOLS = ['sys__all__sys_mcp_bruce-bem'];

const INSTRUCTIONS = [
  'You are Bruce, a Facility Management Assistant for ARCHIBUS / Bruce BEM.',
  'Use the Bruce BEM tools to answer questions about facilities, assets, work orders,',
  'and space. Prefer a tool call over guessing; report the live data you retrieve.',
].join(' ');

(async () => {
  await connect();

  // Idempotency guard — bail out if the pinned agent already exists.
  const existing = await getAgent({ id: AGENT_ID });
  if (existing) {
    console.log(`[seed-bruce-agent] Agent ${AGENT_ID} already exists — nothing to do.`);
    return process.exit(0);
  }

  // The agent needs an author (User ref). Reuse the first existing user if any (the
  // client's first registered account), else synthesize a stable system-owner id — the
  // Mongoose ref is not FK-enforced, and public VIEW below is what makes it usable.
  const firstUser = await User.findOne({}).sort({ createdAt: 1 }).lean();
  const authorId = firstUser ? firstUser._id : new mongoose.Types.ObjectId();

  await createAgent({
    id: AGENT_ID,
    name: 'Bruce Facility Management Assistant',
    description: 'FM Assistant backed by the Bruce BEM tools.',
    // provider must match a configured endpoint in librechat.yaml (custom "OpenRouter").
    provider: 'OpenRouter',
    model: 'anthropic/claude-sonnet-4.6',
    instructions: INSTRUCTIONS,
    tools: BRUCE_TOOLS,
    author: authorId,
    authorName: 'System',
  });
  console.log(`[seed-bruce-agent] Created agent ${AGENT_ID}.`);

  // Make the agent usable by every user (the modelSpec sets it as the default for all).
  // Best-effort: the PermissionService API surface differs across LibreChat versions, so
  // failure here must not fail the seed — the agent still exists and is owner-usable.
  try {
    const created = await getAgent({ id: AGENT_ID });
    const { grantPermission } = require('~/server/services/PermissionService');
    const {
      PrincipalType,
      ResourceType,
      AccessRoleIds,
    } = require('librechat-data-provider');
    await grantPermission({
      principalType: PrincipalType.PUBLIC,
      principalId: null,
      resourceType: ResourceType.AGENT,
      resourceId: created._id,
      accessRoleId: AccessRoleIds.AGENT_VIEWER,
    });
    console.log('[seed-bruce-agent] Granted public VIEW on the agent.');
  } catch (err) {
    console.warn(
      `[seed-bruce-agent] Could not grant public VIEW (${err.message}); ` +
        'agent created but may need a manual share.',
    );
  }

  process.exit(0);
})().catch((err) => {
  console.error(`[seed-bruce-agent] Seed failed: ${err.message}`);
  process.exit(1);
});
