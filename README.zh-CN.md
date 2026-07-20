# 🤖 AutoFLC

语言: [English](README.md) | **中文**

[![CI](https://github.com/dfjdkjkdf/AutoFLC/actions/workflows/ci.yml/badge.svg)](https://github.com/dfjdkjkdf/AutoFLC/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

https://github.com/user-attachments/assets/26ba76af-d3f8-46e5-b9cc-9fdef28b29a0

AutoFLC 是一个基于 Docker 的工具,可以自动把 C 语言源代码——无论是上传的 ZIP 包,还是直接拉取的 **GitHub 仓库/分支链接**——转换成 PlantUML 流程图。它集成了 Streamlit 前端、兼容 OpenAI 接口的多模型 LLM 后端(OpenAI、OpenRouter、Ollama 等),以及一个 PlantUML 渲染引擎。

## 📂 目录结构

````text
.
├── Dockerfile              # 构建 Docker 镜像
├── requirements.txt        # 运行时 Python 依赖
├── requirements-dev.txt    # 测试/lint 依赖（pytest、ruff）— 不会打进镜像
├── pyproject.toml          # pytest + ruff 配置
├── app.py                  # Streamlit 入口（仅 UI）
├── config.yaml             # 模型配置、提示词与语言设置
├── autoflc/                # 核心逻辑，按职责拆分
│   ├── config.py           #   config.yaml 加载 + 环境变量覆盖 API key
│   ├── task_tracker.py     #   任务状态存储 + 后台日志
│   ├── c_parser.py         #   基于 tree-sitter 的 C 函数提取
│   ├── llm_client.py       #   LLM 调用 + PlantUML 响应后处理
│   ├── renderer.py         #   PlantUML -> PNG 渲染
│   ├── archive.py          #   zip 解压（含乱码文件名处理）
│   ├── github_source.py    #   GitHub 仓库/分支链接 -> 本地 zip
│   └── worker.py           #   后台流水线编排
├── tests/                  # pytest 单元测试（无需 Java/PlantUML/网络）
├── .github/workflows/ci.yml
└── history/                # 存放生成的图片和 ZIP 包，文件夹名与任务 ID 一致
````

## 🌐 语言支持

AutoFLC 的 UI 文字和流程图注释都支持 **中文（`zh`）** 和 **英文（`en`）**。

切换语言只需要改 `config.yaml` 里的一行，然后重启容器：

````yaml
# config.yaml
language: "zh"   # "en" = 英文流程图注释 + 英文界面
                 # "zh" = 中文流程图注释 + 中文界面
````

> **注意**：切换语言会同时影响 AI 生成的流程图节点文字、网页 UI 文字，以及用户手册内容。

## 🚀 部署与使用指南

### 1. 构建镜像

````bash
docker build -t flowchart-agent .
````

### 2. 启动容器

把整个项目目录挂载进去，这样 `config.yaml`、`app.py`，或者 `autoflc/` 下的任何文件都可以直接编辑，不用重新构建镜像：

````bash
docker run -d -p 8501:8501 \
  --name flowchart-dev \
  -v YOUR_PATH\AutoFLC:/app \
  -e AUTOFLC_API_KEY=你的真实API密钥 \
  --add-host=host.docker.internal:host-gateway \
  flowchart-agent
````

> 💡 整个项目作为一个卷挂载，所以你可以切换语言、更新提示词，或者调整 `autoflc/*.py` 下的任何模块，**都不需要重新构建镜像**——改完文件、重启容器即可。

> 🔑 **API key 不会存放在 `config.yaml` 里。** `config.yaml` 里的 `api_key` 留空字符串 `""` 就行，真实的 key 通过 `AUTOFLC_API_KEY` 环境变量传入（如果配置了多个模型，也可以用 `AUTOFLC_API_KEY_<模型名>` 单独指定某一个模型的 key），这样就不会被不小心提交进 git 仓库。
>
> 📦 `plantuml.jar` 放在镜像内的 `/opt/plantuml/plantuml.jar`（在 `/app` 目录之外），由镜像内置的 `PLANTUML_JAR` 环境变量指向它——所以把整个项目挂载覆盖 `/app` 也不会把它遮住。

### 3. 修改配置后重启

````bash
docker restart flowchart-dev
````

## 🧪 开发与测试

`autoflc/` 下的核心逻辑用 `pytest` 做了单元测试，运行这些测试不需要 Java、PlantUML，也不需要联网：

````bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest -q
````

CI 在每次 push/PR 时都会自动跑这两条命令（见 `.github/workflows/ci.yml`）。

## 📖 使用说明

1. **准备**一份 C 语言源码，两种方式二选一：
   - 把你的 C 项目文件夹（比如 `usr` 目录）压缩成 `.zip` 文件；**或者**
   - 准备好一个公开的 GitHub 仓库链接——可以是仓库根目录（`https://github.com/owner/repo`），也可以是某个具体分支（`https://github.com/owner/repo/tree/branch`）。
2. **配置**：
   - 在左侧边栏选择 **AI 模型**。
   - 调整 **最大重试次数** 滑块（推荐 10）。
   - 调整 **跳过短函数** 滑块（推荐 0～5 行）。
3. **运行**：在 **"开始新任务"** 标签页，选择输入来源是 **"上传 ZIP"** 还是 **"GitHub 链接"**，提供对应的 ZIP 文件或链接，然后点击 **"在后台开始分析"**。
4. **监控**：切换到 **"任务监控"** 标签页查看实时日志。
   - 点击日志条目前的 `>` 图标展开查看详细代码。
   - 点击红色的 **"中止任务"** 按钮可以随时停止任务。
5. **交付**：任务完成后，点击 **"下载结果 (Zip)"** 下载所有 PNG 图片。

## 🔎 示例：C 代码 → 流程图（CS_HousekeepingCmd）

**输入（C 代码）：**
````c
CFE_Status_t CS_ReportBaselineAppCmd(const CS_ReportBaselineAppCmd_t *CmdPtr)
{
    /* command verification variables */
    CS_Res_App_Table_Entry_t *ResultsEntry;
    uint32                    Baseline;
    char                      Name[OS_MAX_API_NAME];

    strncpy(Name, CmdPtr->Payload.Name, sizeof(Name) - 1);
    Name[sizeof(Name) - 1] = '\0';

    if (CS_GetAppResTblEntryByName(&ResultsEntry, Name))
    {
        if (ResultsEntry->ComputedYet == true)
        {
            Baseline = ResultsEntry->ComparisonValue;
            CFE_EVS_SendEvent(CS_BASELINE_APP_INF_EID, CFE_EVS_EventType_INFORMATION,
                              "Report baseline of app %s is 0x%08X", Name, (unsigned int)Baseline);
        }
        else
        {
            CFE_EVS_SendEvent(CS_NO_BASELINE_APP_INF_EID, CFE_EVS_EventType_INFORMATION,
                              "Report baseline of app %s has not been computed yet", Name);
        }
        CS_AppData.HkPacket.Payload.CmdCounter++;
    }
    else
    {
        CFE_EVS_SendEvent(CS_BASELINE_INVALID_NAME_APP_ERR_EID, CFE_EVS_EventType_ERROR,
                          "App report baseline failed, app %s not found", Name);
        CS_AppData.HkPacket.Payload.CmdErrCounter++;
    }

    return CFE_SUCCESS;
}
````

**输出（流程图）：**

![CS_HousekeepingCmd Flowchart](./examples/CS_ReportBaselineAppCmd.png)

- 一眼就能看清错误处理和遥测上报路径
- 通过 `config.yaml` 同时支持 **英文** 和 **中文** 两种注释风格
- 帮助理解代码结构和语义
