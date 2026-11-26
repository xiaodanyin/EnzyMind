"""
数据提取工具 - 从Jupyter Notebook提取测试结果
"""
import json
import nbformat
import re
import sys
from typing import List, Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class TestResult:
    """测试结果数据结构"""
    uniprot_id: str
    response_text: str
    predicted_sequence: str = None
    predicted_length: int = None
    predicted_molecular_weight: float = None
    
    def __post_init__(self):
        pass


class DataExtractor:
    """数据提取器"""
    
    def __init__(self, parse_predictions: bool = False):
        """
        初始化数据提取器
        
        Args:
            parse_predictions: 是否进行预解析（默认False，让LLM直接处理原始内容）
        """
        self.parse_predictions = parse_predictions
    
    def extract_results_from_notebook(self, notebook_path: str) -> List[TestResult]:
        """从notebook提取测试结果"""
        print(f"📖 正在从notebook提取数据: {notebook_path}")
        
        try:
            with open(notebook_path, 'r', encoding='utf-8') as f:
                nb = nbformat.read(f, as_version=4)
        except Exception as e:
            raise Exception(f"无法读取notebook文件: {e}")
        
        results = []
        current_uniprot_id = None
        
        for cell in nb.cells:
            if cell.cell_type == 'code':
                # 从代码单元格提取UniProt ID
                source = cell.source
                # 尝试多种模式匹配UniProt ID
                uniprot_match = re.search(r'uniprot ID ([A-Z0-9]+)', source, re.IGNORECASE)
                if not uniprot_match:
                    # 尝试匹配括号中的UniProt ID，如 (B8MKR3)
                    uniprot_match = re.search(r'\(([A-Z][0-9][A-Z0-9]{3}[0-9])\)', source)
                if uniprot_match:
                    current_uniprot_id = uniprot_match.group(1)
                    print(f"   🔍 找到UniProt ID: {current_uniprot_id}")
                
                # 从输出中提取响应文本
                if current_uniprot_id and 'outputs' in cell and cell.outputs:
                    for output in cell.outputs:
                        if output.output_type == 'display_data' and 'data' in output:
                            if 'text/markdown' in output.data:
                                response_text = output.data['text/markdown']
                                
                                result = TestResult(
                                    uniprot_id=current_uniprot_id,
                                    response_text=response_text
                                )
                                
                                # 可选：解析预测结果（默认不解析，让LLM处理）
                                if self.parse_predictions:
                                    self._parse_predictions(result)
                                    print(f"   ✓ 提取并解析结果: {current_uniprot_id}")
                                else:
                                    print(f"   ✓ 提取原始输出: {current_uniprot_id}")
                                
                                results.append(result)
                                current_uniprot_id = None  # 重置，避免重复
                                break
        
        print(f"📊 总共提取到 {len(results)} 个测试结果")
        return results
    
    def _parse_predictions(self, result: TestResult):
        """解析响应文本中的预测结果"""
        text = result.response_text
        
        # 提取序列长度
        length_patterns = [
            r'length[:\s]*(\d+)',
            r'(\d+)\s*amino acids',
            r'sequence.*?(\d+).*?residues'
        ]
        for pattern in length_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result.predicted_length = int(match.group(1))
                break
        
        # 提取分子量
        mw_patterns = [
            r'molecular weight[:\s]*([\d,]+\.?\d*)\s*(?:Da|daltons?)',
            r'([\d,]+\.?\d*)\s*Da',
            r'weight[:\s]*([\d,]+\.?\d*)'
        ]
        for pattern in mw_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                mw_str = match.group(1).replace(',', '')
                result.predicted_molecular_weight = float(mw_str)
                break
        
        # 提取氨基酸序列（查找连续的大写字母序列）
        seq_pattern = r'[ACDEFGHIKLMNPQRSTVWY]{50,}'
        seq_match = re.search(seq_pattern, text)
        if seq_match:
            result.predicted_sequence = seq_match.group(0)
    
    def save_results_to_json(self, results: List[TestResult], output_file: str):
        """将提取的结果保存为JSON文件"""
        data = []
        for result in results:
            data.append(asdict(result))
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 测试结果已保存到: {output_file}")
        return output_file
    
    def load_results_from_json(self, json_file: str) -> List[TestResult]:
        """从JSON文件加载测试结果"""
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        results = []
        for item in data:
            result = TestResult(**item)
            results.append(result)
        
        print(f"📂 从{json_file}加载了 {len(results)} 个测试结果")
        return results
    
    def print_summary(self, results: List[TestResult]):
        """打印提取结果的摘要"""
        print(f"\n📋 提取结果摘要:")
        print(f"   总样本数: {len(results)}")
        
        # 如果进行了预解析，显示解析结果
        if self.parse_predictions and results:
            seq_count = sum(1 for r in results if r.predicted_sequence)
            length_count = sum(1 for r in results if r.predicted_length)
            mw_count = sum(1 for r in results if r.predicted_molecular_weight)
            
            print(f"   有序列信息: {seq_count}")
            print(f"   有长度信息: {length_count}")
            print(f"   有分子量信息: {mw_count}")
        else:
            print("   原始输出内容已保存，未进行预解析")
        
        print(f"\n📝 UniProt IDs:")
        for i, result in enumerate(results, 1):
            if self.parse_predictions:
                info_parts = []
                if result.predicted_length:
                    info_parts.append(f"长度: {result.predicted_length}")
                if result.predicted_molecular_weight:
                    info_parts.append(f"分子量: {result.predicted_molecular_weight:.2f} Da")
                info_str = ", ".join(info_parts) if info_parts else "未解析"
                print(f"   {i}. {result.uniprot_id}: {info_str}")
            else:
                output_length = len(result.response_text)
                print(f"   {i}. {result.uniprot_id}: 原始输出({output_length}字符)")
                
    def show_raw_output(self, results: List[TestResult], uniprot_id: str = None):
        """显示原始输出内容"""
        if uniprot_id:
            result = next((r for r in results if r.uniprot_id == uniprot_id), None)
            if result:
                print(f"\n📄 {uniprot_id} 的原始输出:")
                print("="*60)
                print(result.response_text)
                print("="*60)
            else:
                print(f"❌ 未找到 {uniprot_id} 的结果")
        else:
            print(f"\n📄 所有结果的原始输出:")
            for result in results:
                print(f"\n--- {result.uniprot_id} ---")
                print(result.response_text[:200] + "..." if len(result.response_text) > 200 else result.response_text)


