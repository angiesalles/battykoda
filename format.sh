#!/bin/bash
set -e

# Colors for better output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Running isort to sort imports...${NC}"
docker compose exec -T web isort .

echo -e "${YELLOW}Running black to format code...${NC}"
docker compose exec -T web black .

echo -e "${GREEN}Code formatting complete!${NC}"
echo -e "${YELLOW}Note: flake8 issues must be fixed manually. Run './lint.sh' to check for remaining issues.${NC}"