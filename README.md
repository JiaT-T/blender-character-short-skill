# Blender Character Short Skill · v43a

从已授权的 PMX 角色、角色映射和故事配置制作本地 Blender 角色短片（Eevee与保存的Cycles工程路线分开使用）的可移植 skill。包含导入、表演与分镜、接触诊断、材质与后处理、视频编码和检查脚本。

## 示范视频

[![涅缇娅短片示范](docs/media/nietiya-demo-poster.jpg)](docs/media/nietiya-demo-1080p30.mp4)

[查看／下载 1080p、30 fps 示范视频](docs/media/nietiya-demo-1080p30.mp4) · [完整借物表与使用条件](docs/DEMO-CREDITS.md)

约 13 秒的无文字、无声示范：挥手与谢幕之后，镜头揭示空剧场，再以表情收尾。使用现有 MMD/MMR 控制器、许可库动作、表情、物理、五个镜头及 Eevee 渲染与合成。

本示范为非商业同人及技术展示，仅公开成片和视频封面，不分发模型、动作、贴图或工程。外观使用后续本地材质适配，不等于仓库 v43a 冻结代码单独重建结果。README 展示静态封面，点击封面或视频链接可进入 MP4 文件页查看或下载。

## v43a 当前更新

本版保留已有用户控制器，提供外部映射的缺失旋转绑定、已拟合动作目标导入、
分离的物理缓存生产与新进程复验，以及保存Cycles工程的有界续渲。优先复用
许可动作，角色配置与素材置于仓库外。用一个涅提娅项目实测了库动作挥手/鞠躬
及简化彩排场景；未重新生成MMR控制器，也不宣称修复了此前生成失败。

冻结包有169文件/133Python脚本，131项原生测试通过；实际361帧导入与保存后
重开、缓存检查、两条本地影片的编码和整段解码有分项证据。**助手未完成正常速度连续观看；用户随后报告已看过V04成片并验收通过。**
用户人工视频验收与半帧接触、精确物理、全身碰撞或完整原始输入独立重建是不同范围；
这些客观技术项仍未验证。 摄像机切点
变化明确复用了未改状态的帧，不作为全片重新渲染。该次 v43a 代码发布未上传模型、
原始/派生动作、场景、工程、视频、插件或角色配置；后来单独增加的示范成片见上方。

入口：[现有控制器工程流程](blender-character-short/references/existing-controller-projects.md)、
[库动作](blender-character-short/references/library-actions.md)、
[MMD Tools/MMR说明与边界](blender-character-short/references/mmd-plugins.md)。
当前分发身份见[清单](release/distribution-manifest.json)和[发布检查](release/validation.json)。
所有Python脚本保持冻结v43a原始字节；仅文档/示例脱敏差异逐项记录。

一个本地物理生产者曾在保存后同进程重开时崩溃；新进程复验通过，但原因未明。
新缓存路线要求分别启动生产与验证进程，不能把缓存成功或解码成功当成自然度通过。

### 原生单元测试

在仓库根目录、已具备匹配Blender依赖的环境，可用独立后台进程运行：

```text
blender --background --disable-autoexec --offline-mode --python-exit-code 1 --python-expr "import sys,unittest; sys.path.insert(0,'blender-character-short/scripts'); suite=unittest.defaultTestLoader.discover('blender-character-short/scripts',pattern='test_*.py'); result=unittest.TextTestRunner().run(suite); assert result.wasSuccessful()"
```

这些测试不是131项视觉质量测试；没有携带角色或许可动作数据。发布步骤本身不重渲染，
下方v33内容保留为历史背景，当前能力与限制以v43a记录及各专门文档为准。

## v33 历史背景

**v33 有纸飞机剧情从原始 PMX 全流程重建的本地技术证据，尚未通过连续观看或自然度验收。** 实际验证使用本哈希的 ZIP、相对路径外部配置、许可动作和 PowerShell 入口，在同一台机器的新目录完成 240 帧低清构建、后处理、编码/解码、范围内检查及配对工程重开。它只覆盖 Nanami Q 这一个角色与纸飞机剧情，不代表独立上下文、其他电脑或跨角色通过。

