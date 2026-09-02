def agent(observation, configuration):
    # Always take the safest no-op-ish legal action
    return {"action": "WAIT"}  # or whatever the null/cheap action is