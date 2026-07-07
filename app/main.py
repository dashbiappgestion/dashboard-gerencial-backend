from fastapi import FastAPI

app = FastAPI(title="Dashboard Gerencial API")

@app.get("/")
def root():
    return {"status": "ok"}
    