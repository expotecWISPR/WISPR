#!/usr/bin/env bash
# Crea en CloudWatch las métricas de actividad de WISPR y el panel "WISPR".
#
# Se corre en AWS CloudShell (ícono >_ arriba en la consola), en la región de la EC2:
#   bash crear_metricas.sh
# Se puede correr varias veces: reemplaza lo que ya existe, no lo duplica.
#
# De dónde sale cada número: del registro de accesos de nginx (/var/log/nginx/access.log),
# que el agente de CloudWatch de la EC2 manda al grupo /wispr/nginx/access. No se cuenta desde
# Supabase porque la tabla `sessions` borra la fila al cerrar sesión: no sirve de historial.
#
# Lo que se cuenta (todo con respuesta del servidor, no intentos):
#   Ingresos        login completo: código de correo correcto (estudiante/profesor) o voucher (admin)
#   Registros       cuenta nueva verificada con el código del correo
#   LoginsFallidos  contraseña incorrecta (sirve para ver fuerza bruta)
#   Visitas         cargas de la página principal (web y app de escritorio; también bots)
#   Errores5xx      fallos del servidor (FastAPI o Node caídos, errores internos)

set -euo pipefail

REGION="us-east-2"
INSTANCE_ID="i-0bed484476a88a19f"
ACCESS="/wispr/nginx/access"
ERRORS="/wispr/nginx/error"
NS="WISPR"

export AWS_DEFAULT_REGION="$REGION"

# Formato "combined" de nginx (el de Ubuntu por defecto), 9 campos:
#   ip - usuario [fecha] "MÉTODO /ruta HTTP/x" estado bytes "referer" "navegador"
CAMPOS='ip, id, user, timestamp'
COLA='bytes, referer, agent'

# nombre_del_filtro | métrica | patrón (request, status)
FILTROS=(
  "wispr-ingresos-codigo|Ingresos|request=\"POST /api/players/login-verify *\", status=200"
  "wispr-ingresos-voucher|Ingresos|request=\"POST /api/players/login-voucher *\", status=200"
  "wispr-registros|Registros|request=\"POST /api/players/verify *\", status=200"
  "wispr-logins-fallidos|LoginsFallidos|request=\"POST /api/players/login *\", status=401"
  "wispr-visitas|Visitas|request=\"GET / *\", status=200"
  "wispr-errores-5xx|Errores5xx|request, status=5*"
)

# Líneas de ejemplo para comprobar los patrones antes de crearlos.
EJEMPLOS=(
  '203.0.113.7 - - [16/Nov/2026:18:07:09 +0000] "POST /api/players/login-verify HTTP/1.1" 200 512 "https://wispr.training/" "Mozilla/5.0"'
  '203.0.113.7 - - [16/Nov/2026:18:07:09 +0000] "POST /api/players/login-voucher HTTP/1.1" 200 512 "https://wispr.training/" "Mozilla/5.0"'
  '203.0.113.7 - - [16/Nov/2026:18:07:09 +0000] "POST /api/players/verify HTTP/1.1" 200 512 "https://wispr.training/" "Mozilla/5.0"'
  '203.0.113.7 - - [16/Nov/2026:18:07:09 +0000] "POST /api/players/login HTTP/1.1" 401 80 "https://wispr.training/" "Mozilla/5.0"'
  '203.0.113.7 - - [16/Nov/2026:18:07:09 +0000] "GET / HTTP/1.1" 200 9000 "-" "Mozilla/5.0"'
  '203.0.113.7 - - [16/Nov/2026:18:07:09 +0000] "GET /api/challenges HTTP/1.1" 502 150 "-" "Mozilla/5.0"'
)

echo "== 1. Grupos de registros (30 días de retención)"
for g in "$ACCESS" "$ERRORS"; do
  aws logs create-log-group --log-group-name "$g" 2>/dev/null || true
  aws logs put-retention-policy --log-group-name "$g" --retention-in-days 30
  echo "   $g"
done

echo "== 2. Probar cada patrón con una línea que SÍ debe contar"
i=0
for f in "${FILTROS[@]}"; do
  IFS='|' read -r nombre metrica condicion <<<"$f"
  patron="[$CAMPOS, $condicion, $COLA]"
  coincide=$(aws logs test-metric-filter --filter-pattern "$patron" \
    --log-event-messages "${EJEMPLOS[$i]}" --query 'length(matches)' --output text)
  if [ "$coincide" != "1" ]; then
    echo "   FALLA $nombre: el patrón no reconoce su línea de ejemplo. No se creó nada más."
    exit 1
  fi
  echo "   ok  $nombre"
  i=$((i + 1))