def main():
    """主要功能"""
    print("=== 数据提取工具 ===\n")
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("1. python data_extractor.py extract <notebook_path> [output_json] [--parse]")
        print("2. python data_extractor.py summary <json_file>")
        print("3. python data_extractor.py show <json_file> [UniProt_ID]")
        print("\n示例:")
        print("   # 提取原始输出（推荐，让LLM直接分析）")
        print("   python data_extractor.py extract deepseek_test.ipynb")
        print("   # 提取并预解析（使用正则表达式）")
        print("   python data_extractor.py extract deepseek_test.ipynb --parse")
        print("   # 查看提取结果摘要")
        print("   python data_extractor.py summary extracted_results.json")
        print("   # 查看原始输出内容")
        print("   python data_extractor.py show extracted_results.json Q8XPH4")
        return
    
    command = sys.argv[1]
    extractor = DataExtractor()
    
    if command == "extract":
        if len(sys.argv) < 3:
            print("❌ 请提供notebook文件路径")
            return
        
        notebook_path = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else "extracted_results.json"
        
        # 检查是否需要预解析
        parse_flag = "--parse" in sys.argv or "-p" in sys.argv
        extractor = DataExtractor(parse_predictions=parse_flag)
        
        try:
            results = extractor.extract_results_from_notebook(notebook_path)
            if results:
                extractor.save_results_to_json(results, output_file)
                extractor.print_summary(results)
                
                # 如果没有预解析，提示用户可以查看原始输出
                if not parse_flag:
                    print(f"\n💡 提示：")
                    print(f"   - 原始输出内容已保存，LLM将直接分析完整内容")
                    print(f"   - 查看原始输出：python data_extractor.py show {output_file} [UniProt_ID]")
                    print(f"   - 如需预解析：python data_extractor.py extract {notebook_path} {output_file} --parse")
            else:
                print("⚠️ 未提取到任何结果")
        except Exception as e:
            print(f"❌ 提取失败: {e}")
    
    elif command == "summary":
        if len(sys.argv) < 3:
            print("❌ 请提供JSON文件路径")
            return
        
        json_file = sys.argv[2]
        try:
            extractor = DataExtractor()
            results = extractor.load_results_from_json(json_file)
            extractor.print_summary(results)
        except Exception as e:
            print(f"❌ 加载失败: {e}")
    
    elif command == "show":
        if len(sys.argv) < 3:
            print("❌ 请提供JSON文件路径")
            return
        
        json_file = sys.argv[2]
        uniprot_id = sys.argv[3] if len(sys.argv) > 3 else None
        
        try:
            extractor = DataExtractor()
            results = extractor.load_results_from_json(json_file)
            extractor.show_raw_output(results, uniprot_id)
        except Exception as e:
            print(f"❌ 显示失败: {e}")
    
    else:
        print(f"❌ 未知命令: {command}")


if __name__ == "__main__":
    main()