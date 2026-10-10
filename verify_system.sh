#!/bin/bash

# CompareHub End-to-End System Verification Script
# This script tests the full integration: API -> Services -> Repository -> Providers

BASE_URL="http://localhost:8008"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🚀 Starting CompareHub E2E Verification..."
echo "--------------------------------------------------"

# --- SETUP ---
echo -n "Setting up test user... "
USER_RESP=$(curl -s -X POST "$BASE_URL/users/" \
     -H "Content-Type: application/json" \
     -d '{"username": "e2e_tester", "email": "e2e@example.com"}')

USER_ID=$(echo $USER_RESP | grep -o '"id":"[^"]*' | cut -d'"' -f4)

if [ -z "$USER_ID" ]; then
    echo -e "${RED}FAILED: Could not create test user${NC}"
    exit 1
fi
echo -e "${GREEN}SUCCESS${NC} (ID: $USER_ID)"

echo -n "Setting user preferences (alpha)... "
curl -s -X PUT "$BASE_URL/preferences/" \
     -H "X-User-ID: $USER_ID" \
     -H "Content-Type: application/json" \
     -d '{"preferred_provider_ids": ["alpha"]}' > /dev/null
echo -e "${GREEN}SUCCESS${NC}"

# --- TESTS ---

# Scenario 1: Global Success (Guest)
echo -n "Test 1: Guest Search (All Enabled) ... "
RESP=$(curl -s -X POST "$BASE_URL/search/" \
     -H "Content-Type: application/json" \
     -d '{"text": "Nimbus", "category": "ecommerce"}')
if echo "$RESP" | grep -q "alpha" && echo "$RESP" | grep -q "beta"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC} (Expected both alpha and beta)"
fi

# Scenario 2: User Preferences
echo -n "Test 2: User Preference Search ... "
RESP=$(curl -s -X POST "$BASE_URL/search/" \
     -H "X-User-ID: $USER_ID" \
     -H "Content-Type: application/json" \
     -d '{"text": "Nimbus", "category": "ecommerce"}')
if echo "$RESP" | grep -q "alpha" && ! echo "$RESP" | grep -q "beta"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC} (Expected only alpha)"
fi

# Scenario 3: Explicit Override
echo -n "Test 3: Explicit Selection Override ... "
RESP=$(curl -s -X POST "$BASE_URL/search/" \
     -H "X-User-ID: $USER_ID" \
     -H "Content-Type: application/json" \
     -d '{"text": "Nimbus", "category": "ecommerce", "providers": ["beta"]}')
if echo "$RESP" | grep -q "beta" && ! echo "$RESP" | grep -q "alpha"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC} (Expected only beta)"
fi

# Scenario 4: Zero Results
echo -n "Test 4: No Match Search ... "
RESP=$(curl -s -X POST "$BASE_URL/search/" \
     -H "Content-Type: application/json" \
     -d '{"text": "XyloPhone", "category": "ecommerce"}')
if echo "$RESP" | grep -q '"results":\[\]'; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC} (Expected empty results)"
fi

# Scenario 5: Transient Failure (Mock Flaky)
echo -n "Test 5: Transient Failure (Timeout) ... "
RESP=$(curl -s -X POST "$BASE_URL/search/" \
     -H "Content-Type: application/json" \
     -d '{"text": "Nimbus", "category": "ecommerce", "providers": ["mock-flaky"]}')
if echo "$RESP" | grep -qi "timeout"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC} (Expected timeout state. Response: $RESP)"
fi

# Scenario 6: Hard Blocked (Flipkart)
echo -n "Test 6: Hard Blocked (Unavailable) ... "
RESP=$(curl -s -X POST "$BASE_URL/search/" \
     -H "Content-Type: application/json" \
     -d '{"text": "Nimbus", "category": "ecommerce", "providers": ["flipkart"]}')
if echo "$RESP" | grep -qi "unavailable"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC} (Expected unavailable state. Response: $RESP)"
fi

# Scenario 7: Validation Error (Ghost Store)
echo -n "Test 7: Invalid Provider (422) ... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/search/" \
     -H "Content-Type: application/json" \
     -d '{"text": "Nimbus", "category": "ecommerce", "providers": ["ghost-store"]}')
if [ "$HTTP_CODE" == "422" ]; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC} (Expected HTTP 422, got $HTTP_CODE)"
fi

echo "--------------------------------------------------"
echo "✅ Verification Complete."
