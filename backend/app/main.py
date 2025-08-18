from fastapi import FastAPI

# Create the FastAPI application object
app = FastAPI()

# Define a route that responds to HTTP GET /ping
@app.get("/ping")
def ping():
    # Returning a Python dict automatically becomes JSON: {"message":"pong"}
    return {"message": "pong"}
