#!/usr/bin/env bash
export SOURCE=examples/GetTransactiveValues
export CONFIG=examples/GetTransactiveValues/config

export TAG=getValues

# Uncomment to make this agent the platform historian.
#export AGENT_VIP_IDENTITY=platform.historian

./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable