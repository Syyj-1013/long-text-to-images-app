from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv
import asyncio
import json
from volcenginesdkarkruntime import Ark
# 图像处理和生成
from PIL import Image, ImageDraw, ImageFont
import requests
import io
import base64
import hashlib
from datetime import datetime
import openai

# 加载环境变量
load_dotenv()

# 创建FastAPI应用
app = FastAPI(
    title="创意加速器 - 长文本转图片API",
    description="将长文本智能拆分并生成对应图片的AI应用",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据模型定义
class TextAnalysisRequest(BaseModel):
    text: str
    style_prompt: Optional[str] = "现代简约风格"
    max_segments: Optional[int] = 10

class TextSegment(BaseModel):
    id: int
    content: str
    summary: str
    image_prompt: str

class TextAnalysisResponse(BaseModel):
    segments: List[TextSegment]
    total_count: int
    estimated_time: int  # 预估生成时间（秒）

class ImageGenerationRequest(BaseModel):
    segments: List[TextSegment]
    style_prompt: str
    image_size: str = "3:4"

class GeneratedImage(BaseModel):
    segment_id: int
    image_url: str
    thumbnail_url: str
    status: str  # "generating", "completed", "failed"

class ImageGenerationResponse(BaseModel):
    images: List[GeneratedImage]
    batch_id: str
    total_count: int

# AI服务配置
VOLCANO_ARK_API_KEY = os.getenv("VOLCANO_ARK_API_KEY")
VOLCANO_ARK_API_SECRET = os.getenv("VOLCANO_ARK_API_SECRET")

if not VOLCANO_ARK_API_KEY:
    print("警告: 未找到火山方舟API密钥，请在.env文件中配置VOLCANO_ARK_API_KEY")
    print("当前将使用占位图片作为演示")

# 初始化火山方舟客户端
client = None
if VOLCANO_ARK_API_KEY and VOLCANO_ARK_API_KEY not in ["YOUR_API_KEY_HERE", "YOUR_REAL_API_KEY_HERE"]:
    try:
        # 使用OpenAI兼容的客户端初始化方式
        import openai
        client = openai.OpenAI(
            api_key=VOLCANO_ARK_API_KEY,
            base_url="https://ark.cn-beijing.volces.com/api/v3"
        )
        print("火山方舟客户端初始化成功")
    except Exception as e:
        print(f"火山方舟客户端初始化失败: {e}")
        client = None
else:
    print("使用演示模式，将生成占位图片")

# 图片生成服务配置
IMAGE_GENERATION_SERVICE = os.getenv("IMAGE_GENERATION_SERVICE", "demo")
VOLCANO_IMAGE_MODEL = os.getenv("VOLCANO_IMAGE_MODEL", "doubao-seedream-4-0-250828")
VOLCANO_IMAGE_SIZE = os.getenv("VOLCANO_IMAGE_SIZE", "768x1024")  # 小红书风格的3:4比例
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY")
ALI_API_KEY = os.getenv("ALI_API_KEY")

class ImageGenerationService:
    """图片生成服务类"""
    
    def __init__(self):
        self.service_type = IMAGE_GENERATION_SERVICE
        if self.service_type == "openai" and OPENAI_API_KEY:
            openai.api_key = OPENAI_API_KEY
    
    async def generate_image(self, prompt: str, segment_id: int) -> str:
        """根据提示词生成图片"""
        try:
            if self.service_type == "volcano" and client:
                # 使用火山方舟SeeDream生成图片
                return await self._generate_with_volcano(prompt)
            elif self.service_type == "openai" and OPENAI_API_KEY and OPENAI_API_KEY != "YOUR_OPENAI_API_KEY_HERE":
                return await self._generate_with_openai(prompt)
            elif self.service_type == "baidu" and BAIDU_API_KEY and BAIDU_API_KEY != "YOUR_BAIDU_API_KEY_HERE":
                return await self._generate_with_baidu(prompt)
            elif self.service_type == "ali" and ALI_API_KEY and ALI_API_KEY != "YOUR_ALI_API_KEY_HERE":
                return await self._generate_with_ali(prompt)
            else:
                # 演示模式：生成基于内容的占位图片
                return await self._generate_demo_image(prompt, segment_id)
        except Exception as e:
            print(f"图片生成失败: {e}")
            return await self._generate_demo_image(prompt, segment_id)
    
    async def _generate_with_volcano(self, prompt: str) -> str:
        """使用火山方舟SeeDream生成图片"""
        try:
            print(f"使用火山方舟SeeDream生成图片: {prompt}")
            
            # 根据官方文档使用正确的参数格式
            response = client.images.generate(
                model=VOLCANO_IMAGE_MODEL,
                prompt=prompt,
                size="1024x1024",  # 使用标准尺寸格式
                n=1,  # 生成图片数量
                response_format="url"  # 返回URL格式
            )
            
            print(f"火山方舟API响应: {response}")
            
            # 处理响应格式
            if hasattr(response, 'data') and response.data and len(response.data) > 0:
                image_url = response.data[0].url
                print(f"火山方舟图片生成成功: {image_url}")
                return image_url
            elif hasattr(response, 'images') and response.images and len(response.images) > 0:
                image_url = response.images[0].url if hasattr(response.images[0], 'url') else response.images[0]
                print(f"火山方舟图片生成成功: {image_url}")
                return image_url
            else:
                print(f"火山方舟API响应格式异常: {response}")
                # 尝试直接访问response的其他可能属性
                print(f"Response类型: {type(response)}")
                print(f"Response属性: {dir(response)}")
                raise Exception("API响应格式异常")
                
        except Exception as e:
            print(f"火山方舟图片生成失败: {e}")
            print(f"错误类型: {type(e)}")
            raise e

    async def _generate_with_openai(self, prompt: str) -> str:
        """使用OpenAI DALL-E生成图片"""
        try:
            response = openai.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="768x1024",  # 小红书风格的3:4比例
                quality="standard",
                n=1,
            )
            return response.data[0].url
        except Exception as e:
            print(f"OpenAI图片生成失败: {e}")
            raise
    
    async def _generate_with_baidu(self, prompt: str) -> str:
        """使用百度文心一格生成图片"""
        # 这里需要实现百度文心一格的API调用
        # 暂时返回占位图片
        return f"https://picsum.photos/800/600?random={hash(prompt) % 10000}"
    
    async def _generate_with_ali(self, prompt: str) -> str:
        """使用阿里通义万相生成图片"""
        # 这里需要实现阿里通义万相的API调用
        # 暂时返回占位图片
        return f"https://picsum.photos/800/600?random={hash(prompt) % 10000}"
    
    async def _generate_demo_image(self, prompt: str, segment_id: int) -> str:
        """
        生成演示图片（使用预设图片库）- 智能解析AI提示词版本
        """
        print(f"\n=== 智能图片匹配分析 段落{segment_id} ===")
        print(f"AI生成的图片提示词: {prompt}")
        
        # 增强版主题映射 - 基于AI描述的语义理解
        enhanced_theme_mapping = {
            # 自然风光类 - 扩展语义词汇
            'nature_mountain': {
                'keywords': ['山', '山峰', '山脉', '登山', '远足', '自然风光', '户外', '徒步', '山景', '高山', '雪山', '山顶', '峰峦', '巍峨', '壮丽'],
                'semantic': ['雄伟', '壮观', '高耸', '险峻', '云雾缭绕', '山川', '峻岭', '巅峰', '登高', '俯瞰'],
                'emotions': ['震撼', '敬畏', '征服', '挑战', '坚毅']
            },
            'nature_ocean': {
                'keywords': ['海', '海洋', '海边', '海滩', '波浪', '海水', '沙滩', '海岸', '蓝色', '水面', '大海', '海浪', '潮汐', '海风'],
                'semantic': ['辽阔', '深邃', '波涛', '浪花', '海天一色', '碧波', '汹涌', '宁静', '海鸥', '帆船'],
                'emotions': ['自由', '宁静', '浪漫', '思考', '放松']
            },
            'nature_forest': {
                'keywords': ['森林', '树林', '绿色', '植物', '叶子', '树木', '自然', '绿意', '清新', '大树', '古树', '林间', '丛林', '绿荫'],
                'semantic': ['茂密', '幽静', '生机', '翠绿', '阳光透过', '鸟语花香', '小径', '清香', '氧气', '生态'],
                'emotions': ['平静', '治愈', '清新', '生机', '和谐']
            },
            'nature_flower': {
                'keywords': ['花', '花朵', '樱花', '梅花', '玫瑰', '花园', '花海', '盛开', '花瓣', '花蕊', '鲜花', '花束', '绽放', '芬芳'],
                'semantic': ['娇艳', '芬芳', '绚烂', '花香', '蜜蜂', '蝴蝶', '花期', '花语', '美丽', '色彩'],
                'emotions': ['美好', '浪漫', '温柔', '纯真', '爱情']
            },
            'nature_sky': {
                'keywords': ['天空', '云', '蓝天', '白云', '晴天', '日出', '日落', '夕阳', '朝霞', '晚霞', '彩霞', '阳光', '云朵', '天际'],
                'semantic': ['广阔', '无垠', '变幻', '光影', '色彩', '云卷云舒', '霞光', '金辉', '蔚蓝', '纯净'],
                'emotions': ['希望', '自由', '梦想', '开阔', '向往']
            },
            
            # 城市生活类
            'city_modern': {
                'keywords': ['城市', '都市', '现代', '高楼', '建筑', '街道', '都市风光', '摩天大楼', '现代建筑', '玻璃幕墙', '钢筋混凝土'],
                'semantic': ['繁华', '现代化', '科技感', '都市节奏', '商业区', 'CBD', '天际线', '灯火辉煌', '车水马龙'],
                'emotions': ['活力', '忙碌', '现代', '进步', '竞争']
            },
            'city_street': {
                'keywords': ['街道', '马路', '路', '街景', '城市街道', '行人', '交通', '繁华', '十字路口', '车流', '人流', '商店'],
                'semantic': ['熙熙攘攘', '川流不息', '红绿灯', '斑马线', '店铺', '招牌', '街头', '都市生活'],
                'emotions': ['热闹', '生活', '忙碌', '多彩', '真实']
            },
            'city_cafe': {
                'keywords': ['咖啡厅', '咖啡', '咖啡馆', '温暖', '惬意', '休闲', '下午茶', '咖啡店', '温馨', '拿铁', '卡布奇诺'],
                'semantic': ['慢生活', '文艺', '小资', '聊天', '阅读', '音乐', '香气', '舒适', '放松'],
                'emotions': ['惬意', '温馨', '放松', '享受', '文艺']
            },
            'city_night': {
                'keywords': ['夜晚', '夜景', '灯光', '霓虹', '夜色', '城市夜景', '璀璨', '霓虹灯', '灯火通明', '夜生活'],
                'semantic': ['绚烂', '迷人', '光影', '夜市', '酒吧', '夜店', '星光', '月光', '灯红酒绿'],
                'emotions': ['浪漫', '神秘', '活力', '魅力', '梦幻']
            },
            
            # 人物情感类
            'people_portrait': {
                'keywords': ['人物', '肖像', '面部', '表情', '眼神', '人像', '特写', '面容', '神情', '五官', '轮廓'],
                'semantic': ['深邃', '专注', '凝视', '微表情', '个性', '气质', '魅力', '特征', '神韵'],
                'emotions': ['专注', '深沉', '个性', '魅力', '真实']
            },
            'people_happy': {
                'keywords': ['快乐', '开心', '笑容', '微笑', '欢乐', '愉快', '高兴', '兴奋', '喜悦', '幸福', '灿烂', '甜美'],
                'semantic': ['阳光', '灿烂', '感染力', '正能量', '活力', '青春', '纯真', '美好'],
                'emotions': ['快乐', '幸福', '满足', '阳光', '积极']
            },
            'people_sad': {
                'keywords': ['伤心', '难过', '悲伤', '忧郁', '沮丧', '失落', '眼泪', '哭泣', '忧伤', '孤独', '思念'],
                'semantic': ['忧郁', '深沉', '思考', '回忆', '怀念', '感伤', '眼泪', '孤单'],
                'emotions': ['悲伤', '忧郁', '思念', '孤独', '感伤']
            },
            'people_love': {
                'keywords': ['爱情', '浪漫', '情侣', '恋人', '拥抱', '亲吻', '甜蜜', '温馨', '爱', '浪漫', '约会', '牵手'],
                'semantic': ['甜蜜', '温馨', '浪漫', '幸福', '相伴', '依偎', '深情', '眷恋'],
                'emotions': ['爱情', '浪漫', '甜蜜', '幸福', '温暖']
            },
            'people_friendship': {
                'keywords': ['友谊', '朋友', '友情', '陪伴', '一起', '合影', '友好', '聚会', '交谈', '分享', '支持'],
                'semantic': ['真诚', '陪伴', '支持', '分享', '快乐', '信任', '理解', '珍贵'],
                'emotions': ['友谊', '温暖', '支持', '快乐', '珍贵']
            },
            'people_family': {
                'keywords': ['家庭', '亲情', '父母', '孩子', '家人', '温馨', '团聚', '家', '亲人', '关爱', '呵护'],
                'semantic': ['温馨', '和睦', '关爱', '呵护', '传承', '责任', '依靠', '港湾'],
                'emotions': ['温馨', '关爱', '安全', '归属', '责任']
            },
            
            # 生活场景类
            'life_home': {
                'keywords': ['家', '家庭', '房间', '客厅', '卧室', '温馨', '居家', '生活', '家居', '装饰', '舒适'],
                'semantic': ['温馨', '舒适', '私密', '放松', '归属', '安全', '个人空间', '生活气息'],
                'emotions': ['温馨', '舒适', '安全', '放松', '归属']
            },
            'life_work': {
                'keywords': ['工作', '办公', '电脑', '会议', '商务', '职场', '学习', '专注', '办公室', '效率', '专业'],
                'semantic': ['专业', '效率', '专注', '认真', '责任', '成就', '挑战', '团队'],
                'emotions': ['专注', '认真', '责任', '成就', '挑战']
            },
            'life_travel': {
                'keywords': ['旅行', '旅游', '度假', '行李', '机场', '酒店', '风景', '探索', '旅途', '冒险', '发现'],
                'semantic': ['自由', '探索', '发现', '体验', '冒险', '放松', '开阔', '记忆'],
                'emotions': ['自由', '兴奋', '探索', '放松', '开阔']
            },
            'life_food': {
                'keywords': ['美食', '食物', '餐厅', '烹饪', '料理', '美味', '餐桌', '品尝', '菜肴', '香味', '色香味'],
                'semantic': ['美味', '香气', '色彩', '精致', '享受', '满足', '文化', '分享'],
                'emotions': ['享受', '满足', '幸福', '分享', '文化']
            },
            'life_reading': {
                'keywords': ['读书', '阅读', '书本', '学习', '知识', '图书', '文字', '思考', '书籍', '智慧', '文学'],
                'semantic': ['安静', '专注', '思考', '智慧', '知识', '成长', '内涵', '修养'],
                'emotions': ['宁静', '专注', '智慧', '成长', '充实']
            },
            
            # 抽象概念类
            'abstract_dream': {
                'keywords': ['梦想', '希望', '未来', '理想', '憧憬', '目标', '追求', '愿望', '梦', '志向', '抱负'],
                'semantic': ['远大', '美好', '追求', '奋斗', '坚持', '信念', '光明', '可能'],
                'emotions': ['希望', '憧憬', '激励', '坚定', '美好']
            },
            'abstract_memory': {
                'keywords': ['回忆', '记忆', '过去', '怀念', '思念', '往事', '童年', '青春', '时光', '岁月', '怀旧'],
                'semantic': ['珍贵', '美好', '怀念', '感慨', '时光', '青春', '纯真', '难忘'],
                'emotions': ['怀念', '感慨', '珍贵', '温暖', '感伤']
            },
            'abstract_growth': {
                'keywords': ['成长', '进步', '发展', '提升', '改变', '蜕变', '突破', '进化', '成熟', '学习', '进取'],
                'semantic': ['进步', '提升', '突破', '坚持', '努力', '收获', '成就', '蜕变'],
                'emotions': ['成就', '满足', '自豪', '坚定', '积极']
            },
            'abstract_peace': {
                'keywords': ['平静', '安静', '宁静', '祥和', '放松', '冥想', '内心', '禅意', '宁静', '静谧', '安详'],
                'semantic': ['宁静', '平和', '安详', '内心', '冥想', '禅意', '超脱', '纯净'],
                'emotions': ['平静', '安详', '放松', '纯净', '超脱']
            },
            'abstract_emotion': {
                'keywords': ['情感', '温暖', '感动', '关爱', '温情', '心情', '感受', '情绪', '内心', '心灵', '感触'],
                'semantic': ['深刻', '真挚', '温暖', '感人', '触动', '共鸣', '理解', '包容'],
                'emotions': ['感动', '温暖', '真挚', '深刻', '共鸣']
            },
            
            # 季节时间类
            'season_spring': {
                'keywords': ['春天', '春季', '新绿', '生机', '复苏', '嫩芽', '春意', '温暖', '春日', '花开', '万物复苏'],
                'semantic': ['生机', '希望', '新生', '活力', '温暖', '绿意', '花开', '复苏'],
                'emotions': ['希望', '活力', '新生', '温暖', '美好']
            },
            'season_summer': {
                'keywords': ['夏天', '夏季', '炎热', '阳光', '海滩', '游泳', '清凉', '活力', '夏日', '热情', '火热'],
                'semantic': ['热情', '活力', '阳光', '热烈', '充满活力', '青春', '激情', '奔放'],
                'emotions': ['热情', '活力', '激情', '自由', '青春']
            },
            'season_autumn': {
                'keywords': ['秋天', '秋季', '落叶', '金黄', '收获', '枫叶', '萧瑟', '成熟', '金秋', '丰收', '凉爽'],
                'semantic': ['成熟', '收获', '丰富', '沉淀', '金黄', '美丽', '诗意', '感怀'],
                'emotions': ['成熟', '收获', '感怀', '诗意', '沉静']
            },
            'season_winter': {
                'keywords': ['冬天', '冬季', '雪', '寒冷', '雪花', '冰', '纯洁', '静谧', '雪景', '银装素裹', '洁白'],
                'semantic': ['纯洁', '静谧', '洁白', '宁静', '素雅', '清冷', '美丽', '神圣'],
                'emotions': ['纯洁', '宁静', '清冷', '神圣', '美丽']
            },
            
            # 活动行为类
            'activity_sport': {
                'keywords': ['运动', '健身', '跑步', '瑜伽', '游泳', '锻炼', '活力', '健康', '体育', '汗水', '坚持'],
                'semantic': ['活力', '健康', '坚持', '挑战', '突破', '汗水', '努力', '强健'],
                'emotions': ['活力', '健康', '坚持', '挑战', '成就']
            },
            'activity_art': {
                'keywords': ['艺术', '绘画', '音乐', '创作', '设计', '美术', '文艺', '创意', '艺术', '灵感', '美感'],
                'semantic': ['创意', '美感', '灵感', '表达', '创造', '艺术', '文化', '审美'],
                'emotions': ['创意', '美感', '表达', '文艺', '灵感']
            },
            'activity_relax': {
                'keywords': ['休息', '放松', '躺着', '睡觉', '安静', '舒适', '惬意', '慵懒', '休闲', '悠闲', '享受'],
                'semantic': ['舒适', '惬意', '悠闲', '放松', '享受', '慵懒', '安逸', '自在'],
                'emotions': ['放松', '舒适', '惬意', '悠闲', '享受']
            },
            
            # 动物宠物类
            'animal_cat': {
                'keywords': ['猫', '小猫', '猫咪', '喵星人', '可爱猫', '宠物猫', '猫咪', '喵喵'],
                'semantic': ['可爱', '温顺', '优雅', '独立', '神秘', '灵动', '治愈', '陪伴'],
                'emotions': ['可爱', '治愈', '温顺', '陪伴', '温暖']
            },
            'animal_dog': {
                'keywords': ['狗', '小狗', '狗狗', '宠物狗', '忠诚', '汪星人', '犬', '小犬'],
                'semantic': ['忠诚', '友好', '活泼', '陪伴', '守护', '可爱', '温暖', '信任'],
                'emotions': ['忠诚', '友好', '陪伴', '温暖', '信任']
            },
            'animal_bird': {
                'keywords': ['鸟', '小鸟', '飞鸟', '鸟儿', '翅膀', '飞翔', '鸟类', '羽毛'],
                'semantic': ['自由', '轻盈', '优雅', '飞翔', '歌声', '美丽', '灵动', '天空'],
                'emotions': ['自由', '轻盈', '优雅', '美丽', '灵动']
            },
            'animal_wild': {
                'keywords': ['野生动物', '兔子', '松鼠', '蝴蝶', '昆虫', '动物', '野生', '自然'],
                'semantic': ['自然', '野性', '生态', '和谐', '美丽', '神奇', '多样', '生命'],
                'emotions': ['自然', '和谐', '美丽', '神奇', '生命']
            }
        }
        
        # 智能语义分析算法
        theme_scores = {}
        prompt_text = prompt.lower()
        
        # 提取AI描述中的关键信息
        ai_description_analysis = self._analyze_ai_description(prompt_text)
        print(f"AI描述分析结果: {ai_description_analysis}")
        
        # 基于增强主题映射进行智能匹配
        for theme, theme_data in enhanced_theme_mapping.items():
            score = 0
            
            # 1. 关键词匹配 (权重: 40%)
            keyword_score = 0
            for keyword in theme_data['keywords']:
                if keyword in prompt_text:
                    # 精确匹配加分
                    keyword_score += 3
                    # 位置权重：出现在前面的词权重更高
                    position = prompt_text.find(keyword)
                    if position < len(prompt_text) * 0.3:  # 前30%位置
                        keyword_score += 1
                    # 频率权重：多次出现加分
                    frequency = prompt_text.count(keyword)
                    keyword_score += min(frequency - 1, 2)  # 最多额外加2分
            
            # 2. 语义词汇匹配 (权重: 30%)
            semantic_score = 0
            for semantic_word in theme_data['semantic']:
                if semantic_word in prompt_text:
                    semantic_score += 2
                    # 语义词汇的上下文相关性
                    context_words = prompt_text.split()
                    word_index = -1
                    for i, word in enumerate(context_words):
                        if semantic_word in word:
                            word_index = i
                            break
                    if word_index >= 0:
                        # 检查前后词汇的相关性
                        context_start = max(0, word_index - 2)
                        context_end = min(len(context_words), word_index + 3)
                        context = ' '.join(context_words[context_start:context_end])
                        for related_word in theme_data['keywords'][:5]:  # 检查前5个关键词
                            if related_word in context:
                                semantic_score += 1
                                break
            
            # 3. 情感词汇匹配 (权重: 20%)
            emotion_score = 0
            for emotion in theme_data['emotions']:
                if emotion in prompt_text:
                    emotion_score += 2
                    # 情感强度分析
                    emotion_context = self._get_emotion_context(prompt_text, emotion)
                    if emotion_context:
                        emotion_score += 1
            
            # 4. AI描述分析加分 (权重: 10%)
            ai_analysis_score = 0
            if ai_description_analysis:
                # 场景匹配
                if 'scene_type' in ai_description_analysis:
                    scene_type = ai_description_analysis['scene_type']
                    if any(scene_word in theme for scene_word in scene_type.split('_')):
                        ai_analysis_score += 3
                
                # 情感匹配
                if 'dominant_emotion' in ai_description_analysis:
                    dominant_emotion = ai_description_analysis['dominant_emotion']
                    if dominant_emotion in theme_data['emotions']:
                        ai_analysis_score += 2
                
                # 视觉元素匹配
                if 'visual_elements' in ai_description_analysis:
                    visual_elements = ai_description_analysis['visual_elements']
                    for element in visual_elements:
                        if element in theme_data['keywords'] or element in theme_data['semantic']:
                            ai_analysis_score += 1
            
            # 计算总分 (加权平均)
            total_score = (
                keyword_score * 0.4 +
                semantic_score * 0.3 +
                emotion_score * 0.2 +
                ai_analysis_score * 0.1
            )
            
            theme_scores[theme] = total_score
            
            if total_score > 0:
                 print(f"主题 {theme}: 总分={total_score:.2f} (关键词={keyword_score:.1f}, 语义={semantic_score:.1f}, 情感={emotion_score:.1f}, AI分析={ai_analysis_score:.1f})")
        
        # 选择最佳匹配主题
        if theme_scores:
            best_theme = max(theme_scores.items(), key=lambda x: x[1])
            selected_theme = best_theme[0]
            best_score = best_theme[1]
            print(f"\n选中最佳主题: {selected_theme} (得分: {best_score:.2f})")
        else:
            # 智能默认主题选择
            selected_theme = self._get_intelligent_default_theme(prompt_text)
            print(f"\n使用智能默认主题: {selected_theme}")
        
        # 小红书风格竖版图片库 - 扩展版
        xiaohongshu_images = {
            # 自然风光类
            'nature_mountain': [
                'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1464822759844-d150baec0494?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1519904981063-b0cf448d479e?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1551632811-561732d1e306?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1506197603052-3cc9c3a201bd?w=400&h=600&fit=crop'
            ],
            'nature_ocean': [
                'https://images.unsplash.com/photo-1505142468610-359e7d316be0?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1439066615861-d1af74d74000?w=400&h=600&fit=crop'
            ],
            'nature_forest': [
                'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1448375240586-882707db888b?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1511593358241-7eea1f3c84e5?w=400&h=600&fit=crop'
            ],
            'nature_flower': [
                'https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1518895949257-7621c3c786d7?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1463320726281-696a485928c7?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1502082553048-f009c37129b9?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop'
            ],
            'nature_sky': [
                'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1519904981063-b0cf448d479e?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1506197603052-3cc9c3a201bd?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1464822759844-d150baec0494?w=400&h=600&fit=crop'
            ],
            
            # 城市生活类
            'city_modern': [
                'https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1514565131-fce0801e5785?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1480714378408-67cf0d13bc1f?w=400&h=600&fit=crop'
            ],
            'city_street': [
                'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1514565131-fce0801e5785?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1480714378408-67cf0d13bc1f?w=400&h=600&fit=crop'
            ],
            'city_cafe': [
                'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1559056199-641a0ac8b55e?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1521017432531-fbd92d768814?w=400&h=600&fit=crop'
            ],
            'city_night': [
                'https://images.unsplash.com/photo-1514565131-fce0801e5785?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1480714378408-67cf0d13bc1f?w=400&h=600&fit=crop'
            ],
            
            # 人物情感类
            'people_portrait': [
                'https://images.unsplash.com/photo-1494790108755-2616c6106db4?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=600&fit=crop'
            ],
            'people_happy': [
                'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1494790108755-2616c6106db4?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=600&fit=crop'
            ],
            'people_sad': [
                'https://images.unsplash.com/photo-1494790108755-2616c6106db4?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=600&fit=crop'
            ],
            'people_love': [
                'https://images.unsplash.com/photo-1516589178581-6cd7833ae3b2?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1518568814500-bf0f8d125f46?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop'
            ],
            'people_friendship': [
                'https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop',
                'https://images.unsplash.com/photo-1494790108755-2616c6106db4?w=400&h=600&fit=crop'
            ],
            'people_family': [
                 'https://images.unsplash.com/photo-1511895426328-dc8714191300?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1494790108755-2616c6106db4?w=400&h=600&fit=crop'
             ],
             
             # 生活场景类
             'life_home': [
                 'https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1484154218962-a197022b5858?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=400&h=600&fit=crop'
             ],
             'life_work': [
                 'https://images.unsplash.com/photo-1497032628192-86f99bcd76bc?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1486312338219-ce68d2c6f44d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop'
             ],
             'life_travel': [
                 'https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1464822759844-d150baec0494?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1519904981063-b0cf448d479e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1551632811-561732d1e306?w=400&h=600&fit=crop'
             ],
             'life_food': [
                 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1565299624946-b28f40a0ca4b?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1551782450-a2132b4ba21d?w=400&h=600&fit=crop'
             ],
             'life_reading': [
                 'https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1494790108755-2616c6106db4?w=400&h=600&fit=crop'
             ],
             
             # 抽象概念类
             'abstract_dream': [
                 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1519904981063-b0cf448d479e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1506197603052-3cc9c3a201bd?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1464822759844-d150baec0494?w=400&h=600&fit=crop'
             ],
             'abstract_memory': [
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1494790108755-2616c6106db4?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=600&fit=crop'
             ],
             'abstract_growth': [
                 'https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1518895949257-7621c3c786d7?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1463320726281-696a485928c7?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1502082553048-f009c37129b9?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop'
             ],
             'abstract_peace': [
                 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1519904981063-b0cf448d479e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1506197603052-3cc9c3a201bd?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1464822759844-d150baec0494?w=400&h=600&fit=crop'
             ],
             'abstract_emotion': [
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1494790108755-2616c6106db4?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&h=600&fit=crop'
             ],
             
             # 季节时间类
             'season_spring': [
                 'https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1518895949257-7621c3c786d7?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1463320726281-696a485928c7?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1502082553048-f009c37129b9?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop'
             ],
             'season_summer': [
                 'https://images.unsplash.com/photo-1505142468610-359e7d316be0?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1439066615861-d1af74d74000?w=400&h=600&fit=crop'
             ],
             'season_autumn': [
                 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1448375240586-882707db888b?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1518837695005-2083093ee35b?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1511593358241-7eea1f3c84e5?w=400&h=600&fit=crop'
             ],
             'season_winter': [
                 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1547036967-23d11aacaee0?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1483664852095-d6cc6870702d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1464822759844-d150baec0494?w=400&h=600&fit=crop'
             ],
             
             # 活动行为类
             'activity_sport': [
                 'https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop'
             ],
             'activity_art': [
                 'https://images.unsplash.com/photo-1513475382585-d06e58bcb0e0?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1494790108755-2616c6106db4?w=400&h=600&fit=crop'
             ],
             'activity_relax': [
                 'https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1484154218962-a197022b5858?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=400&h=600&fit=crop'
             ],
             
             # 动物宠物类
             'animal_cat': [
                 'https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1533738363-b7f9aef128ce?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1574158622682-e40e69881006?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1592194996308-7b43878e84a6?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1518791841217-8f162f1e1131?w=400&h=600&fit=crop'
             ],
             'animal_dog': [
                 'https://images.unsplash.com/photo-1552053831-71594a27632d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1518717758536-85ae29035b6d?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1583337130417-3346a1be7dee?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1561037404-61cd46aa615b?w=400&h=600&fit=crop'
             ],
             'animal_bird': [
                 'https://images.unsplash.com/photo-1444464666168-49d633b86797?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1520637836862-4d197d17c55a?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1464822759844-d150baec0494?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1519904981063-b0cf448d479e?w=400&h=600&fit=crop'
             ],
             'animal_wild': [
                 'https://images.unsplash.com/photo-1474511320723-9a56873867b5?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1464822759844-d150baec0494?w=400&h=600&fit=crop',
                 'https://images.unsplash.com/photo-1519904981063-b0cf448d479e?w=400&h=600&fit=crop'
             ]
         }
         
        # 根据选中主题和段落ID选择图片
        if selected_theme in xiaohongshu_images:
            theme_images = xiaohongshu_images[selected_theme]
        else:
            # 默认使用自然风光图片
            theme_images = xiaohongshu_images['nature_sky']
         
        # 使用哈希算法确保同一段落总是选择相同的图片
        import hashlib
        hash_input = f"{prompt}_{segment_id}".encode('utf-8')
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        image_index = hash_value % len(theme_images)
        selected_image = theme_images[image_index]
        
        print(f"选择图片: {selected_image} (索引: {image_index})")
        print(f"=== 图片匹配完成 ===")
        
        return selected_image

    def _analyze_ai_description(self, prompt_text: str) -> dict:
        """
        分析AI生成的图片描述，提取关键信息
        """
        analysis = {
            'scene_type': 'general',
            'dominant_emotion': 'neutral',
            'visual_elements': []
        }
        
        # 场景类型分析
        scene_keywords = {
            'nature_mountain': ['山', '山峰', '山脉', '高山', '雪山', '峰峦', '登山', '徒步'],
            'nature_ocean': ['海', '海洋', '海滩', '海岸', '波浪', '海水', '沙滩', '海边'],
            'nature_forest': ['森林', '树林', '树木', '绿色', '叶子', '植物', '自然'],
            'nature_flower': ['花', '花朵', '花园', '鲜花', '花瓣', '盛开', '绽放'],
            'nature_sky': ['天空', '云', '云朵', '蓝天', '白云', '晴空', '天际'],
            'city_modern': ['城市', '建筑', '高楼', '现代', '都市', '摩天大楼'],
            'city_street': ['街道', '马路', '街景', '商店', '行人', '车辆'],
            'lifestyle_food': ['食物', '美食', '餐厅', '菜品', '料理', '烹饪'],
            'lifestyle_travel': ['旅行', '旅游', '景点', '度假', '探索', '冒险'],
            'lifestyle_fashion': ['时尚', '服装', '穿搭', '风格', '潮流', '搭配'],
            'animal_pet': ['宠物', '猫', '狗', '动物', '可爱', '毛茸茸'],
            'animal_bird': ['鸟', '小鸟', '飞鸟', '翅膀', '飞翔', '羽毛'],
            'animal_wild': ['野生动物', '兔子', '松鼠', '蝴蝶', '昆虫', '野生']
        }
        
        for scene_type, keywords in scene_keywords.items():
            for keyword in keywords:
                if keyword in prompt_text:
                    analysis['scene_type'] = scene_type
                    break
            if analysis['scene_type'] != 'general':
                break
        
        # 情感分析
        emotion_keywords = {
            '温暖': ['温暖', '温馨', '舒适', '柔和', '亲切'],
            '宁静': ['宁静', '安静', '平静', '祥和', '静谧'],
            '活力': ['活力', '生机', '充满', '活跃', '动感'],
            '浪漫': ['浪漫', '唯美', '梦幻', '美丽', '优雅'],
            '神秘': ['神秘', '深邃', '朦胧', '幽深', '隐秘'],
            '壮观': ['壮观', '雄伟', '壮丽', '震撼', '宏伟']
        }
        
        for emotion, keywords in emotion_keywords.items():
            for keyword in keywords:
                if keyword in prompt_text:
                    analysis['dominant_emotion'] = emotion
                    break
            if analysis['dominant_emotion'] != 'neutral':
                break
        
        # 视觉元素提取
        visual_elements = []
        element_keywords = ['颜色', '光线', '阴影', '纹理', '形状', '线条', '构图', '透视', '对比', '明暗']
        for element in element_keywords:
            if element in prompt_text:
                visual_elements.append(element)
        
        analysis['visual_elements'] = visual_elements
        
        return analysis

    def _get_emotion_context(self, prompt_text: str, emotion: str) -> str:
        """
        获取情感词汇的上下文
        """
        words = prompt_text.split()
        for i, word in enumerate(words):
            if emotion in word:
                start = max(0, i - 2)
                end = min(len(words), i + 3)
                return ' '.join(words[start:end])
        return ""

    def _get_intelligent_default_theme(self, prompt_text: str) -> str:
        """
        智能选择默认主题
        """
        # 基于文本内容的简单分类
        if any(word in prompt_text for word in ['自然', '风景', '户外', '天空', '云']):
            return 'nature_sky'
        elif any(word in prompt_text for word in ['城市', '建筑', '现代', '都市']):
            return 'city_modern'
        elif any(word in prompt_text for word in ['动物', '宠物', '可爱']):
            return 'animal_pet'
        elif any(word in prompt_text for word in ['食物', '美食', '料理']):
            return 'lifestyle_food'
        else:
            return 'nature_sky'  # 默认自然风光

    # 图片合成功能

