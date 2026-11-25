"""Compatibility transport for explicitly selected historical n8n webhooks.

The public notebook client lives in agent_n8n.client. This module preserves the
original userID/message, multipart FASTA and NDJSON protocol without executing
any archived notebook.
"""

import uuid
import json
import requests
from pathlib import Path
from typing import Optional, Union, Iterator, Callable


def _in_notebook() -> bool:
    """检测是否在 Jupyter Notebook/Lab 环境中运行"""
    try:
        from IPython import get_ipython
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True  # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False
    except (ImportError, NameError, AttributeError):
        return False


def _display_markdown(text: str) -> None:
    """在 Jupyter 中以 Markdown 格式显示文本"""
    from IPython.display import display, Markdown
    # 预处理：格式化 [Used tools: ...] 块
    processed_text = _format_tool_usage_blocks(text)
    display(Markdown(processed_text))


def _format_tool_usage_blocks(text: str) -> str:
    """格式化 [Used tools: Tool: xxx, Input: {}, Result: [...]] 块"""
    import re
    
    if not text:
        return text
    
    # 匹配 [Used tools: ...] 模式
    pattern = r'\[Used tools:\s*Tool:\s*([^,]+),\s*Input:\s*(\{[^}]*\}),\s*Result:\s*(\[[\s\S]*?\])\]'
    
    def format_match(match):
        tool_name = match.group(1).strip()
        result_str = match.group(3)
        
        try:
            results = json.loads(result_str)
            formatted = f"\n\n---\n**⚙️ Tool: {tool_name}**\n\n"
            
            if results and len(results) > 0:
                result = results[0]
                if 'result' in result:
                    formatted += result['result'] + "\n"
                elif 'error' in result:
                    formatted += f"❌ **Error:** {result['error']}\n"
                else:
                    formatted += f"```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```\n"
            
            formatted += "---\n\n"
            return formatted
        except (json.JSONDecodeError, KeyError, IndexError):
            return f"\n\n> **⚙️ Tool Used:** {tool_name}\n\n"
    
    return re.sub(pattern, format_match, text)


def _parse_ndjson_line(line: str) -> Optional[dict]:
    """解析 NDJSON 行，返回解析结果或 None"""
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _extract_content_from_stream(response_text: str) -> str:
    """从流式响应文本中提取所有内容"""
    content_parts = []
    for line in response_text.split('\n'):
        parsed = _parse_ndjson_line(line)
        if parsed and parsed.get('type') == 'item' and 'content' in parsed:
            content_parts.append(parsed['content'])
    return ''.join(content_parts)


