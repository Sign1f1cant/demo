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
        
        # 计算标准 chunk 大小
        self.chunk_stride = self.chunk_size[1] * 960  # 9600 采样点 = 600ms @ 16kHz
        
        # 加载模型
        logger.info("正在加载 paraformer-zh-streaming 模型...")
        self.model = AutoModel(model="/etc/nginx/html/demo/models/paraformer-zh-streaming")
        logger.info("模型加载完成!")
        logger.info(f"标准 chunk 大小: {self.chunk_stride} 采样点 (600ms)")
        
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
            "chunk_count": 0,
            "audio_buffer": np.array([], dtype=np.float32)  # 音频缓冲区
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
        
        # 🔧 关键修复：缓冲音频直到达到标准 chunk 大小
        session["audio_buffer"] = np.concatenate([session["audio_buffer"], audio_chunk])
        
        # 如果缓冲区不够一个完整 chunk，继续等待
        if len(session["audio_buffer"]) < self.chunk_stride:
            logger.debug(f"缓冲中: {len(session['audio_buffer'])}/{self.chunk_stride}")
            return None
        
        # 取出一个完整 chunk
        speech_chunk = session["audio_buffer"][:self.chunk_stride]
        session["audio_buffer"] = session["audio_buffer"][self.chunk_stride:]  # 保留剩余
        
        logger.debug(f"处理 chunk: {len(speech_chunk)} 采样点, 剩余: {len(session['audio_buffer'])}")
        
        try:
            # 流式识别（按照官方示例）
            res = self.model.generate(
                input=speech_chunk,
                cache=session["cache"],
                is_final=False,
                chunk_size=self.chunk_size,
                encoder_chunk_look_back=self.encoder_chunk_look_back,
                decoder_chunk_look_back=self.decoder_chunk_look_back
            )
            
            print(f"\n{'='*60}")
            print(f"🔍 模型原始返回: {res}")
            
            # 提取识别结果
            if res and len(res) > 0:
                text = res[0].get("text", "")
                
                print(f"📝 提取文本: [{text}]")
                print(f"📚 当前累积: [{session['accumulated_text']}]")
                print(f"{'='*60}\n")
                
                logger.info(f"🔍 模型原始返回: {res}")
                logger.info(f"📝 提取文本: [{text}]")
                logger.info(f"📚 当前累积: [{session['accumulated_text']}]")
                
                if text:
                    # 🔧 修复：每个chunk返回的是独立片段，直接追加
                    new_text = text
                    
                    # 更新累积文本（直接拼接）
                    session["accumulated_text"] += text
                    session["chunk_count"] += 1
                    
                    logger.info(f"✅ 识别第 {session['chunk_count']} 块: 片段=[{text}], 累积=[{session['accumulated_text']}]")
                    
                    return {
                        "current_text": new_text,  # 本次的文字片段
                        "accumulated_text": session["accumulated_text"],  # 完整的累积文字
                        "chunk_count": session["chunk_count"]
                    }
                else:
                    logger.debug(f"本轮无文本返回")
        
        except Exception as e:
            logger.error(f"识别错误: {e}", exc_info=True)
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
        
        # 处理缓冲区中剩余的音频
        if len(session["audio_buffer"]) > 0:
            logger.info(f"处理剩余音频: {len(session['audio_buffer'])} 采样点")
            
            try:
                res = self.model.generate(
                    input=session["audio_buffer"],
                    cache=session["cache"],
                    is_final=True,  # 标记为最后一块
                    chunk_size=self.chunk_size,
                    encoder_chunk_look_back=self.encoder_chunk_look_back,
                    decoder_chunk_look_back=self.decoder_chunk_look_back
                )
                
                if res and len(res) > 0:
                    text = res[0].get("text", "")
                    if text:
                        session["accumulated_text"] = text
                        logger.info(f"🔚 最终文本: [{text}]")
            
            except Exception as e:
                logger.error(f"最终块处理错误: {e}", exc_info=True)
        
        result = session["accumulated_text"]
        
        # 更新统计
        self.stats["total_requests"] += 1
        
        logger.info(f"⏹️  会话结束: {session_id}, 最终识别: [{result}]")
        
        return result
    
    def cleanup_session(self, session_id: str):
        """清理会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.stats["active_sessions"] = len(self.sessions)
            logger.info(f"🧹 清理会话: {session_id}")
    
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
        
        # 按照官方示例分块处理
        cache = {}
        results = []
        
        total_chunk_num = int(len(audio_data - 1) / self.chunk_stride + 1)
        
        for i in range(total_chunk_num):
            speech_chunk = audio_data[i * self.chunk_stride : (i + 1) * self.chunk_stride]
            is_final = (i == total_chunk_num - 1)
            
            res = self.model.generate(
                input=speech_chunk,
                cache=cache,
                is_final=is_final,
                chunk_size=self.chunk_size,
                encoder_chunk_look_back=self.encoder_chunk_look_back,
                decoder_chunk_look_back=self.decoder_chunk_look_back
            )
            
            if res and len(res) > 0:
                text = res[0].get("text", "")
                if text:
                    results.append(text)
        
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