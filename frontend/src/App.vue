<script setup>
import { ref, reactive } from 'vue'
import axios from 'axios'

// 应用状态
const currentStep = ref(1)
const loading = ref(false)
const error = ref('')

// 表单数据
const formData = reactive({
  text: '',
  stylePrompt: '现代简约风格，色彩丰富，构图精美',
  maxSegments: 8
})

// 分析结果
const analysisResult = ref(null)
const editableSegments = ref([]) // 用户可编辑的段落数据
const generatedImages = ref([])
const batchId = ref('')

// API基础URL
const API_BASE = 'http://localhost:8000'

// 步骤1：分析文本
const analyzeText = async () => {
  if (!formData.text.trim()) {
    error.value = '请输入要转换的文本内容'
    return
  }
  
  if (formData.text.length > 10000) {
    error.value = '文本长度不能超过10000字'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    console.log('发送文本分析请求:', {
      text: formData.text,
      style_prompt: formData.stylePrompt,
      max_segments: formData.maxSegments
    })
    
    const response = await axios.post(`${API_BASE}/api/analyze-text`, {
      text: formData.text,
      style_prompt: formData.stylePrompt,
      max_segments: formData.maxSegments
    })
    
    console.log('收到文本分析响应:', response.data)
    
    analysisResult.value = response.data
    // 初始化可编辑的段落数据
    editableSegments.value = response.data.segments.map(segment => ({
      ...segment,
      content: segment.content,
      summary: segment.summary,
      image_prompt: segment.image_prompt
    }))
    currentStep.value = 2
  } catch (err) {
    console.error('文本分析错误:', err)
    error.value = err.response?.data?.detail || '文本分析失败，请重试'
  } finally {
    loading.value = false
  }
}

// 步骤2：生成图片
const generateImages = async () => {
  if (!editableSegments.value || editableSegments.value.length === 0) {
    error.value = '没有可用的文本段落'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    console.log('发送图片生成请求:', {
      segments: editableSegments.value,
      style_prompt: formData.stylePrompt,
      image_size: '3:4'
    })
    
    const response = await axios.post(`${API_BASE}/api/generate-images`, {
      segments: editableSegments.value, // 使用用户编辑后的数据
      style_prompt: formData.stylePrompt,
      image_size: '3:4'
    })
    
    console.log('收到图片生成响应:', response.data)
    
    if (response.data.images && Array.isArray(response.data.images)) {
      // 确保每个图片对象都有正确的结构
      generatedImages.value = response.data.images.map((img, index) => ({
        segment_id: img.segment_id || index + 1,
        image_url: img.image_url || img.url,
        status: img.status || 'completed',
        prompt: img.prompt || analysisResult.value.segments[index]?.image_prompt || ''
      }))
    } else {
      generatedImages.value = response.data.images || []
    }
    
    batchId.value = response.data.batch_id
    currentStep.value = 4  // 更新为步骤4
    
    console.log('设置的图片数据:', generatedImages.value)
  } catch (err) {
    console.error('图片生成错误:', err)
    error.value = err.response?.data?.detail || '图片生成失败，请重试'
  } finally {
    loading.value = false
  }
}

// 进入提示词编辑页面
const goToPromptEditing = () => {
  currentStep.value = 3
  error.value = ''
}

// 重新开始
const restart = () => {
  currentStep.value = 1
  formData.text = ''
  formData.stylePrompt = '现代简约风格，色彩丰富，构图精美'
  formData.maxSegments = 8
  analysisResult.value = null
  generatedImages.value = []
  batchId.value = ''
  error.value = ''
}

// 返回上一步
const goBack = () => {
  if (currentStep.value > 1) {
    currentStep.value--
    error.value = ''
  }
}

// 测试功能
const testFunction = async () => {
  console.log('开始测试功能...')
  
  // 设置测试数据
  formData.text = '春天来了，花园里百花盛开。阳光明媚，微风轻拂。小鸟在枝头歌唱，蝴蝶在花丛中飞舞。'
  
  // 先分析文本
  await analyzeText()
  
  // 等待一秒后生成图片
  setTimeout(async () => {
    await generateImages()
  }, 1000)
}

  // 下载图片
  const downloadImage = (imageUrl, filename) => {
    const link = document.createElement('a')
    link.href = imageUrl
    link.download = filename
    link.click()
  }

