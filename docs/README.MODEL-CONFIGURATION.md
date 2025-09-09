# AI Model Configuration Guide

## Overview

**Important:** This is Phase 2 of LibreChat deployment - enabling AI conversation capabilities.

**What This Guide Covers:**
- How to configure AI models when API keys are provided
- Where to place configuration files
- Container management for configuration changes

**Post-Configuration State:**
- Chat interface can process conversations
- Users can interact with facility management tools
- AI responses enabled for all integrated features

## Prerequisites

- Completed Phase 1 (Infrastructure deployment)
- LibreChat running successfully at localhost:3080
- API keys provided by vendor for configuration

## AI Provider Configuration

LibreChat uses a two-step configuration for built-in AI providers:
1. **Visibility Control** - Choose which providers appear in UI dropdown
2. **Authentication** - Add API keys for chosen providers

### Step 1: Provider Visibility Control

**Edit .env file to uncomment and configure ENDPOINTS:**
```bash
# REQUIRED: Always uncomment for control granular control
# Controls which AI providers appear in the UI dropdown
ENDPOINTS=openAI,anthropic,google

# Available built-in providers:
# openAI     = OpenAI models (GPT-4, GPT-3.5, etc.)
# anthropic  = Claude models (Claude-3.5, Claude-3, etc.)  
# google     = Gemini models (Gemini-1.5, etc.)
```

**Why ENDPOINTS matters:**
- Commented out = No control on which models are available in the model menu
- Explicit list = Exact control over what users see

### Step 2: Provider Authentication

Add API keys for the providers you enabled in ENDPOINTS:

**For OpenAI (if openAI in ENDPOINTS):**
```bash
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
```

**For Anthropic (if anthropic in ENDPOINTS):**
```bash
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
```

**For Google (if google in ENDPOINTS):**
```bash
GOOGLE_KEY=AIzaSyxxxxxxxxxxxxx
```

### Apply Configuration

```bash
# For .env changes, restart is sufficient
docker compose restart api
```

### Verification

**Check provider registration:**
```bash
# Check endpoint registration in logs
docker logs LibreChat | grep "endpoint"
# Should show: "OpenAI endpoint registered" for each configured provider
```

**Test in interface:**
1. Open http://localhost:3080
2. Check provider dropdown shows only your configured providers
3. Check model dropdown shows available models for each provider
4. Send test message to verify AI responses

## Troubleshooting

**Common Issues:**

**"No models available" in UI**
- Check: ENDPOINTS uncommented and includes desired providers
- Verify: API keys properly set for ENDPOINTS providers  
- Logs: `docker logs LibreChat | grep "endpoint"`

**"Provider not appearing in dropdown"**
- Solution: Add provider name to ENDPOINTS list
- Example: Add "anthropic" to ENDPOINTS for Claude models
- Restart: `docker compose restart api`

**"Models not appearing after configuration"**
- Check: Provider included in ENDPOINTS
- Verify: Correct API key format for provider
- Restart: Container restart completed successfully