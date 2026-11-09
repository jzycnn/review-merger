# 审片意见合并系统

Windows 10/11 本机 Web 应用：导入 DOC/DOCX 审片意见，按月份整理节目，人工填写或由 AI 生成责编点评参考，核对后合并导出一个 Word。

## 下载与安装

1. 下载仓库 ZIP 并解压，或使用 Git 克隆。
2. 安装 Python 3.12、Node.js 20 或更新版本，并将二者加入 PATH。
3. 在解压后的项目根目录打开 PowerShell，执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

首次安装需要联网下载依赖。脚本会建立独立 Python 环境、构建前端，并注册当前用户登录时启动的计划任务 `ReviewMerger-Local`。默认资料目录为 `D:\审片意见整理系统`；无 D 盘时使用当前用户的 LocalAppData。可指定目录：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1 -DataRoot 'E:\审片资料'
```

安装后打开 http://127.0.0.1:8765/ 。只监听本机，无需部署服务器。

## 使用流程

1. **导入文件**：默认整理上一个自然月，可更改月份。可直接导入单日稿，也可先导入已有月度母稿再加入新稿。
2. **责编有话说**：在当期原文旁填写点评，可修改 AI 参考并保存；每一期均有独立填写位置。
3. **审片核对**：确认日期、标题、栏目归属和已保存点评。没有标题就留空手填；原文审片起止时间保持原样。栏目别名统一归类。
4. **导出与归档**：正式导出前完成核对。全部节目合并为一个 Word，固定小四12磅、1倍行距、中文宋体、数字及西文 Times New Roman，不同日期以横线分隔。新版下载置顶并标记格式检查结果；另提供 Excel 来源核对表。

处理失败时可查看原因、重试或清除当前月份后重新整理。清除前请阅读界面说明，注意区分重新处理和清除资料。

## AI（可选）

规则识别和手工填写不需要 API。需要生成参考点评时，在设置中填入自己的 OpenAI 兼容接口地址、模型名和密钥；可使用 Gemini 的兼容接口。需要网络代理时填写本机可用的代理地址，不附带任何公共代理或共享密钥。

AI 默认关闭，启用后会把当期原文发送给所配置的服务商。参考稿须人工修改、保存并核实。密钥保存在本机凭据库，不在源码中。公开版仅附带一个虚构的措辞示例；可在 `backend/resources/editor_examples.json` 中替换为有权使用的参考资料，字段为 source、title、context、comment。

## 启停与备份

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

在导出页备份全部数据。停止应用后使用 `scripts\restore.ps1 -BackupFile '备份文件.zip'` 恢复。跨账户使用时重新配置密钥。卸载计划任务使用 `scripts\uninstall.ps1`，资料保留。

## 开发

前端 React / TypeScript / Vite / Ant Design，后端 FastAPI / SQLAlchemy / SQLite，独立 Worker。前端构建产物由 FastAPI 提供。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

测试使用隔离数据库。依赖真实样本的测试在公开版自动跳过。不要把运行资料目录或密钥加入 Git。

## 文件支持与边界

普通 DOCX 可直接读取；传统 DOC 优先用 Microsoft Word 转换，无 Word 时使用保守的二进制文本读取器。复杂 DOC、加密、损坏或含嵌入对象的文件可能需要先另存为 DOCX。文本框、图片文字、嵌套表格和修订内容不保证可靠识别，应对照原件核实。

本仓库不包含真实审片文档、历史点评、运行数据库、导出稿或 API 密钥。项目名称仅描述应用用途，不代表节目或机构的官方发布。

## 许可

源码采用 MIT 许可证，允许复制、修改和再分发，请保留许可证。依赖组件遵循各自许可证。