class ImageComposer:
    """图文合成服务类 - 小红书风格"""
    
    def __init__(self):
        # 小红书风格的竖版尺寸比例 (3:4)
        self.canvas_width = 600
        self.canvas_height = 800
        self.padding = 30
        self.corner_radius = 20
    
    async def compose_image_text(self, image_url: str, text: str, summary: str) -> str:
        """合成小红书风格的图文"""
        try:
            # 下载原图片
            response = requests.get(image_url, timeout=10)
            if response.status_code != 200:
                raise Exception(f"无法下载图片: {response.status_code}")
            
            # 打开图片
            original_image = Image.open(io.BytesIO(response.content))
            
            # 创建画布 - 小红书风格的竖版比例
            canvas = Image.new('RGB', (self.canvas_width, self.canvas_height), '#FAFAFA')
            
            # 调整原图片大小，保持比例并填充大部分画布
            image_height = int(self.canvas_height * 0.75)  # 图片占75%高度
            image_width = self.canvas_width - 2 * self.padding
            
            # 保持原图比例的同时调整大小
            original_ratio = original_image.width / original_image.height
            target_ratio = image_width / image_height
            
            if original_ratio > target_ratio:
                # 原图更宽，以高度为准
                new_height = image_height
                new_width = int(new_height * original_ratio)
                resized_image = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # 居中裁剪
                crop_x = (new_width - image_width) // 2
                resized_image = resized_image.crop((crop_x, 0, crop_x + image_width, new_height))
            else:
                # 原图更高，以宽度为准
                new_width = image_width
                new_height = int(new_width / original_ratio)
                resized_image = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # 居中裁剪
                crop_y = (new_height - image_height) // 2
                resized_image = resized_image.crop((0, crop_y, new_width, crop_y + image_height))
            
            # 创建圆角图片
            rounded_image = self._create_rounded_image(resized_image, self.corner_radius)
            
            # 将图片粘贴到画布上
            image_y = self.padding
            canvas.paste(rounded_image, (self.padding, image_y), rounded_image)
            
            # 在图片底部区域添加文字 - 小红书风格
            draw = ImageDraw.Draw(canvas)
            
            # 加载字体
            try:
                # Windows系统字体
                title_font = ImageFont.truetype("msyh.ttc", 20)  # 标题字体
                content_font = ImageFont.truetype("msyh.ttc", 14)  # 内容字体
                tag_font = ImageFont.truetype("msyh.ttc", 12)  # 标签字体
            except:
                try:
                    title_font = ImageFont.truetype("arial.ttf", 20)
                    content_font = ImageFont.truetype("arial.ttf", 14)
                    tag_font = ImageFont.truetype("arial.ttf", 12)
                except:
                    title_font = ImageFont.load_default()
                    content_font = ImageFont.load_default()
                    tag_font = ImageFont.load_default()
            
            # 文字区域起始位置
            text_start_y = image_y + image_height + 20
            text_area_height = self.canvas_height - text_start_y - self.padding
            
            # 绘制标题 - 小红书风格的标题
            title_text = f"✨ {summary}"
            title_y = text_start_y
            draw.text((self.padding, title_y), title_text, fill='#2C2C2C', font=title_font)
            
            # 绘制内容预览 - 限制行数，添加省略号
            content_y = title_y + 35
            max_width = self.canvas_width - 2 * self.padding
            
            # 处理文本内容，添加小红书风格的表情符号
            processed_text = self._process_text_for_xiaohongshu(text)
            lines = self._wrap_text(processed_text, content_font, max_width, draw)
            
            # 最多显示3行内容
            max_lines = 3
            for i, line in enumerate(lines[:max_lines]):
                line_y = content_y + i * 22
                if line_y + 22 < self.canvas_height - self.padding - 30:
                    # 如果是最后一行且还有更多内容，添加省略号
                    if i == max_lines - 1 and len(lines) > max_lines:
                        line = line[:30] + "..."
                    draw.text((self.padding, line_y), line, fill='#666666', font=content_font)
            
            # 添加小红书风格的标签
            tag_y = self.canvas_height - self.padding - 25
            tags = ["#AI生成", "#创意分享", "#长文本"]
            tag_x = self.padding
            
            for tag in tags:
                # 绘制标签背景
                tag_bbox = draw.textbbox((0, 0), tag, font=tag_font)
                tag_width = tag_bbox[2] - tag_bbox[0] + 16
                tag_height = 20
                
                # 检查是否超出画布宽度
                if tag_x + tag_width > self.canvas_width - self.padding:
                    break
                
                # 绘制圆角矩形背景
                self._draw_rounded_rectangle(draw, (tag_x, tag_y, tag_x + tag_width, tag_y + tag_height), 
                                           fill='#F0F0F0', radius=10)
                
                # 绘制标签文字
                text_x = tag_x + 8
                text_y = tag_y + 3
                draw.text((text_x, text_y), tag, fill='#888888', font=tag_font)
                
                tag_x += tag_width + 8
            
            # 保存合成图片到内存
            output_buffer = io.BytesIO()
            canvas.save(output_buffer, format='JPEG', quality=95)
            output_buffer.seek(0)
            
            # 转换为base64编码
            image_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
            return f"data:image/jpeg;base64,{image_base64}"
            
        except Exception as e:
            print(f"小红书风格图文合成失败: {e}")
            # 返回原图片URL作为备选
            return image_url
    
    def _create_rounded_image(self, image: Image.Image, radius: int) -> Image.Image:
        """创建圆角图片"""
        # 创建一个带alpha通道的图片
        rounded = Image.new('RGBA', image.size, (0, 0, 0, 0))
        
        # 创建圆角遮罩
        mask = Image.new('L', image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, image.size[0], image.size[1]), radius=radius, fill=255)
        
        # 将原图转换为RGBA
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        # 应用遮罩
        rounded.paste(image, (0, 0))
        rounded.putalpha(mask)
        
        return rounded
    
    def _draw_rounded_rectangle(self, draw, coords, fill, radius):
        """绘制圆角矩形"""
        x1, y1, x2, y2 = coords
        draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=fill)
    
    def _process_text_for_xiaohongshu(self, text: str) -> str:
        """为文本添加小红书风格的处理"""
        # 限制文本长度
        if len(text) > 150:
            text = text[:150] + "..."
        
        # 添加一些小红书风格的表情符号（随机）
        emojis = ["💫", "✨", "🌟", "💖", "🎀", "🌸", "🦋", "🌈"]
        import random
        if random.random() < 0.3:  # 30%概率添加表情符号
            emoji = random.choice(emojis)
            text = f"{emoji} {text}"
        
        return text
    
    def _wrap_text(self, text: str, font, max_width: int, draw) -> List[str]:
        """文字自动换行 - 优化版"""
        lines = []
        
        # 按句号、感叹号、问号等分割
        sentences = text.replace('。', '。\n').replace('！', '！\n').replace('？', '？\n').split('\n')
        
        current_line = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 检查当前行加上新句子是否超宽
            test_line = current_line + sentence
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line = test_line
            else:
                # 如果当前行不为空，先保存当前行
                if current_line.strip():
                    lines.append(current_line.strip())
                
                # 检查单个句子是否需要进一步分割
                if len(sentence) > 20:  # 如果句子太长，按字符分割
                    words = list(sentence)  # 中文按字符分割
                    current_line = ""
                    for word in words:
                        test_line = current_line + word
                        bbox = draw.textbbox((0, 0), test_line, font=font)
                        width = bbox[2] - bbox[0]
                        
                        if width <= max_width:
                            current_line = test_line
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = word
                else:
                    current_line = sentence
        
        # 添加最后一行
        if current_line.strip():
            lines.append(current_line.strip())
        
        return lines

