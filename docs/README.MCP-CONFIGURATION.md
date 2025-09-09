# MCP Integration Configuration Guide

## Overview

**Important:** This is Phase 3 of LibreChat deployment - connecting Bruce BEM facility management tools.

**What's Included:**
- Pre-configured MCP connection to Bruce BEM server
- Ready-to-use `librechat.yaml` file 
- No server setup required on your end

**Post-Configuration State:**
- Facility management tools available in chat interface
- Users can search assets, create work requests naturally
- Integration works transparently through conversation

## Prerequisites

- Completed Phase 1 (Infrastructure) and Phase 2 (AI Models)
- LibreChat running successfully at localhost:3080
- Basic Docker Compose knowledge

## Configuration Steps

### 1. MCP Configuration File

The repository includes a pre-configured `librechat.yaml` file that connects to Bruce BEM facility management tools.

**File location:** `librechat.yaml` (repository root)
**Contents:** Pre-configured MCP server connection (no modifications needed)

### 2. Mount Configuration in Docker

Create `docker-compose.override.yml` to mount the MCP configuration:

```yaml
services:
  api:
    volumes:
      - ./librechat.yaml:/app/librechat.yaml:ro
```

**Why override file:**
- Preserves original docker-compose.yml 
- Adds volume mount for MCP configuration
- Read-only mount prevents accidental changes

### 3. Apply Configuration

**Critical:** Container must be recreated (not just restarted) for volume changes:

```bash
# Wrong - won't pick up new volume mounts
docker compose restart api  

# Correct - recreates container with new volumes
docker compose down && docker compose up -d
```

**Why recreation needed:**
- Volume mounts are set at container creation time
- Restart only stops/starts existing container
- Down/up creates new container with updated configuration

### 4. Verification

**Verify file is accessible in container:**
```bash
docker exec LibreChat cat /app/librechat.yaml
# Should display MCP configuration content
```

**Check MCP tools loaded successfully:**
```bash
docker logs LibreChat | grep -i "mcp.*bruce"
# Should show: "Added [X] MCP tools" (not 0)
```

**Test in LibreChat interface:**
1. Open http://localhost:3080
2. Look for server dropdown below chat input area
3. Select "Bruce BEM" from available servers
4. MCP tools now available for facility management conversations

## Troubleshooting

**Common Issues:**

**"0 MCP tools loaded"**
- Solution: Ensure container was recreated (not just restarted)
- Verify: `docker exec LibreChat cat /app/librechat.yaml` shows content

**"Config file not found"**
- Solution: Check volume mount in docker-compose.override.yml
- Verify: File path is `./librechat.yaml:/app/librechat.yaml:ro`

**"MCP server not responding"**  
- Solution: Check container logs for connection errors
- Command: `docker logs LibreChat | grep -i error`

## Configuration Details

**What's Pre-Configured:**
- Bruce BEM server connection endpoints
- Authentication settings
- Tool availability settings
- Error handling configuration

**What You Control:**
- When to enable/disable the integration (volume mount)
- Container restart/recreation timing
- Log monitoring and verification

**What You Don't Need to Configure:**
- MCP server URLs or endpoints
- Authentication credentials or tokens  
- Tool registration or discovery

## Next Steps

After successful MCP integration:

1. **Train Users:** Facility staff can now request work orders conversationally
2. **Monitor Usage:** Check logs for tool usage patterns
3. **Scale Access:** Add more users through LibreChat user management

**Example Conversations:**
- "The coffee machine in Building A is not working"
- "Search for all HVAC equipment in the north wing"
- "Create a work request for elevator maintenance"

**Current Status:** Bruce BEM tools integrated and ready for facility management workflows.

---

*MCP configuration validated and ready for production deployment.*