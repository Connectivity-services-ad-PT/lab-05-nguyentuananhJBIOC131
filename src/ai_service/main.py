from fastapi import FastAPI

app = FastAPI(title="AI Mock Service - Team IoT")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ai-service"}

@app.post("/predict")
def predict_mock(data: dict):
    return {"status": "success", "prediction": "anomaly_not_detected", "confidence": 0.99}