// 根据segment_id获取段落信息
const getSegmentById = (segmentId) => {
  return editableSegments.value.find(segment => segment.id === segmentId)
}

// 删除段落
const removeSegment = (segmentId) => {
  editableSegments.value = editableSegments.value.filter(segment => segment.id !== segmentId)
}

// 添加新段落
const addNewSegment = () => {
  const newId = editableSegments.value.length > 0 ? Math.max(...editableSegments.value.map(s => s.id)) + 1 : 1
  const newSegment = {
    id: newId,
    content: '',
    summary: '新段落',
    image_prompt: '请编辑此段落内容'
  }
  editableSegments.value.push(newSegment)
}

// 编辑段落内容
const editSegment = (segmentId, field, value) => {
  const segment = editableSegments.value.find(s => s.id === segmentId)
  if (segment) {
    segment[field] = value
    // 如果编辑了内容，自动更新摘要
    if (field === 'content' && value.trim()) {
      segment.summary = value.substring(0, 20) + (value.length > 20 ? '...' : '')
      segment.image_prompt = `描绘：${segment.summary}`
    }
  }
}
</script>

<template>
  <div class="app">
    <!-- 头部 -->
    <header class="header">
      <h1>🎨 创意加速器</h1>
      <p>将长文本智能转换为精美图片</p>
      <button @click="testFunction" style="background: #4ade80; color: white; padding: 0.5rem 1rem; border: none; border-radius: 4px; margin-top: 1rem; cursor: pointer;">🧪 快速测试</button>
    </header>

    <!-- 进度指示器 -->
    <div class="progress-bar">
      <div class="step" :class="{ active: currentStep >= 1, completed: currentStep > 1 }">
        <span class="step-number">1</span>
        <span class="step-label">输入文本</span>
      </div>
      <div class="step" :class="{ active: currentStep >= 2, completed: currentStep > 2 }">
        <span class="step-number">2</span>
        <span class="step-label">编辑段落</span>
      </div>
      <div class="step" :class="{ active: currentStep >= 3, completed: currentStep > 3 }">
        <span class="step-number">3</span>
        <span class="step-label">编辑提示词</span>
      </div>
      <div class="step" :class="{ active: currentStep >= 4 }">
        <span class="step-number">4</span>
        <span class="step-label">生成图片</span>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <!-- 主要内容区域 -->
    <main class="main-content">
      <!-- 步骤1：文本输入 -->
      <div v-if="currentStep === 1" class="step-content">
        <div class="input-section">
          <h2>📝 输入您的文本内容</h2>
          <textarea 
            v-model="formData.text"
            placeholder="请粘贴您的长文本内容（最多10000字）...\n\n例如：\n今天是个美好的日子，阳光明媚，微风轻拂。我走在公园的小径上，看到了许多美丽的花朵正在盛开。春天的气息弥漫在空气中，让人心情愉悦..."
            class="text-input"
            :disabled="loading"
          ></textarea>
          <div class="char-count">{{ formData.text.length }}/10000 字</div>
        </div>

        <div class="settings-section">
          <h3>🎨 图片风格设置</h3>
          <div class="form-group">
            <label>风格描述：</label>
            <input 
              v-model="formData.stylePrompt"
              type="text"
              placeholder="描述您希望的图片风格"
              class="style-input"
              :disabled="loading"
            />
          </div>
          <div class="form-group">
            <label>最大图片数量：</label>
            <input 
              v-model.number="formData.maxSegments"
              type="number"
              min="1"
              max="20"
              placeholder="输入图片数量（1-20）"
              class="segment-input"
              :disabled="loading"
            />
            <div class="input-hint">建议：3-8张图片效果最佳</div>
          </div>
        </div>

        <div class="action-buttons">
          <button 
            @click="analyzeText" 
            :disabled="loading || !formData.text.trim()"
            class="primary-button"
          >
            <span v-if="loading">🔄 分析中...</span>
            <span v-else>🚀 开始分析</span>
          </button>
        </div>
      </div>

      <!-- 步骤2：编辑段落 -->
      <div v-if="currentStep === 2" class="step-content">
        <h2>📋 编辑文本段落</h2>
        <div v-if="editableSegments.length > 0" class="analysis-result">
          <div class="result-summary">
            <p><strong>共分析出 {{ editableSegments.length }} 个段落</strong></p>
            <p>预估生成时间：{{ Math.floor(editableSegments.length * 30 / 60) }} 分钟</p>
            <div class="segment-actions">
              <button @click="addNewSegment" class="add-segment-button">
                ➕ 添加新段落
              </button>
            </div>
          </div>
          
          <div class="segments-preview">
            <div 
              v-for="segment in editableSegments" 
              :key="segment.id"
              class="segment-card editable"
            >
              <div class="segment-header">
                <span class="segment-id">段落 {{ segment.id }}</span>
                <div class="segment-controls">
                  <button 
                    @click="removeSegment(segment.id)" 
                    class="remove-button"
                    title="删除段落"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              
              <!-- 可编辑的段落摘要 -->
              <div class="editable-field">
                <label>段落标题：</label>
                <input 
                  :value="segment.summary"
                  @input="editSegment(segment.id, 'summary', $event.target.value)"
                  class="segment-summary-input"
                  placeholder="输入段落标题"
                />
              </div>
              
              <!-- 可编辑的段落内容 -->
              <div class="editable-field">
                <label>段落内容：</label>
                <textarea 
                  :value="segment.content"
                  @input="editSegment(segment.id, 'content', $event.target.value)"
                  class="segment-content-input"
                  placeholder="输入段落内容"
                  rows="3"
                ></textarea>
              </div>
            </div>
          </div>
        </div>

        <div class="action-buttons">
          <button @click="goBack" class="secondary-button" :disabled="loading">
            ← 返回修改
          </button>
          <button 
            @click="goToPromptEditing" 
            :disabled="loading"
            class="primary-button"
          >
            下一步：编辑提示词 →
          </button>
        </div>
      </div>

      <!-- 步骤3：编辑提示词 -->
      <div v-if="currentStep === 3" class="step-content">
        <h2>🎨 编辑图片生成提示词</h2>
        <div v-if="analysisResult" class="prompt-editing-section">
          <div class="prompt-summary">
            <p><strong>为每个段落配置图片生成提示词</strong></p>
            <p>提示词将决定生成图片的风格和内容</p>
          </div>
          
          <div class="prompts-preview">
            <div 
              v-for="segment in editableSegments" 
              :key="segment.id"
              class="prompt-card"
            >
              <div class="prompt-header">
                <span class="segment-title">{{ segment.summary }}</span>
                <span class="segment-id">段落 {{ segment.id }}</span>
              </div>
              
              <div class="segment-content-preview">
                <p>{{ segment.content.substring(0, 100) }}{{ segment.content.length > 100 ? '...' : '' }}</p>
              </div>
              
              <!-- 可编辑的图片提示词 -->
              <div class="prompt-field">
                <label>图片生成提示词：</label>
                <textarea 
                  :value="segment.image_prompt"
                  @input="editSegment(segment.id, 'image_prompt', $event.target.value)"
                  class="prompt-input"
                  placeholder="描述希望生成的图片内容、风格、色彩等..."
                  rows="3"
                ></textarea>
              </div>
            </div>
          </div>
        </div>

        <div class="action-buttons">
          <button @click="goBack" class="secondary-button" :disabled="loading">
            ← 返回编辑段落
          </button>
          <button 
            @click="generateImages" 
            :disabled="loading"
            class="primary-button"
          >
            <span v-if="loading">🎨 生成中...</span>
            <span v-else>✨ 生成图片</span>
          </button>
        </div>
      </div>

      <!-- 步骤4：图片生成结果 -->
      <div v-if="currentStep === 4" class="step-content">
        <h2>📖 小红书风格图文展示</h2>
        <div v-if="loading" class="loading-info" style="background: #e0f2fe; padding: 1rem; margin-bottom: 1rem; border-radius: 8px; text-align: center;">
          <p>🎨 正在生成图片，请稍候...</p>
        </div>
        
        <!-- 图文合成结果展示 -->
        <div v-if="generatedImages && generatedImages.length > 0" class="image-grid">
          <div 
            v-for="(image, index) in generatedImages" 
            :key="image.segment_id"
            class="image-item"
          >
            <!-- 图片区域（已包含文字内容） -->
            <div class="image-container">
              <img 
                :src="image.image_url" 
                :alt="`段落 ${image.segment_id} 的图文合成图片`"
                class="composed-image"
              />
              <div class="image-overlay">
                <button 
                  @click="downloadImage(image.image_url, `segment-${image.segment_id}.jpg`)"
                  class="download-button"
                >
                  📥 下载
                </button>
              </div>
            </div>
            <div class="image-status-badge" :class="image.status">
              {{ image.status === 'completed' ? '✅ 生成完成' : '❌ 生成失败' }}
            </div>
          </div>
        </div>
        
        <div v-else-if="!loading" class="no-images">
          <p>暂无生成的图片</p>
        </div>

        <div class="action-buttons">
          <button @click="goBack" class="secondary-button">
            ← 返回编辑提示词
          </button>
          <button @click="restart" class="primary-button">
            🔄 重新开始
          </button>
        </div>
      </div>
    </main>

    <!-- 页脚 -->
    <footer class="footer">
      <p>© 2024 创意加速器 - 让文字变成艺术</p>
    </footer>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.header {
  text-align: center;
  padding: 2rem 1rem;
  color: white;
}