最新 15 秒主片保留私有原始编排与私有视线修正，**不是通用 skill 从原始 PMX 完整重建的主片**，也没有因此新增通用头眼求解功能。手指可信包握、跨角色/通用 FBX/Mixamo 重定向和正常速度连续观感仍未完成。主片、视频、模型、原始及派生动作、私有重建输入均不在此仓库。

## 相对 v26c 的更新

- 配置式原骨架全身接近流程：比例拟合、测量位移、脚底选区支撑、有限停步衔接，以及可选的准备姿势与起步加速；仍是选定节点动作与单角色映射。
- 保持手腕的肘部方向调整、选定加权角色区域三角面检查和按剧情要求的头/手/脚/道具画面边界检查。
- 耦合全场景时间映射、放置确认后的场景材质响应，以及与外部手部、注视和身体计划的阶段组合。
- 保存重复尝试日志、真实子进程退出信息和输入/脚本身份，支持有界后处理暂停后按原身份继续。

既有 GLB CPU 动作转换、静态场景导入、真实目标注视、原始骨架表演、外部 LUT/SMAA 后处理和编码检查仍保留。转换器的关键时刻检查不保证两 key 之间的全部连续时间安全。每个场景须保留自己的实际 producer 和输入；新脚本不得直接移入旧渲染缓存继续。

## 内容

- [`blender-character-short/SKILL.md`](blender-character-short/SKILL.md)：skill 入口。
- [`references/production.md`](blender-character-short/references/production.md)：角色、故事和动作配置约定。
- [`references/execution.md`](blender-character-short/references/execution.md)：命令、阶段产物和恢复方式。
- [`references/validation.md`](blender-character-short/references/validation.md)：历史证据范围和未完成项。
- [`references/motion-conversion.md`](blender-character-short/references/motion-conversion.md)：CPU 转换命令、许可字段、支持子集、资源边界和验证范围。
- [`references/body-approach.md`](blender-character-short/references/body-approach.md)：配置式接近/停步及外部动作身份。
- [`references/grounded-launch.md`](blender-character-short/references/grounded-launch.md)：准备姿势和有界起步。
- [`references/character-region-surfaces.md`](blender-character-short/references/character-region-surfaces.md)、[`references/story-framing.md`](blender-character-short/references/story-framing.md)：选定表面与画面范围的检查边界。
- `blender-character-short/scripts/`：当前保持 v43a 冻结 ZIP 的原始脚本字节。
- [`release/distribution-manifest.json`](release/distribution-manifest.json)：来源 ZIP 哈希、文件清单、分发差异和排除项。数量用于完整性核查，不代表品质验收。
- [`release/validation.json`](release/validation.json)：本次上传前的聚焦检查结果。

原项目历史和制作日志不在本仓库。上方仅另行提供示范 MP4、视频封面和借物信息；模型、纹理、PMX/GLB、`.blend`、其余媒体、LUT、SMAA 查找图、依赖二进制和角色专用映射仍须另行准备。

## 环境与安装

历史验证环境：Windows、Blender 4.5.15 LTS / Eevee、mmd_tools 4.5.14 源码与其配套 wheels、宿主 Python 3.14.7、NumPy 2.5.4、Pillow 13.0.0、imageio-ffmpeg 0.6.0 / FFmpeg 7.1。Blender 自带 Python 是另一套运行时，不能用宿主 Python 直接运行依赖 `bpy` 的脚本。Windows 协作执行锁尚未在其他系统验证。

将完整的 `blender-character-short` 文件夹放入所用助手的技能目录，或让助手直接读取其中的 `SKILL.md`。例如 Codex 的用户技能目录为 `$CODEX_HOME/skills`，未设置时通常为 `~/.codex/skills`。安装 skill 不会安装 Blender 或第三方依赖，也不包含可直接制作的角色资产。

## 使用

先准备已授权的 PMX、原始角色映射、故事与材质配置、适用动作及其权利记录、后处理配置和查找资源。克隆此仓库本身不包含可直接复现影片的角色输入。历史技术验证使用的完整私有 PowerShell 重建入口和编排也未发布。

