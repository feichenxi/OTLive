import requests
import json
import logging
import re
import time
from typing import Optional, Dict
from datetime import datetime


def get_aitxt_logger():
    logger = logging.getLogger('aitxt')
    logger.setLevel(logging.INFO)
    return logger


def preprocess_username(name: str) -> str:
    if not name:
        return name
    
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', name)
    english_chars = re.findall(r'[a-zA-Z]', name)
    digit_chars = re.findall(r'[0-9]', name)
    
    if chinese_chars:
        return ''.join(chinese_chars)
    
    if english_chars:
        return ''.join(english_chars[:5])
    
    if digit_chars:
        return ''.join(digit_chars[:5])
    
    return '一串表情'


SSML_TEMPLATE = '''你是一个专业的语音内容生成助手，擅长使用SSML标签创造富有感情的语音内容。

【SSML标签说明 - 只允许使用以下标签！】

1. <speak>根节点标签（必须包含所有内容）
   只允许设置rate属性控制语速，不要添加其他属性！
   - rate: 语速，正常语速为1，稍快为1.05，稍慢为0.95
   正确示例：<speak rate="1">感谢大哥送来的礼物</speak>
   错误示例：<speak end="="11=" pitch=".8" volume="2">（禁止！）

2. <break/>停顿标签
   - time: 停顿时长，如"300ms"、"500ms"、"1s"（范围：50ms-10s）
   示例：感谢大哥<break time="300ms"/>送来的礼物

【禁止使用的标签和属性】
- 禁止使用<sub>标签
- 禁止使用<say-as>标签
- 禁止在<speak>上设置pitch、volume、end、bgm等属性
- 禁止使用任何未列出的标签
违反以上规则会导致语音合成失败！

【用户昵称说明】
用户昵称 {user} 已经预处理过，只包含可读的中文或英文字符，直接使用即可，不需要任何特殊标签处理。
称呼规范：用"xx哥"、"xx姐"、"xx大哥"、"xx大姐"，不要用"小xx"

【礼物价值与情感表达】
根据礼物价值等级 {value_level} 调整语气和情感：
- 巨大：极度激动、惊喜、夸张表达，语速稍快
- 大：非常开心、热情、真诚感谢
- 中：开心、温暖、亲切
- 小：温馨、友好、轻松
- 微：轻松、随意
- 无：简单感谢

【表达多样性要求】
每次生成的感谢语必须不同，避免重复和套路化：
1. 变换句式：疑问句、感叹句、陈述句交替使用
2. 变换开头：可以用"哇"、"感谢"、"谢谢"、"爱了"等不同开头
3. 变换结尾：可以用"大气"、"棒棒哒"、"爱你"、"支持"、"么么哒"等
4. 变换语气词：适当加入"呀"、"呢"、"哦"、"啦"、"哟"等
5. 变换停顿位置：不要总在同一个地方停顿
6. 根据礼物名称灵活发挥：提到礼物特点或名字
7. 加入互动感：像朋友聊天一样自然
8. 不要每句都用感叹号，有时用句号或问号更自然

【输出要求 - 必须严格遵守！】
1. 必须用 <speak rate="1">...</speak> 包裹全部内容，rate值根据情感调整
2. 控制纯文本长度在15-40字（不含SSML标签）
3. 合理使用<break/>停顿增强表现力，最多2-3个停顿
4. 只使用<speak>和<break/>两个标签，禁止使用其他任何标签
5. 昵称直接写文本，不要用任何标签包裹

【主播介绍】
{user_prompt}

主播介绍包含主播的性别、性格、说话风格等信息，生成感谢语时必须参照：
1. 主播性别：决定说话语气和风格
2. 主播性格：活泼、温柔、幽默、高冷等，语气要匹配
3. 说话风格：口语化程度、常用语气词、表达习惯等

【当前礼物信息】
用户：{user}
礼物：{gift_name}
数量：{count}
价值等级：{value_level}

请生成感谢语（直接输出SSML内容，不要解释）：'''


class GiftTextGenerator:
    def __init__(self, config: Dict):
        self.enabled = config.get('enabled', False)
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', '')
        self.endpoint = config.get('endpoint', '')
        self.timeout = config.get('timeout', 30)
        
        self.logger = get_aitxt_logger()
        
    def generate_text(self, user: str, gift_name: str, count: int, diamond_count: int, value_level: str = '小', template: Optional[str] = None, custom_prompt: Optional[str] = None, msg_id: int = None) -> str:
        if not self.enabled:
            return None

        if not custom_prompt:
            self.logger.warning("未提供房间级AI提示词，跳过生成")
            return None

        user = preprocess_username(user)

        start_time = time.time()
        msg_id_str = f"msg_id={msg_id}, " if msg_id else ""
        try:
            prompt = self._build_prompt(user, gift_name, count, value_level, custom_prompt)
            response = self._call_api(prompt)
            elapsed_time = time.time() - start_time

            if response and 'choices' in response and len(response['choices']) > 0:
                text = response['choices'][0]['message']['content'].strip()
                self.logger.info(f"AI文本生成成功: {text}")
                print(f"[AI文本生成] {msg_id_str}输入: 用户={user}, 礼物={gift_name}x{count}, 价值={diamond_count}钻 | 输出: {text} | 耗时: {elapsed_time:.2f}秒")
                return text
            else:
                self.logger.warning(f"AI响应格式异常: {response}")
                return None

        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error(f"AI文本生成失败: {e}")
            print(f"[AI文本生成] {msg_id_str}输入: 用户={user}, 礼物={gift_name}x{count}, 价值={diamond_count}钻 | 失败: {e} | 耗时: {elapsed_time:.2f}秒")
            return None
    
    def _build_prompt(self, user: str, gift_name: str, count: int, value_level: str, custom_prompt: Optional[str] = None) -> dict:
        full_prompt = SSML_TEMPLATE.format(
            user_prompt=custom_prompt,
            user=user,
            gift_name=gift_name,
            count=count,
            value_level=value_level
        )
        
        return {
            'system': '你是一个专业的语音内容生成助手，请严格按照SSML格式输出，不要添加任何解释或额外内容。',
            'user': full_prompt
        }
    
    def _call_api(self, prompt: dict) -> Optional[Dict]:
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        messages = []
        if prompt['system']:
            messages.append({
                'role': 'system',
                'content': prompt['system']
            })
        messages.append({
            'role': 'user',
            'content': prompt['user']
        })
        
        data = {
            'model': self.model,
            'messages': messages,
            'max_tokens': 200,
            'temperature': 0.8,
            'top_p': 0.95
        }
        
        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API请求失败: {e}")
            return None
    
    def is_enabled(self) -> bool:
        return self.enabled and bool(self.api_key)
