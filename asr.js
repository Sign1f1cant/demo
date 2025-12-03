// ASR语音识别模块

class ASRService {
    constructor() {
        this.ws = null;
        this.audioContext = null;
        this.processor = null;
        this.mediaStream = null;
        this.isRecording = false;
        this.sessionId = null;
        this.accumulatedText = '';
        
        this.statusCallback = null;
        this.resultCallback = null;
    }
    
    // 设置回调函数
    setCallbacks(statusCallback, resultCallback) {
        this.statusCallback = statusCallback;
        this.resultCallback = resultCallback;
    }
    
    // 连接WebSocket
    async connect() {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(CONFIG.WS_URL);
                
                this.ws.onopen = () => {
                    console.log('✅ WebSocket连接成功');
                    if (this.statusCallback) {
                        this.statusCallback('connected');
                    }
                    
                    // 发送start信号
                    this.ws.send(JSON.stringify({ action: 'start' }));
                    resolve();
                };
                
                this.ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                };
                
                this.ws.onerror = (error) => {
                    console.error('❌ WebSocket错误:', error);
                    if (this.statusCallback) {
                        this.statusCallback('error');
                    }
                    reject(error);
                };
                
                this.ws.onclose = () => {
                    console.log('👋 WebSocket连接关闭');
                    if (this.statusCallback) {
                        this.statusCallback('disconnected');
                    }
                };
                
            } catch (error) {
                console.error('❌ 连接失败:', error);
                reject(error);
            }
        });
    }
    
    // 处理WebSocket消息
    handleMessage(data) {
        if (data.type === 'status') {
            this.sessionId = data.session_id;
            console.log(`✅ 会话就绪: ${this.sessionId}`);
        } else if (data.type === 'partial') {
            // 实时识别结果
            const text = data.text || '';
            this.accumulatedText = text;
            
            if (this.resultCallback) {
                this.resultCallback({
                    type: 'partial',
                    text: text,
                    chunk: data.chunk || ''
                });
            }
        } else if (data.type === 'final') {
            // 最终识别结果
            console.log(`✅ 最终结果: ${data.text}`);
            this.accumulatedText = data.text;
            
            if (this.resultCallback) {
                this.resultCallback({
                    type: 'final',
                    text: data.text
                });
            }
        } else if (data.type === 'error') {
            console.error('❌ 识别错误:', data.message);
            if (this.statusCallback) {
                this.statusCallback('error', data.message);
            }
        }
    }
    
    // 开始录音
    async startRecording() {
        try {
            console.log('🎤 请求麦克风权限...');
            
            // 请求麦克风权限
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            // 创建音频上下文
            this.audioContext = new AudioContext({ sampleRate: 16000 });
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);
            this.processor = this.audioContext.createScriptProcessor(8192, 1, 1);
            
            // 连接音频处理链
            source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
            
            // 处理音频数据
            this.processor.onaudioprocess = (e) => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    const inputData = e.inputBuffer.getChannelData(0);
                    const float32Array = new Float32Array(inputData);
                    
                    // 发送音频数据到后端
                    this.ws.send(float32Array.buffer);
                }
            };
            
            this.isRecording = true;
            this.accumulatedText = '';
            
            console.log('✅ 录音已开始');
            if (this.statusCallback) {
                this.statusCallback('recording');
            }
            
            return true;
            
        } catch (error) {
            console.error('❌ 无法访问麦克风:', error);
            if (this.statusCallback) {
                this.statusCallback('error', '无法访问麦克风，请确保已授予权限');
            }
            return false;
        }
    }
    
    // 停止录音
    stopRecording() {
        console.log('⏹️ 停止录音');
        
        // 断开音频处理
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }
        
        // 关闭音频上下文
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        // 停止媒体流
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        
        // 发送停止信号
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'stop' }));
        }
        
        this.isRecording = false;
        
        if (this.statusCallback) {
            this.statusCallback('stopped');
        }
        
        return this.accumulatedText;
    }
    
    // 断开连接
    disconnect() {
        this.stopRecording();
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        console.log('👋 已断开连接');
    }
    
    // 获取识别结果
    getResult() {
        return this.accumulatedText;
    }
}

// 导出ASR服务实例
const asrService = new ASRService();