CPU 动作转换可单独执行，不需要 Blender。按 motion-conversion 文档填写实际 `source_sha256`、作者、许可、附加限制和修改说明，把转换输出放在公开仓库之外的新目录：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B "$Skill/scripts/convert_glb_motion.py" --source $ReviewedGlb --provenance $RightsJson --output $NewMotionDirectory
python -B "$Skill/scripts/verify_glb_motion.py" --output $NewCpuVerificationDirectory
```

存在多个动画时，转换命令须明确传 `--animation INDEX`。生成的动作、层级及许可报告可能继续受源条款约束，不能随通用代码自动公开。验证脚本生成自有临时数值 GLB，不需要下载或附带第三方资产。

制作前阅读 production 和 execution 文档，准备 mmd_tools 源码及依赖、角色/故事 JSON、后处理配置和 LUT；启用 SMAA 时另提供匹配版本的 Area/Search 图。外部路径有各自的解析基准，按文档从外部项目根目录启动，并检查实际收集到的输入身份。

在 PowerShell 中将下列变量设为实际路径；`$Skill` 指向此仓库的 skill 文件夹，`$Output` 使用仓库外的新输出目录。按所用流程另附身体、肘部、注视、时间映射或场景响应计划参数，具体合同见各引用文档：

```powershell
python "$Skill/scripts/run_short.py" --blender $Blender --asset $Pmx --mmd-source $MmdSource --dependencies $Deps --character $CharacterJson --story $StoryJson --post-config $PostJson --lut $LutPng --output $Output --variant A --width 640 --height 360 --samples 16
```

先完成低成本预览并检查真实结果。默认输出无声视频；解码通过、抽帧检查、连续观看和试听是不同的验证步骤。`references/jobs.example.json` 是旧 PNG 队列的示例，不会执行新的外部后处理链。通用配置示例和公式夹具不能代替角色专用输入。

已有依赖环境下，可在仓库根目录复查分发文件：

```powershell
python -B validation/validate_distribution.py --report release/validation.json
python -B -m unittest discover -s validation -p 'test_*.py'
```

分发检查编译脚本、解析 JSON、检查内部文档链接与敏感文件模式，并运行可在宿主 Python 执行的 CLI 帮助入口。原有聚焦测试检查身份、旋转解码、注视/调时边界和后处理恢复；`verify_glb_motion.py` 另执行自有合成 CPU 套件。依赖 `bpy` 的场景检查须在另行许可的 Blender 环境运行；本次发布不重新渲染。测试输出、原始及转换动作均不属于公开文件。

## 历史v33限制与仍适用的边界

- 严格 HairHET/模板、透明深度与 MRT、环境贴图 HTTP 403，以及适用源 GPU 数值一致性仍未解决。
- 助手连续正常速度视觉验收尚未完成；用户已报告V04成片人工验收通过。默认自动产物为静音。有限接触采样不能证明全网格、所有帧或子帧均无穿插。
- 恢复签名不覆盖所有间接资源。mmd_tools/wheels、材质配置引用的 GLB、贴图、蓝图和清单需要另行冻结并校验。
- v33只完成选定 Cesium 节点动作与 Nanami 原始骨架的配置适配；v43a另有单个已有控制器的许可捕捉动作证据；手指、通用 FBX/Mixamo、跨角色重定向、自然稳步与可信抓握均未完成。接近段有腾空，不能称为稳定步行。
- 从原始 PMX 完整复用的证据只属于纸飞机剧情。主片使用私有编排；局部视线修正、技术检查和抽帧不等于连续观看或自然度通过。
- v43a 代码发布时只复查代码、CPU 用例与分发文件，没有新增渲染或影片；上方示范属于后续单独重渲染。历史启动故障和后来成功运行按各版本记录区分；不把旧故障推断为当前应用状态。完整限制见 validation 文档。

## 来源与使用权

参见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本次发布没有为来源权利尚未确认的代码添加统一开源许可证。仓库公开可读不代表对代码、第三方公式、模型或其他资源授予额外使用权。
