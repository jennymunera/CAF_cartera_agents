# Script de deployment para Azure Function con Service Bus trigger
# Requiere Azure CLI instalado y autenticado

param(
    [Parameter(Mandatory=$true)]
    [string]$SubscriptionId = "6e30581f-5e6d-4f9f-8339-420301cce5f4",
    
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "RG-POC-CARTERA-CR",
    
    [Parameter(Mandatory=$false)]
    [string]$FunctionAppName = "azfunc-analisis-MVP-CARTERA-CR",
    
    [Parameter(Mandatory=$false)]
    [string]$StorageAccount = "asmvpcarteracr",
    
    [Parameter(Mandatory=$false)]
    [string]$ServiceBusNamespace = "sb-messaging-mvp-cartera-cr",
    
    [Parameter(Mandatory=$false)]
    [string]$QueueName = "analysis-event-queue",
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "East US",
    
    [Parameter(Mandatory=$false)]
    [string]$AppInsightsName = "ai-analisis-MVP-CARTERA-CR"
)

Write-Host "🚀 Iniciando deployment de Azure Function" -ForegroundColor Green
Write-Host "📋 Parámetros:" -ForegroundColor Yellow
Write-Host "   - Subscription: $SubscriptionId" -ForegroundColor White
Write-Host "   - Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "   - Function App: $FunctionAppName" -ForegroundColor White
Write-Host "   - Storage Account: $StorageAccount" -ForegroundColor White
Write-Host "   - Service Bus: $ServiceBusNamespace" -ForegroundColor White
Write-Host "   - Queue: $QueueName" -ForegroundColor White
Write-Host "   - Location: $Location" -ForegroundColor White

# Configurar suscripción
Write-Host "🔧 Configurando suscripción..." -ForegroundColor Blue
az account set --subscription $SubscriptionId

# Verificar que el Resource Group existe
Write-Host "📁 Verificando Resource Group..." -ForegroundColor Blue
$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "false") {
    Write-Host "❌ Resource Group $ResourceGroup no existe. Creándolo..." -ForegroundColor Red
    az group create --name $ResourceGroup --location $Location
    Write-Host "✅ Resource Group creado" -ForegroundColor Green
} else {
    Write-Host "✅ Resource Group existe" -ForegroundColor Green
}

# Crear Application Insights
Write-Host "📊 Creando Application Insights..." -ForegroundColor Blue
$appInsights = az monitor app-insights component create `
    --app $AppInsightsName `
    --location $Location `
    --resource-group $ResourceGroup `
    --application-type web `
    --query "instrumentationKey" `
    --output tsv

if ($appInsights) {
    Write-Host "✅ Application Insights creado: $appInsights" -ForegroundColor Green
} else {
    Write-Host "⚠️  Application Insights ya existe o error en creación" -ForegroundColor Yellow
    $appInsights = az monitor app-insights component show `
        --app $AppInsightsName `
        --resource-group $ResourceGroup `
        --query "instrumentationKey" `
        --output tsv
}

# Verificar Storage Account
Write-Host "💾 Verificando Storage Account..." -ForegroundColor Blue
$storageExists = az storage account check-name --name $StorageAccount --query "nameAvailable" --output tsv
if ($storageExists -eq "false") {
    Write-Host "✅ Storage Account existe" -ForegroundColor Green
} else {
    Write-Host "❌ Storage Account $StorageAccount no existe" -ForegroundColor Red
    exit 1
}

# Obtener Storage Account Key
$storageKey = az storage account keys list `
    --resource-group $ResourceGroup `
    --account-name $StorageAccount `
    --query "[0].value" `
    --output tsv

# Verificar Service Bus Namespace
Write-Host "🚌 Verificando Service Bus Namespace..." -ForegroundColor Blue
$serviceBusExists = az servicebus namespace exists --name $ServiceBusNamespace --query "nameAvailable" --output tsv
if ($serviceBusExists -eq "false") {
    Write-Host "✅ Service Bus Namespace existe" -ForegroundColor Green
} else {
    Write-Host "❌ Service Bus Namespace $ServiceBusNamespace no existe" -ForegroundColor Red
    exit 1
}

# Obtener Service Bus Connection String
$serviceBusConnectionString = az servicebus namespace authorization-rule keys list `
    --resource-group $ResourceGroup `
    --namespace-name $ServiceBusNamespace `
    --name RootManageSharedAccessKey `
    --query "primaryConnectionString" `
    --output tsv

# Verificar que la cola existe
Write-Host "📬 Verificando cola Service Bus..." -ForegroundColor Blue
$queueExists = az servicebus queue show `
    --resource-group $ResourceGroup `
    --namespace-name $ServiceBusNamespace `
    --name $QueueName `
    --query "name" `
    --output tsv 2>$null

if (-not $queueExists) {
    Write-Host "📬 Creando cola Service Bus..." -ForegroundColor Blue
    az servicebus queue create `
        --resource-group $ResourceGroup `
        --namespace-name $ServiceBusNamespace `
        --name $QueueName `
        --max-size 1024
    Write-Host "✅ Cola Service Bus creada" -ForegroundColor Green
} else {
    Write-Host "✅ Cola Service Bus existe" -ForegroundColor Green
}