class LegacyWebhookClient:
    """
    EnzyMind N8N Agent 客户端
    
    每次实例化时会生成一个唯一的 userID，用于维护对话上下文。
    同一个实例的多次 chat 调用会共享同一个对话历史。
    
    在 Jupyter Notebook 中会自动将响应渲染为 Markdown 格式。
    """
    
    # N8N Webhook Production URL
    # 格式: https://<domain>/webhook/<path>
    DEFAULT_BASE_URL = "http://localhost:5678"
    WEBHOOK_PATH = "8e6add2a-15cd-4a13-be8f-937593f5680a"
    
    def __init__(
        self, 
        base_url: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout: int = 300,
        auto_display: bool = True,
        webhook_url: Optional[str] = None
    ):
        """
        初始化客户端
        
        Args:
            base_url: N8N服务的基础URL，默认使用 DEFAULT_BASE_URL
            user_id: 自定义userID，如果不提供则自动生成UUID
            timeout: 请求超时时间（秒），默认300秒（5分钟），因为AI推理可能需要较长时间
            auto_display: 是否在Jupyter环境中自动渲染Markdown，默认True
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip('/')
        self.user_id = user_id or str(uuid.uuid4())
        self.timeout = timeout
        self.webhook_url = f"{self.base_url}/webhook/{self.WEBHOOK_PATH}" if webhook_url is None else webhook_url
        self.auto_display = auto_display
        self._in_notebook = _in_notebook()
        
        # 打印初始化信息
        print(f"🤖 EnzyMind Agent initialized")
        print(f"   Session ID: {self.user_id}")
        
    def chat(
        self, 
        message: str, 
        fasta_file: Optional[Union[str, Path]] = None,
        display: bool = True,
        stream: Optional[bool] = None,
        on_tool_start: Optional[Callable[[int], None]] = None,
        on_tool_end: Optional[Callable[[int], None]] = None
    ) -> str:
        """
        发送消息并获取AI响应
        
        Args:
            message: 用户输入的消息
            fasta_file: 可选的FASTA文件路径，用于上传蛋白序列文件
            display: 是否显示响应（在Jupyter中渲染Markdown），默认True
            stream: 是否流式输出（实时打印响应），默认None（在Jupyter中自动启用）
            on_tool_start: 工具开始调用时的回调函数，参数为工具编号
            on_tool_end: 工具调用完成时的回调函数，参数为工具编号
            
        Returns:
            AI Agent的响应文本
            
        Raises:
            requests.RequestException: 请求失败时抛出
            FileNotFoundError: FASTA文件不存在时抛出
            ValueError: 响应格式错误时抛出
        """
        # 在 Jupyter 中默认启用流式输出
        if stream is None:
            stream = self._in_notebook
        
        try:
            if stream:
                result = self._chat_stream(message, fasta_file, on_tool_start, on_tool_end)
            elif fasta_file is not None:
                # 使用 multipart/form-data 上传文件
                result = self._chat_with_file(message, fasta_file)
            else:
                # 使用 JSON 格式发送纯文本消息
                result = self._chat_json(message)
            
            # 在 Jupyter 中自动渲染 Markdown（非流式模式）
            if display and self.auto_display and self._in_notebook and not stream:
                _display_markdown(result)
            
            return result
            
        except requests.Timeout:
            raise TimeoutError(
                f"请求超时（{self.timeout}秒）。AI推理可能需要更长时间，"
                "请尝试增加 timeout 参数。"
            )
        except requests.RequestException as e:
            raise RuntimeError(f"请求失败: {e}")
    
    def _chat_json(self, message: str) -> str:
        """使用 JSON 格式发送消息（无文件）"""
        payload = {
            "userID": self.user_id,
            "message": message
        }
        
        response = requests.post(
            self.webhook_url,
            json=payload,
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
                "Accept-Encoding": "identity"  # 禁用压缩
            }
        )
        response.raise_for_status()
        # 解析 NDJSON 流式响应
        return _extract_content_from_stream(response.text)
    
    def _chat_with_file(self, message: str, fasta_file: Union[str, Path]) -> str:
        """使用 multipart/form-data 格式发送消息和文件"""
        fasta_path = Path(fasta_file)
        
        if not fasta_path.exists():
            raise FileNotFoundError(f"FASTA文件不存在: {fasta_path}")
        
        if not fasta_path.is_file():
            raise ValueError(f"路径不是文件: {fasta_path}")
        
        # 准备 multipart/form-data 数据
        data = {
            "userID": self.user_id,
            "message": message
        }
        
        with open(fasta_path, 'rb') as f:
            files = {
                "data": (fasta_path.name, f, "text/plain")
            }
            
            response = requests.post(
                self.webhook_url,
                data=data,
                files=files,
                timeout=self.timeout,
                headers={
                    "Accept-Encoding": "identity"  # 禁用压缩
                }
            )
        
        response.raise_for_status()
        # 解析 NDJSON 流式响应
        return _extract_content_from_stream(response.text)
    
    def _chat_stream(
        self, 
        message: str, 
        fasta_file: Optional[Union[str, Path]] = None,
        on_tool_start: Optional[Callable[[int], None]] = None,
        on_tool_end: Optional[Callable[[int], None]] = None
    ) -> str:
        """流式发送消息并实时输出响应"""
        
        # 准备请求
        if fasta_file is not None:
            fasta_path = Path(fasta_file)
            if not fasta_path.exists():
                raise FileNotFoundError(f"FASTA文件不存在: {fasta_path}")
            if not fasta_path.is_file():
                raise ValueError(f"路径不是文件: {fasta_path}")
            
            data = {"userID": self.user_id, "message": message}
            with open(fasta_path, 'rb') as f:
                files = {"data": (fasta_path.name, f, "text/plain")}
                response = requests.post(
                    self.webhook_url,
                    data=data,
                    files=files,
                    timeout=self.timeout,
                    headers={"Accept-Encoding": "identity"},
                    stream=True
                )
        else:
            payload = {"userID": self.user_id, "message": message}
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Accept-Encoding": "identity"
                },
                stream=True
            )
        
        response.raise_for_status()
        
        # 判断是否在 Jupyter 环境
        use_jupyter_display = self._in_notebook
        display_handle = None
        
        if use_jupyter_display:
            from IPython.display import display, Markdown
            display_handle = display(Markdown("*🤔 正在思考...*"), display_id=True)
        
        # 流式解析和输出
        content_parts = []
        tool_count = 0
        last_was_end = False
        is_first_begin = True
        tool_indicator = ""
        
        def update_display():
            """更新 Jupyter 显示"""
            if use_jupyter_display and display_handle:
                full_content = ''.join(content_parts)
                display_text = tool_indicator + full_content if tool_indicator else full_content
                if not display_text.strip():
                    display_text = "*🤔 正在思考...*"
                display_handle.update(Markdown(display_text))
        
        # 逐块读取并处理
        buffer = ""
        for chunk in response.iter_content(chunk_size=1024):
            if not chunk:
                continue
            
            # 解码
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8', errors='ignore')
            
            buffer += chunk
            
            # 按行分割处理
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                if not line:
                    continue
                
                parsed = _parse_ndjson_line(line)
                if not parsed:
                    continue
                
                if parsed.get('type') == 'begin':
                    if is_first_begin:
                        is_first_begin = False
                    elif last_was_end:
                        # 工具调用完成
                        if on_tool_end:
                            on_tool_end(tool_count)
                        tool_indicator = f"*⚙️ Used {tool_count} tool(s)*\n\n"
                        update_display()
                    last_was_end = False
                    
                elif parsed.get('type') == 'end':
                    # 开始工具调用
                    tool_count += 1
                    if on_tool_start:
                        on_tool_start(tool_count)
                    tool_indicator = f"*⚙️ Calling tool #{tool_count}...*\n\n"
                    update_display()
                    last_was_end = True
                    
                elif parsed.get('type') == 'item' and 'content' in parsed:
                    content = parsed['content']
                    content_parts.append(content)
                    tool_indicator = ""  # 收到内容后清除工具指示
                    update_display()
                    last_was_end = False
        
        # 处理剩余 buffer
        if buffer.strip():
            parsed = _parse_ndjson_line(buffer.strip())
            if parsed and parsed.get('type') == 'item' and 'content' in parsed:
                content_parts.append(parsed['content'])
                update_display()
        
        # 确保最后的工具调用也标记完成
        if last_was_end:
            if on_tool_end:
                on_tool_end(tool_count)
            tool_indicator = f"*⚙️ Used {tool_count} tool(s)*\n\n"
            update_display()
        
        # 最终显示（格式化 [Used tools: ...] 块）
        final_content = ''.join(content_parts)
        formatted_content = _format_tool_usage_blocks(final_content)
        if use_jupyter_display and display_handle:
            display_handle.update(Markdown(formatted_content if formatted_content else "*无响应内容*"))
        
        return final_content
    
    def new_conversation(self) -> str:
        """
        开始新的对话（生成新的userID）
        
        Returns:
            新的userID
        """
        self.user_id = str(uuid.uuid4())
        return self.user_id
    
    def __repr__(self) -> str:
        return f"EnzyMindN8NClient(user_id='{self.user_id}', webhook_url='{self.webhook_url}')"


