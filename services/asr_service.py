from funasr import AutoModel
import numpy as np
import soundfile
import io
from typing import Dict, Any, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

class ASRService:
    def __init__(self):
        """初始化ASR服务 - 只使用 paraformer-zh-streaming"""
        # 流式配置
        self.chunk_size = [0, 10, 5]  # 600ms延迟
        self.encoder_chunk_look_back = 4
        self.decoder_chunk_look_back = 1
        
        # 加载模型
        logger.info("正在加载 paraformer-zh-streaming 模型...")
        self.model = AutoModel(model="/etc/nginx/html/demo/models/paraformer-zh-streaming")
        logger.info("模型加载完成!")
        
        # 会话管理
        self.sessions = {}
        
        # 统计
        self.stats = {"total_requests": 0, "active_sessions": 0}
    
    def is_ready(self) -> bool:
        """检查服务是否就绪"""
        return self.model is not None
    
    def create_session(self) -> str:
        """
        创建新的识别会话
        
        Returns:
            会话ID
        """
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "cache": {},
            "accumulated_text": "",
            "chunk_count": 0
        }
        
        self.stats["active_sessions"] = len(self.sessions)
        logger.info(f"创建会话: {session_id}")
        return session_id
    
    def process_chunk(self, session_id: str, audio_chunk: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        处理音频块（流式识别）
        
        Args:
            session_id: 会话ID
            audio_chunk: 音频数据 (float32, 16kHz)
            
        Returns:
            识别结果字典，如果没有识别到文字返回 None
        """
        if session_id not in self.sessions:
            raise ValueError(f"无效的会话ID: {session_id}")
        
        session = self.sessions[session_id]
        
        # 跳过太短的音频
        if len(audio_chunk) < 100:
            return None
        
        try:
            # 流式识别
            res = self.model.generate(
                input=audio_chunk,
                cache=session["cache"],
                is_final=False,
                chunk_size=self.chunk_size,
                encoder_chunk_look_back=self.encoder_chunk_look_back,
                decoder_chunk_look_back=self.decoder_chunk_look_back
            )
            
            # 提取识别结果
            if res and len(res) > 0 and "text" in res[0]:
                text = res[0]["text"]
                
                if text and text.strip():
                    session["accumulated_text"] += text
                    session["chunk_count"] += 1
                    
                    return {
                        "current_text": text,
                        "accumulated_text": session["accumulated_text"],
                        "chunk_count": session["chunk_count"]
                    }
        
        except Exception as e:
            logger.error(f"识别错误: {e}")
            raise
        
        return None
    
    def finalize_session(self, session_id: str, final_chunk: Optional[np.ndarray] = None) -> str:
        """
        结束会话，获取最终结果
        
        Args:
            session_id: 会话ID
            final_chunk: 最后一块音频（可选）
            
        Returns:
            完整的识别文本
        """
        if session_id not in self.sessions:
            return ""
        
        session = self.sessions[session_id]
        
        # 如果有最后一块音频，设置 is_final=True 强制输出
        if final_chunk is not None and len(final_chunk) > 0:
            try:
                res = self.model.generate(
                    input=final_chunk,
                    cache=session["cache"],
                    is_final=True,  # 关键：强制输出最后的文字
                    chunk_size=self.chunk_size,
                    encoder_chunk_look_back=self.encoder_chunk_look_back,
                    decoder_chunk_look_back=self.decoder_chunk_look_back
                )
                
                if res and len(res) > 0 and "text" in res[0]:
                    text = res[0]["text"]
                    if text and text.strip():
                        session["accumulated_text"] += text
            
            except Exception as e:
                logger.error(f"最终块处理错误: {e}")
        
        result = session["accumulated_text"]
        
        # 更新统计
        self.stats["total_requests"] += 1
        
        logger.info(f"会话结束: {session_id}, 识别文本: {result[:50]}...")
        
        return result
    
    def cleanup_session(self, session_id: str):
        """清理会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.stats["active_sessions"] = len(self.sessions)
            logger.info(f"清理会话: {session_id}")
    
    def recognize_file(self, audio_bytes: bytes) -> Dict[str, Any]:
        """
        识别完整音频文件（分块流式处理）
        
        Args:
            audio_bytes: 音频文件字节
            
        Returns:
            识别结果
        """
        # 读取音频
        audio_data, sample_rate = soundfile.read(io.BytesIO(audio_bytes))
        
        if sample_rate != 16000:
            raise ValueError(f"音频采样率必须为16kHz，当前为{sample_rate}Hz")
        
        # 分块处理
        chunk_stride = self.chunk_size[1] * 960  # 600ms = 10 * 960 采样点
        cache = {}
        results = []
        
        total_chunk_num = int(len(audio_data - 1) / chunk_stride + 1)
        
        for i in range(total_chunk_num):
            speech_chunk = audio_data[i * chunk_stride : (i + 1) * chunk_stride]
            is_final = (i == total_chunk_num - 1)
            
            res = self.model.generate(
                input=speech_chunk,
                cache=cache,
                is_final=is_final,
                chunk_size=self.chunk_size,
                encoder_chunk_look_back=self.encoder_chunk_look_back,
                decoder_chunk_look_back=self.decoder_chunk_look_back
            )
            
            if res and len(res) > 0 and "text" in res[0]:
                results.append(res[0]["text"])
        
        text = "".join(results)
        
        # 更新统计
        self.stats["total_requests"] += 1
        
        return {
            "text": text,
            "duration": len(audio_data) / sample_rate
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_requests": self.stats["total_requests"],
            "active_sessions": self.stats["active_sessions"]
        }