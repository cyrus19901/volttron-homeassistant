#!/usr/bin/env bash
export SOURCE=/home/pi/volttron-homeassistant/examples/HEMSAgent
export CONFIG=/home/pi/volttron-homeassistant/examples/HEMSAgent/HEMS_config

export TAG=HEMS

# Uncomment to make this agent the platform historian.
#export AGENT_VIP_IDENTITY=platform.historian
export AGENT_VIP_IDENTITY='HEMS'
./scripts/core/make-agent.sh

# To set the agent to autostart with the platform, pass "enable"
# to make-agent.sh: ./scripts/core/make-agent.sh enable
