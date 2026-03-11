# GITHUB_PREUPLOAD_CHECKLIST

## 1. 上传目标确认

在上传前，先确认你的目标是：

- 上传 `close/` 这个主线子项目；
- 让 GPT / GitHub 先理解论文主线、图表、分析流程；
- 暂时不追求“整个大仓库一起上传”；
- 暂时不追求“别人 clone 后立刻跑通硬件闭环”。

如果以上都成立，那么当前推荐上传对象就是：

- `close/`

---

## 2. 必查清单

### 2.1 密钥与隐私

确认以下事项：

- [ ] `close/config/api_config.py` 中没有真实 API key
- [ ] `close/auto_control/modules/report_bundle.py` 中没有真实 API fallback
- [ ] 真实 key 只保存在你本地环境变量或 `.env` 中
- [ ] `.env` 不上传，`.env.example` 上传

### 2.2 Git 忽略规则

确认以下事项：

- [ ] `close/.gitignore` 已存在
- [ ] `output/` 已被忽略
- [ ] `data/raw_eis/` 已被忽略
- [ ] 本地缓存、日志、临时文件不会被一起上传

### 2.3 核心说明文件

确认以下文件存在并建议一起上传：

- [ ] `README.md`
- [ ] `PROJECT_MAP.md`
- [ ] `GITHUB_UPLOAD_GUIDE.md`
- [ ] `ENVIRONMENT_SETUP.md`
- [ ] `CLEANUP_CANDIDATES.md`

### 2.4 代码主线完整性

确认以下目录保留：

- [ ] `phase1/`
- [ ] `phase2/`
- [ ] `phase3/`
- [ ] `phase3-v2.0/`
- [ ] `auto_control/`
- [ ] `specific_conductance/`
- [ ] `paper/`
- [ ] `paper_figure/`
- [ ] `config/`
- [ ] `docs/`
- [ ] `utils/`

### 2.5 环境边界说明

确认以下认知已经写清楚：

- [ ] `close/` 适合 GitHub 分析、论文协作、图表复现
- [ ] `close/` 还不是标准化发布版软件包
- [ ] `auto_control/` 的一部分功能需要 Windows 本地 GUI、CHI 软件、串口和硬件
- [ ] 缺少 `pyautogui` / `pyserial` 这类报错属于环境问题，不是路径改造失败

对应文档：

- [ ] `ENVIRONMENT_SETUP.md`

### 2.6 数据与结果边界

上传前确认：

- [ ] 不默认上传大体积原始实验数据
- [ ] 不默认上传本地运行生成的全部 `output/`
- [ ] 如果论文讨论必须引用某些结果图/结果表，优先保留脚本、说明文档和必要的小型示例文件

---

## 3. 推荐上传内容

建议上传：

- `README.md`
- `PROJECT_MAP.md`
- `GITHUB_UPLOAD_GUIDE.md`
- `GITHUB_PREUPLOAD_CHECKLIST.md`
- `ENVIRONMENT_SETUP.md`
- `.gitignore`
- `.env.example`
- `phase1/`
- `phase2/`
- `phase3/`
- `phase3-v2.0/`
- `auto_control/`
- `specific_conductance/`
- `config/`
- `paper/`
- `paper_figure/`
- `docs/`
- `utils/`

默认不建议上传：

- `output/`
- `data/raw_eis/`
- 本地日志
- 临时文件
- 压缩包

---

## 4. 最稳妥的上传方式

最推荐的方式不是直接在当前大仓库里操作，而是：

1. 在本地新建一个单独文件夹，例如 `close-github/`
2. 把当前 `close/` 的内容复制进去
3. 在这个新文件夹里初始化新的 git 仓库
4. 新建 GitHub 仓库后把它推上去

这样做的好处是：

- 不会受当前父仓库混乱历史影响
- 不会把父仓库的删除记录或无关文件一起带上去
- 后续 GPT 分析时上下文更干净

---

## 5. 上传前最后 30 秒自检

如果你只想在上传前快速确认，至少看这 6 条：

- [ ] 上传的是 `close/`，不是整个大仓库
- [ ] `.env` 不上传，`.env.example` 上传
- [ ] `output/` 不上传
- [ ] `data/raw_eis/` 不上传
- [ ] `README.md`、`GITHUB_UPLOAD_GUIDE.md`、`ENVIRONMENT_SETUP.md` 都在
- [ ] 你接受“当前仓库适合分析和论文协作，但不是标准发布版软件”

---

## 6. 上传后如何让 GPT 更快理解

上传后优先让 GPT 阅读：

1. `README.md`
2. `PROJECT_MAP.md`
3. `GITHUB_UPLOAD_GUIDE.md`
4. `ENVIRONMENT_SETUP.md`
5. `paper/` 与 `paper_figure/`

然后再让 GPT 结合你的初稿去做：

- 论文结构梳理
- Figure / SI 补强
- 机理报告支撑性检查
- “系统能力是否真的被证明”这一点的审查
