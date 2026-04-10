#!/usr/bin/env python3
"""
Knowledge Quiz Skill 结构验证测试

运行: pytest tests/test_skill_structure.py -v
"""

import json
import pytest
from pathlib import Path


class TestSkillStructure:
    """Skill 结构完整性测试"""

    @pytest.fixture
    def skill_root(self):
        """Skill 根目录"""
        return Path(__file__).parent.parent

    def test_skill_md_exists(self, skill_root):
        """测试 SKILL.md 存在"""
        skill_md = skill_root / "SKILL.md"
        assert skill_md.exists(), "SKILL.md 文件不存在"
        assert skill_md.stat().st_size > 0, "SKILL.md 文件为空"

    def test_skill_md_frontmatter(self, skill_root):
        """测试 SKILL.md frontmatter 格式"""
        skill_md = skill_root / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")

        # 检查 frontmatter 边界
        assert content.startswith("---"), "SKILL.md 必须以 YAML frontmatter 开头"
        assert "---\n" in content[4:], "SKILL.md frontmatter 必须闭合"

        # 检查必要字段
        required_fields = ["name", "description", "type", "tools"]
        frontmatter_end = content.index("---", 4)
        frontmatter = content[4:frontmatter_end]

        for field in required_fields:
            assert f"{field}:" in frontmatter, f"frontmatter 缺少必要字段: {field}"

    def test_skill_md_steps(self, skill_root):
        """测试 SKILL.md 包含执行步骤"""
        skill_md = skill_root / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")

        # 检查步骤格式
        assert "## Step" in content or "### Step" in content, "SKILL.md 必须包含执行步骤"

    def test_readme_exists(self, skill_root):
        """测试 README.md 存在"""
        readme = skill_root / "README.md"
        assert readme.exists(), "README.md 文件不存在"
        assert readme.stat().st_size > 0, "README.md 文件为空"

    def test_references_guide_exists(self, skill_root):
        """测试参考文档存在"""
        guide = skill_root / "references" / "guide.md"
        assert guide.exists(), "references/guide.md 文件不存在"

    def test_lint_rules_exist(self, skill_root):
        """测试 Lint 规则存在"""
        forbidden = skill_root / ".claude" / "lint" / "forbidden-patterns.json"
        structure = skill_root / ".claude" / "lint" / "structure-rules.json"

        assert forbidden.exists(), "forbidden-patterns.json 不存在"
        assert structure.exists(), "structure-rules.json 不存在"

    def test_lint_rules_valid_json(self, skill_root):
        """测试 Lint 规则是有效 JSON"""
        forbidden = skill_root / ".claude" / "lint" / "forbidden-patterns.json"

        with open(forbidden, encoding="utf-8") as f:
            data = json.load(f)

        assert "forbidden" in data, "forbidden-patterns.json 必须包含 'forbidden' 字段"
        assert isinstance(data["forbidden"], list), "'forbidden' 必须是列表"
        assert len(data["forbidden"]) > 0, "'forbidden' 列表不能为空"

    def test_logs_directory_exists(self, skill_root):
        """测试 logs 目录存在"""
        logs_dir = skill_root / "logs"
        assert logs_dir.is_dir(), "logs/ 目录不存在"


class TestSkillMetadata:
    """Skill 元数据测试"""

    @pytest.fixture
    def skill_metadata(self):
        """提取 SKILL.md 元数据"""
        skill_md = Path(__file__).parent.parent / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")

        # 提取 frontmatter
        start = content.index("---") + 3
        end = content.index("---", start)
        frontmatter = content[start:end]

        # 简单解析
        metadata = {}
        for line in frontmatter.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        return metadata

    def test_metadata_name(self, skill_metadata):
        """测试元数据 name 字段"""
        assert "name" in skill_metadata, "缺少 name 字段"
        assert skill_metadata["name"] == "knowledge-quiz", "name 应为 'knowledge-quiz'"

    def test_metadata_type(self, skill_metadata):
        """测试元数据 type 字段"""
        assert "type" in skill_metadata, "缺少 type 字段"
        assert skill_metadata["type"] == "skill", "type 应为 'skill'"

    def test_metadata_tools(self, skill_metadata):
        """测试元数据 tools 字段"""
        assert "tools" in skill_metadata, "缺少 tools 字段"
        # tools 可能是 YAML 列表格式


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
