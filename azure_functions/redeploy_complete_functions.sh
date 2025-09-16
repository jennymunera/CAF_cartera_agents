#!/usr/bin/env bash
set -euo pipefail

# Always run from this script's directory so relative paths work
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables if a .env file exists (repo root or here)
if [ -f ../.env ]; then
  # shellcheck disable=SC1091
  source ../.env
elif [ -f ./.env ]; then
  # shellcheck disable=SC1091
  source ./.env
fi

# Deployment targets (can be overridden via environment)
# Defaults set to the requested Function App and existing RG
FUNCTION_APP_NAME="${FUNCTION_APP_NAME:-azfunc-analisis-batch-MVP-CARTERA-CR}"
RESOURCE_GROUP="${RESOURCE_GROUP:-RG-POC-CARTERA-CR}"
DEPLOYMENT_ZIP="deployment_complete.zip"
# App settings sync opt-in (0 = no, 1 = yes)
SYNC_APP_SETTINGS="${SYNC_APP_SETTINGS:-0}"
# Seconds to wait after changing settings to let SCM restart
SCM_WARMUP_SECONDS="${SCM_WARMUP_SECONDS:-25}"

echo "🚀 Despliegue Azure Functions (${FUNCTION_APP_NAME})"

# 0) Sin activación automática de entorno virtual
echo "ℹ️  No se activa entorno virtual automáticamente. Actívalo manualmente si aplica."

# 1) Validaciones de raíz
[ -f "host.json" ] || { echo "❌ host.json no encontrado en $(pwd)"; exit 1; }
[ -f "requirements.txt" ] || { echo "❌ requirements.txt no encontrado"; exit 1; }
[ -d "OpenAiProcess" ] || { echo "❌ Falta carpeta OpenAiProcess/"; exit 1; }
[ -d "PoolingProcess" ] || { echo "❌ Falta carpeta PoolingProcess/"; exit 1; }
[ -d "FinalCsvProcess" ] || { echo "❌ Falta carpeta FinalCsvProcess/"; exit 1; }
[ -d "shared_code" ] || { echo "⚠️  shared_code/ no existe. Si tienes módulos locales, esto causará import errors."; }

# 2) Limpiar ZIP previo
rm -f "$DEPLOYMENT_ZIP"

# 3) Armar ZIP (sin venv local ni __pycache__)
echo "📦 Empaquetando..."
# Construir la lista de archivos a incluir de forma segura
ZIP_FILES=()

# Requeridos (ya validados arriba)
ZIP_FILES+=(host.json requirements.txt OpenAiProcess/ PoolingProcess/ FinalCsvProcess/)

# Opcional: shared_code/
if [[ -d shared_code ]]; then ZIP_FILES+=(shared_code/); fi

# Opcionales: prompts con espacios
for f in "prompt Auditoria.txt" "prompt Desembolsos.txt" "prompt Productos.txt"; do
  [[ -f "$f" ]] && ZIP_FILES+=("$f")
done

# Incluir .funcignore solo si existe para evitar warnings de zip
if [[ -f .funcignore ]]; then ZIP_FILES+=(.funcignore); fi

zip -r "$DEPLOYMENT_ZIP" "${ZIP_FILES[@]}" \
  -x "*/__pycache__/*" ".venv/*" "venv/*" ".python_packages/*" "local.settings.json"

echo "📋 Contenido del ZIP:"
zip -sf "$DEPLOYMENT_ZIP"

# 5) Autenticación Azure
echo "🔐 Verificando autenticación Azure..."
az account show -o table >/dev/null

# 6) Construir y aplicar App Settings en un solo llamado
SETTINGS_TO_APPLY=()

# 6.1) Cargar settings desde local.settings.json si está habilitado
if [[ "$SYNC_APP_SETTINGS" = "1" ]] && [ -f "local.settings.json" ]; then
  echo "🔧 Preparando App Settings desde local.settings.json..."
  while IFS=$'\t' read -r KEY VALUE; do
    [ -z "$KEY" ] && continue
    if [[ "$KEY" == "AzureWebJobsStorage" && "$VALUE" == *"UseDevelopmentStorage=true"* ]]; then
      echo "   • $KEY (omitido: UseDevelopmentStorage=true detectado)"
      continue
    fi
    echo "   • $KEY"
    SETTINGS_TO_APPLY+=("$KEY=$VALUE")
  done < <(
    python3 - <<'PY'
import json
from pathlib import Path
p = Path('local.settings.json')
data = json.loads(p.read_text(encoding='utf-8'))
values = data.get('Values', {})
for k, v in values.items():
    if v is None:
        v = ''
    print(f"{k}\t{v}")
PY
  )
else
  echo "ℹ️  Sincronización de App Settings omitida (establece SYNC_APP_SETTINGS=1 para habilitar)"
fi

# 6.2) Forzar Oryx remoto mediante app settings (añadir al final para asegurar precedencia)
SETTINGS_TO_APPLY+=(
  "SCM_DO_BUILD_DURING_DEPLOYMENT=true"
  "ENABLE_ORYX_BUILD=true"
)

echo "📝 Aplicando ${#SETTINGS_TO_APPLY[@]} App Settings en una sola operación..."
az functionapp config appsettings set \
  -g "$RESOURCE_GROUP" -n "$FUNCTION_APP_NAME" \
  --settings ${SETTINGS_TO_APPLY[@]} >/dev/null

# Asegurar que NO usamos Run-From-Package (quitar/neutralizar si existe)
echo "🧹 Deshabilitando WEBSITE_RUN_FROM_PACKAGE si está configurado..."
# Opción 1: ponerlo en 0 (efecto: no run-from-package)
az functionapp config appsettings set \
  -g "$RESOURCE_GROUP" -n "$FUNCTION_APP_NAME" \
  --settings WEBSITE_RUN_FROM_PACKAGE=0 >/dev/null || true
# Opción 2: eliminar el setting si existe (best-effort)
az functionapp config appsettings delete \
  -g "$RESOURCE_GROUP" -n "$FUNCTION_APP_NAME" \
  --setting-names WEBSITE_RUN_FROM_PACKAGE >/dev/null || true

# 7) Espera de calentamiento del sitio SCM para evitar reinicio durante el deploy
echo "⏳ Esperando ${SCM_WARMUP_SECONDS}s para que SCM reinicie y propague settings..."
sleep "$SCM_WARMUP_SECONDS"

# 8) Despliegue (siempre con Oryx remoto) con reintentos
echo "☁️  Desplegando con Oryx remoto (zip deploy vía webapp)..."

max_retries=3
attempt=1
until [ $attempt -gt $max_retries ]; do
  echo "➡️  Intento $attempt/$max_retries"
  if az webapp deployment source config-zip \
      -g "$RESOURCE_GROUP" -n "$FUNCTION_APP_NAME" \
      --src "$DEPLOYMENT_ZIP" \
      --timeout 1800 \
      --verbose; then
    echo "✅ Despliegue enviado satisfactoriamente"
    break
  fi
  if [ $attempt -eq $max_retries ]; then
    echo "❌ Falló el despliegue tras $max_retries intentos"
    exit 1
  fi
  sleep_seconds=$(( 10 * attempt ))
  echo "⏳ Esperando ${sleep_seconds}s antes de reintentar..."
  sleep "$sleep_seconds"
  attempt=$(( attempt + 1 ))
done

echo "📜 Consultando logs de despliegue (best-effort)..."
az webapp log deployment show -n "$FUNCTION_APP_NAME" -g "$RESOURCE_GROUP" || true

echo "✅ Despliegue enviado. Consultando logs..."
az webapp log deployment show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" || true
