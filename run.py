import uvicorn

if __name__ == "__main__":
    print("=========================================================")
    print("  TalentAI: Autonomous Resume Screening Agent Starting  ")
    print("=========================================================")
    print("  Employer Portal & Candidate Portal: http://127.0.0.1:8000")
    print("  API Docs & OpenAPI: http://127.0.0.1:8000/docs")
    print("  Live Excel Synchronizer: records/screened_candidates.xlsx")
    print("=========================================================\n")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
