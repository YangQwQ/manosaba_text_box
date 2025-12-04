from typing import Optional, Dict, Any
import re

import openai
from config import ConfigLoader


class AIClientManager:
    """AI客户端管理器"""
    
    def __init__(self):
        self.clients = {}
        self.current_client = None
        self.config_loader = ConfigLoader()
        
    def initialize_client(self, client_type: str, config: Dict[str, Any]) -> bool:
        """初始化AI客户端"""
        try:
            openai.api_key = config.get("api_key", "")
            openai.base_url = config.get("base_url", "http://localhost:11434/v1/")
            self.current_client = client_type

            return self._test_connection(config.get("model", ""))
            
        except Exception as e:
            print(f"初始化AI客户端失败: {e}")
            return False
    
    def _test_connection(self, model_name: str) -> bool:
        """测试连接"""
        try:
            # 发送一个简单的测试请求
            response = openai.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return response.choices[0].message.content is not None
        except Exception as e:
            print(f"连接测试失败: {e}")
            return False
    
    def _load_config_from_file(self) -> Dict[str, Any]:
        """从配置文件加载配置"""
        config_path = get_resource_path(os.path.join("config", "settings.yml"))
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config or {}
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return {}
    
    def _save_config_to_file(self, config: Dict[str, Any]) -> bool:
        """保存配置到文件"""
        config_path = get_resource_path(os.path.join("config", "settings.yml"))
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        """获取可用模型配置"""
        # 使用ConfigLoader获取模型配置
        return self.config_loader.get_available_models()
    
class SentimentAnalyzer:
    def __init__(self):
        self.client_manager = AIClientManager()  # 使用客户端管理器
        self.is_initialized = False
        self.emotion_list = ["无感情", "愤怒", "嫌弃", "疑惑", "惊讶", "伤心", "害羞", "开心", "恐惧", "无语", "大笑"]
        
        self.selected_emotion = None #用来在generate_image里显示选择的表情

        # 更严格的规则提示词
        self.rule_prompt = """你是一个专门聊天文本的情感分析助手。你的任务是：分析用户输入文本的情感，并从以下11个选项中选择最匹配的一个：["无感情", "愤怒", "嫌弃", "疑惑", "惊讶", "伤心", "害羞", "开心", "恐惧", "无语", "大笑"]。

规则：
1. 只返回情感词汇，不要添加其他内容
2. 文本没有实际含义时，可能需要推测前后文来判断情感
3. 无法判断时返回"无感情"

请严格按照这个格式回复，现在请回复"好的"以确认你理解了规则。"""
        
    def initialize(self, client_type: str, config: Dict[str, Any]) -> bool:
        """
        初始化函数 - 使用新的配置结构
        """
        try:
            # 使用客户端管理器初始化
            success = self.client_manager.initialize_client(client_type, config)
            
            if success:
                # 发送规则提示词
                response = self._send_request(self.rule_prompt)
                # 直接检查回复，不需要单独的方法
                confirmation_keywords = ['好的', '明白', '了解']
                response_lower = response.lower()
                self.is_initialized = any(keyword in response_lower for keyword in confirmation_keywords)
                
                if self.is_initialized:
                    print(f"{client_type} 情感分析器初始化成功")
                else:
                    print(f"AI未正确确认规则，回复: {response}")
                
                return self.is_initialized
            else:
                print(f"{client_type} 客户端初始化失败")
                return False
                
        except Exception as e:
            print(f"初始化失败: {e}")
            self.is_initialized = False
            return False
    

    def _send_request(self, message: str) -> str:
        """发送请求到对应的API"""
        try:
            messages = [
                {"role": "system", "content": self.rule_prompt},
                {"role": "user", "content": message}
            ]

            # 获取模型配置
            models = self.client_manager.get_available_models()
            current_client = self.client_manager.current_client
            model_name = models[current_client]["model"] if current_client in models else "deepseek-chat"

            response = openai.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.1,
                max_tokens=10,
                stream=False
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"请求失败: {e}")
            raise

    def _extract_emotion(self, response: str) -> Optional[str]:
        """从AI回复中提取情感词汇"""
        # 清理回复文本
        cleaned_response = re.sub(r'[^\w\u4e00-\u9fff]', '', response)
        
        return cleaned_response if cleaned_response in self.emotion_list else None
        
    def switch_api(self, new_client_type: str, config: Dict[str, Any]) -> bool:
        """
        切换AI客户端
        """
        print(f"正在切换到 {new_client_type}")
        
        try:
            success = self.client_manager.initialize_client(new_client_type, config)
            
            if success:
                self.is_initialized = True
                print(f"成功切换到 {new_client_type}")
                return True
            else:
                print(f"切换到 {new_client_type} 失败")
                return False
                
        except Exception as e:
            print(f"切换过程中发生错误: {e}")
            return False
    
    def analyze_sentiment(self, text: str) -> Optional[str]:
        """
        情感检测函数
        """
        if not self.client_manager.current_client:
            print("未设置AI客户端，请先调用initialize函数")
            return None
        
        try:
            response = self._send_request(text)
            print(f"AI原始回复: {response}")
            
            # 提取情感
            self.selected_emotion = self._extract_emotion(response)
            return self.selected_emotion if self.selected_emotion else None
                
        except Exception as e:
            print(f"情感分析请求失败: {e}")
            return None

    
# # 使用示例
# def main():
#     analyzer = SentimentAnalyzer()
    
#     # 初始化 DeepSeek
#     # print("=== 初始化 DeepSeek ===")
#     # deepseek_success = analyzer.initialize(
#     #     api_type='deepseek',
#     #     api_key='api_key',  # 替换为你的 API key
#     #     base_url='https://api.deepseek.com',
#     #     model='deepseek-chat'
#     # )
    
#     print("=== 初始化 qwen ===")
#     deepseek_success = analyzer.initialize(
#         api_type='ollama',
#         api_key='api_key',  # 替换为你的 API key
#         base_url='http://localhost:11434/v1/',
#         model='qwen2.5'
#     )
#     if deepseek_success:
#         test_texts = [
#             "我草，你这个有点吊",
#             "嘻嘻",
#             "你什么意思！",
#             "我喜欢你",
#             "我不理解"
#         ]
        
#         for text in test_texts:
#             result = analyzer.analyze_sentiment(text)
#             print(f"文本: '{text}' -> 情感: {result}")
#             print("-" * 50)

# if __name__ == "__main__":
#     main()