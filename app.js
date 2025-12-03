// 主应用逻辑

// 全局变量
let currentStep = 1;
let userInstruction = '';
let unsafeDangerNeurons = 0;
let safeDangerNeurons = 0;
let isVoiceInputActive = false;

let unsafeVisualization = null;
let safeVisualization = null;
let unsafeMatrix = null;
let safeMatrix = null;

// ========================================
// 预设指令选择
// ========================================
function selectPreset(command) {
    document.getElementById('userInput').value = command;
}

// ========================================
// 语音输入功能
// ========================================
async function startVoiceInput() {
    const voiceBtn = document.getElementById('voiceBtn');
    const voiceStatus = document.getElementById('voiceStatus');
    
    if (isVoiceInputActive) {
        // 停止录音
        const result = asrService.stopRecording();
        
        voiceBtn.classList.remove('recording');
        voiceBtn.innerHTML = '🎤 语音输入';
        voiceStatus.textContent = '';
        isVoiceInputActive = false;
        
        // 将识别结果填入输入框
        if (result) {
            document.getElementById('userInput').value = result;
            voiceStatus.innerHTML = `<span class="text-green-400">✓ 识别完成: ${result}</span>`;
        }
        
        return;
    }
    
    try {
        // 连接WebSocket（如果未连接）
        if (!asrService.ws || asrService.ws.readyState !== WebSocket.OPEN) {
            voiceStatus.innerHTML = '<span class="text-yellow-400">正在连接语音服务...</span>';
            await asrService.connect();
        }
        
        // 设置回调
        asrService.setCallbacks(
            (status, message) => {
                // 状态回调
                if (status === 'recording') {
                    voiceStatus.innerHTML = '<span class="text-green-400">🎤 录音中，实时识别...</span>';
                } else if (status === 'stopped') {
                    voiceStatus.innerHTML = '<span class="text-blue-400">处理完成</span>';
                } else if (status === 'error') {
                    voiceStatus.innerHTML = `<span class="text-red-400">错误: ${message}</span>`;
                }
            },
            (result) => {
                // 识别结果回调
                if (result.type === 'partial') {
                    // 实时更新输入框
                    document.getElementById('userInput').value = result.text;
                    if (result.chunk) {
                        voiceStatus.innerHTML = `<span class="text-cyan-400">识别中: ${result.chunk}</span>`;
                    }
                } else if (result.type === 'final') {
                    // 最终结果
                    document.getElementById('userInput').value = result.text;
                    voiceStatus.innerHTML = `<span class="text-green-400">✓ 识别完成: ${result.text}</span>`;
                }
            }
        );
        
        // 开始录音
        const success = await asrService.startRecording();
        
        if (success) {
            isVoiceInputActive = true;
            voiceBtn.classList.add('recording');
            voiceBtn.innerHTML = '🔴 停止录音';
        }
        
    } catch (error) {
        console.error('语音输入错误:', error);
        voiceStatus.innerHTML = `<span class="text-red-400">语音输入失败: ${error.message}</span>`;
    }
}

// ========================================
// 处理用户输入
// ========================================
function processInput() {
    userInstruction = document.getElementById('userInput').value.trim();
    
    if (!userInstruction) {
        alert('请输入或选择一个指令');
        return;
    }
    
    showLoading();
    
    setTimeout(() => {
        hideLoading();
        
        if (isSafeInstruction(userInstruction)) {
            showStep2(true);
        } else {
            showStep3();
        }
    }, CONFIG.TIMING.LOADING_DELAY);
}

// ========================================
// 检查指令是否安全
// ========================================
function isSafeInstruction(instruction) {
    const lowerInstruction = instruction.toLowerCase();
    return CONFIG.SAFE_KEYWORDS.some(keyword => lowerInstruction.includes(keyword));
}

// ========================================
// 显示步骤2：安全检测结果
// ========================================
function showStep2(isSafe) {
    hideAllSteps();
    document.getElementById('step2').classList.remove('hidden');
    
    const resultDiv = document.getElementById('safetyResult');
    
    if (isSafe) {
        resultDiv.innerHTML = `
            <div class="text-6xl mb-4">✅</div>
            <p class="text-2xl text-green-400">安全指令</p>
            <p class="text-lg text-gray-300 mt-2">经过检测，当前指令安全，可以正常处理。</p>
        `;
    } else {
        resultDiv.innerHTML = `
            <div class="text-6xl mb-4">⚠️</div>
            <p class="text-2xl text-red-400">危险指令</p>
            <p class="text-lg text-gray-300 mt-2">检测到潜在威胁，将展示模型处理过程。</p>
            <button 
                onclick="showStep3()" 
                class="mt-4 px-6 py-3 bg-red-600 rounded-lg hover:bg-red-700 transition-all"
            >
                继续查看处理过程
            </button>
        `;
    }
    
    currentStep = 2;
}

