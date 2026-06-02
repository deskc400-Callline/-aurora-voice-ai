#!/bin/bash
# Aurora Deployment Script

echo "🌙 Aurora WebRTC Voice System - Deployment"
echo "=========================================="

# Check for required env vars
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY not set"
    echo "   Get one at: https://platform.openai.com"
    exit 1
fi

echo "✅ OPENAI_API_KEY found"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found."
    exit 1
fi

echo "✅ Docker found"

# Start services
echo ""
echo "🚀 Starting services..."
docker-compose up --build -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Check health
echo ""
echo "🏥 Checking health..."
curl -s http://localhost:8000/api/health || echo "⚠️  Health check failed (may still be starting)"

echo ""
echo "🌙 Aurora is ready!"
echo "   Local: http://localhost:8000"
echo ""
echo "📖 To deploy to Railway:"
echo "   1. Push to GitHub"
echo "   2. Connect repo at https://railway.app"
echo "   3. Add PostgreSQL + Redis services"
echo "   4. Set environment variables"
echo ""
echo "🎙️  Press Spacebar to speak during calls"
echo ""
