# backend/app.py (简化的启动入口)
import uvicorn
from main import app
from config import config

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info"
    )