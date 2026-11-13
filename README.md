# Blender Character Short Skill · v48.2

面向 **MMD PMX/PMD 骨架**的本地 Blender 短片制作 skill。优先使用已生成的 MMR 控制器，将角色映射、模型、动作、材质资产与通用代码分开。当前制作入口为 [`short_project.py`](blender-character-short/scripts/short_project.py)，完整合同见[当前流程](blender-character-short/references/current-production.md)。生产者标识保留为 `v48.2`，公开版本与分发差异见[发布清单](release/distribution-manifest.json)。

## v48.2: verified saved scene execution

The [execution guide](blender-character-short/references/verified-mcp-production.md)
adds process-only installed-addon activation, binds shot declarations to saved
cameras, and checks the declared actor physics population in scenes with multiple
MMD roots. The complete current producer ran a private captured-action story
through actual MCP doctor, new cache baking with a fresh process check, final
rendering with cooperative cancellation/resume, and encoding. The initial
complete rehearsal used an earlier frozen producer and retains its own identity.
[Stage evidence](release/mcp-production-evidence-v48_2.json) binds the exercised
module bytes, 113 related host checks and 214 native regressions. The current
producer retains its frozen script/version identity; do not mix its frames with
the earlier rehearsal.
An intermittent uncertain host-test outcome remains unresolved. Cache checks and
all-frame decoding do not certify naturalness or continuous normal-speed viewing.
No story assets, motion libraries or private footage are included.

## v48.1: bounded animated cord smoothing

The optional [curve smoothing route](blender-character-short/references/curve-smoothing.md)
replaces visible POLY corners with a bounded cubic curve, preserves original
endpoint and weight channels, and independently checks the saved result against
all original knots and declared contact times. Shared verification budgets fail
before mutation. Native length measurements must agree with independent cubic
integration. A portable two-process fixture exercises the real Blender writer and
reader; [stage evidence](release/curve-smoothing-evidence-v48_1.json) records the
measured scope. Contact and normal-speed visual acceptance remain separate gates.

## v48: optional asynchronous Blender execution

The [local MCP companion](blender-character-short/references/mcp-execution.md)
adds persistent allowlisted jobs, status/log/result queries, idempotent requests
and stage-boundary cancellation while reusing the canonical scripts. Existing
blender-mcp interactive editing remains separate. The [setup workflow](blender-character-short/references/mcp-setup.md)
includes missing-component installation, non-overwriting configuration, optional
client registration and health checks. It does not silently replace an active
service. A client that kills its process tree can stop workers; persisted state
prevents blind retries, not OS-level termination. New physics routing requires
an explicitly assembled saved project and reviewed plan.

Tests cover CPU orchestration, real stdio interaction and a native background
doctor. No new full render/bake or GUI bridge acceptance is claimed. Installing
and enabling optional services on a user's active client remains a separate
operation under its permissions.

## v47: shot planning, review and scene lighting

Optional [shot planning / film review](blender-character-short/references/shot-review.md) and [scene light candidates](blender-character-short/references/lighting-candidates.md) add concrete preproduction and review aids. They do not generate complete films, automatically judge acting, or apply lighting without review.

The update was developed in isolation and adopted only after the prior film finished rendering and encoding. That film retains its v46.1 evidence and a verified producer snapshot; do not reuse its frames with v47. Tests use synthetic CPU fixtures; the v46 real-scene evidence below remains historical, not validation of these new visual choices.

## v46.1: production workflow

[Six-step workflow](blender-character-short/references/production-workflow.md): require MMD character, scene and basic story unless explicitly exempted; preserve intent while adding detail; simplify missing maps while retaining basic toon style; shade/render stills and search motions; storyboard; produce and deliver. Login-dependent work pauses for authorization. No separate asset/license-check gate is added. The new host-only `workflow` command validates brief/state/evidence references and reports missing inputs, fallback plans and next stage. It does **not** automate internet retrieval, artistic judgment, shader fallbacks or movie authoring. Existing v46 static-render evidence below is historical; no new render/dynamic validation was run for this workflow-only change.

## v46: executable static refinement

The new [`refine` production stage](blender-character-short/references/static-refinement.md) automates hash-bound backup, Huaxu-compatible coverage-aware bloom/GPU compositing, explicit scene-only material and linked-light adjustments, save-as and fresh-reopen protection checks. Scene/style choices remain reviewed external inputs; model assets and private plans are not published. Static matched renders reproduced the prior character result at 720p/32 samples and V05 stage result at 720p/48 samples with zero pixel difference in the checked views. See [v46 evidence](release/refinement-evidence-v46.json); these are bounded still-frame tests, not general or dynamic acceptance. Existing animation/production stages retain their v45a behavior. The v45a evidence below is historical, not a claim that all old suites were rerun on v46.


## 示范视频

[![涅缇娅短片示范](docs/media/nietiya-demo-poster.jpg)](docs/media/nietiya-demo-1080p30.mp4)

[查看／下载 1080p、30 fps 示范视频](docs/media/nietiya-demo-1080p30.mp4) · [完整借物表与使用条件](docs/DEMO-CREDITS.md)

