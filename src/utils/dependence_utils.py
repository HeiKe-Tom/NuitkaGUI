import ast
from pathlib import Path
from typing import List


class DependenceUtils:
    @staticmethod
    def get_import_name_from_py_file(file_path: Path) -> List[str]:
        import_names = []

        # 1️⃣ 读取文件（防止编码炸）
        try:
            with file_path.open('r', encoding='utf-8', errors='ignore') as file:
                file_content = file.read()
        except Exception as e:
            print(f"[DependenceUtils] 读取失败: {file_path} -> {e}")
            return []

        # 2️⃣ 解析 AST（防止语法炸）
        try:
            tree = ast.parse(file_content)
        except SyntaxError as e:
            print(f"[DependenceUtils] 跳过语法错误文件: {file_path}")
            print(f"  -> {e}")
            return []
        except Exception as e:
            print(f"[DependenceUtils] AST解析异常: {file_path} -> {e}")
            return []

        # 3️⃣ 提取 import
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_names.append(alias.name.split('.')[0])

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    import_names.append(node.module.split('.')[0])
                else:
                    # 相对导入：from . import xxx
                    for alias in node.names:
                        import_names.append(alias.name.split('.')[0])

        return list(set(import_names))  # 去重
