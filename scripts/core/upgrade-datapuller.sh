#!/usr/bin/env bash

# Build a temp file string for use with the configuration
export CONFIG=$(mktemp /tmp/abc-script.XXXXXX)

cat > $CONFIG <<EOL
{

    "agentid": "puller",
	"source-vip": "tcp://127.0.0.1:23916",
    "source-serverkey": "PjeDETJFBAFq22XUf6RZRfMPmMVddxX-wMHntUYmeSw",
    "custom_topic_list": [],
    "services_topic_list": [
        "devices", "analysis", "record", "datalogger", "actuators"
    ],
    "topic_replace_list": [
	    #{"from": "FromString", "to": "ToString"}
    ]
}

EOL

export SOURCE=examples/DataPuller/
export TAG=datapuller

# Uncomment this to set the identity of the agent. Overrides the platform default identity and the agent's
# preferred identity.
export AGENT_VIP_IDENTITY="datapuller"

./scripts/core/upgrade-agent.sh enable

rm $CONFIG 
