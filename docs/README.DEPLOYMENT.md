# LibreChat Deployment Guide

## Deployment Overview

**Important:** This is Phase 1 of a 3-phase deployment:
1. **Infrastructure** (this guide) - Deploy chat interface foundation
2. **AI Models** (pending) - Configure AI capabilities for conversation
3. **MCP Integration** (pending) - Connect facility management tools


**Post-Deployment State:**

- Interface loads with welcome message
- All services running healthy (MongoDB, Meilisearch, RAG API, etc.)
- Cannot send messages yet (no AI models configured)
- No facility management tools available (MCP not connected)

This is expected behavior - not an error.

## Prerequisites

- Ubuntu server with Docker and Docker Compose installed
- Git installed
- Minimum 4GB RAM, 10GB disk space
- Network access to port 3080

## Deployment Steps

### 1. Clone Pre-Configured Repository

This repository contains LibreChat deployment files.

```bash
git clone https://github.com/veloxforce/archibus-deploy.git
cd archibus-deploy
```

**Note:** All necessary configurations are already included.

### 2. Environment Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
```

**Required modifications in `.env`:**
- Update `HOST` and `PORT` if needed (defaults: localhost:3080)

**Example configuration:**
```bash
# Default settings (modify if needed)
HOST=localhost
PORT=3080
```

### 3. Deploy with Docker

Build and start all services:

```bash
docker compose up -d --build
```

This will:
- Build LibreChat application
- Start MongoDB database
- Start Meilisearch for conversation search
- Start RAG API for document processing
- Start the main LibreChat application

### 4. Verify Deployment

**Check service status:**
```bash
docker compose ps
```

All containers should show "Up" status.

**Access the application:**
- Open browser to `http://localhost:3080`
- You should see the LibreChat interface

### 5. Create Admin Account

1. Navigate to `http://localhost:3080`
2. Click "Sign up" to create your admin account
3. Complete registration process

## Next Steps

This completes infrastructure deployment. The system now requires:

1. **Model Configuration** (see README.MODEL-CONFIGURATION.md) - Enable AI conversation capabilities
2. **MCP Integration** (see README.MCP-CONFIGURATION.md) - Connect Bruce BEM facility tools

**Current Status:** Infrastructure ready, awaiting model configuration strategy from management.