# 初始化服务
image_generator = ImageGenerationService()
image_composer = ImageComposer()

# AI服务函数（待实现具体API调用）
def _detect_text_type(text: str) -> str:
    """
    检测文本类型：叙事类、议论类、说明类等
    """
    narrative_keywords = ['故事', '情节', '人物', '对话', '场景', '时间', '地点', '发生', '经历', '遇到']
    argumentative_keywords = ['观点', '论证', '认为', '因为', '所以', '然而', '但是', '首先', '其次', '总之']
    descriptive_keywords = ['介绍', '说明', '特点', '功能', '方法', '步骤', '原理', '结构', '组成']
    
    narrative_score = sum(1 for keyword in narrative_keywords if keyword in text)
    argumentative_score = sum(1 for keyword in argumentative_keywords if keyword in text)
    descriptive_score = sum(1 for keyword in descriptive_keywords if keyword in text)
    
    if narrative_score >= argumentative_score and narrative_score >= descriptive_score:
        return 'narrative'  # 叙事类
    elif argumentative_score >= descriptive_score:
        return 'argumentative'  # 议论类
    else:
        return 'descriptive'  # 说明类

def _smart_segment_text(text: str, text_type: str) -> List[str]:
    """
    根据文本类型智能分段
    """
    segments = []
    
    if text_type == 'narrative':
        # 叙事类：按故事发展阶段、场景转换、人物互动分段
        scene_markers = ['突然', '接着', '然后', '后来', '最后', '终于', '此时', '这时', '当时', '那天', '第二天']
        dialogue_markers = ['说道', '回答', '问道', '喊道', '笑着说', '严肃地说']
        
        # 按段落和场景标记分割
        paragraphs = text.split('\n\n')
        current_segment = ""
        
        for para in paragraphs:
            if len(current_segment) + len(para) > 1200:  # 控制段落长度
                if current_segment.strip():
                    segments.append(current_segment.strip())
                current_segment = para
            else:
                current_segment += "\n\n" + para if current_segment else para
                
            # 检查是否有场景转换标记
            for marker in scene_markers:
                if marker in para and len(current_segment) > 500:
                    segments.append(current_segment.strip())
                    current_segment = ""
                    break
        
        if current_segment.strip():
            segments.append(current_segment.strip())
            
    elif text_type == 'argumentative':
        # 议论类：按论点模块分段
        argument_markers = ['首先', '其次', '再次', '最后', '另外', '此外', '然而', '但是', '因此', '所以']
        
        paragraphs = text.split('\n\n')
        current_segment = ""
        
        for para in paragraphs:
            if any(marker in para for marker in argument_markers) and len(current_segment) > 600:
                if current_segment.strip():
                    segments.append(current_segment.strip())
                current_segment = para
            else:
                current_segment += "\n\n" + para if current_segment else para
                
            if len(current_segment) > 1500:  # 控制段落长度
                segments.append(current_segment.strip())
                current_segment = ""
        
        if current_segment.strip():
            segments.append(current_segment.strip())
            
    else:  # descriptive 说明类
        # 说明类：按说明对象的不同维度分段
        dimension_markers = ['外观', '功能', '特点', '优势', '方法', '步骤', '原理', '结构', '用途', '效果']
        
        paragraphs = text.split('\n\n')
        current_segment = ""
        
        for para in paragraphs:
            if any(marker in para for marker in dimension_markers) and len(current_segment) > 600:
                if current_segment.strip():
                    segments.append(current_segment.strip())
                current_segment = para
            else:
                current_segment += "\n\n" + para if current_segment else para
                
            if len(current_segment) > 1200:  # 控制段落长度
                segments.append(current_segment.strip())
                current_segment = ""
        
        if current_segment.strip():
            segments.append(current_segment.strip())
    
    # 如果分段结果太少或太多，使用备选方案
    if len(segments) < 2 or len(segments) > 8:
        # 按长度均匀分割
        text_length = len(text)
        target_segments = min(5, max(3, text_length // 800))
        segment_length = text_length // target_segments
        
        segments = []
        for i in range(0, text_length, segment_length):
            segment = text[i:i+segment_length]
            if segment.strip():
                segments.append(segment.strip())
    
    return segments[:6]  # 最多6段

async def analyze_text_with_doubao(text: str, style_prompt: str) -> List[TextSegment]:
    """
    使用字节火山方舟 doubao 1.6 Thinking 智能分析文本
    """
    # 1. 检测文本类型
    text_type = _detect_text_type(text)
    print(f"检测到文本类型: {text_type}")
    
    # 2. 智能分段
    raw_segments = _smart_segment_text(text, text_type)
    print(f"智能分段完成，共{len(raw_segments)}段")
    
    if not client:
        # 如果API未配置，使用本地增强的分段逻辑
        segments = []
        for i, segment_text in enumerate(raw_segments):
            # 生成更好的摘要
            summary = _generate_local_summary(segment_text, i + 1, text_type)
            # 生成小红书风格的图片提示词
            image_prompt = _generate_xiaohongshu_prompt(segment_text, style_prompt, text_type)
            
            segments.append(TextSegment(
                id=i + 1,
                content=segment_text,
                summary=summary,
                image_prompt=image_prompt
            ))
        return segments
    
    try:
        # 3. 构建增强的分析提示词
        analysis_prompt = f"""
你是小红书内容创作专家，请将以下{text_type}类型的长文本进行智能分析和视觉化处理。

文本类型说明：
- narrative（叙事类）：关注故事发展、场景转换、人物情感
- argumentative（议论类）：关注论点逻辑、观点对比、论证过程  
- descriptive（说明类）：关注对象特征、功能介绍、操作步骤

任务要求：
1. 【内容分析】为每个已分段的内容提供精准的主题摘要
2. 【视觉化转换】为每段生成小红书爆款风格的图片描述，必须遵循以下结构：
   
   **Prompt结构："小红书爆款配图 + 核心场景 + 主体元素 + 动作/状态 + 氛围色调 + 风格细节"**
   
   **示例模板：**
   - 叙事类："小红书爆款配图，[具体场景]，[人物/主体][服饰/特征]，[动作/表情]，[情感氛围]，[色调描述]，竖版构图，背景虚化，留白20%，画面柔和"
   - 议论类："小红书爆款配图，[概念场景]，[象征元素]，[对比/层次]，[理性氛围]，[简洁色调]，现代简约风格，竖版构图，重点突出"
   - 说明类："小红书爆款配图，[产品/对象场景]，[核心特征展示]，[功能体现]，[清晰明亮氛围]，[干净色调]，产品摄影风格，竖版构图"

3. 【风格要求】
   - 竖版比例（3:4或9:16），符合小红书浏览习惯
   - 清新治愈滤镜，画面柔和不刺眼
   - 构图留白20%，主体突出
   - 背景适度虚化，增强焦点
   - 色调温暖或清新，避免过于浓烈

4. 【输出格式】严格按照JSON数组格式返回，每个对象包含：
   - id: 段落编号
   - content: 段落原文内容  
   - summary: 内容主题摘要（20字以内）
   - image_prompt: 小红书风格图片描述（按上述结构生成）

指定风格融合：{style_prompt}
文本类型：{text_type}

待分析的分段内容：
"""
        
        # 添加分段内容
        for i, segment in enumerate(raw_segments):
            analysis_prompt += f"\n\n【第{i+1}段】\n{segment}"
        
        analysis_prompt += "\n\n请返回JSON数组格式的分析结果，确保每个image_prompt都能让人清晰想象出具体的小红书风格画面。"
        
        # 调用doubao 1.6 Thinking API
        completion = client.chat.completions.create(
            model="doubao-seed-1.6-thinking",
            messages=[
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=6000,
            temperature=0.6  # 降低随机性，提高一致性
        )
        
        response_content = completion.choices[0].message.content
        print(f"Doubao API响应长度: {len(response_content)}")
        
        # 尝试解析JSON响应
        try:
            # 提取JSON部分（可能包含在代码块中）
            if "```json" in response_content:
                json_start = response_content.find("```json") + 7
                json_end = response_content.find("```", json_start)
                json_content = response_content[json_start:json_end].strip()
            elif "[" in response_content and "]" in response_content:
                json_start = response_content.find("[")
                json_end = response_content.rfind("]") + 1
                json_content = response_content[json_start:json_end]
            else:
                json_content = response_content
            
            segments_data = json.loads(json_content)
            print(f"成功解析JSON，包含{len(segments_data)}个段落")
            
            # 转换为TextSegment对象
            segments = []
            for i, segment_data in enumerate(segments_data):
                # 确保使用原始分段内容
                original_content = raw_segments[i] if i < len(raw_segments) else segment_data.get("content", f"段落 {i + 1}")
                
                segments.append(TextSegment(
                    id=segment_data.get("id", i + 1),
                    content=original_content,
                    summary=segment_data.get("summary", f"第{i + 1}段内容摘要"),
                    image_prompt=segment_data.get("image_prompt", _generate_xiaohongshu_prompt(original_content, style_prompt, text_type))
                ))
            
            return segments
            
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {str(e)}")
            print(f"响应内容: {response_content[:500]}...")
            
    except Exception as e:
        print(f"调用doubao API失败: {str(e)}")
    
    # 备选方案：使用本地增强逻辑
    print("使用本地增强分段逻辑")
    segments = []
    for i, segment_text in enumerate(raw_segments):
        summary = _generate_local_summary(segment_text, i + 1, text_type)
        image_prompt = _generate_xiaohongshu_prompt(segment_text, style_prompt, text_type)
        
        segments.append(TextSegment(
            id=i + 1,
            content=segment_text,
            summary=summary,
            image_prompt=image_prompt
        ))
    
    return segments

def _generate_local_summary(text: str, segment_id: int, text_type: str) -> str:
    """
    生成本地摘要
    """
    # 提取关键词
    key_phrases = []
    if text_type == 'narrative':
        narrative_keywords = ['故事', '情节', '人物', '场景', '情感', '经历', '遇到', '发生']
        key_phrases = [kw for kw in narrative_keywords if kw in text]
    elif text_type == 'argumentative':
        argument_keywords = ['观点', '论证', '分析', '认为', '因为', '所以', '结论']
        key_phrases = [kw for kw in argument_keywords if kw in text]
    else:
        descriptive_keywords = ['介绍', '说明', '特点', '功能', '方法', '原理', '结构']
        key_phrases = [kw for kw in descriptive_keywords if kw in text]
    
    # 生成摘要
    if key_phrases:
        return f"第{segment_id}段：{key_phrases[0]}相关内容"
    else:
        return f"第{segment_id}段内容摘要"

def _generate_xiaohongshu_prompt(text: str, style_prompt: str, text_type: str) -> str:
    """
    生成小红书风格的图片提示词 - 按照标准格式
    【风格定位】+【核心内容】+【视觉元素】+【排版要求】+【细节补充】
    专为长文转图片工具设计，适合小红书平台发布
    """
    print(f"正在为文本生成提示词: {text[:50]}...")
    
    # 提取文章核心信息
    core_info = _extract_article_core_info(text)
    visual_elements = _build_visual_elements(core_info, text_type)
    
    # 【风格定位】- 确定整体视觉风格
    style_positioning = _build_style_positioning(core_info, text_type, style_prompt)
    
    # 【核心内容】- 提取文章主要内容和关键信息
    core_content = _build_core_content(core_info, text)
    
    # 【视觉元素】- 构建具体的视觉描述
    visual_desc = _build_visual_description(visual_elements, core_info)
    
    # 【排版要求】- 小红书平台的排版规范
    layout_requirements = _build_layout_requirements()
    
    # 【细节补充】- 技术参数和质量要求
    detail_supplements = _build_detail_supplements(core_info, text_type)
    
    # 确保每个部分都有内容，避免空值
    if not style_positioning.strip():
        style_positioning = "清新自然风格"
    if not core_content.strip():
        core_content = "温馨故事场景"
    if not visual_desc.strip():
        visual_desc = "柔和光线，温暖色调"
    
    # 按格式组合提示词，使用分号分隔确保格式清晰
    prompt_sections = [
        f"【风格定位】{style_positioning.strip()}",
        f"【核心内容】{core_content.strip()}",
        f"【视觉元素】{visual_desc.strip()}",
        f"【排版要求】{layout_requirements.strip()}",
        f"【细节补充】{detail_supplements.strip()}"
    ]
    
    full_prompt = "；".join(prompt_sections)
    
    # 长度控制（保持在300字以内，确保生成效果）
    if len(full_prompt) > 300:
        # 智能压缩各部分内容，保持核心信息
        style_positioning = _truncate_text(style_positioning, 15)
        core_content = _truncate_text(core_content, 50)
        visual_desc = _truncate_text(visual_desc, 60)
        layout_requirements = _truncate_text(layout_requirements, 30)
        detail_supplements = _truncate_text(detail_supplements, 25)
        
        prompt_sections = [
            f"【风格定位】{style_positioning}",
            f"【核心内容】{core_content}",
            f"【视觉元素】{visual_desc}",
            f"【排版要求】{layout_requirements}",
            f"【细节补充】{detail_supplements}"
        ]
        full_prompt = "；".join(prompt_sections)
    
    print(f"生成的图片提示词: {full_prompt}")
    return full_prompt

def _truncate_text(text: str, max_length: int) -> str:
    """智能截断文本，保持完整性"""
    if len(text) <= max_length:
        return text
    
    # 在逗号或句号处截断
    for i in range(max_length - 1, max_length // 2, -1):
        if text[i] in '，。、':
            return text[:i]
    
    # 如果没有合适的截断点，直接截断
    return text[:max_length]

def _extract_article_core_info(text: str) -> dict:
    """
    深度提取文章核心信息：专为小红书图片生成优化
    """
    import re
    
    core_info = {
        'main_theme': '',
        'key_scenes': [],
        'core_elements': {
            'characters': [],  # 人物
            'objects': [],     # 物品
            'locations': [],   # 地点
            'emotions': [],    # 情感
            'actions': [],     # 动作
            'time': '',        # 时间
            'atmosphere': ''   # 氛围
        },
        'content_focus': '',  # 内容重点
        'specific_details': [],  # 具体细节描述
        'visual_elements': []    # 可视化元素
    }
    
    # 第一步：提取文章中的具体描述性句子
    sentences = [s.strip() for s in re.split(r'[。！？]', text) if len(s.strip()) > 5]
    
    # 第二步：智能提取主题和重点内容
    # 提取文章开头的主要内容作为主题
    if sentences:
        first_sentence = sentences[0]
        # 提取主题关键词
        theme_keywords = re.findall(r'[一-龯]{2,6}', first_sentence)
        if theme_keywords:
            core_info['main_theme'] = theme_keywords[0]
        
        # 提取内容重点（通常在前几句中）
        content_parts = []
        for sentence in sentences[:3]:
            if len(sentence) >= 10:
                content_parts.append(sentence[:25])  # 取前25个字符作为重点
        core_info['content_focus'] = "，".join(content_parts[:2])
    
    # 第三步：提取情感和氛围词汇
    emotion_words = ['快乐', '愉悦', '温暖', '舒适', '宁静', '激动', '感动', '美好', '幸福', '满足']
    atmosphere_words = ['温馨', '清新', '自然', '现代', '时尚', '简约', '优雅', '活力', '宁静', '明亮', '柔和']
    
    text_lower = text
    for word in emotion_words:
        if word in text_lower:
            core_info['core_elements']['emotions'].append(word)
    
    for word in atmosphere_words:
        if word in text_lower:
            core_info['core_elements']['atmosphere'] = word
            break
    
    # 如果没有找到氛围词，根据内容推断
    if not core_info['core_elements']['atmosphere']:
        if any(word in text for word in ['学习', '工作', '办公']):
            core_info['core_elements']['atmosphere'] = '简约'
        elif any(word in text for word in ['自然', '户外', '风景']):
            core_info['core_elements']['atmosphere'] = '清新'
        elif any(word in text for word in ['家', '温暖', '舒适']):
            core_info['core_elements']['atmosphere'] = '温馨'
        else:
            core_info['core_elements']['atmosphere'] = '自然'
    
    # 第四步：提取具体的物品和场景元素
    # 常见的可视化物品
    visual_objects = ['书', '咖啡', '花', '植物', '电脑', '手机', '笔记本', '杯子', '窗户', '桌子', '椅子', '灯', '相机']
    for obj in visual_objects:
        if obj in text:
            core_info['core_elements']['objects'].append(obj)
    
    # 场景关键词
    scene_keywords = ['室内', '户外', '办公室', '咖啡厅', '家里', '公园', '街道', '教室', '图书馆']
    for scene in scene_keywords:
        if scene in text:
            core_info['core_elements']['locations'].append(scene)
    
    # 第五步：提取关键场景描述
    descriptive_patterns = [
        r'.*[看到听到感受到].*',  # 感官描述
        r'.*[美丽漂亮温暖舒适].*',  # 感受描述
        r'.*[阳光光线色彩颜色].*',  # 视觉元素
    ]
    
    for sentence in sentences:
        for pattern in descriptive_patterns:
            if re.search(pattern, sentence) and len(sentence) <= 40:
                core_info['key_scenes'].append(sentence)
                break
        if len(core_info['key_scenes']) >= 2:  # 最多保留2个关键场景
            break
    
    return core_info

def _analyze_content_semantics(text: str) -> dict:
    """
    分析文章内容的语义特征，而不是简单的关键词匹配
    """
    analysis = {
        'theme': '生活美学',
        'atmosphere': '温馨自然',
        'emotions': [],
        'visual_elements': []
    }
    
    # 基于内容长度和复杂度的主题判断
    if any(word in text for word in ['森林', '树', '山', '海', '天空', '阳光', '月光', '花', '草', '风', '云']):
        analysis['theme'] = '自然风光'
        analysis['atmosphere'] = '宁静自然'
        analysis['visual_elements'] = ['自然光线', '清新色调', '广角视野']
    elif any(word in text for word in ['城市', '街道', '建筑', '灯光', '车', '人群', '商店']):
        analysis['theme'] = '都市生活'
        analysis['atmosphere'] = '现代都市'
        analysis['visual_elements'] = ['城市灯光', '现代建筑', '人文气息']
    elif any(word in text for word in ['人', '朋友', '家人', '微笑', '拥抱', '眼神', '心情', '感情']):
        analysis['theme'] = '人物情感'
        analysis['atmosphere'] = '温暖情感'
        analysis['visual_elements'] = ['温暖色调', '人物特写', '情感表达']
    elif any(word in text for word in ['食物', '美食', '咖啡', '茶', '香味', '味道', '烹饪']):
        analysis['theme'] = '美食生活'
        analysis['atmosphere'] = '温馨美味'
        analysis['visual_elements'] = ['暖色调', '精致摆盘', '生活质感']
    
    # 情感分析
    if any(word in text for word in ['温暖', '舒适', '安心', '治愈', '宁静']):
        analysis['emotions'].append('温暖治愈')
    if any(word in text for word in ['快乐', '开心', '兴奋', '活力', '阳光']):
        analysis['emotions'].append('活力阳光')
    if any(word in text for word in ['思考', '深沉', '哲学', '思辨', '内省']):
        analysis['emotions'].append('深沉思考')
    if any(word in text for word in ['浪漫', '唯美', '梦幻', '诗意', '美丽']):
        analysis['emotions'].append('浪漫唯美')
    
    return analysis
    
def _build_visual_elements(core_info: dict, text_type: str) -> dict:
    """
    根据核心信息构建视觉元素描述 - 基于具体内容而非模板
    """
    visual = {
        'main_subject': '',
        'scene_description': '',
        'style_elements': '',
        'technical_specs': ''
    }
    
    # 使用具体的文章内容构建主体描述
    if core_info['specific_details']:
        # 从具体描述中提取主体
        first_detail = core_info['specific_details'][0]
        visual['main_subject'] = first_detail
    elif core_info['content_focus']:
        # 使用内容重点作为主体
        visual['main_subject'] = core_info['content_focus'][:20]
    else:
        # 兜底方案
        visual['main_subject'] = f"{core_info['main_theme']}场景"
    
    # 构建场景描述 - 结合具体内容和视觉元素
    scene_parts = []
    
    # 添加具体的视觉元素
    if core_info['visual_elements']:
        scene_parts.extend(core_info['visual_elements'][:2])
    
    # 添加氛围描述
    if core_info['core_elements']['atmosphere']:
        scene_parts.append(f"{core_info['core_elements']['atmosphere']}氛围")
    
    # 添加情感色彩
    if core_info['core_elements']['emotions']:
        emotion = core_info['core_elements']['emotions'][0]
        scene_parts.append(f"{emotion}感")
    
    visual['scene_description'] = "，".join(scene_parts) if scene_parts else "温馨生活场景"
    
    # 构建风格元素
    style_parts = []
    if core_info['core_elements']['atmosphere']:
        style_parts.append(core_info['core_elements']['atmosphere'])
    if core_info['core_elements']['emotions']:
        style_parts.append(core_info['core_elements']['emotions'][0])
    visual['style_elements'] = "，".join(style_parts) if style_parts else "温馨自然"
    
    # 技术规格
    visual['technical_specs'] = "高清摄影，专业构图，自然光线"
    
    return visual

# 全局风格模板系统
STYLE_TEMPLATES = {
    "温馨治愈": {
        "base_style": "温馨治愈风格",
        "color_palette": "暖色调，米色，奶茶色，浅粉色",
        "lighting": "柔和自然光，温暖光线",
        "composition": "居中构图，温馨氛围",
        "texture": "柔和质感，温润材质",
        "mood": "温馨舒适，治愈感"
    },
    "清新自然": {
        "base_style": "清新自然风格",
        "color_palette": "清新色调，绿色，白色，浅蓝色",
        "lighting": "明亮自然光，清晨阳光",
        "composition": "简洁构图，自然布局",
        "texture": "清爽质感，自然材质",
        "mood": "清新舒适，自然感"
    },
    "现代简约": {
        "base_style": "现代简约风格",
        "color_palette": "简约色调，黑白灰，高级灰",
        "lighting": "均匀光线，现代感照明",
        "composition": "几何构图，简洁布局",
        "texture": "光滑质感，现代材质",
        "mood": "简约大气，现代感"
    },
    "文艺复古": {
        "base_style": "文艺复古风格",
        "color_palette": "复古色调，棕色，深绿，暗红",
        "lighting": "柔和侧光，复古氛围",
        "composition": "经典构图，文艺布局",
        "texture": "复古质感，怀旧材质",
        "mood": "文艺气息，复古感"
    },
    "活力青春": {
        "base_style": "活力青春风格",
        "color_palette": "明亮色调，橙色，黄色，粉色",
        "lighting": "明亮光线，活力照明",
        "composition": "动感构图，活跃布局",
        "texture": "光泽质感，活力材质",
        "mood": "青春活力，动感十足"
    }
}

def _determine_unified_style(core_info: dict, text_type: str, style_prompt: str) -> str:
    """
    确定统一的风格模板
    """
    atmosphere = core_info['core_elements'].get('atmosphere', '')
    emotions = core_info['core_elements'].get('emotions', [])
    
    # 优先使用用户指定的风格
    if style_prompt and style_prompt != "现代简约风格":
        if "温馨" in style_prompt or "治愈" in style_prompt:
            return "温馨治愈"
        elif "清新" in style_prompt or "自然" in style_prompt:
            return "清新自然"
        elif "文艺" in style_prompt or "复古" in style_prompt:
            return "文艺复古"
        elif "活力" in style_prompt or "青春" in style_prompt:
            return "活力青春"
        else:
            return "现代简约"
    
    # 基于内容自动判断风格
    if '温馨' in atmosphere or '温暖' in atmosphere:
        return "温馨治愈"
    elif '清新' in atmosphere or '自然' in atmosphere:
        return "清新自然"
    elif emotions and ('快乐' in emotions or '愉悦' in emotions):
        return "活力青春"
    elif '文艺' in atmosphere or '怀旧' in atmosphere:
        return "文艺复古"
    else:
        return "现代简约"

def _build_style_positioning(core_info: dict, text_type: str, style_prompt: str) -> str:
    """
    构建【风格定位】部分 - 确定整体视觉风格（统一风格）
    """
    # 确定统一风格模板
    unified_style = _determine_unified_style(core_info, text_type, style_prompt)
    template = STYLE_TEMPLATES[unified_style]
    
    # 构建风格描述
    style_elements = [
        template["base_style"],
        template["mood"]
    ]
    
    return "，".join(style_elements)

def _build_core_content(core_info: dict, text: str) -> str:
    """
    构建【核心内容】部分 - 提取文章主要内容和关键信息
    """
    content_parts = []
    
    # 从原文中提取关键句子，避免重复
    import re
    sentences = [s.strip() for s in re.split(r'[。！？]', text) if 15 <= len(s.strip()) <= 40]
    
    if sentences:
        # 选择最有描述性的句子
        descriptive_sentence = None
        for sentence in sentences[:3]:  # 只检查前3句
            if any(word in sentence for word in ['的', '在', '像', '如', '美', '光', '色', '温', '柔']):
                descriptive_sentence = sentence
                break
        
        if descriptive_sentence:
            content_parts.append(descriptive_sentence)
    
    # 添加主要主题（如果与已有内容不重复）
    if core_info.get('main_theme'):
        theme = core_info['main_theme']
        if not content_parts or theme not in content_parts[0]:
            content_parts.append(theme)
    
    # 如果没有足够内容，添加通用描述
    if not content_parts:
        content_parts.append("温馨生活场景")
    
    return "，".join(content_parts[:2])  # 最多2个内容点

def _build_visual_description(visual_elements: dict, core_info: dict) -> str:
    """
    构建【视觉元素】部分 - 统一风格的视觉描述
    """
    # 获取统一风格模板
    unified_style = _determine_unified_style(core_info, "", "")
    template = STYLE_TEMPLATES[unified_style]
    
    visual_parts = []
    
    # 主体描述（限制长度）
    if visual_elements.get('main_subject'):
        subject = visual_elements['main_subject']
        if len(subject) <= 20:  # 只使用简短的主体描述
            visual_parts.append(subject)
    
    # 场景描述（限制长度）
    if visual_elements.get('scene_description'):
        scene = visual_elements['scene_description']
        if len(scene) <= 15:
            visual_parts.append(scene)
    
    # 应用统一的色彩和光线
    visual_parts.append(template["color_palette"])
    visual_parts.append(template["lighting"])
    
    # 构图和质感
    visual_parts.append(template["composition"])
    
    # 如果没有足够的视觉元素，添加默认值
    if len(visual_parts) < 3:
        visual_parts.extend([template["color_palette"], template["lighting"]])
    
    return "，".join(visual_parts[:4])  # 限制最多4个元素

def _build_layout_requirements() -> str:
    """
    构建【排版要求】部分 - 小红书平台的排版规范
    """
    return "竖版构图9:16，小红书风格排版，清晰易读，视觉层次分明"

def _build_detail_supplements(core_info: dict, text_type: str) -> str:
    """
    构建【细节补充】部分 - 统一风格的技术参数和质量要求
    """
    # 获取统一风格模板
    unified_style = _determine_unified_style(core_info, text_type, "")
    template = STYLE_TEMPLATES[unified_style]
    
    details = []
    
    # 基础技术要求（统一）
    details.append("高清摄影")
    details.append("专业构图")
    
    # 应用风格特定的质感
    details.append(template["texture"])
    
    # 根据文本类型添加特定要求
    if text_type == '叙事文':
        details.append("情感表达")
    elif text_type == '说明文':
        details.append("简洁明了")
    else:
        details.append("视觉美感")
    
    return "，".join(details)

def _get_xiaohongshu_style_keywords(theme: str) -> str:
    """
    根据主题生成对应的小红书风格关键词
    """
    base_style = "小红书风格摄影，竖版构图9:16，清新自然，柔和光线"
    
    theme_styles = {
        '自然风光': f"{base_style}，自然光影，广角视野，层次丰富，绿色清新，治愈系色调",
        '都市生活': f"{base_style}，都市时尚，现代感强，暖色调滤镜，生活质感，ins风格",
        '人物情感': f"{base_style}，人像摄影，情感表达，温暖色调，柔焦效果，治愈系氛围",
        '学习工作': f"{base_style}，简约风格，干净背景，专业质感，明亮色调，文艺气息",
        '美食生活': f"{base_style}，美食摄影，诱人色泽，精致摆盘，暖色调，食欲感强",
        '旅行探索': f"{base_style}，旅行摄影，异域风情，色彩丰富，探索感，记录美好"
    }
    
    return theme_styles.get(theme, f"{base_style}，高饱和度，温暖色调，生活美学")

def _analyze_text_content(text: str) -> dict:
    """
    智能分析文本内容，提取关键信息
    """
    import re
    
    analysis = {
        'main_theme': '',
        'key_objects': [],
        'actions': [],
        'emotions': [],
        'settings': [],
        'colors': [],
        'time_context': '',
        'specific_details': []
    }
    
    # 扩展的关键词库
    theme_keywords = {
        '自然风光': ['山', '海', '湖', '河', '森林', '树', '花', '草', '天空', '云', '阳光', '月亮', '星星', '雨', '雪', '风景', '自然', '户外'],
        '都市生活': ['城市', '街道', '建筑', '高楼', '商店', '咖啡厅', '餐厅', '办公室', '地铁', '公交', '车', '马路', '灯光', '夜景'],
        '人物情感': ['人', '女孩', '男孩', '朋友', '家人', '恋人', '孩子', '老人', '微笑', '拥抱', '眼神', '表情', '手势'],
        '学习工作': ['学习', '工作', '书', '笔', '电脑', '手机', '办公', '会议', '思考', '写作', '阅读', '研究', '项目'],
        '美食生活': ['食物', '美食', '咖啡', '茶', '蛋糕', '面包', '水果', '蔬菜', '料理', '烹饪', '餐具', '厨房', '味道'],
        '旅行探索': ['旅行', '旅游', '探索', '冒险', '路', '地图', '背包', '相机', '景点', '文化', '体验', '发现'],
        '艺术创作': ['艺术', '画', '音乐', '创作', '设计', '色彩', '线条', '构图', '灵感', '美感', '创意', '表达'],
        '运动健康': ['运动', '健身', '跑步', '游泳', '瑜伽', '健康', '活力', '汗水', '坚持', '挑战', '目标', '成就']
    }
    
    # 情感词汇库
    emotion_keywords = {
        '温暖治愈': ['温暖', '治愈', '舒适', '安心', '放松', '宁静', '平和', '柔和', '温馨', '甜蜜'],
        '活力阳光': ['活力', '阳光', '开心', '快乐', '兴奋', '充满', '生机', '活跃', '明亮', '积极'],
        '深沉思考': ['思考', '深沉', '沉思', '理性', '智慧', '哲学', '内省', '冥想', '专注', '严肃'],
        '浪漫唯美': ['浪漫', '唯美', '梦幻', '美丽', '优雅', '诗意', '柔美', '迷人', '动人', '醉人'],
        '忧郁深邃': ['忧郁', '深邃', '孤独', '思念', '怀念', '伤感', '惆怅', '沉重', '复杂', '细腻']
    }
    
    # 场景设定词汇
    setting_keywords = {
        '室内': ['房间', '家', '客厅', '卧室', '厨房', '书房', '办公室', '教室', '图书馆', '咖啡厅', '餐厅'],
        '室外': ['公园', '街道', '广场', '海边', '山上', '森林', '花园', '阳台', '天台', '操场', '田野'],
        '特殊场所': ['学校', '医院', '商场', '机场', '车站', '博物馆', '剧院', '体育馆', '工厂', '农场']
    }
    
    # 时间语境
    time_keywords = {
        '早晨': ['早晨', '清晨', '黎明', '日出', '晨光', '朝阳'],
        '白天': ['白天', '中午', '下午', '阳光', '明亮', '日光'],
        '傍晚': ['傍晚', '黄昏', '夕阳', '日落', '余晖', '暮色'],
        '夜晚': ['夜晚', '深夜', '月光', '星光', '灯火', '夜色']
    }
    
    # 颜色词汇
    color_keywords = ['红', '橙', '黄', '绿', '蓝', '紫', '粉', '白', '黑', '灰', '金', '银', '彩色', '鲜艳', '柔和', '明亮', '暗淡']
    
    text_lower = text.lower()
    
    # 分析主题
    theme_scores = {}
    for theme, keywords in theme_keywords.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > 0:
            theme_scores[theme] = score
    
    if theme_scores:
        analysis['main_theme'] = max(theme_scores.items(), key=lambda x: x[1])[0]
    
    # 提取具体对象（更智能的方式）
    for theme, keywords in theme_keywords.items():
        for keyword in keywords:
            if keyword in text and keyword not in analysis['key_objects']:
                analysis['key_objects'].append(keyword)
    
    # 分析情感氛围
    for emotion, keywords in emotion_keywords.items():
        if any(keyword in text for keyword in keywords):
            analysis['emotions'].append(emotion)
    
    # 分析场景设定
    for setting, keywords in setting_keywords.items():
        if any(keyword in text for keyword in keywords):
            analysis['settings'].append(setting)
    
    # 分析时间语境
    for time_period, keywords in time_keywords.items():
        if any(keyword in text for keyword in keywords):
            analysis['time_context'] = time_period
            break
    
    # 提取颜色信息
    analysis['colors'] = [color for color in color_keywords if color in text]
    
    # 提取具体细节（文本中的具体描述）
    sentences = text.split('。')
    for sentence in sentences[:3]:  # 只取前3句
        if len(sentence.strip()) > 10:  # 过滤太短的句子
            analysis['specific_details'].append(sentence.strip()[:30])  # 截取前30字符
    
    return analysis

def _generate_visual_elements(content_analysis: dict, text_type: str) -> dict:
    """
    根据内容分析生成视觉元素描述
    """
    visual = {
        'main_subject': '',
        'composition': '',
        'lighting': '',
        'atmosphere': '',
        'color_scheme': ''
    }
    
    # 主体对象
    if content_analysis['key_objects']:
        main_obj = content_analysis['key_objects'][0]
        visual['main_subject'] = f"{main_obj}为主体"
    else:
        visual['main_subject'] = "生活场景为主体"
    
    # 构图方式
    if content_analysis['main_theme'] == '自然风光':
        visual['composition'] = "广角构图，层次丰富"
    elif content_analysis['main_theme'] == '人物情感':
        visual['composition'] = "人物特写，情感聚焦"
    elif content_analysis['main_theme'] == '美食生活':
        visual['composition'] = "俯视构图，精致摆盘"
    else:
        visual['composition'] = "居中构图，平衡和谐"
    
    # 光线效果
    if content_analysis['time_context'] == '早晨':
        visual['lighting'] = "柔和晨光，温暖明亮"
    elif content_analysis['time_context'] == '傍晚':
        visual['lighting'] = "金色夕阳，浪漫温馨"
    elif content_analysis['time_context'] == '夜晚':
        visual['lighting'] = "柔和灯光，氛围温馨"
    else:
        visual['lighting'] = "自然光线，明亮清晰"
    
    # 氛围营造
    if content_analysis['emotions']:
        emotion = content_analysis['emotions'][0]
        if emotion == '温暖治愈':
            visual['atmosphere'] = "温暖治愈氛围，心灵平静"
        elif emotion == '活力阳光':
            visual['atmosphere'] = "活力四射氛围，充满生机"
        elif emotion == '浪漫唯美':
            visual['atmosphere'] = "浪漫唯美氛围，梦幻迷人"
        elif emotion == '深沉思考':
            visual['atmosphere'] = "深沉思考氛围，理性沉稳"
        else:
            visual['atmosphere'] = "忧郁深邃氛围，情感细腻"
    else:
        visual['atmosphere'] = "温暖治愈氛围"
    
    # 色彩方案
    if content_analysis['colors']:
        main_color = content_analysis['colors'][0]
        visual['color_scheme'] = f"{main_color}色调为主"
    elif content_analysis['main_theme'] == '自然风光':
        visual['color_scheme'] = "绿色自然色调"
    elif content_analysis['main_theme'] == '都市生活':
        visual['color_scheme'] = "现代都市色调"
    else:
        visual['color_scheme'] = "温暖柔和色调"
    
    return visual

def _build_narrative_scene(content_analysis: dict, visual_elements: dict) -> str:
    """
    构建叙事类场景描述
    """
    scene_parts = []
    
    # 主体描述
    scene_parts.append(visual_elements['main_subject'])
    
    # 添加具体细节
    if content_analysis['specific_details']:
        detail = content_analysis['specific_details'][0]
        scene_parts.append(f"展现{detail}的场景")
    
    # 场景设定
    if content_analysis['settings']:
        setting = content_analysis['settings'][0]
        scene_parts.append(f"{setting}环境")
    
    # 光线和构图
    scene_parts.append(visual_elements['lighting'])
    scene_parts.append(visual_elements['composition'])
    
    return "，".join(scene_parts)

def _build_concept_visual(content_analysis: dict, visual_elements: dict) -> str:
    """
    构建概念类视觉描述
    """
    concept_parts = []
    
    # 抽象概念
    if content_analysis['main_theme']:
        concept_parts.append(f"{content_analysis['main_theme']}概念可视化")
    else:
        concept_parts.append("抽象概念可视化")
    
    # 几何元素
    concept_parts.append("简约几何元素")
    
    # 色彩方案
    concept_parts.append(visual_elements['color_scheme'])
    
    # 现代感
    concept_parts.append("现代设计感")
    
    return "，".join(concept_parts)

def _build_display_style(content_analysis: dict, visual_elements: dict) -> str:
    """
    构建展示类风格描述
    """
    display_parts = []
    
    # 主体展示
    display_parts.append(visual_elements['main_subject'])
    
    # 展示方式
    if content_analysis['main_theme'] == '美食生活':
        display_parts.append("美食摄影风格，诱人色泽")
    elif content_analysis['main_theme'] == '学习工作':
        display_parts.append("产品展示风格，简洁明了")
    else:
        display_parts.append("清晰展示风格，细节丰富")
    
    # 背景处理
    display_parts.append("简洁背景，突出主体")
    
    # 光线效果
    display_parts.append(visual_elements['lighting'])
    
    return "，".join(display_parts)

async def generate_images_with_seedream(segments: List[TextSegment], style_prompt: str) -> List[GeneratedImage]:
    """
    使用SeeDream 4.0生成图片
    """
    images = []
    
    for segment in segments:
        try:
            if client:
                # 使用火山方舟SeeDream 4.0 API生成图片
                combined_prompt = f"{style_prompt}, {segment.image_prompt}"
                print(f"生成图片 - 段落{segment.id}: {combined_prompt}")
                
                response = client.images.generate(
                    model=VOLCANO_IMAGE_MODEL,
                    prompt=combined_prompt,
                    size=VOLCANO_IMAGE_SIZE
                )
                
                if hasattr(response, 'data') and response.data and len(response.data) > 0:
                    image_url = response.data[0].url
                    images.append(GeneratedImage(
                        segment_id=segment.id,
                        image_url=image_url,
                        thumbnail_url=image_url,  # 可以后续添加缩略图生成逻辑
                        status="completed"
                    ))
                elif hasattr(response, 'images') and response.images and len(response.images) > 0:
                    # 尝试另一种响应格式
                    image_url = response.images[0].url if hasattr(response.images[0], 'url') else response.images[0]
                    images.append(GeneratedImage(
                        segment_id=segment.id,
                        image_url=image_url,
                        thumbnail_url=image_url,
                        status="completed"
                    ))
                else:
                    # API调用失败，使用备选方案
                    print(f"API响应格式异常: {response}")
                    images.append(GeneratedImage(
                        segment_id=segment.id,
                        image_url=f"https://picsum.photos/600/800?random={segment.id + 100}",
                        thumbnail_url=f"https://picsum.photos/150/200?random={segment.id + 100}",
                        status="failed"
                    ))
            else:
                # 客户端未初始化，使用演示图片
                # 使用不同的颜色和更好的文本来模拟真实图片
                colors = ["4f46e5", "7c3aed", "db2777", "dc2626", "ea580c", "d97706", "65a30d", "059669", "0891b2", "0284c7"]
                color = colors[(segment.id - 1) % len(colors)]
                
                # 使用AI生成的image_prompt来创建真正相关的图片
                image_prompt = segment.image_prompt if segment.image_prompt else f"{style_prompt}，{segment.content[:100]}..."
                
                try:
                    # 使用AI图片生成服务生成图片
                    original_image_url = await image_generator.generate_image(image_prompt, segment.id)
                    
                    # 使用图文合成服务创建最终的图文合成图片
                    composed_image_url = await image_composer.compose_image_text(
                        original_image_url, 
                        segment.content, 
                        segment.summary
                    )
                    
                    images.append(GeneratedImage(
                        segment_id=segment.id,
                        image_url=composed_image_url,
                        thumbnail_url=composed_image_url,  # 缩略图使用同一张图片
                        status="completed"
                    ))
                    
                except Exception as generation_error:
                    print(f"图片生成或合成失败 (段落 {segment.id}): {generation_error}")
                    # 使用备选方案：生成基于内容的占位图片
                    fallback_url = await image_generator._generate_demo_image(image_prompt, segment.id)
                    
                    images.append(GeneratedImage(
                        segment_id=segment.id,
                        image_url=fallback_url,
                        thumbnail_url=fallback_url,
                        status="completed"
                    ))
                
        except Exception as api_error:
            print(f"SeeDream API调用失败: {api_error}")
            # 使用备选方案
            images.append(GeneratedImage(
                segment_id=segment.id,
                image_url=f"https://picsum.photos/600/800?random={segment.id + 200}",
                thumbnail_url=f"https://picsum.photos/150/200?random={segment.id + 200}",
                status="failed"
            ))
    
    return images

# API端点
@app.get("/")
async def root():
    return {"message": "创意加速器 API 服务正在运行", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "long-text-to-images"}

@app.post("/api/analyze-text", response_model=TextAnalysisResponse)
async def analyze_text(request: TextAnalysisRequest):
    """
    分析长文本，智能拆分为多个段落
    """
    try:
        # 验证输入
        if len(request.text.strip()) == 0:
            raise HTTPException(status_code=400, detail="文本内容不能为空")
        
        if len(request.text) > 10000:  # 限制1万字
            raise HTTPException(status_code=400, detail="文本长度不能超过10000字")
        
        # 调用AI分析服务
        segments = await analyze_text_with_doubao(request.text, request.style_prompt or "现代简约风格")
        
        # 限制段落数量
        if request.max_segments and len(segments) > request.max_segments:
            segments = segments[:request.max_segments]
        
        return TextAnalysisResponse(
            segments=segments,
            total_count=len(segments),
            estimated_time=len(segments) * 30  # 每张图片预估30秒
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文本分析失败: {str(e)}")

@app.post("/api/generate-images", response_model=ImageGenerationResponse)
async def generate_images(request: ImageGenerationRequest):
    """
    根据文本段落生成对应图片
    """
    try:
        # 验证输入
        if not request.segments:
            raise HTTPException(status_code=400, detail="文本段落不能为空")
        
        # 生成批次ID
        import uuid
        batch_id = str(uuid.uuid4())
        
        # 调用图片生成服务
        images = await generate_images_with_seedream(request.segments, request.style_prompt)
        
        return ImageGenerationResponse(
            images=images,
            batch_id=batch_id,
            total_count=len(images)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")

@app.get("/api/batch-status/{batch_id}")
async def get_batch_status(batch_id: str):
    """
    查询批次生成状态
    """
    # TODO: 实现批次状态查询逻辑
    return {
        "batch_id": batch_id,
        "status": "completed",
        "progress": 100,
        "completed_count": 5,
        "total_count": 5
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)