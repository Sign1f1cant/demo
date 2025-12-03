// 3D可视化模块

class Visualization3D {
    constructor(containerId, isUnsafe = true) {
        this.containerId = containerId;
        this.isUnsafe = isUnsafe;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.animationId = null;
    }
    
    // 初始化3D场景
    init() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`容器 ${this.containerId} 未找到`);
            return;
        }
        
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        // 创建场景
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0a);
        
        // 创建相机
        this.camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        this.camera.position.z = 30;
        
        // 创建渲染器
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        container.innerHTML = '';
        container.appendChild(this.renderer.domElement);
        
        // 添加光照
        const ambientLight = new THREE.AmbientLight(0x404040);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
        directionalLight.position.set(5, 5, 5);
        this.scene.add(directionalLight);
        
        // 创建神经网络
        this.createNeuralNetwork();
        
        // 开始动画
        this.animate();
    }
    
    // 创建神经网络可视化
    createNeuralNetwork() {
        const { LAYERS, LAYER_POSITIONS, NEURON_SIZE } = CONFIG.VISUALIZATION;
        const neuronGeometry = new THREE.SphereGeometry(NEURON_SIZE, 16, 16);
        
        LAYERS.forEach((count, layerIndex) => {
            for (let i = 0; i < count; i++) {
                // 计算神经元颜色
                const isDangerous = this.isUnsafe ?
                    (Math.random() > 0.3) : // 不安全模型：70%几率是危险神经元
                    (Math.random() <= 0.1); // 安全模型：只有10%几率是危险神经元
                
                const color = isDangerous ? 0xff0000 : 0x00ff00;
                
                const material = new THREE.MeshPhongMaterial({
                    color: color,
                    emissive: color,
                    emissiveIntensity: 0.3
                });
                
                const neuron = new THREE.Mesh(neuronGeometry, material);
                const y = (i - count / 2) * 2;
                const z = (Math.random() - 0.5) * 5;
                neuron.position.set(LAYER_POSITIONS[layerIndex], y, z);
                this.scene.add(neuron);
                
                // 创建连接线
                if (layerIndex < LAYERS.length - 1) {
                    const nextLayerCount = LAYERS[layerIndex + 1];
                    for (let j = 0; j < nextLayerCount; j++) {
                        if (Math.random() > 0.7) { // 稀疏连接
                            const nextY = (j - nextLayerCount / 2) * 2;
                            const nextZ = (Math.random() - 0.5) * 5;
                            
                            const points = [
                                new THREE.Vector3(LAYER_POSITIONS[layerIndex], y, z),
                                new THREE.Vector3(LAYER_POSITIONS[layerIndex + 1], nextY, nextZ)
                            ];
                            
                            const geometry = new THREE.BufferGeometry().setFromPoints(points);
                            
                            const isConnectionDangerous = this.isUnsafe ?
                                (Math.random() > 0.5) : // 不安全模型：50%危险连接
                                (Math.random() > 0.8);  // 安全模型：20%危险连接
                            
                            const lineColor = isConnectionDangerous ? 0xff0066 : 0x00ffff;
                            
                            const material = new THREE.LineBasicMaterial({
                                color: lineColor,
                                opacity: CONFIG.VISUALIZATION.CONNECTION_OPACITY,
                                transparent: true
                            });
                            
                            const line = new THREE.Line(geometry, material);
                            this.scene.add(line);
                        }
                    }
                }
            }
        });
    }
    
    // 动画循环
    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());
        this.scene.rotation.y += CONFIG.VISUALIZATION.ROTATION_SPEED;
        this.renderer.render(this.scene, this.camera);
    }
    
    // 清理资源
    dispose() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        if (this.renderer) {
            this.renderer.dispose();
        }
    }
}

// 注意力矩阵可视化
class AttentionMatrix {
    constructor(containerId, isUnsafe = true) {
        this.containerId = containerId;
        this.isUnsafe = isUnsafe;
        this.dangerCount = 0;
    }
    
    // 创建矩阵
    create() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`容器 ${this.containerId} 未找到`);
            return 0;
        }
        
        container.innerHTML = '';
        this.dangerCount = 0;
        
        const { LAYERS, GRID_SIZE, UNSAFE_DANGER_THRESHOLD, SAFE_DANGER_THRESHOLD } = CONFIG.MATRIX;
        
        LAYERS.forEach((layerName, layerIndex) => {
            const matrixDiv = document.createElement('div');
            matrixDiv.className = 'glass-morphism rounded-lg p-4';
            matrixDiv.innerHTML = `
                <h4 class="text-center font-bold mb-3">${layerName}</h4>
                <div class="matrix-grid" id="${this.containerId}-layer${layerIndex}"></div>
            `;
            container.appendChild(matrixDiv);
            
            const gridDiv = document.getElementById(`${this.containerId}-layer${layerIndex}`);
            const totalNeurons = GRID_SIZE * GRID_SIZE;
            
            for (let i = 0; i < totalNeurons; i++) {
                const neuron = document.createElement('div');
                neuron.className = 'neuron inactive';
                
                // 随机激活模式
                const isActive = Math.random() > 0.7;
                if (isActive) {
                    const threshold = this.isUnsafe ? UNSAFE_DANGER_THRESHOLD : SAFE_DANGER_THRESHOLD;
                    const isDangerous = Math.random() > threshold;
                    
                    if (isDangerous) {
                        neuron.classList.add('active-danger');
                        this.dangerCount++;
                    } else {
                        neuron.classList.add('active-safe');
                    }
                }
                
                gridDiv.appendChild(neuron);
            }
        });
        
        // 添加连接效果
        setTimeout(() => this.createConnections(), CONFIG.TIMING.MATRIX_ANIMATION);
        
        return this.dangerCount;
    }
    
    // 创建层间连接效果
    createConnections() {
        const { LAYERS } = CONFIG.MATRIX;
        
        LAYERS.forEach((layerName, index) => {
            if (index < LAYERS.length - 1) {
                const currentLayer = document.getElementById(`${this.containerId}-layer${index}`);
                const nextLayer = document.getElementById(`${this.containerId}-layer${index + 1}`);
                
                if (currentLayer && nextLayer) {
                    // 高亮部分连接以显示激活路径
                    const neurons = currentLayer.querySelectorAll('.neuron.active-danger, .neuron.active-safe');
                    neurons.forEach(neuron => {
                        if (Math.random() > 0.5) {
                            const borderColor = this.isUnsafe ? '#ff0066' : '#00ff66';
                            neuron.style.border = `2px solid ${borderColor}`;
                        }
                    });
                }
            }
        });
    }
    
    // 获取危险神经元数量
    getDangerCount() {
        return this.dangerCount;
    }
}