约 13 秒的无文字、无声示范：挥手与谢幕之后，镜头揭示空剧场，再以表情收尾。使用现有 MMD/MMR 控制器、许可库动作、表情、物理、五个镜头及 Eevee 渲染与合成。

本示范为非商业同人及技术展示，仅公开成片和视频封面，不分发模型、动作、贴图或工程。外观使用后续本地材质适配，不等于仓库 v43a 冻结代码单独重建结果。README 展示静态封面，点击封面或视频链接可进入 MP4 文件页查看或下载。

## 当前能力与验证范围

| 环节 | v45a 行为与证据 |
|---|---|
| 版本与入口 | 一个后台入口串起依赖检查、基线、外观迁移、保存工程渲染和编码；记录 Blender、插件、二进制及脚本身份。`build` 不自动编写故事或制作完整影片。 |
| MMD/MMR | 已有未带旧动作的控制器工程，以及用户指导的直接生成分支，均在一个模型上保存并独立重开；各通过 18 项真实加权蒙皮响应，涵盖手臂 FK、手腕、手 IK、十指主控、躯干和头。 |
| 已审核外观 | 通用迁移器要求匹配的网格、UV、法线和材质索引，保留目标 rig/蒙皮/动作/镜头；迁移保存的材质与唯一原生合成链。需要另行提供有权使用的 packed look donor 和角色配置，不随仓库提供 h07 工程或素材。 |
| 动态外观检查 | 正面、侧面、闭眼、转头、活动相机切换与切回共六组真实画面及 HET/头轴检查；与保存的 h07 基准对照，未宣称与网站逐像素等价。 |
| 帧率与续渲 | 读取保存的 `fps/fps_base`；帧率参数只作一致性断言。绑定工程、声明资源、脚本集合、版本、Blender 二进制、采样、尺寸、镜头等身份，逐帧核验 PNG 字节与哈希。 |
| 编码 | 仅编码完整、输入身份已验证的序列；从回执读取帧率，输出静音 H.264 并完整解码，核对尺寸、帧数、帧率和时长。 |

本地冻结 v45a 有 **196 个文件、155 个 Python 脚本**，66 项主机测试与 202 项原生 Blender 测试通过，两套计数有重叠，不能相加。保存工程到编码链另有真实素材验证：保留的 v45 生产者完成 1920×1080、30fps、30 帧的 1 秒技术片；加入阶段绑定修复后的 v45a 独立完成默认 1280×720、24fps、6 帧的 0.25 秒技术片。两条序列都分批续渲、原前缀哈希不变并完整解码；各有 8 项实际错误输入拒绝，新版另有 3 项基线/外观/编码绑定 CLI 拒绝。两条技术片、角色输入和项目回执均留在本地，未随本次代码发布。

这些是技术集成与抽帧证据，**不是新剧情影片、动作库自然度或正常速度整段观看验收**。先前用户对 V04 的验收只属于该片；上方既有 13 秒示范也不因此新增验收。分项证据和限制见 [runtime evidence](release/runtime-evidence-v45a.json)。本次发布步骤复查代码和分发内容，不重新渲染。

## 默认规格与设备

新视频默认 **1280×720、24fps**；只有用户明确要求更高规格时才提高。已有工程保留真实 `fps/fps_base`，当前显式规格不被覆盖；需要重定时时另存新工程，不把 30fps 序列重新标为 24fps。低成本分镜可明确选择更小预览规格。

常规新视频与预览优先 **Eevee + 兼容独显**。引擎选择和设备选择分开：保存工程保留原引擎，已有 Cycles 工程有独立入口。Eevee 的实际 graphics context 必须与硬件清单唯一匹配，不能只凭“检测到一块显卡”声称已使用它。

独显存在但不可用、驱动错误或设备分类不明时，停止受影响渲染并报告，不静默改用 CPU。只有可靠识别为纯核显机器时，CPU 才可用于适用的 Cycles 路线；**Eevee 没有 CPU 模式**，核显环境不能自动切引擎，应由用户决定独立的材质/引擎适配。物理、合成与编码的 CPU 计算不等于 3D 渲染改用 CPU。硬件分类当前使用 Windows DXCore，其他系统和跨机器未验证。详见[设备与引擎策略](blender-character-short/references/render-devices.md)。

## 环境与安装

本次真实验证环境：Windows、Blender 4.5.15 LTS、MMD Tools 4.5.14、MikuMikuRig 3.86 与随 Blender 启用的 Rigify。Blender 内置 Python 3.11.15 / NumPy 1.26.4；外部编排和编码使用 Python 3.14.7、NumPy 2.5.4、Pillow 13.0.0、imageio-ffmpeg 0.6.0 / FFmpeg 7.1。版本是已验证组合，不代表其他组合已兼容。

克隆本仓库，将整个 `blender-character-short` 文件夹交给支持 skill 的助手读取，或安装到其技能目录。入口为 [`SKILL.md`](blender-character-short/SKILL.md)。安装 skill 不会安装 Blender、插件、Python 依赖或角色素材；按各插件可信来源及说明单独准备并启用，参见 [MMD/MMR 说明](blender-character-short/references/mmd-plugins.md)。依赖 `bpy` 的脚本必须由匹配的 Blender 后台执行，不能用外部 Python 直接运行。

