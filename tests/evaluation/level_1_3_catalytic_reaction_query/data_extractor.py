"""
数据提取工具 - 从 Jupyter Notebook 提取 catalytic reaction query 测试结果
"""

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import nbformat


@dataclass
class TestResult:
    """测试结果数据结构"""

    uniprot_id: str
    response_text: str


class DataExtractor:
    """Catalytic reaction query 数据提取器"""

    def __init__(self, parse_predictions: bool = False):
        """初始化数据提取器。"""
        self.parse_predictions = parse_predictions

    def extract_results_from_notebook(self, notebook_path: str) -> List[TestResult]:
        """从 notebook 提取测试结果。"""
        print(f"📖 正在从 notebook 提取数据: {notebook_path}")

        try:
            with open(notebook_path, "r", encoding="utf-8") as handle:
                notebook = nbformat.read(handle, as_version=4)
        except Exception as exc:
            raise Exception(f"无法读取 notebook 文件: {exc}") from exc

        results: List[TestResult] = []
        current_uniprot_id: Optional[str] = None

        for cell in notebook.cells:
            if cell.cell_type != "code":
                continue

            current_uniprot_id = self._extract_uniprot_id_from_source(cell.source) or current_uniprot_id
            if current_uniprot_id:
                print(f"   🔍 找到 UniProt ID: {current_uniprot_id}")

            response_text = self._extract_response_from_cell(cell)
            if not current_uniprot_id or not response_text:
                continue

            result = TestResult(
                uniprot_id=current_uniprot_id,
                response_text=response_text,
            )

            if self.parse_predictions:
                parsed_activities = self._parse_predicted_activities(response_text)
                print(
                    f"   ✓ 提取并完成预解析: {current_uniprot_id} "
                    f"(activities={len(parsed_activities)})"
                )
            else:
                print(f"   ✓ 提取原始输出: {current_uniprot_id}")

            results.append(result)
            current_uniprot_id = None

        print(f"📊 总共提取到 {len(results)} 个测试结果")
        return results

    def _extract_uniprot_id_from_source(self, source: str) -> Optional[str]:
        """从代码单元格中提取 UniProt ID。"""
        patterns = [
            r"uniprot\s+ID\s+([A-Z0-9]+)",
            r"enzyme\s*\(([A-Z0-9]+)\)",
            r"\(([A-Z][0-9][A-Z0-9]{3}[0-9](?:[A-Z0-9]{4,6})?)\)",
            r"\b([A-Z][0-9][A-Z0-9]{3}[0-9](?:[A-Z0-9]{4,6})?)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_response_from_cell(self, cell: Any) -> str:
        """从单元格输出中提取文本响应。"""
        parts: List[str] = []

        for output in getattr(cell, "outputs", []):
            output_type = output.get("output_type")
            if output_type == "display_data":
                data = output.get("data", {})
                if "text/markdown" in data:
                    markdown_value = data["text/markdown"]
                    if isinstance(markdown_value, list):
                        parts.append("".join(markdown_value))
                    else:
                        parts.append(markdown_value)
                elif "text/plain" in data:
                    plain_value = data["text/plain"]
                    if isinstance(plain_value, list):
                        parts.append("".join(plain_value))
                    else:
                        parts.append(plain_value)
            elif output_type == "stream":
                text = output.get("text", "")
                if isinstance(text, list):
                    parts.append("".join(text))
                else:
                    parts.append(text)

        return "\n".join(part.strip() for part in parts if part and str(part).strip()).strip()

    def _parse_predicted_activities(self, response_text: str) -> List[Dict[str, Optional[str]]]:
        """用轻量正则从原始输出中尝试解析 reaction/EC/Rhea。"""
        predicted_activities: List[Dict[str, Optional[str]]] = []

        table_pattern = re.compile(
            r"\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|\n]+?)\s*\|"
        )
        for match in table_pattern.finditer(response_text):
            predicted_activities.append(
                {
                    "rhea_id": self._normalize_optional_value(match.group(1)),
                    "reaction_name": self._normalize_optional_value(match.group(2)),
                    "ec_number": self._normalize_optional_value(match.group(3)),
                }
            )

        if predicted_activities:
            return predicted_activities

        ec_match = re.search(r"EC(?:\s+number)?[:\s]*([0-9]+(?:\.[0-9n-]+){3})", response_text, re.IGNORECASE)
        rhea_match = re.search(r"RHEA[:\s-]*([0-9]+)|Rhea\s+ID[:\s]*([0-9]+)", response_text, re.IGNORECASE)
        reaction_match = re.search(
            r"(?:reaction|catalytic activity)[:\s]*([^\n]+)",
            response_text,
            re.IGNORECASE,
        )

        if ec_match or rhea_match or reaction_match:
            predicted_activities.append(
                {
                    "rhea_id": self._normalize_optional_value((rhea_match.group(1) or rhea_match.group(2)) if rhea_match else None),
                    "reaction_name": self._normalize_optional_value(reaction_match.group(1) if reaction_match else None),
                    "ec_number": self._normalize_optional_value(ec_match.group(1) if ec_match else None),
                }
            )

        return predicted_activities

    def _normalize_optional_value(self, value: Optional[str]) -> Optional[str]:
        """规范化可选字段。"""
        if value is None:
            return None

        normalized = value.strip().strip("`*")
        if not normalized or normalized.upper() == "N/A":
            return None
        return normalized

    def save_results_to_json(self, results: List[TestResult], output_file: str) -> str:
        """将提取结果保存为 JSON。"""
        data = [
            {
                "uniprot_id": result.uniprot_id,
                "response_text": result.response_text,
            }
            for result in results
        ]

        with open(output_file, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

        print(f"💾 测试结果已保存到: {output_file}")
        return output_file

    def load_results_from_json(self, json_file: str) -> List[TestResult]:
        """从 JSON 文件加载测试结果。"""
        with open(json_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        results = [TestResult(**item) for item in data]
        print(f"📂 从 {json_file} 加载了 {len(results)} 个测试结果")
        return results

    def print_summary(self, results: List[TestResult]):
        """打印提取结果摘要。"""
        print("\n📋 提取结果摘要:")
        print(f"   总样本数: {len(results)}")

        if self.parse_predictions and results:
            print("   已对原始输出执行轻量预解析，但不会写入导出 JSON")
        else:
            print("   原始输出内容已保存，未进行预解析")

        print("\n📝 UniProt IDs:")
        for index, result in enumerate(results, 1):
            print(f"   {index}. {result.uniprot_id}: 原始输出({len(result.response_text)} 字符)")

    def show_raw_output(self, results: List[TestResult], uniprot_id: Optional[str] = None):
        """显示原始输出内容。"""
        if uniprot_id:
            result = next((item for item in results if item.uniprot_id == uniprot_id), None)
            if not result:
                print(f"❌ 未找到 {uniprot_id} 的结果")
                return

            print(f"\n📄 {uniprot_id} 的原始输出:")
            print("=" * 60)
            print(result.response_text)
            print("=" * 60)
            return

        print("\n📄 所有结果的原始输出:")
        for result in results:
            preview = result.response_text[:300]
            suffix = "..." if len(result.response_text) > 300 else ""
            print(f"\n--- {result.uniprot_id} ---")
            print(f"{preview}{suffix}")


def main():
    """命令行入口。"""
        
    print("=== Catalytic Reaction Query 数据提取工具 ===\n")

    if len(sys.argv) < 2:
        print("使用方法:")
        print("1. python data_extractor.py extract <notebook_path> [output_json] [--parse]")
        print("2. python data_extractor.py summary <json_file>")
        print("3. python data_extractor.py show <json_file> [UniProt_ID]")
        return

    command = sys.argv[1]

    if command == "extract":
        if len(sys.argv) < 3:
            print("❌ 请提供 notebook 文件路径")
            return

        notebook_path = sys.argv[2]
        output_file = "extracted_results.json"

        extra_args = [arg for arg in sys.argv[3:] if arg not in {"--parse", "-p"}]
        if extra_args:
            output_file = extra_args[0]

        parse_flag = "--parse" in sys.argv or "-p" in sys.argv
        extractor = DataExtractor(parse_predictions=parse_flag)

        try:
            results = extractor.extract_results_from_notebook(notebook_path)
            if not results:
                print("⚠️ 未提取到任何结果")
                return

            extractor.save_results_to_json(results, output_file)
            extractor.print_summary(results)
        except Exception as exc:
            print(f"❌ 提取失败: {exc}")

    elif command == "summary":
        if len(sys.argv) < 3:
            print("❌ 请提供 JSON 文件路径")
            return

        extractor = DataExtractor()
        try:
            results = extractor.load_results_from_json(sys.argv[2])
            extractor.print_summary(results)
        except Exception as exc:
            print(f"❌ 加载失败: {exc}")

    elif command == "show":
        if len(sys.argv) < 3:
            print("❌ 请提供 JSON 文件路径")
            return

        extractor = DataExtractor()
        try:
            results = extractor.load_results_from_json(sys.argv[2])
            extractor.show_raw_output(results, sys.argv[3] if len(sys.argv) > 3 else None)
        except Exception as exc:
            print(f"❌ 显示失败: {exc}")

    else:
        print(f"❌ 未知命令: {command}")


if __name__ == "__main__":
    main()