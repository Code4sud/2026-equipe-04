# Prépare la configuration puis démarre toute l'application avec Docker.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Die {
    param([string]$Message)
    Write-Error "Erreur : $Message"
    exit 1
}

function Setting {
    param([string]$Name)

    if (-not (Test-Path ".env")) {
        return ""
    }

    $lines = Get-Content ".env"
    $matches = $lines | Where-Object { $_ -match "^$([regex]::Escape($Name))=" }

    if ($matches) {
        return ($matches[-1] -split "=", 2)[1]
    }

    return ""
}

function Fill-Placeholder {
    param(
        [string]$File,
        [string]$Placeholder,
        [string]$Value
    )

    $content = Get-Content $File -Raw
    $content = $content.Replace($Placeholder, $Value)
    Set-Content -Path $File -Value $content -NoNewline
}

function New-Secret {
    param([int]$Bytes)

    $randomBytes = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()

    try {
        $rng.GetBytes($randomBytes)
    }
    finally {
        $rng.Dispose()
    }

    return [Convert]::ToHexString($randomBytes).ToLowerInvariant()
}

function Create-Env {
    $postgres = New-Secret 24
    $s3       = New-Secret 24
    $jwt      = New-Secret 32
    $psy      = New-Secret 8
    $youth    = New-Secret 8

    Copy-Item ".env.example" ".env"

    Fill-Placeholder ".env" "change-me-postgres" $postgres
    Fill-Placeholder ".env" "change-me-s3" $s3
    Fill-Placeholder ".env" "change-me-jwt" $jwt
    Fill-Placeholder ".env" "change-me-psy" $psy
    Fill-Placeholder ".env" "change-me-jeune" $youth

    Write-Host "Configuration créée dans .env, avec des secrets générés pour cette machine."
}

function Create-BackendEnv {
    Copy-Item "backend/.env.example" "backend/.env"

    Fill-Placeholder "backend/.env" "change-me-postgres" (Setting "POSTGRES_PASSWORD")
    Fill-Placeholder "backend/.env" "change-me-s3" (Setting "S3_SECRET_KEY")
    Fill-Placeholder "backend/.env" "change-me-jwt" (Setting "JWT_SECRET_KEY")

    if (-not $nativeOllama) {
        Fill-Placeholder "backend/.env" "localhost:11434" "localhost:$(Setting 'OLLAMA_PORT')"
    }
}

# Vérification des dépendances
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Die "Docker est introuvable. Installez Docker Desktop : https://www.docker.com/products/docker-desktop/"
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Die "Le plugin « docker compose » est introuvable."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Die "Docker est installé mais ne tourne pas. Démarrez-le puis relancez."
}

if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
    Die "openssl est introuvable."
}

# Détection d'Ollama natif sur macOS
$nativeOllama = $false

if ($IsMacOS -and
    (Get-Command ollama -ErrorAction SilentlyContinue)) {

    try {
        $response = Invoke-WebRequest `
            -Uri "http://localhost:11434/api/version" `
            -TimeoutSec 2 `
            -ErrorAction Stop

        if ($response.StatusCode -eq 200) {
            $nativeOllama = $true
        }
    }
    catch {
        $nativeOllama = $false
    }
}

# Création des fichiers de configuration
if (-not (Test-Path ".env")) {
    Create-Env
}

if (-not (Test-Path "backend/.env")) {
    Create-BackendEnv
}

# Configuration Ollama natif
$model = Setting "OLLAMA_MODEL"

if ($nativeOllama) {
    Write-Host "Ollama détecté sur ce Mac : il sera utilisé à la place du conteneur."

    $installedModels = ollama list 2>$null |
        Select-Object -Skip 1 |
        ForEach-Object { ($_ -split '\s+')[0] }

    if ($installedModels -notcontains $model -and
        $installedModels -notcontains "${model}:latest") {
        ollama pull $model

        if ($LASTEXITCODE -ne 0) {
            Die "Impossible de télécharger le modèle Ollama : $model"
        }
    }

    $env:OLLAMA_URL = "http://host.docker.internal:11434"
    $env:COMPOSE_PROFILES = ""
}

# Démarrage de Docker Compose
docker compose up -d --build

if ($LASTEXITCODE -ne 0) {
    Die "Impossible de démarrer les conteneurs Docker."
}

$port = Setting "FRONTEND_PORT"

Write-Host "Démarrage de l'application" -NoNewline

# Attente de disponibilité : 90 tentatives de 2 secondes
for ($i = 0; $i -lt 90; $i++) {
    try {
        $null = Invoke-WebRequest `
            -Uri "http://localhost:$port/api/health" `
            -TimeoutSec 2 `
            -ErrorAction Stop

        Write-Host "`n"
        Write-Host "Application prête : http://localhost:$port"
        Write-Host ""
        Write-Host "Comptes de démonstration :"
        Write-Host "  Psychologue : $(Setting 'SEED_PSY_EMAIL') / $(Setting 'SEED_PSY_PASSWORD')"
        Write-Host "  Jeune       : $(Setting 'SEED_YOUTH_EMAIL') / $(Setting 'SEED_YOUTH_PASSWORD')"
        Write-Host ""

        if (-not $nativeOllama -and $env:COMPOSE_PROFILES -eq "ollama") {
            Write-Host "Le modèle peut encore se télécharger (environ 4 Go) : docker compose logs -f ollama-pull"
        }

        exit 0
    }
    catch {
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
}

Write-Host "`n"
docker compose ps

Die "L'application ne répond pas. Consultez les journaux : docker compose logs backend"
