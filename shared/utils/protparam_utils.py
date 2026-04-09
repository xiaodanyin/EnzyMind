"""
ProtParam工具函数
"""
import requests
from bs4 import BeautifulSoup


def send_expasy_param_request(url: str, data: dict) -> str:
    """发送ExPASy ProtParam请求"""
    session = requests.Session()
    session.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://web.expasy.org",
        "Referer": "https://web.expasy.org/protparam/",
        "Connection": "keep-alive",
    }
    
    try:
        response = session.post(url, files=data, headers=session.headers, timeout=60)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network request error: {e}")


def extract_and_process_protparam_html(html_content: str) -> str:
    """从ProtParam HTML响应中提取参数信息"""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        pre_tags = soup.find_all("pre")
        
        if not pre_tags or len(pre_tags) < 2:
            raise ValueError("Failed to locate the correct <pre> tag in the HTML content.")
        
        parameter_pre = pre_tags[1]
        pre_lines = parameter_pre.get_text().strip().split("\n")
        
        start_line = next((i for i, line in enumerate(pre_lines) if "Number of amino acids:" in line), None)
        end_line = next((i for i, line in enumerate(pre_lines) if "Grand average of hydropathicity (GRAVY):" in line), None)
        
        if start_line is None or end_line is None:
            raise ValueError("Failed to locate the required content in <pre>.")
        
        relevant_lines = pre_lines[start_line:end_line + 1]
        return "\n".join(relevant_lines)
        
    except Exception as e:
        return f"Error processing ProtParam HTML: {e}"


def convert_protparam_to_markdown(cleaned_html_content: str) -> str:
    """将ProtParam结果转换为Markdown格式"""
    lines = cleaned_html_content.strip().split("\n")
    markdown_output = "## ProtParam Results\n\n"
    
    for line in lines:
        markdown_output += f"- {line.strip()}\n"
    
    return markdown_output
