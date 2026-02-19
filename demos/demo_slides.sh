#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DEMO: Slideshow — Split-screen: LEFT=Live README / RIGHT=Oczekiwania+Walidacja
# ═══════════════════════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

if [ -f ".venv/bin/activate" ]; then source .venv/bin/activate 2>/dev/null; fi

BROWSER_PORT=${BROWSER_PORT:-9091}
SLIDES_DIR="$PROJECT_DIR/generated/slides"
mkdir -p "$SLIDES_DIR"

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║  DEMO: Slideshow — LEFT: Live README / RIGHT: Oczekiwania + Walidacja       ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  ${YELLOW}→${NC} Generuję prezentację HTML..."
python3 "$SCRIPT_DIR/_gen_slides.py" "$SLIDES_DIR"
echo -e "  ${GREEN}✓${NC} HTML: $SLIDES_DIR/index.html"

echo -e "  ${YELLOW}→${NC} Generuję PDF..."
python3 "$SCRIPT_DIR/_gen_slides_pdf.py" "$SLIDES_DIR"
echo -e "  ${GREEN}✓${NC} PDF: $SLIDES_DIR/marksync_flow.pdf"

# Start server
fuser -k "$BROWSER_PORT/tcp" 2>/dev/null || true
sleep 0.5

echo -e "  ${YELLOW}→${NC} Startuję serwer na porcie $BROWSER_PORT..."

cd "$SLIDES_DIR"
python3 -m http.server "$BROWSER_PORT" --bind 0.0.0.0 &
SERVER_PID=$!
cd "$PROJECT_DIR"
sleep 1

if kill -0 "$SERVER_PID" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Serwer: http://localhost:$BROWSER_PORT"
else
    echo -e "  ${RED}✗${NC} Nie udało się uruchomić serwera"
    exit 1
fi

URL="http://localhost:$BROWSER_PORT"
if command -v xdg-open &>/dev/null; then xdg-open "$URL" 2>/dev/null &
elif command -v open &>/dev/null; then open "$URL" 2>/dev/null &
fi

echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Prezentacja: ${BOLD}$URL${NC}"
echo -e "${GREEN}  ← → strzałki | Spacja = auto-play | Ctrl+C = stop${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""

trap "kill $SERVER_PID 2>/dev/null; echo -e '\n${YELLOW}Serwer zatrzymany.${NC}'" EXIT
wait "$SERVER_PID"