.header h1 {
  font-size: 2.5rem;
  margin: 0;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.header p {
  font-size: 1.2rem;
  margin: 0.5rem 0 0 0;
  opacity: 0.9;
}

.progress-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2rem 1rem;
  gap: 2rem;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: rgba(255,255,255,0.6);
  transition: all 0.3s ease;
}

.step.active {
  color: white;
}

.step.completed {
  color: #4ade80;
}

.step-number {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-bottom: 0.5rem;
  transition: all 0.3s ease;
}

.step.active .step-number {
  background: white;
  color: #667eea;
}

.step.completed .step-number {
  background: #4ade80;
  color: white;
}

.step-label {
  font-size: 0.9rem;
  text-align: center;
}

.error-message {
  background: #fee2e2;
  color: #dc2626;
  padding: 1rem;
  margin: 1rem auto;
  max-width: 800px;
  border-radius: 8px;
  border-left: 4px solid #dc2626;
}

.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem 1rem;
  width: 100%;
}

.step-content {
  background: white;
  border-radius: 16px;
  padding: 2.5rem;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
  width: 100%;
  max-width: none;
}

.input-section h2 {
  color: #374151;
  margin-bottom: 1.5rem;
}

.text-input {
  width: 100%;
  min-height: 300px;
  padding: 1rem;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  font-size: 1rem;
  line-height: 1.6;
  resize: vertical;
  transition: border-color 0.3s ease;
}

