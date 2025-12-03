from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import json
import logging

from services.asr_service import ASRService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="语音识别服务")

# CORS - 允许来自demo.zjuicsr.cn的请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://demo.zjuicsr.cn:3780",
        "https://demo.zjuicsr.cn:3780",
        "http://demo.zjuicsr.cn",
        "https://demo.zjuicsr.cn",
        "*"  # 开发时可以用，生产环境建议限制
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化ASR服务
logger.info("=" * 60)
logger.info("初始化ASR服务...")
try:
    asr_service = ASRService()
    logger.info("✅ ASR服务初始化完成!")
except Exception as e:
    logger.error(f"❌ ASR服务初始化失败: {e}")
    raise
logger.info("=" * 60)

@app.get("/")
async def root():
    """根路径 - 服务信息"""
    return {
        "service": "ASR语音识别服务",
        "model": "paraformer-zh-streaming",
        "status": "running",
        "endpoints": {
            "websocket": "/ws/asr",
            "health": "/health",
            "upload": "/api/asr/file"
        },
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy" if asr_service.is_ready() else "not ready",
        "stats": asr_service.get_stats(),
        "service": "asr",
        "timestamp": np.datetime64('now').astype(str)
    }

@app.websocket("/ws/asr")
async def websocket_asr(websocket: WebSocket):
    """WebSocket流式语音识别"""
    client_host = None
    session = None
    
    try:
        await websocket.accept()
        client_host = websocket.client.host if websocket.client else "unknown"
        logger.info(f"📞 客户端已连接: {client_host}")
        
        # 创建会话
        session = asr_service.create_session()
        logger.info(f"🆕 创建会话: {session}")
        
        while True:
            message = await websocket.receive()
            
            # 处理控制信号
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    
                    if data.get("action") == "start":
                        # 开始新会话
                        if session:
                            asr_service.cleanup_session(session)
                        session = asr_service.create_session()
                        await websocket.send_json({
                            "type": "status",
                            "status": "ready",
                            "session_id": session
                        })
                        logger.info(f"▶️  会话开始: {session}")
                        continue
                    
                    if data.get("action") == "stop":
                        # 停止并获取最终结果
                        final_text = asr_service.finalize_session(session)
                        await websocket.send_json({
                            "type": "final",
                            "text": final_text,
                            "status": "completed"
                        })
                        logger.info(f"⏹️  会话结束: {session}")
                        logger.info(f"📝 最终结果: {final_text[:100]}...")
                        # 重置会话
                        session = asr_service.create_session()
                        continue
                        
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON解析错误: {e}")
                    continue
            
            # 处理音频数据
            if "bytes" in message:
                try:
                    audio_bytes = message["bytes"]
                    audio_chunk = np.frombuffer(audio_bytes, dtype=np.float32)
                    
                    # 跳过太短的音频块
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
                        logger.debug(f"🎤 识别块: {result['current_text']}")
                        
                except Exception as e:
                    logger.error(f"❌ 音频处理错误: {e}", exc_info=True)
                    
    except WebSocketDisconnect:
        logger.info(f"👋 客户端断开连接: {client_host}")
    except Exception as e:
        logger.error(f"❌ WebSocket错误: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        # 清理会话
        if session:
            asr_service.cleanup_session(session)
            logger.info(f"🧹 清理会话: {session}")

@app.post("/api/asr/file")
async def upload_audio_file(file: UploadFile = File(...)):
    """上传音频文件识别（非实时）"""
    try:
        logger.info(f"📁 收到文件上传: {file.filename}")
        audio_bytes = await file.read()
        logger.info(f"📊 文件大小: {len(audio_bytes)} bytes")
        
        result = asr_service.recognize_file(audio_bytes)
        
        logger.info(f"✅ 识别完成: {result['text'][:100]}...")
        
        return {
            "success": True,
            "text": result["text"],
            "duration": result["duration"],
            "filename": file.filename
        }
    except Exception as e:
        logger.error(f"❌ 文件识别错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """服务启动事件"""
    logger.info("🚀 ASR服务启动")
    logger.info(f"📊 服务统计: {asr_service.get_stats()}")

@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭事件"""
    logger.info("🛑 ASR服务关闭")
    logger.info(f"📊 最终统计: {asr_service.get_stats()}")

if __name__ == "__main__":
    import uvicorn
    
    logger.info("=" * 60)
    logger.info("🎙️  ASR语音识别服务")
    logger.info("=" * 60)
    logger.info("配置信息:")
    logger.info("  - 监听地址: 127.0.0.1:8000 (内部)")
    logger.info("  - 外部访问: http://demo.zjuicsr.cn:3780 (通过Nginx)")
    logger.info("  - WebSocket: ws://demo.zjuicsr.cn:3780/ws/asr")
    logger.info("=" * 60)
    
    uvicorn.run(
        app, 
        host="127.0.0.1",  # 只监听本地回环地址（安全）
        port=8000,         # 内部端口，通过Nginx代理
        log_level="info",
        access_log=True
    )