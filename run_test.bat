@echo off
title Waha Bot - Test Runner
echo ============================================
echo   Waha Bot - Rebuild ^& Test
echo   (Incluye WAHA + API Bot)
echo ============================================
echo.

:: 1. Bajar contenedores existentes
echo [1/4] Deteniendo contenedores anteriores...
docker compose down
echo.

:: 2. Rebuild y levantar (ambos: waha + api)
echo [2/4] Construyendo y levantando AMBOS servicios (waha + api)...
docker compose up -d --build
echo.

:: 3. Esperar a que los contenedores arranquen
echo [3/4] Esperando que los servicios inicien (20s)...
timeout /t 20 /nobreak >nul

:: 4. Verificar estado
echo.
echo ============================================
echo   Estado de los contenedores:
echo ============================================
docker compose ps
echo.

:: 5. Mostrar ultimos logs de la API (para verificar que Gemini arranco bien)
echo ============================================
echo   Ultimos logs del servicio API:
echo ============================================
docker compose logs api --tail=30
echo.

:: 6. Abrir dashboard de WAHA en el navegador
echo Abriendo WAHA Dashboard en http://localhost:3000 ...
start http://localhost:3000

echo.
echo ============================================
echo   SERVICIOS ACTIVOS:
echo   - WAHA Dashboard: http://localhost:3000
echo     Usuario: admin
echo     Pass:    f6e75508bb61453f8bfc0fd2360eabb9
echo.
echo   - API Bot:        http://localhost:5006
echo ============================================
echo.
echo Mostrando logs en vivo (Ctrl+C para salir)...
echo.
docker compose logs -f --tail=50
