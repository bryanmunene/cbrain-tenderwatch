# Setup AI Features for TenderWatch
# Run this script to install and configure AI/ML capabilities

Write-Host "🤖 TenderWatch AI/ML Setup" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# Step 1: Install AI libraries
Write-Host "📦 Step 1: Installing AI libraries..." -ForegroundColor Yellow
Write-Host "This may take 5-10 minutes on first run (downloading ~500MB)`n"

cd tenderwatch_app
pip install --upgrade pip
pip install sentence-transformers spacy scikit-learn torch numpy

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to install AI libraries" -ForegroundColor Red
    exit 1
}

Write-Host "✅ AI libraries installed`n" -ForegroundColor Green

# Step 2: Download spaCy model
Write-Host "📥 Step 2: Downloading spaCy language model..." -ForegroundColor Yellow
python -m spacy download en_core_web_sm

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to download spaCy model" -ForegroundColor Red
    exit 1
}

Write-Host "✅ spaCy model downloaded`n" -ForegroundColor Green

# Step 3: Migrate database
Write-Host "🔄 Step 3: Migrating database schema..." -ForegroundColor Yellow
python migrate_ai_db.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Database migration failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Database migrated`n" -ForegroundColor Green

# Step 4: Test installation
Write-Host "🧪 Step 4: Testing AI features..." -ForegroundColor Yellow
python -c "from app.ai_scoring import semantic_score; result = semantic_score('EDMS procurement tender'); print(f'Test score: {result[0]}')"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ AI features test failed" -ForegroundColor Red
    exit 1
}

Write-Host "✅ AI features working!`n" -ForegroundColor Green

# Done
Write-Host "`n🎉 Setup Complete!" -ForegroundColor Green
Write-Host "================================`n" -ForegroundColor Cyan
Write-Host "Your TenderWatch app now includes:" -ForegroundColor White
Write-Host "  ✅ Semantic scoring with embeddings" -ForegroundColor White
Write-Host "  ✅ Entity extraction (buyer, budget, deadline)" -ForegroundColor White
Write-Host "  ✅ Adaptive learning from your preferences`n" -ForegroundColor White

Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Restart your app:" -ForegroundColor White
Write-Host "     streamlit run streamlit_app.py" -ForegroundColor Cyan
Write-Host "     OR" -ForegroundColor White
Write-Host "     python run.py`n" -ForegroundColor Cyan
Write-Host "  2. Run a scan to test AI scoring" -ForegroundColor White
Write-Host "  3. Save/favorite tenders to train the learning model`n" -ForegroundColor White

Write-Host "📖 See AI_FEATURES.md for full documentation`n" -ForegroundColor Yellow