// ========================================
// 显示步骤3：不安全模型处理
// ========================================
function showStep3() {
    hideAllSteps();
    document.getElementById('step3').classList.remove('hidden');
    
    // 设置输入文本
    document.getElementById('unsafeInput').textContent = userInstruction;
    
    // 生成不安全模型输出
    const unsafeOutput = generateUnsafeOutput(userInstruction);
    document.getElementById('unsafeOutput').textContent = unsafeOutput;
    
    // 创建注意力矩阵
    unsafeMatrix = new AttentionMatrix('unsafeMatrices', true);
    unsafeDangerNeurons = unsafeMatrix.create();
    document.getElementById('dangerCount').textContent = unsafeDangerNeurons;
    
    // 初始化3D可视化
    unsafeVisualization = new Visualization3D('unsafe3DContainer', true);
    unsafeVisualization.init();
    
    currentStep = 3;
}

// ========================================
// 生成不安全模型输出
// ========================================
function generateUnsafeOutput(instruction) {
    const response = CONFIG.RESPONSES.UNSAFE[instruction];
    return response || `这是一个关于"${instruction}"的有害响应示例。不安全模型可能会提供危险的信息，对用户造成潜在威胁。`;
}

// ========================================
// 开始安全训练过渡
// ========================================
function startSafetyTraining() {
    hideAllSteps();
    document.getElementById('step4').classList.remove('hidden');
    showTransitionEffect();
    
    setTimeout(() => {
        hideTransitionEffect();
        showStep5();
    }, CONFIG.TIMING.TRANSITION_DURATION);
}

// ========================================
// 显示步骤5：安全模型处理
// ========================================
function showStep5() {
    hideAllSteps();
    document.getElementById('step5').classList.remove('hidden');
    
    // 设置输入文本
    document.getElementById('safeInput').textContent = userInstruction;
    
    // 生成安全模型输出
    const safeOutput = generateSafeOutput(userInstruction);
    document.getElementById('safeOutput').textContent = safeOutput;
    
    // 创建注意力矩阵
    safeMatrix = new AttentionMatrix('safeMatrices', false);
    safeDangerNeurons = safeMatrix.create();
    document.getElementById('safeDangerCount').textContent = safeDangerNeurons;
    
    // 计算减少率
    const reductionRate = Math.round(((unsafeDangerNeurons - safeDangerNeurons) / unsafeDangerNeurons) * 100);
    document.getElementById('reductionRate').textContent = reductionRate + '%';
    
    // 初始化3D可视化
    safeVisualization = new Visualization3D('safe3DContainer', false);
    safeVisualization.init();
    
    currentStep = 5;
}

// ========================================
// 生成安全模型输出
// ========================================
function generateSafeOutput(instruction) {
    return CONFIG.RESPONSES.SAFE(instruction);
}

// ========================================
// 重置到步骤1
// ========================================
function resetToStep1() {
    hideAllSteps();
    document.getElementById('step1').classList.remove('hidden');
    document.getElementById('userInput').value = '';
    currentStep = 1;
    
    // 清理3D场景
    if (unsafeVisualization) {
        unsafeVisualization.dispose();
        unsafeVisualization = null;
    }
    if (safeVisualization) {
        safeVisualization.dispose();
        safeVisualization = null;
    }
}

// ========================================
// 工具函数
// ========================================
function hideAllSteps() {
    document.querySelectorAll('.step-content').forEach(step => {
        step.classList.add('hidden');
    });
}

function showLoading() {
    document.getElementById('loadingScreen').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingScreen').classList.add('hidden');
}

function showTransitionEffect() {
    document.getElementById('transitionEffect').classList.remove('hidden');
}

function hideTransitionEffect() {
    document.getElementById('transitionEffect').classList.add('hidden');
}

// ========================================
// 页面初始化
// ========================================
document.addEventListener('DOMContentLoaded', function() {
    // 添加回车键支持
    document.getElementById('userInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            processInput();
        }
    });
    
    console.log('✅ 应用初始化完成');
    console.log('📡 ASR服务地址:', CONFIG.WS_URL);
});

// ========================================
// 页面卸载时清理
// ========================================
window.addEventListener('beforeunload', () => {
    if (asrService) {
        asrService.disconnect();
    }
    if (unsafeVisualization) {
        unsafeVisualization.dispose();
    }
    if (safeVisualization) {
        safeVisualization.dispose();
    }
});