set -euo pipefail

FUNCTION_APP_NAME="azfunc-analisis-MVP-CARTERA-CR"
RESOURCE_GROUP="RG-POC-CARTERA-CR"
DEPLOYMENT_ZIP="deployment_complete.zip"
USE_PREBUILD="${USE_PREBUILD:-0}"   # 0 = Oryx remoto, 1 = subir .python_packages ya construido (sin Oryx)

echo "🚀 Despliegue Azure Functions (${FUNCTION_APP_NAME})"

# 0) Activar entorno virtual si existe
if [ -d ".venv311" ]; then
  echo "🐍 Activando entorno virtual .venv311..."
  source .venv311/bin/activate
  echo "✅ Entorno virtual activado: $(which python)"
else
  echo "⚠️  No se encontró .venv311, usando Python del sistema"
fi

# 1) Validaciones de raíz
[ -f "host.json" ] || { echo "❌ host.json no encontrado. Ejecuta desde azure_functions/"; exit 1; }
[ -f "requirements.txt" ] || { echo "❌ requirements.txt no encontrado"; exit 1; }
[ -d "OpenAiProcess" ] || { echo "❌ Falta carpeta OpenAiProcess/"; exit 1; }
[ -d "PoolingProcess" ] || { echo "❌ Falta carpeta PoolingProcess/"; exit 1; }
[ -d "shared_code" ] || { echo "⚠️  shared_code/ no existe. Si tienes módulos locales, esto causará import errors."; }

# 2) Limpiar ZIP previo
rm -f "$DEPLOYMENT_ZIP"

# 3) (Opcional) Preconstruir dependencias para Linux y evitar Oryx
if [ "$USE_PREBUILD" = "1" ]; then
  echo "🛠️  Construyendo .python_packages (Linux) con Oryx build container..."
  docker run --rm -v "$PWD":/app -w /app mcr.microsoft.com/oryx/build:stable bash -lc '
    python3.11 -m venv .venv && . .venv/bin/activate &&
    python -m pip install -U pip &&
    pip install --no-cache-dir -r requirements.txt -t .python_packages/lib/site-packages
  '
  echo "✅ .python_packages construido"
fi

# 4) Armar ZIP (sin venv local ni __pycache__)
echo "📦 Empaquetando..."
zip -r "$DEPLOYMENT_ZIP" host.json requirements.txt .funcignore \
  OpenAiProcess/ PoolingProcess/ shared_code/ \
  "prompt Auditoria.txt" "prompt Desembolsos.txt" "prompt Productos.txt" \
  -x "*/__pycache__/*" ".venv/*" "venv/*" ".python_packages/*" "local.settings.json"

# Si USE_PREBUILD=1, agrega .python_packages al ZIP
if [ "$USE_PREBUILD" = "1" ]; then
  zip -r "$DEPLOYMENT_ZIP" .python_packages/ -x "*/__pycache__/*"
fi

echo "📋 Contenido del ZIP:"
zip -sf "$DEPLOYMENT_ZIP"

# 5) Autenticación Azure
echo "🔐 Verificando autenticación Azure..."
az account show -o table >/dev/null

# 6) Despliegue
echo "☁️  Desplegando (build remoto Oryx=$( [ "$USE_PREBUILD" = "0" ] && echo ON || echo OFF ))..."
if [ "$USE_PREBUILD" = "0" ]; then
  # Con Oryx remoto
  az functionapp deployment source config-zip \
    --name "$FUNCTION_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --src "$DEPLOYMENT_ZIP" \
    --build-remote true \
    --verbose
else
  # Sin Oryx (subimos paquete listo)
  az functionapp config appsettings set \
    -g "$RESOURCE_GROUP" -n "$FUNCTION_APP_NAME" \
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=false ENABLE_ORYX_BUILD=false >/dev/null
  az webapp deployment source config-zip \
    -g "$RESOURCE_GROUP" -n "$FUNCTION_APP_NAME" --src "$DEPLOYMENT_ZIP" --verbose
fi

echo "✅ Despliegue enviado. Consultando logs..."
az webapp log deployment show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" || true