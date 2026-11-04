# Blender Character Short Skill · v33

从已授权的 PMX 角色、角色映射和故事配置制作本地 Blender Eevee 短片的可移植 skill。包含导入、表演与分镜、接触诊断、材质与后处理、视频编码和检查脚本。

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
- `blender-character-short/scripts/`：保持 v33 冻结 ZIP 中的原始脚本字节。
- [`release/distribution-manifest.json`](release/distribution-manifest.json)：来源 ZIP 哈希、文件清单、分发差异和排除项。数量用于完整性核查，不代表品质验收。
- [`release/validation.json`](release/validation.json)：本次上传前的聚焦检查结果。

原项目历史、制作日志和媒体不在本仓库。模型、纹理、PMX/GLB、`.blend`、视频、LUT、SMAA 查找图、依赖二进制和角色专用映射均须另行准备。

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

## 已知限制

- 严格 HairHET/模板、透明深度与 MRT、环境贴图 HTTP 403，以及适用源 GPU 数值一致性仍未解决。
- 连续正常速度视觉验收和音频验收尚未完成；默认自动产物为静音。有限接触采样不能证明全网格、所有帧或子帧均无穿插。
- 恢复签名不覆盖所有间接资源。mmd_tools/wheels、材质配置引用的 GLB、贴图、蓝图和清单需要另行冻结并校验。
- 只完成选定 Cesium 节点动作与 Nanami 原始骨架的配置适配；手指、通用 FBX/Mixamo、跨角色重定向、自然稳步与可信抓握均未完成。接近段有腾空，不能称为稳定步行。
- 从原始 PMX 完整复用的证据只属于纸飞机剧情。主片使用私有编排；局部视线修正、技术检查和抽帧不等于连续观看或自然度通过。
- 本次发布只复查代码、CPU 用例与分发文件，没有新增渲染或影片。历史启动故障和后来成功运行按各版本记录区分；不把旧故障推断为当前应用状态。完整限制见 validation 文档。

## 来源与使用权

参见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本次发布没有为来源权利尚未确认的代码添加统一开源许可证。仓库公开可读不代表对代码、第三方公式、模型或其他资源授予额外使用权。
