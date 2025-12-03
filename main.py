from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import json
import logging

from services.asr_service import ASRService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="语音识别服务")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化ASR服务
logger.info("初始化ASR服务...")
asr_service = ASRService()
logger.info("服务初始化完成!")

@app.get("/")
async def root():
    return {
        "service": "ASR语音识别服务",
        "model": "paraformer-zh-streaming",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy" if asr_service.is_ready() else "not ready",
        "stats": asr_service.get_stats()
    }

@app.websocket("/ws/asr")
async def websocket_asr(websocket: WebSocket):
    """WebSocket流式语音识别"""
    await websocket.accept()
    logger.info("客户端已连接")
    
    session = asr_service.create_session()
    
    try:
        while True:
            message = await websocket.receive()
            
            # 处理控制信号
            if "text" in message:
                data = json.loads(message["text"])
                
                if data.get("action") == "start":
                    # 开始新会话
                    session = asr_service.create_session()
                    await websocket.send_json({
                        "type": "status",
                        "status": "ready",
                        "session_id": session
                    })
                    continue
                
                if data.get("action") == "stop":
                    # 停止并获取最终结果
                    final_text = asr_service.finalize_session(session)
                    await websocket.send_json({
                        "type": "final",
                        "text": final_text,
                        "status": "completed"
                    })
                    # 重置会话
                    session = asr_service.create_session()
                    continue
            
            # 处理音频数据
            if "bytes" in message:
                audio_bytes = message["bytes"]
                audio_chunk = np.frombuffer(audio_bytes, dtype=np.float32)
                
                if len(audio_chunk) < 100:
                    continue
                
                # 流式识别
                result = asr_service.process_chunk(session, audio_chunk)
                
                if result:
                    # 发送实时结果
                    await websocket.send_json({
                        "type": "partial",
                        "text": result["accumulated_text"],
                        "chunk": result["current_text"],
                        "status": "recognizing"
                    })
                    
    except WebSocketDisconnect:
        logger.info("客户端断开连接")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        asr_service.cleanup_session(session)

@app.post("/api/asr/file")
async def upload_audio_file(file: UploadFile = File(...)):
    """上传音频文件识别（非实时）"""
    try:
        audio_bytes = await file.read()
        result = asr_service.recognize_file(audio_bytes)
        
        return {
            "success": True,
            "text": result["text"],
            "duration": result["duration"]
        }
    except Exception as e:
        logger.error(f"文件识别错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")