.text-input:focus {
  outline: none;
  border-color: #667eea;
}

.char-count {
  text-align: right;
  color: #6b7280;
  font-size: 0.9rem;
  margin-top: 0.5rem;
}

.settings-section {
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid #e5e7eb;
}

.settings-section h3 {
  color: #374151;
  margin-bottom: 1rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #374151;
  font-weight: 500;
}

.style-input, .segment-select, .segment-input {
  width: 100%;
  padding: 0.75rem;
  border: 2px solid #e5e7eb;
  border-radius: 6px;
  font-size: 1rem;
  transition: border-color 0.3s ease;
}

.style-input:focus, .segment-select:focus, .segment-input:focus {
  outline: none;
  border-color: #667eea;
}

.input-hint {
  font-size: 0.8rem;
  color: #6b7280;
  margin-top: 0.5rem;
  font-style: italic;
}

.action-buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid #e5e7eb;
}

.primary-button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 1rem 2rem;
  border-radius: 8px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 150px;
}

.primary-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}

.primary-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.secondary-button {
  background: #f3f4f6;
  color: #374151;
  border: 2px solid #e5e7eb;
  padding: 1rem 2rem;
  border-radius: 8px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.secondary-button:hover:not(:disabled) {
  background: #e5e7eb;
  transform: translateY(-1px);
}

.analysis-result {
  margin-bottom: 2rem;
}

.result-summary {
  background: #f0f9ff;
  padding: 1.5rem;
  border-radius: 8px;
  margin-bottom: 2rem;
  border-left: 4px solid #0ea5e9;
}

.result-summary p {
  margin: 0.5rem 0;
  color: #0c4a6e;
}

.segments-preview {
  display: grid;
  gap: 1rem;
  max-height: 400px;
  overflow-y: auto;
}

.segment-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 1rem;
  transition: all 0.3s ease;
}

