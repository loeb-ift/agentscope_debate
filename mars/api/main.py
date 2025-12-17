from fastapi import FastAPI

app = FastAPI(title="MARS Research API", version="2.0.0")

@app.get("/")
def read_root():
    return {"message": "Welcome to MARS Research API V2"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "mars-api"}