# Crear Function App
Write-Host "⚡ Creando Function App..." -ForegroundColor Blue
$functionApp = az functionapp create `
    --resource-group $ResourceGroup `
    --consumption-plan-location $Location `
    --runtime python `
    --runtime-version 3.11 `
    --functions-version 4 `
    --name $FunctionAppName `
    --storage-account $StorageAccount `
    --app-insights $AppInsightsName `
    --query "name" `
    --output tsv

if ($functionApp) {
    Write-Host "✅ Function App creado: $functionApp" -ForegroundColor Green
} else {
    Write-Host "⚠️  Function App ya existe o error en creación" -ForegroundColor Yellow
}

# Configurar Application Settings
Write-Host "⚙️  Configurando Application Settings..." -ForegroundColor Blue

# Leer variables del archivo .env del proyecto principal
$envFile = "../.env"
if (Test-Path $envFile) {
    Write-Host "📄 Leyendo configuración desde .env..." -ForegroundColor Blue
    $envVars = @{}
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $envVars[$matches[1]] = $matches[2]
        }
    }
    
    # Configurar variables de entorno en Function App
    az functionapp config appsettings set `
        --name $FunctionAppName `
        --resource-group $ResourceGroup `
        --settings `
            "ServiceBusConnectionString=$serviceBusConnectionString" `
            "AZURE_STORAGE_ACCOUNT=$StorageAccount" `
            "AZURE_STORAGE_KEY=$storageKey" `
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=$($envVars['AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'])" `
            "AZURE_DOCUMENT_INTELLIGENCE_KEY=$($envVars['AZURE_DOCUMENT_INTELLIGENCE_KEY'])" `
            "AZURE_OPENAI_API_KEY=$($envVars['AZURE_OPENAI_API_KEY'])" `
            "AZURE_OPENAI_ENDPOINT=$($envVars['AZURE_OPENAI_ENDPOINT'])" `
            "AZURE_OPENAI_API_VERSION=$($envVars['AZURE_OPENAI_API_VERSION'])" `
            "AZURE_OPENAI_DEPLOYMENT_NAME=$($envVars['AZURE_OPENAI_DEPLOYMENT_NAME'])" `
            "APPINSIGHTS_INSTRUMENTATIONKEY=$appInsights" `
            "PYTHON_ISOLATE_WORKER_DEPENDENCIES=1"
            
    Write-Host "✅ Variables de entorno configuradas" -ForegroundColor Green
} else {
    Write-Host "⚠️  Archivo .env no encontrado. Configurar manualmente las variables." -ForegroundColor Yellow
}

# Crear archivo ZIP para deployment
Write-Host "📦 Creando paquete de deployment..." -ForegroundColor Blue
$zipFile = "function-deployment.zip"
if (Test-Path $zipFile) {
    Remove-Item $zipFile
}

# Comprimir archivos (excluyendo archivos innecesarios)
Compress-Archive -Path "OpenAiProcess_local", "shared", "requirements.txt", "host.json" -DestinationPath $zipFile
Write-Host "✅ Paquete creado: $zipFile" -ForegroundColor Green

# Deploy Function
Write-Host "🚀 Deployando Function..." -ForegroundColor Blue
az functionapp deployment source config-zip `
    --resource-group $ResourceGroup `
    --name $FunctionAppName `
    --src $zipFile

Write-Host "✅ Deployment completado" -ForegroundColor Green

# Mostrar información final
Write-Host "" -ForegroundColor White
Write-Host "🎉 DEPLOYMENT COMPLETADO EXITOSAMENTE" -ForegroundColor Green
Write-Host "" -ForegroundColor White
Write-Host "📋 Información del deployment:" -ForegroundColor Yellow
Write-Host "   - Function App: $FunctionAppName" -ForegroundColor White
Write-Host "   - Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host "   - Service Bus Queue: $ServiceBusNamespace/$QueueName" -ForegroundColor White
Write-Host "   - Storage Account: $StorageAccount" -ForegroundColor White
Write-Host "   - Application Insights: $AppInsightsName" -ForegroundColor White
Write-Host "" -ForegroundColor White
Write-Host "🔗 URLs útiles:" -ForegroundColor Yellow
Write-Host "   - Function App: https://$FunctionAppName.azurewebsites.net" -ForegroundColor White
Write-Host "   - Azure Portal: https://portal.azure.com/#@/resource/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/overview" -ForegroundColor White
Write-Host "" -ForegroundColor White
Write-Host "📨 Para probar, envía un mensaje a la cola con formato:" -ForegroundColor Yellow
Write-Host '   {"projectName": "test_project", "requestId": "12345"}' -ForegroundColor White

# Limpiar archivo temporal
Remove-Item $zipFile -ErrorAction SilentlyContinue

Write-Host "" -ForegroundColor White
Write-Host "✅ Script completado" -ForegroundColor Green