.segment-card:hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
}

.segment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.segment-id {
  font-weight: 600;
  color: #667eea;
}

.segment-summary {
  color: #6b7280;
  font-size: 0.9rem;
}

.segment-content {
  color: #374151;
  line-height: 1.5;
  margin-bottom: 0.5rem;
}

.segment-prompt {
  color: #7c3aed;
  font-size: 0.9rem;
  font-style: italic;
}

.images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 2rem;
  margin-bottom: 2rem;
}

.image-card {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transition: all 0.3s ease;
}

.image-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 25px rgba(0,0,0,0.15);
}

.image-container {
  position: relative;
  width: 100%;
  overflow: hidden;
  border-radius: 12px;
}

.composed-image {
  width: 100%;
  height: auto;
  display: block;
  transition: transform 0.3s ease;
}

.image-container:hover .composed-image {
  transform: scale(1.02);
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.image-container:hover .image-overlay {
  opacity: 1;
}

.download-button {
  background: white;
  color: #374151;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.download-button:hover {
  background: #f3f4f6;
  transform: scale(1.05);
}

.image-info {
  padding: 1rem;
  background: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.image-title {
  font-weight: 600;
  color: #374151;
}

.image-status {
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 500;
}

.image-status.completed {
  background: #dcfce7;
  color: #166534;
}

.footer {
  text-align: center;
  padding: 2rem;
  color: rgba(255,255,255,0.8);
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 2rem;
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

.image-item {
  background: white;
  border-radius: 16px;
  padding: 1rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  transition: all 0.3s ease;
}

.image-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(0,0,0,0.12);
}

.text-section {
  padding: 1rem;
}

.segment-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.segment-number {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.9rem;
}

.segment-title {
  color: #374151;
  margin: 0;
  font-size: 1.2rem;
}

.segment-content {
  color: #6b7280;
  line-height: 1.6;
  margin-bottom: 1rem;
}

.image-prompt {
  background: #f0f9ff;
  padding: 0.75rem;
  border-radius: 8px;
  border-left: 3px solid #0ea5e9;
}

.prompt-label {
  font-weight: 600;
  color: #0c4a6e;
}

.prompt-text {
  color: #075985;
  font-style: italic;
}

.image-section {
  position: relative;
}

.image-container {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  transition: all 0.3s ease;
}

.image-container:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(0,0,0,0.15);
}

.generated-image {
  width: 100%;
  height: auto;
  display: block;
  transition: transform 0.3s ease;
}

.image-container:hover .generated-image {
  transform: scale(1.02);
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.image-container:hover .image-overlay {
  opacity: 1;
}

.download-button {
  background: white;
  color: #374151;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.download-button:hover {
  background: #f3f4f6;
  transform: scale(1.05);
}

.image-status-badge {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: rgba(255,255,255,0.95);
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.image-status-badge.completed {
  color: #166534;
  background: rgba(220, 252, 231, 0.95);
}

.no-images {
  text-align: center;
  padding: 3rem;
  color: #6b7280;
  background: #f9fafb;
  border-radius: 12px;
  border: 2px dashed #d1d5db;
}

/* 段落编辑功能样式 */
.segment-actions {
  margin-top: 1rem;
  text-align: center;
}

.add-segment-button {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.add-segment-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}

.segment-card.editable {
  border: 2px solid #e5e7eb;
  background: #fafafa;
  transition: all 0.3s ease;
}

.segment-card.editable:hover {
  border-color: #667eea;
  background: white;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}

.segment-controls {
  display: flex;
  gap: 0.5rem;
}

.remove-button {
  background: #fee2e2;
  color: #dc2626;
  border: none;
  padding: 0.5rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.3s ease;
}

.remove-button:hover {
  background: #fecaca;
  transform: scale(1.1);
}

.editable-field {
  margin-bottom: 1rem;
}

.editable-field label {
  display: block;
  margin-bottom: 0.5rem;
  color: #374151;
  font-weight: 500;
  font-size: 0.9rem;
}

.segment-summary-input,
.segment-content-input,
.segment-prompt-input {
  width: 100%;
  padding: 0.75rem;
  border: 2px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.95rem;
  transition: border-color 0.3s ease;
  background: white;
}

.segment-summary-input:focus,
.segment-content-input:focus,
.segment-prompt-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.segment-content-input {
  resize: vertical;
  min-height: 80px;
  font-family: inherit;
  line-height: 1.5;
}

.segment-prompt-input {
  font-style: italic;
  color: #7c3aed;
}

/* 提示词编辑页面样式 */
.prompt-editing-section {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.prompt-summary {
  background: #f8fafc;
  padding: 2rem;
  border-radius: 12px;
  margin-bottom: 2rem;
  text-align: center;
  border: 2px solid #e2e8f0;
}

.prompt-summary p {
  margin: 0.5rem 0;
  color: #475569;
}

.prompt-summary p:first-child {
  font-weight: 600;
  color: #1e293b;
  font-size: 1.1rem;
}

.prompts-preview {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.prompt-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 2px 10px rgba(0,0,0,0.08);
  border: 1px solid #e5e7eb;
  transition: all 0.3s ease;
}

.prompt-card:hover {
  box-shadow: 0 4px 20px rgba(0,0,0,0.12);
  transform: translateY(-2px);
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid #f1f5f9;
}

.segment-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #1e293b;
}

.segment-id {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 500;
}

.segment-content-preview {
  background: #f8fafc;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  border-left: 3px solid #cbd5e1;
}

.segment-content-preview p {
  margin: 0;
  color: #64748b;
  line-height: 1.6;
  font-size: 0.95rem;
}

.prompt-field {
  margin-top: 1rem;
}

.prompt-field label {
  display: block;
  margin-bottom: 0.5rem;
  color: #374151;
  font-weight: 600;
  font-size: 0.95rem;
}

.prompt-input {
  width: 100%;
  padding: 1rem;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  font-size: 0.95rem;
  line-height: 1.5;
  transition: all 0.3s ease;
  background: white;
  resize: vertical;
  min-height: 80px;
  font-family: inherit;
}

.prompt-input:focus {
  outline: none;
  border-color: #8b5cf6;
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
  background: #fefbff;
}

.prompt-input::placeholder {
  color: #9ca3af;
  font-style: italic;
}

@media (max-width: 768px) {
  .header h1 {
    font-size: 2rem;
  }
  
  .progress-bar {
    gap: 1rem;
    padding: 1.5rem 1rem;
  }
  
  .main-content {
    padding: 1rem 0.5rem;
  }
  
  .step-content {
    padding: 1.5rem;
    margin: 0 0.5rem;
  }
  
  .action-buttons {
    flex-direction: column;
  }
  
  .content-pair {
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }
  
  .content-pair.reverse .text-section,
  .content-pair.reverse .image-section {
    order: unset;
  }
  
  .xiaohongshu-layout {
    gap: 2rem;
  }
  
  .prompt-editing-section {
    padding: 0 0.5rem;
  }
  
  .prompt-summary {
    padding: 1.5rem;
    margin: 0 0.5rem 2rem 0.5rem;
  }
  
  .prompt-card {
    margin: 0 0.5rem;
    padding: 1rem;
  }
}

/* 平板设备适配 */
@media (min-width: 769px) and (max-width: 1024px) {
  .main-content {
    max-width: 900px;
    padding: 2rem 1.5rem;
  }
  
  .step-content {
    padding: 2rem;
  }
  
  .prompt-editing-section {
    max-width: 900px;
  }
}

/* 大屏设备优化 */
@media (min-width: 1400px) {
  .main-content {
    max-width: 1400px;
  }
  
  .step-content {
    padding: 3rem;
  }
  
  .prompt-editing-section {
    max-width: 1400px;
  }
}
</style>
