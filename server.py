    secret: str
    url: str

@app.post("/quiz")
async def handle_quiz(request: Request):
    """Main endpoint that receives quiz tasks"""
    
    # Get the JSON data
    try:
        body = await request.json()
    except:
        return JSONResponse(status_code=400, content={"error": "Bad JSON"})
    
    # Check the data
    try:
        quiz_req = QuizRequest(**body)
    except:
        return JSONResponse(status_code=400, content={"error": "Missing fields"})
    
    # Verify email and secret
    if quiz_req.email != YOUR_EMAIL:
        return JSONResponse(status_code=403, content={"error": "Wrong email"})
    
    if quiz_req.secret != YOUR_SECRET:
        return JSONResponse(status_code=403, content={"error": "Wrong secret"})
    
    print(f"\n✓ Got quiz request: {quiz_req.url}")
    
    # Solve the quiz
    result = await solve_quiz_chain(quiz_req.url)
    
    if result.get('success'):
        return JSONResponse(status_code=200, content={
            "status": "success",
            "quizzes_solved": result.get('quizzes_solved', 0)
        })
    else:
        return JSONResponse(status_code=200, content={
            "status": "error",
            "message": "Failed to solve quiz"
        })

@app.get("/")
def home():
    """Home page"""
    return {"status": "online", "service": "Quiz Solver"}

if __name__ == "__main__":
    print("\n=== Quiz Solver Server ===")
    print(f"Email: {YOUR_EMAIL}")
    print(f"Port: {SERVER_PORT}")
    print(f"\nStarting server...\n")
    
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)