## 使用流程

1. 将有权使用的模型、已有控制器工程、角色映射、动作、look donor、镜头与物理输入置于仓库外。为新输出选择独立目录，保护原工程；按[项目合同](blender-character-short/references/current-production.md)填写外部项目 JSON、真实路径和 SHA256。
2. 优先使用已有未带旧影片动作的 MMR 基线。只有原始未生成控制器的 MMD 副本才使用直接生成：选中原 MMD 骨架 → Extras/Finger options → Build a controller，核对实际骨名与外部 preset。不要对已有 rig 重复生成；Finger options 不代替正确骨名映射。
3. 在通过基线和外观检查的副本中，按剧情导入许可动作、场景与镜头，编辑表情/手势，按需要制作并复验物理缓存。`build` 后的工程可能仍是静态，必须将审核后的动画工程另存，并以实际 SHA256 声明 `render.source`。
4. 用统一入口分批渲染、续渲和编码，分别记录技术检查、抽帧、连续观看及用户验收。每次更换输入或制作代码都使用新输出身份，不接纳仅尺寸相同的旧 PNG。

在仓库根目录用外部 Python 编排（项目配置示意路径需替换为自己的文件）：

```powershell
$Skill = Join-Path (Get-Location) 'blender-character-short'
$Project = '../my-short/project.json'
python -B "$Skill/scripts/short_project.py" version
python -B "$Skill/scripts/short_project.py" doctor --project $Project
python -B "$Skill/scripts/short_project.py" build --project $Project
python -B "$Skill/scripts/short_project.py" check-look --project $Project
# 另存审核过的动作/镜头/物理工程，并更新外部 render.source 后：
python -B "$Skill/scripts/short_project.py" render --project $Project
python -B "$Skill/scripts/short_project.py" render --project $Project --complete --max-seconds 1800
python -B "$Skill/scripts/short_project.py" encode --project $Project
```

`diagnostic` 只生成短的转头/眨眼/切镜技术夹具，不是库动作或剧情制作器。单次预算在完成帧边界停下；无回执 final/partial PNG 必须检查并采用单独恢复版本，不会自动接纳。场景图片需打包；当前保存工程路线拒绝未冻结的链接库和外部仿真缓存。唯一原生合成链使用 `saved-native`，不能再调用外部 Bloom/LUT/SMAA 链二次调色。

历史动作转换、接触、手部、场景、原始 PMX 和源 AOV 路线仍保留，按需阅读[历史专门入口](blender-character-short/references/legacy-routes.md)。它们各自的限制仍适用，不作为当前统一入口的隐式步骤。

## 验证

在具备匹配依赖的环境：

```powershell
python -B validation/validate_distribution.py --report release/validation.json
python -B -m unittest discover -s validation -p 'test_*.py'
python -B "$Skill/scripts/short_project.py" tests --project $Project
```

分发检查核验清单、Python/JSON、文档链接、排除项、敏感模式、准确的示范媒体哈希和主机 CLI；不会加载角色或启动 Blender。原生测试入口使用外部项目报告目录保存临时夹具，不向公开仓库写入 Blender 产物。本次发布的实际检查结果见 [validation](release/validation.json)。

## 已知限制与历史

- 只验证了一个 MMD 角色；没有任意 PMX、任意骨名/轴向、跨角色或跨机器兼容保证。十个指尖 IK 控制器未逐一测试；已测试的是十指主控和双手 IK 等响应。
- h07 迁移需要相符的几何/UV/法线/材质索引及审核过的外部材质工程。刘海投影、HET 与后处理仍含近似，不是任意 GLB→PMX 材质转换，也不是网站的 stencil/MRT/SMAA 等价实现。
- 真实素材试验和短技术片不能证明新剧情、全身动作自然度、可信抓握、所有帧/子帧无穿插、完整物理或音频验收。完整故事的编排、许可资产选择和正常速度检查仍需完成。
- 本包不包含角色、纹理、模型、动作/派生目标、场景、look donor、工程、插件/依赖二进制或本机路径。已有示范视频和封面是先前单独审核的例外，本次保持不变。
- [v43a 清单](release/history/v43a-distribution-manifest.json)、[v43a 发布检查](release/history/v43a-validation.json)及 [v43a README](https://github.com/JiaT-T/blender-character-short-skill/blob/429b5745ad7e2868a54e3df5ef28dfe62126bd5c/README.md)保留其历史范围。v33 的 Nanami 纸飞机原始输入复用证据、v43a 的既有控制器动作证据，不自动升级为本版完整影片验收。

## 来源与使用权

本次只更新通用 skill 代码和文档，保留既有示范与[借物表](docs/DEMO-CREDITS.md)。参见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)：不新增覆盖全部代码的开源许可证，不扩大上游代码、公式、模型或动作的权利。下载或公开可读不代表允许商用、改模、再分发或自动公开派生资产。