done

echo "== 3. Crear los filtros de métricas"
for f in "${FILTROS[@]}"; do
  IFS='|' read -r nombre metrica condicion <<<"$f"
  aws logs put-metric-filter \
    --log-group-name "$ACCESS" \
    --filter-name "$nombre" \
    --filter-pattern "[$CAMPOS, $condicion, $COLA]" \
    --metric-transformations "metricName=$metrica,metricNamespace=$NS,metricValue=1,defaultValue=0"
  echo "   $nombre -> $NS/$metrica"
done

echo "== 4. Panel WISPR"
VISITANTES_QUERY="SOURCE '$ACCESS' | parse @message '* - * [*] \"* * *\" * *' as ip, usuario, fecha, metodo, ruta, protocolo, estado, bytes | filter metodo = 'GET' and ruta = '/' | stats count_distinct(ip) as visitantes_distintos by bin(1d)"

cat > /tmp/wispr-panel.json <<EOF
{
  "widgets": [
    { "type": "metric", "x": 0, "y": 0, "width": 12, "height": 6,
      "properties": { "title": "Ingresos y registros (por hora)", "region": "$REGION", "view": "timeSeries",
        "stat": "Sum", "period": 3600,
        "metrics": [ ["$NS", "Ingresos"], ["$NS", "Registros"] ] } },
    { "type": "metric", "x": 12, "y": 0, "width": 12, "height": 6,
      "properties": { "title": "Visitas a la página (por hora)", "region": "$REGION", "view": "timeSeries",
        "stat": "Sum", "period": 3600,
        "metrics": [ ["$NS", "Visitas"] ] } },
    { "type": "metric", "x": 0, "y": 6, "width": 8, "height": 6,
      "properties": { "title": "Totales del periodo", "region": "$REGION", "view": "singleValue",
        "stat": "Sum", "period": 2592000, "setPeriodToTimeRange": true,
        "metrics": [ ["$NS", "Ingresos"], ["$NS", "Registros"], ["$NS", "Visitas"] ] } },
    { "type": "metric", "x": 8, "y": 6, "width": 16, "height": 6,
      "properties": { "title": "Logins fallidos y errores del servidor (por hora)", "region": "$REGION",
        "view": "timeSeries", "stat": "Sum", "period": 3600,
        "metrics": [ ["$NS", "LoginsFallidos"], ["$NS", "Errores5xx"] ] } },
    { "type": "metric", "x": 0, "y": 12, "width": 12, "height": 6,
      "properties": { "title": "CPU de la EC2 (%)", "region": "$REGION", "view": "timeSeries",
        "stat": "Average", "period": 300,
        "metrics": [ ["AWS/EC2", "CPUUtilization", "InstanceId", "$INSTANCE_ID"] ] } },
    { "type": "metric", "x": 12, "y": 12, "width": 12, "height": 6,
      "properties": { "title": "Memoria y disco de la EC2 (%)", "region": "$REGION", "view": "timeSeries",
        "stat": "Average", "period": 300, "yAxis": { "left": { "min": 0, "max": 100 } },
        "metrics": [
          [ { "expression": "SEARCH('Namespace=\"$NS\" MetricName=\"mem_used_percent\"', 'Average', 300)",
              "id": "memoria", "label": "Memoria" } ],
          [ { "expression": "SEARCH('Namespace=\"$NS\" MetricName=\"disk_used_percent\"', 'Average', 300)",
              "id": "disco", "label": "Disco" } ]
        ] } },
    { "type": "log", "x": 0, "y": 18, "width": 24, "height": 6,
      "properties": { "title": "Visitantes distintos por día (IPs distintas)", "region": "$REGION",
        "view": "table", "query": $(printf '%s' "$VISITANTES_QUERY" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))') } }
  ]
}
EOF

aws cloudwatch put-dashboard --dashboard-name WISPR --dashboard-body file:///tmp/wispr-panel.json \
  --query 'DashboardValidationMessages' --output text
echo
echo "Listo. Panel: https://$REGION.console.aws.amazon.com/cloudwatch/home?region=$REGION#dashboards/dashboard/WISPR"
echo "Las métricas aparecen cuando el agente de la EC2 empiece a mandar registros (unos minutos)."
