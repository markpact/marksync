#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# MARKSYNC DEMO LAUNCHER — Główny skrypt do wyboru demo
# ═══════════════════════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

show_menu() {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                      MARKSYNC — Demo Launcher                               ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "  ${BOLD}1${NC})  ${CYAN}Pełny scenariusz${NC}       — Workflow od promptu do deploymentu + ewolucja"
    echo -e "      ${DIM}./demo_scenario.sh${NC}"
    echo ""
    echo -e "  ${BOLD}2${NC})  ${CYAN}Contract Builder${NC}      — Budowanie kontraktu z promptu (human/llm/script)"
    echo -e "      ${DIM}./demos/demo_contract.sh${NC}"
    echo ""
    echo -e "  ${BOLD}3${NC})  ${CYAN}Integrations${NC}          — Komunikacja: API, Shell, Email, Webhook, SSE"
    echo -e "      ${DIM}./demos/demo_integrations.sh${NC}"
    echo ""
    echo -e "  ${BOLD}4${NC})  ${CYAN}Browser View${NC}          — README + dane w przeglądarce (otwiera http)"
    echo -e "      ${DIM}./demos/demo_browser.sh${NC}"
    echo ""
    echo -e "  ${BOLD}5${NC})  ${CYAN}Slideshow${NC}             — Prezentacja w przeglądarce (← → strzałki)"
    echo -e "      ${DIM}./demos/demo_slides.sh${NC}"
    echo ""
    echo -e "  ${BOLD}6${NC})  ${CYAN}Wszystkie po kolei${NC}    — Uruchom demo 1→2→3→4 kaskadowo"
    echo ""
    echo -e "  ${BOLD}q${NC})  Wyjdź"
    echo ""
    echo -e "${DIM}  Ustaw DEMO_DELAY=2 aby zwolnić wyświetlanie (domyślnie 1s)${NC}"
    echo ""
}

run_demo() {
    local script="$1"
    local name="$2"
    echo -e "\n${BOLD}${GREEN}▶ Uruchamiam: $name${NC}\n"
    bash "$script"
    echo ""
    read -p "Naciśnij Enter aby wrócić do menu..." _
}

while true; do
    show_menu
    read -p "  Wybierz demo [1-6, q]: " choice

    case "$choice" in
        1)
            run_demo "$PROJECT_DIR/demo_scenario.sh" "Pełny scenariusz"
            ;;
        2)
            run_demo "$SCRIPT_DIR/demo_contract.sh" "Contract Builder"
            ;;
        3)
            run_demo "$SCRIPT_DIR/demo_integrations.sh" "Integrations"
            ;;
        4)
            echo -e "\n${BOLD}${GREEN}▶ Uruchamiam: Browser View${NC}\n"
            echo -e "${YELLOW}Serwer HTTP uruchomi się w tle. Ctrl+C aby zatrzymać.${NC}\n"
            bash "$SCRIPT_DIR/demo_browser.sh"
            ;;
        5)
            echo -e "\n${BOLD}${GREEN}▶ Uruchamiam: Slideshow${NC}\n"
            echo -e "${YELLOW}Prezentacja otworzy się w przeglądarce. Ctrl+C aby zatrzymać.${NC}\n"
            bash "$SCRIPT_DIR/demo_slides.sh"
            ;;
        6)
            echo -e "\n${BOLD}${GREEN}▶ Uruchamiam wszystkie demo kaskadowo...${NC}\n"
            export DEMO_DELAY=${DEMO_DELAY:-1}
            bash "$PROJECT_DIR/demo_scenario.sh"
            echo -e "\n${YELLOW}──────────────────────────────────────────────────────────────────${NC}"
            read -p "Naciśnij Enter aby kontynuować do Contract Builder..." _
            bash "$SCRIPT_DIR/demo_contract.sh"
            echo -e "\n${YELLOW}──────────────────────────────────────────────────────────────────${NC}"
            read -p "Naciśnij Enter aby kontynuować do Integrations..." _
            bash "$SCRIPT_DIR/demo_integrations.sh"
            echo -e "\n${YELLOW}──────────────────────────────────────────────────────────────────${NC}"
            read -p "Naciśnij Enter aby otworzyć Slideshow..." _
            bash "$SCRIPT_DIR/demo_slides.sh"
            ;;
        q|Q)
            echo -e "\n${YELLOW}Do widzenia!${NC}\n"
            exit 0
            ;;
        *)
            echo -e "\n${RED}Nieznana opcja: $choice${NC}"
            sleep 1
            ;;
    esac
done
