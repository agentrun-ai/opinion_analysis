from agent import opinion_agent, StateDeps, OpinionState

app = opinion_agent.to_ag_ui(deps=StateDeps(OpinionState()))

if __name__ == "__main__":
    # run the app
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
